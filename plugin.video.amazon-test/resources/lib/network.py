#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import mechanicalsoup
import random
import re
import requests
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from timeit import default_timer as timer
from bs4 import BeautifulSoup
from copy import deepcopy
from urllib.parse import urlencode, quote_plus, urlparse, parse_qs
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import xbmcgui

from .common import Globals, Settings, sleep, MechanizeLogin, get_key, findKey
from .logging import Log, WriteLog, LogJSON
from .l10n import getString
from .configs import getConfig, writeConfig
from .metrics import addNetTime

_session = None
_grabjson_lock = threading.RLock()
_g = Globals()
_s = Settings()


class _RateLimiter:
    """
    Adaptiver Rate-Limiter für paralleles Webscraping:
    - Begrenzt gleichzeitige Requests über ein BoundedSemaphore.
    - Pausiert alle Worker-Threads bei HTTP 429 / 503 oder Captcha-Erkennung mit Exponential Backoff + Jitter.
    """
    def __init__(self, max_concurrent=4):
        self.semaphore = threading.BoundedSemaphore(max_concurrent)
        self._lock = threading.Lock()
        self._cooldown_until = 0.0
        self._consecutive_429 = 0

    def wait_before_request(self):
        while not _g.monitor.abortRequested():
            with self._lock:
                wait_sec = self._cooldown_until - time.monotonic()
            if wait_sec <= 0:
                break
            if _g.monitor.waitForAbort(min(wait_sec, 0.5)):
                break

    def trigger_cooldown(self, retry_after_header=None, reason='HTTP 429/503'):
        with self._lock:
            self._consecutive_429 = min(self._consecutive_429 + 1, 5)
            delay = None
            if retry_after_header:
                try:
                    delay = min(float(retry_after_header), 30.0)
                except (ValueError, TypeError):
                    delay = None
            if delay is None:
                base = min(1.5 * (2 ** (self._consecutive_429 - 1)), 15.0)
                delay = base + random.uniform(0.15, 0.75)
            target = time.monotonic() + delay
            if target > self._cooldown_until:
                self._cooldown_until = target
                Log(f'RateLimiter cooldown ({reason}): pausing parallel workers for {delay:.2f}s', Log.WARNING)

    def record_success(self):
        with self._lock:
            if self._consecutive_429 > 0 and time.monotonic() >= self._cooldown_until:
                self._consecutive_429 = max(0, self._consecutive_429 - 1)


_rate_limiter = _RateLimiter(max_concurrent=4)


def _Error(data):
    code = data['errorCode'].lower()
    Log(f"{data['message']} ({code}) ", Log.ERROR)
    if 'invalidrequest' in code:
        return getString(30204)
    elif 'noavailablestreams' in code:
        return getString(30205)
    elif 'notowned' in code:
        return getString(30206)
    elif 'invalidgeoip' in code or 'dependency' in code:
        return getString(30207)
    elif 'temporarilyunavailable' in code:
        return getString(30208)
    else:
        return f"{data['message']} ({code}) "


def getUA(blacklist=False):
    Log('Switching UserAgent')
    UAlist = json.loads(getConfig('UAlist', json.dumps([])))
    UAcur = ''

    if blacklist:
        UAcur = getConfig('UserAgent')
        UAlist = [i for i in UAlist if i not in UAcur]
        writeConfig('UAlist', json.dumps(UAlist))
        Log(f'UA: {UAcur} blacklisted')

    if not UAlist:
        Log('Loading list of common UserAgents')
        result = getURL('https://microlink.io/user-agents.json')
        sorted_ua = result.get('user', {})
        UAlist = [ua for ua in sorted_ua if 'windows' in ua.lower() and ua not in UAcur]
        if not UAlist:
            UAlist = ['Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36']
        writeConfig('UAlist', json.dumps(UAlist))
    writeConfig('UserAgent', UAlist[0])
    Log('Using UserAgent: ' + UAlist[0])
    return


def mobileUA(content):
    soup = BeautifulSoup(content, 'html.parser')
    res = soup.find('html')
    res = res.get('class', '') if res else ''
    return True if 'a-mobile' in res or 'a-tablet' in res else False


def _get_session(retry=True):
    global _session

    if _session is not None:
        return _session

    session = requests.Session()
    retries = Retry(
        total=4,
        backoff_factor=0.6,
        status_forcelist=[500, 502, 503, 504, 408, 429],
        respect_retry_after_header=True,
        raise_on_status=False
    )
    adapter = HTTPAdapter(pool_connections=20, pool_maxsize=20, max_retries=retries)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    _session = session
    return session


def getURL(url, useCookie=False, silent=False, headers=None, rjson=True, check=False, postdata=None, binary=False, allow_redirects=True):
    getURL.lastResponseCode = 0
    retval = {} if rjson else ''
    method = 'POST' if postdata is not None else 'HEAD' if check else 'GET'
    headers = {} if not headers else deepcopy(headers)
    session = _get_session(not check)

    if useCookie:
        cj = MechanizeLogin() if isinstance(useCookie, bool) else useCookie
        if isinstance(cj, bool):
            return retval
        elif isinstance(cj, dict):
            headers.update(cj)
        else:
            session.cookies.update(cj)

    if (not silent) or _s.logging:
        dispurl = re.sub(f'(?i){_g.tvdb}|{_g.tmdb}|&token=\\w+|&customerId=\\w+', '', url).strip()
        Log(f"{'check' if check else method.lower()}URL: {dispurl}")

    def_headers = {'User-Agent': getConfig('UserAgent'),
                   'Accept-Language': _g.userAcceptLanguages,
                   'Accept-Encoding': 'gzip, deflate, br',
                   'Upgrade-Insecure-Requests': '1',
                   'Connection': 'keep-alive'}

    if 'amazon' in url or 'primevideo' in url:
        for k, v in def_headers.items():
            if k not in headers:
                headers[k] = v

    """
    # This **breaks** redirections. Host header OVERRIDES the host in the URL:
    # if the URL is web.eu, but the Host is web.com, request will fetch web.com
    if 'Host' not in headers:
        headers['Host'] = host
    """
    if '/api/' in url:
        headers['X-Requested-With'] = 'XMLHttpRequest'

    try:
        req_headers = dict(session.headers)
        req_headers.update(headers)
        getURL.headers = req_headers
        starttime = timer()
        _rate_limiter.wait_before_request()
        if _g.monitor.abortRequested():
            return retval
        with _rate_limiter.semaphore:
            r = session.request(method, url, data=postdata, headers=req_headers, verify=_s.ssl_verif, stream=True, allow_redirects=allow_redirects, timeout=(10, 20))
            if check and r.status_code in (400, 403, 404, 405, 501):
                r.close()
                r = session.request('GET', url, data=postdata, headers=req_headers, verify=_s.ssl_verif, stream=True, allow_redirects=allow_redirects, timeout=(10, 20))
        getURL.lastResponseCode = r.status_code  # Set last response code
        if check:
            r.close()
        if r.status_code in (429, 503):
            _rate_limiter.trigger_cooldown(r.headers.get('Retry-After'), f'HTTP {r.status_code}')
        elif 200 <= r.status_code < 400:
            _rate_limiter.record_success()
        response = 'OK' if 400 > r.status_code >= 200 else ''
        if not check:
            try:
                response = r.content if binary else r.json() if rjson else r.text
                if _s.log_http:
                    WriteLog(BeautifulSoup(r.text, 'html.parser').prettify(), 'html', True, comment=f'<-- {url} -->')
            finally:
                r.close()
        if useCookie and isinstance(response, str) and 'auth-cookie-warning-message' in response:
            Log('Cookie invalid', Log.ERROR)
            _g.dialog.notification(_g.__plugin__, getString(30266), xbmcgui.NOTIFICATION_ERROR)
            return retval
        if useCookie and not isinstance(useCookie, dict):
            from .users import saveUserCookies
            saveUserCookies(session.cookies)
    except (requests.exceptions.Timeout,
            requests.exceptions.ConnectionError,
            requests.exceptions.SSLError,
            requests.exceptions.HTTPError,
            requests.packages.urllib3.exceptions.InsecurePlatformWarning,
            ValueError) as e:
        eType = e.__class__.__name__
        Log(f'Error reason: {e!s} ({eType})', Log.ERROR)
        if 'InsecurePlatformWarning' in eType:
            Log('Using an outdated SSL module.', Log.ERROR)
            _g.dialog.ok('SSL module outdated', 'The SSL module for Python is outdated.',
                         'You can find a Linux guide on how to update Python and its modules for Kodi here: https://goo.gl/CKtygz',
                         'Additionally, follow this guide to update the required modules: https://goo.gl/ksbbU2')
            exit()
        return retval
    res = response
    duration = timer()
    duration -= starttime
    addNetTime(duration)
    Log(f'Download Time: {duration}', Log.DEBUG)
    return res


def getURLData(mode, asin, retformat='json', devicetypeid=_g.dtid_web, version=2, firmware='1', opt='', extra=False,
               useCookie=False, retURL=False, vMT='Feature', dRes='PlaybackUrls,SubtitleUrls,ForcedNarratives',
               proxyEndpoint=None, silent=False):

    playback_req = 'PlaybackUrls' in dRes or 'Widevine2License' in dRes
    url = _g.ATVUrl + '/cdp/' + mode
    url += '?asin=' + asin
    url += '&deviceTypeID=' + devicetypeid
    url += '&firmware=' + firmware
    url += '&deviceID=' + _g.deviceID
    url += '&marketplaceID=' + _g.MarketID
    url += '&format=' + retformat
    url += '&version=' + str(version)
    url += '&gascEnabled=' + str(_g.UsePrimeVideo).lower()
    url += "&subtitleFormat=TTMLv2" if 'SubtitleUrls' in dRes else ''
    url += '&operatingSystemName=Windows' if playback_req and (_g.platform & _g.OS_ANDROID or _g.platform & _g.OS_WEBOS) and devicetypeid == _g.dtid_web and _s.wvl1_device else ''  # cookie auth on android
    if extra:
        url += '&resourceUsage=ImmediateConsumption&consumptionType=Streaming&deviceDrmOverride=CENC' \
               '&deviceStreamingTechnologyOverride=DASH&deviceProtocolOverride=Https' \
               '&deviceBitrateAdaptationsOverride=CVBR%2CCBR&audioTrackId=all'
        url += '&languageFeature=MLFv2'  # Audio Description tracks
        url += '&videoMaterialType=' + vMT
        url += '&desiredResources=' + dRes
        url += '&supportedDRMKeyScheme=DUAL_KEY' if playback_req else ''
        if _s.wvl1_device:
            url += '&deviceVideoCodecOverride=H264' + (',H265' if _s.use_h265 else '')
            url += '&deviceHdrFormatsOverride=' + supported_hdr()
            url += '&deviceVideoQualityOverride=' + ('UHD' if _s.enable_uhd else 'HD')
        elif playback_req and vMT in ('Feature', 'LiveStreaming') and not _s.l3_request_hd:
            # Since Oct 2026 Amazon refuses the HD Widevine license for devices without L1 (software CDM),
            # the license response then holds no license and IS.A retries endlessly. Request SD for both
            # the manifest and the license, so the keys Amazon grants match the streams in the manifest.
            url += '&deviceVideoQualityOverride=SD'

    if retURL:
        return url
    url += opt
    data = getURL(url if not proxyEndpoint else f"http://{getConfig('proxyaddress')}/{proxyEndpoint}/{quote_plus(url)}",
                  useCookie=useCookie, postdata='', silent=silent)
    if data:
        if 'error' in data.keys():
            return False, _Error(data['error'])
        elif 'AudioVideoUrls' in data.get('errorsByResource', ''):
            return False, _Error(data['errorsByResource']['AudioVideoUrls'])
        elif 'PlaybackUrls' in data.get('errorsByResource', ''):
            return False, _Error(data['errorsByResource']['PlaybackUrls'])
        else:
            return True, data
    return False, 'HTTP Error'


def supported_hdr():
    hdr = []
    if _s.enable_dovi == 'true':
        hdr.append('DolbyVision')
    if _s.enable_hdr10 == 'true':
        hdr.append('Hdr10')
    if len(hdr) == 0:
        hdr.append('None')
    return ','.join(hdr)


def getATVData(pg_mode, query='', version=2, useCookie=False, site_id=None):
    # ids: A28RQHJKHM2A2W - ps3 / AFOQV1TK6EU6O - ps4 / A1IJNVP3L4AY8B - samsung / A2E0SNTXJVT7WK - firetv1 /
    #      ADVBD696BHNV5 - montoya / A3VN4E5F7BBC7S - roku / A1MPSLFC7L5AFK - kindle / A2M4YX06LWP8WI - firetv2 /
    # PrimeVideo web device IDs:
    #      A63V4FRV3YUP9 / SILVERLIGHT_PC, A2G17C9GWLWFKO / SILVERLIGHT_MAC, AOAGZA014O5RE / HTML5
    # TypeIDs = {'GetCategoryList': 'firmware=fmw:15-app:1.1.23&deviceTypeID=A1MPSLFC7L5AFK',
    #            'GetSimilarities': 'firmware=fmw:15-app:1.1.23&deviceTypeID=A1MPSLFC7L5AFK',
    #                        'All': 'firmware=fmw:22-app:3.0.211.123001&deviceTypeID=A43PXU4ZN2AL1'}
    #                        'All': 'firmware=fmw:045.01E01164A-app:4.7&deviceTypeID=A3VN4E5F7BBC7S'}
    # TypeIDs = {'All': 'firmware=fmw:17-app:2.0.45.1210&deviceTypeID=A2RJLFEH0UEKI9'}
    _TypeIDs = {True: ['firmware=fmw:28-app:5.2.3&deviceTypeID=A3SSWQ04XYPXBH', 'firmware=fmw:26-app:3.0.265.20347&deviceTypeID=A1S15DUFSI8AUG',
                       'firmware=default&deviceTypeID=A1FYY15VCM5WG1'],
                False: ['firmware=fmw:28-app:5.2.3&deviceTypeID=A1C66CX2XD756O', 'firmware=fmw:26-app:3.0.265.20347&deviceTypeID=A12GXV8XMS007S',
                        'firmware=fmw:045.01E01164A-app:4.7&deviceTypeID=A3VN4E5F7BBC7S']}

    if '?' in query:
        query = query.split('?')[1]
    if query:
        query = '&IncludeAll=T&AID=1&' + query.replace('HideNum=T', 'HideNum=F')
    pg_mode = pg_mode.split('_')[0]
    if '/' not in pg_mode:
        pg_mode = 'catalog/' + pg_mode
    rem_pos = False if re.search('(?i)rolluptoseason=t|contenttype=tvseason', query) else _s.tld_episode_thumbnails

    if 'asinlist=&' not in query:
        titles = 0
        ids = len(_TypeIDs[rem_pos]) - 1
        att = 0
        while titles == 0 and att <= ids:
            deviceTypeID = _TypeIDs[rem_pos][att]
            parameter = f'{deviceTypeID}&deviceID={_g.deviceID}&format=json&version={version}&formatVersion=3&marketplaceId={_g.MarketID}'
            if site_id:
                parameter += '&id=' + site_id
            jsondata = getURL(f'{_g.ATVUrl}/cdp/{pg_mode}?{parameter}{query}', useCookie=useCookie)
            if not jsondata:
                return False
            if jsondata['message']['statusCode'] != "SUCCESS":
                Log('Error Code: ' + jsondata['message']['body']['code'], Log.ERROR)
                return None
            titles = len(jsondata['message']['body'].get('titles'))
            att += 1 if 'StartIndex=0' in query else ids + 1

        result = jsondata['message']['body']
        return _sortedResult(result, query) if 'asinlist' in query else result
    return {}


def _sortedResult(result, query):
    asinlist = parse_qs(query.upper(), keep_blank_values=True)['ASINLIST'][0].split(',')
    sorteditems = ['empty'] * len(asinlist)

    for item in result.get('titles', []):
        for index, asin in enumerate(asinlist):
            if asin in str(item):
                sorteditems[index] = item
                break
    if sorteditems.count('empty') > 0:
        Log(f"ASINs {[asinlist[n] for n, i in enumerate(sorteditems) if i == 'empty']} not found")

    result['titles'] = sorteditems
    return result


def FQify(URL):
    """ Makes sure to provide correct fully qualified URLs """
    base = _g.BaseUrl
    if '://' in URL:  # FQ
        return URL
    elif URL.startswith('//'):  # Specified domain, same schema
        return base.split(':')[0] + ':' + URL
    elif URL.startswith('/'):  # Relative URL
        return base + URL
    else:  # Hope and pray we never reach this ¯\_(ツ)_/¯
        return base + '/' + URL


def GrabJSON(url, postData=None):
    """ Extract JSON objects from HTMLs while keeping the API ones intact """
    from html import unescape

    def Unescape(text):
        if not text.startswith('{&#34;'):
            text = text.replace('&#34;', '\\"')
        text = unescape(text)

        try:
            text = text.encode('latin-1').decode('utf-8')
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass

        return text

    def Merge(o, n, keys=[]):
        """ Merge JSON objects with multiple multi-level collisions """
        if (not n) or (o == n):  # Nothing to do
            return
        elif (type(n) == list) or (type(n) == set):  # Insert into list/set
            for item in n:
                if item not in o:
                    if type(n) == list:
                        o.append(item)
                    else:
                        o.add(item)
        elif type(n) == dict:
            for k in list(n):  # list() instead of .keys() to avoid py3 iteration errors
                if k not in o:
                    o[k] = n[k]  # Insert into dictionary
                else:
                    Merge(o[k], n[k], keys + [k])  # Recurse
        else:
            # Ignore reporting collisions on metadata we don't care about
            if keys not in [
                ['csrfToken'],
                ['metadata', 'availability', 'description'],
                ['metadata', 'availability', 'severity'],
            ]:
                k = ' > '.join(keys)
                if _s.json_dump_collisions:
                    LogJSON(n, k, optionalName='CollisionNew')
                    LogJSON(o, k, optionalName='CollisionOld')
                Log('Collision detected during JSON objects merging{}, overwriting and praying (type: {})'.format(
                    ' on key “{}”'.format(k) if keys else '',
                    type(n)
                ), Log.WARNING)
            o = n

    def Prune(d):
        """ Prune some commonly found sensitive info from JSON response bodies """
        if not d:
            return

        l = d
        if isinstance(l, dict):
            for k in list(l):  # list() instead of .keys() to avoid py3 iteration errors
                if k == 'strings':
                    l[k] = {s: l[k][s] for s in ['AVOD_DP_season_selector'] if s in l[k]}
                if (not l[k]) or (k in ['context', 'params', 'playerConfig', 'refine']):
                    del l[k]
            l = d.values()
        for v in l:
            if isinstance(v, dict) or isinstance(v, list):
                Prune(v)

    def do(url, postData):
        GrabJSON.runs = True
        """ Wrapper to facilitate logging """
        headers = {'accept': 'application/json', "X-Requested-With": "XMLHttpRequest"}
        if re.match(r'/(?:gp/video/)?search(?:Default)?/', url):
            up = urlparse(url)
            qs = parse_qs(up.query)
            if 'from' in list(qs):  # list() instead of .keys() to avoid py3 iteration errors
                qs['startIndex'] = qs['from']
                del qs['from']
            up = up._replace(query=urlencode([(k, v) for k, l in qs.items() for v in l]))
            url = up.geturl()
        if '/api/storefront' in url:
            postData = ""
        if '/api/' in url:
            headers = None
        r = getURL(FQify(url), silent=True, useCookie=cj if cj else True, rjson=False, postdata=postData, headers=headers)
        if not r:
            return None
        r = r.strip()
        if '/api/' in url:
            o = json.loads(Unescape(r))
            if _s.json_dump_raw:
                Prune(o)
        else:
            m = HTMLdoc(r) if '<!doctype html>' in r else json.loads(r)
            if ('widgets' in m) and ('Storefront' in m['widgets']):
                m = m['widgets']['Storefront']
            elif 'body' in m or 'props' in m or 'init' in m:
                bodies = findKey('body', m)
                sw = findKey('siteWide', m)
                m = m.get('props', m.get('init', m))
                if len(bodies) > 0:
                    if 'bodyStart' in sw and len(sw['bodyStart']) > 0:
                        for bs in sw['bodyStart']:
                            if 'name' in bs and bs['name'] == 'navigation-bar' and 'props' in bs:
                                m = bs['props']
                    else:
                        m = bodies['sitewide'].get('sitewide-navigation-bar', {}) if 'sitewide' in bodies else {}
                        if isinstance(bodies, dict):
                            bodies = [bodies]

                    if isinstance(bodies, list):
                        for body in bodies:
                            body = body.get('props', body)
                            for p in ['atf', 'btf', 'landingPage', 'browse', 'search', 'categories', 'genre']:
                                Merge(m, body.get(p, {}))
                            for p in ['content', 'containers', 'pagination']:
                                Merge(m, {p: body.get(p, {})})

                if _s.json_dump_raw:
                    # Prune useless/sensitive info
                    for k in list(m):  # list() instead of .keys() to avoid py3 iteration errors
                        if (not m[k]) or (k in ['copyright', 'links', 'logo', 'params', 'playerConfig', 'refine']):
                            del m[k]
                    if 'state' in m:
                        st = m['state']
                        for k in list(st):  # list() instead of .keys() to avoid py3 iteration errors
                            if not st[k]:
                                del st[k]
                            elif k in ['features', 'customerPreferences']:
                                del st[k]
            else:
                m = {}
            # Prune sensitive context info and merge into o
            if _s.json_dump_raw:
                Prune(m)
            o = m
        return o if o else None

    def HTMLdoc(r):
        matches = BeautifulSoup(r, 'html.parser').find_all('script', {'type': re.compile('(?:text/template|application/json)')})
        if not matches:
            matches = Captcha(r)
            if not matches:
                Log('No JSON objects found in the page', Log.ERROR)
                return None

        # Create a single object containing all the data from the multiple JSON objects in the page
        o = {}
        for m in matches:
            if not (m.id is None or 'hydration-data' in m.id):
                continue
            m = json.loads(Unescape(m.string.strip()))
            Merge(o, m)
        return o

    def Captcha(r):
        with _grabjson_lock:
            _rate_limiter.trigger_cooldown(reason='Captcha/MFA challenge detected')
            from .login import MFACheck
            from .common import parseHTML
            u = FQify(url)
            cj_cap = MechanizeLogin()
            br = mechanicalsoup.StatefulBrowser(soup_config={'features': 'html.parser'})
            br.session.headers = getattr(getURL, 'headers', {})
            br.set_cookiejar(cj_cap)
            br.open_fake_page(r, u)
            r, soup = parseHTML(br)
            if any(sp in r for sp in _g.mfa_keywords):
                br = MFACheck(br, '', soup)
                if br is None:
                    return False
                if not br.get_current_form() is None:
                    br.submit_selected()
                from .users import saveUserCookies
                saveUserCookies(cj_cap)
                r = getURL(u, useCookie=True, rjson=False, postdata=postData)
                br.open_fake_page(r, u)
                r, soup = parseHTML(br)
                WriteLog(r, 'captcha-webapi')
            return BeautifulSoup(r, 'html.parser').find_all('script', {'type': re.compile('(?:text/template|application/json)'), 'id': ''})

    cj = getattr(GrabJSON, '_shared_cj', None)
    j = do(url, postData)
    LogJSON(j, url)
    return j


def getURLParallel(urls, useCookie=False, rjson=True, headers=None, max_workers=4):
    """
    Ruft mehrere URLs parallel und rate-limitiert über den globalen Connection-Pool ab.
    Gibt ein Dict {url: response} in deterministischer Reihenfolge zurück.
    """
    unique_urls = list(dict.fromkeys(u for u in urls if u))
    if not unique_urls:
        return {}
    if useCookie is True:
        useCookie = MechanizeLogin()
        if not useCookie:
            return {}
    if len(unique_urls) == 1:
        u0 = unique_urls[0]
        return {u0: getURL(u0, useCookie=useCookie, silent=True, headers=headers, rjson=rjson)}

    results = {}
    workers = min(max_workers, len(unique_urls), 4)
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_url = {
            executor.submit(getURL, u, useCookie=useCookie, silent=True, headers=headers, rjson=rjson): u
            for u in unique_urls
        }
        for future in as_completed(future_to_url):
            u = future_to_url[future]
            if _g.monitor.abortRequested():
                break
            try:
                results[u] = future.result()
            except Exception as exc:
                Log(f'getURLParallel error for {u}: {exc}', Log.ERROR)
                results[u] = {} if rjson else ''
    return {u: results.get(u, {} if rjson else '') for u in unique_urls}


def GrabJSONParallel(urls, max_workers=4):
    """
    Lädt und parst mehrere Web-API-Seiten (HTML oder JSON) parallel in Worker-Threads
    unter Berücksichtigung des adaptiven Rate-Limiters.
    Gibt ein Dict {url: parsed_json_dict} zurück.
    """
    unique_urls = list(dict.fromkeys(u for u in urls if u))
    if not unique_urls:
        return {}
    cj = MechanizeLogin()
    if not cj:
        return {}
    if len(unique_urls) == 1:
        u0 = unique_urls[0]
        return {u0: GrabJSON(u0)}

    results = {}
    workers = min(max_workers, len(unique_urls), 4)
    GrabJSON._shared_cj = cj
    try:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_url = {executor.submit(GrabJSON, u): u for u in unique_urls}
            for future in as_completed(future_to_url):
                u = future_to_url[future]
                if _g.monitor.abortRequested():
                    break
                try:
                    results[u] = future.result()
                except Exception as exc:
                    Log(f'GrabJSONParallel error for {u}: {exc}', Log.ERROR)
                    results[u] = None
    finally:
        GrabJSON._shared_cj = None
    return {u: results.get(u) for u in unique_urls}


def LocaleSelector():
    from .l10n import datetimeParser
    from .common import get_user_lang
    cj = MechanizeLogin()
    if not cj:
        exit()

    if _g.UsePrimeVideo or _s.data_source == 1:
        from .users import loadUser
        langs = [(k, v['language']) for k, v in datetimeParser.items() if 'language' in v]
        l = get_user_lang(cj)
        presel = [i for i, x in enumerate(langs) if x[0] == l]
        '''
        resp = GrabJSON(_g.BaseUrl + '/api/getLanguageSettingsPage?subPage=language&widgetArgs=%7B%7D')
        for widget in resp['widgets']:
            if widget['widgetType'] == 'languages':
                langs = [(l['locale'], l['text'], l.get('selected') is not None) for l in widget['content']['languages']]
        '''
    else:
        # TLDs doesn't store locale in cookie by default
        from mechanicalsoup import StatefulBrowser
        br = StatefulBrowser(soup_config={'features': 'html.parser'})
        br.set_cookiejar(cj)
        br.session.headers.update({'User-Agent': getConfig('UserAgent')})
        br.open(_g.BaseUrl + '/customer-preferences/edit')
        WriteLog(str(br.get_current_page()), 'langsel')
        langs = [(elem.label.input.get('value'), elem.get_text(strip=True), elem.label.input.get('checked') is not None)
                 for elem in br.get_current_page().find_all('div', attrs={'data-a-input-name': 'lop'})]
        presel = [i for i, x in enumerate(langs) if x[2] is True]

    if len(langs) < 1:
        _g.dialog.notification(_g.__plugin__, getString(30270))
        exit()

    sel = _g.dialog.select(getString(30115), [x[1] for x in langs], preselect=presel[0] if presel else -1)
    if sel < 0:
        _g.addon.openSettings()
        exit()
    else:
        return langs[sel][0], langs[sel][1]
