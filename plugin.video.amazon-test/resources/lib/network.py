#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import json
import mechanicalsoup
import re
import requests
from timeit import default_timer as timer
from random import randint
from bs4 import BeautifulSoup
from copy import deepcopy

from kodi_six import xbmcgui

from .common import Globals, Settings, sleep, MechanizeLogin
from .logging import Log, WriteLog, LogJSON
from .l10n import getString
from .configs import getConfig, writeConfig
from .metrics import addNetTime

try:
    from urlparse import urlparse, parse_qs, urlunparse
    from urllib import urlencode, quote_plus
except ImportError:
    from urllib.parse import urlparse, parse_qs, urlencode, quote_plus, urlunparse

_g = Globals()
_s = Settings()


def _Error(data):
    code = data['errorCode'].lower()
    Log('%s (%s) ' % (data['message'], code), Log.ERROR)
    if 'invalidrequest' in code:
        return getString(30204)
    elif 'noavailablestreams' in code:
        return getString(30205)
    elif 'notowned' in code:
        return getString(30206)
    elif 'invalidgeoip' or 'dependency' in code:
        return getString(30207)
    elif 'temporarilyunavailable' in code:
        return getString(30208)
    else:
        return '%s (%s) ' % (data['message'], code)


def getUA(blacklist=False):
    Log('Switching UserAgent')
    UAlist = json.loads(getConfig('UAlist', json.dumps([])))
    UAcur = ''

    if blacklist:
        UAcur = getConfig('UserAgent')
        UAlist = [i for i in UAlist if i not in UAcur]
        writeConfig('UAlist', json.dumps(UAlist))
        Log('UA: %s blacklisted' % UAcur)

    if not UAlist:
        Log('Loading list of common UserAgents')
        # [{'pct': int percent, 'ua': 'useragent string'}, …]
        html = getURL('https://www.useragents.me', rjson=False)
        soup = BeautifulSoup(html, 'html.parser')
        desk = soup.find('div', attrs={'id': 'most-common-desktop-useragents-json-csv'})
        for div in desk.find_all('div'):
            if div.h3.string == 'JSON':
                ua = json.loads(div.textarea.string)
                break
        sorted_ua = sorted(ua, key=lambda x:x.get('pct', 0), reverse=True)
        UAlist = [ua['ua'] for ua in sorted_ua if 'windows' in ua['ua'].lower() and ua['ua'] not in UAcur]
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


def getURL(url, useCookie=False, silent=False, headers=None, rjson=True, attempt=1, check=False, postdata=None, binary=False, allow_redirects=True):
    if not hasattr(getURL, 'sessions'):
        getURL.sessions = {}  # Keep-Alive sessions
        getURL.hostParser = re.compile(r'://([^/]+)(?:/|$)')

    # Static variable to store last response code. 0 means generic error (like SSL/connection errors),
    # while every other response code is a specific HTTP status code
    getURL.lastResponseCode = 0

    # Create sessions for keep-alives and connection pooling
    host = getURL.hostParser.search(url)  # Try to extract the host from the URL
    if None is not host:
        host = host.group(1)
        if host not in getURL.sessions:
            getURL.sessions[host] = requests.Session()
        session = getURL.sessions[host]
    else:
        session = requests.Session()

    retval = {} if rjson else ''
    headers = {} if not headers else deepcopy(headers)
    if useCookie:
        cj = MechanizeLogin() if isinstance(useCookie, bool) else useCookie
        if isinstance(cj, bool):
            return retval
        elif isinstance(cj, dict):
            headers.update(cj)
        else:
            session.cookies.update(cj)

    if (not silent) or _s.logging:
        dispurl = re.sub('(?i)%s|%s|&token=\\w+|&customerId=\\w+' % (_g.tvdb, _g.tmdb), '', url).strip()
        Log('%sURL: %s' % ('check' if check else 'post' if postdata is not None else 'get', dispurl))

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

    class TryAgain(Exception):
        pass  # Try again on temporary errors

    class NoRetries(Exception):
        pass  # Fail on permanent errors

    try:
        session.headers.update(headers)
        getURL.headers = session.headers
        method = 'POST' if postdata is not None else 'GET'
        starttime = timer()
        r = session.request(method, url, data=postdata, verify=_s.ssl_verif, stream=True, allow_redirects=allow_redirects)
        getURL.lastResponseCode = r.status_code  # Set last response code
        response = 'OK' if 400 > r.status_code >= 200 else ''
        if not check:
            response = r.content if binary else r.text
            if _s.log_http:
                WriteLog(BeautifulSoup(response, 'html.parser').prettify(), 'html', True, comment='<-- {} -->'.format(url))
        else:
            rjson = False
        if useCookie and 'auth-cookie-warning-message' in response:
            Log('Cookie invalid', Log.ERROR)
            _g.dialog.notification(_g.__plugin__, getString(30266), xbmcgui.NOTIFICATION_ERROR)
            return retval
        # 408 Timeout, 429 Too many requests and 5xx errors are temporary
        # Consider everything else definitive fail (like 404s and 403s)
        if (408 == r.status_code) or (429 == r.status_code) or (500 <= r.status_code):
            raise TryAgain('{0} error'.format(r.status_code))
        if 400 <= r.status_code:
            raise NoRetries('{0} error'.format(r.status_code))
        if useCookie and not isinstance(useCookie, dict):
            from .users import saveUserCookies
            saveUserCookies(session.cookies)
    except (TryAgain,
            NoRetries,
            requests.exceptions.Timeout,
            requests.exceptions.ConnectionError,
            requests.exceptions.SSLError,
            requests.exceptions.HTTPError,
            requests.packages.urllib3.exceptions.InsecurePlatformWarning) as e:
        eType = e.__class__.__name__
        Log('Error reason: %s (%s)' % (str(e), eType), Log.ERROR)
        if 'InsecurePlatformWarning' in eType:
            Log('Using an outdated SSL module.', Log.ERROR)
            _g.dialog.ok('SSL module outdated', 'The SSL module for Python is outdated.',
                         'You can find a Linux guide on how to update Python and its modules for Kodi here: https://goo.gl/CKtygz',
                         'Additionally, follow this guide to update the required modules: https://goo.gl/ksbbU2')
            exit()
        if (not check) and (3 > attempt) and (('TryAgain' in eType) or ('Timeout' in eType)):
            if _g.headers_android['User-Agent'] not in headers['User-Agent']:
                getUA(True)
            wait = 10 * attempt if '429' in str(e) else 0
            attempt += 1
            Log('Attempt #{0}{1}'.format(attempt, '' if 0 == wait else ' (Too many requests, pause %s seconds…)' % wait))
            if 0 < wait:
                sleep(wait)
            return getURL(url, useCookie, silent, headers, rjson, attempt, check, postdata, binary)
        return retval
    res = response
    if rjson:
        try:
            res = json.loads(response)
        except ValueError:
            res = retval
    duration = timer()
    duration -= starttime
    addNetTime(duration)
    Log('Download Time: %s' % duration, Log.DEBUG)
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
    url += '&operatingSystemName=Windows' if playback_req and (_g.platform & _g.OS_ANDROID) and devicetypeid == _g.dtid_web and _s.wvl1_device else ''  # cookie auth on android
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

    url += opt
    if retURL:
        return url
    data = getURL(url if not proxyEndpoint else 'http://{}/{}/{}'.format(getConfig('proxyaddress'), proxyEndpoint, quote_plus(url)),
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
            parameter = '%s&deviceID=%s&format=json&version=%s&formatVersion=3&marketplaceId=%s' % (
                deviceTypeID, _g.deviceID, version, _g.MarketID)
            if site_id:
                parameter += '&id=' + site_id
            jsondata = getURL('%s/cdp/%s?%s%s' % (_g.ATVUrl, pg_mode, parameter, query), useCookie=useCookie)
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
        Log('ASINs {} not found'.format([asinlist[n] for n, i in enumerate(sorteditems) if i == 'empty']))

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
    try:
        from htmlentitydefs import name2codepoint
    except:
        from html.entities import name2codepoint

    def Unescape(text):
        """ Unescape various html/xml entities in dictionary values, courtesy of Fredrik Lundh """

        def fixup(m):
            """ Unescape entities except for double quotes, lest the JSON breaks """
            text = m.group(0)  # First group is the text to replace

            # Unescape if possible
            if text[:2] == "&#":
                # character reference
                try:
                    bHex = ("&#x" == text[:3])
                    char = int(text[3 if bHex else 2:-1], 16 if bHex else 10)
                    if 34 == char:
                        text = u'\\"'
                    else:
                        try:
                            text = unichr(char)
                        except NameError:
                            text = chr(char)
                except ValueError:
                    pass
            else:
                # named entity
                char = text[1:-1]
                if 'quot' == char:
                    text = u'\\"'
                elif char in name2codepoint:
                    char = name2codepoint[char]
                    try:
                        text = unichr(char)
                    except NameError:
                        text = chr(char)
            return text

        text = re.sub('&#?\\w+;', fixup, text)
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
        r = getURL(FQify(url), silent=True, useCookie=True, rjson=False, postdata=postData)
        if not r:
            return None
        r = r.strip()
        if r.startswith('{'):
            o = json.loads(Unescape(r))
            if _s.json_dump_raw:
                Prune(o)
            return o

        matches = BeautifulSoup(r, 'html.parser').find_all('script', {'type': re.compile('(?:text/template|application/json)'), 'id': ''})
        if not matches:
            matches = Captcha(r)
            if not matches:
                Log('No JSON objects found in the page', Log.ERROR)
                return None

        # Create a single object containing all the data from the multiple JSON objects in the page
        o = {}
        for m in matches:
            m = json.loads(Unescape(m.string.strip()))

            if ('widgets' in m) and ('Storefront' in m['widgets']):
                m = m['widgets']['Storefront']
            elif 'props' in m:
                m = m['props']
                if 'body' in m and len(m['body']) > 0:
                    bodies = m['body']
                    if 'siteWide' in m and 'bodyStart' in m['siteWide'] and len(m['siteWide']['bodyStart']) > 0:
                        for bs in m['siteWide']['bodyStart']:
                            if 'name' in bs and bs['name'] == 'navigation-bar' and 'props' in bs:
                                m = bs['props']
                    for bd in bodies:
                        if 'props' in bd:
                            body = bd['props']
                            for p in ['atf', 'btf', 'landingPage', 'browse', 'search', 'categories', 'genre']:
                                Merge(m, body.get(p, {}))
                            for p in ['content']:
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
            # Prune sensitive context info and merge into o
            if _s.json_dump_raw:
                Prune(m)
            Merge(o, m)
        return o if o else None

    def Captcha(r):
        from .login import MFACheck
        from .common import parseHTML
        u = FQify(url)
        cj = MechanizeLogin()
        br = mechanicalsoup.StatefulBrowser(soup_config={'features': 'html.parser'})
        br.session.headers = getURL.headers
        br.set_cookiejar(cj)
        br.open_fake_page(r, u)
        r, soup = parseHTML(br)
        if any(sp in r for sp in _g.mfa_keywords):
            br = MFACheck(br, '', soup)
            if br is None:
                return False
            if not br.get_current_form() is None:
                br.submit_selected()
            from .users import saveUserCookies
            saveUserCookies(cj)
            r = getURL(u, useCookie=True, rjson=False, postdata=postData)
            br.open_fake_page(r, u)
            r, soup = parseHTML(br)
            WriteLog(r, 'captcha-webapi')
        return BeautifulSoup(r, 'html.parser').find_all('script', {'type': re.compile('(?:text/template|application/json)'), 'id': ''})

    if hasattr(GrabJSON, 'runs') and GrabJSON.runs:
        while GrabJSON.runs:
            sleep(1)
    j = do(url, postData)
    GrabJSON.runs = False
    LogJSON(j, url)
    return j


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
