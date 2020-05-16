#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from base64 import b64encode, b64decode
from kodi_six.utils import py2_decode
from kodi_six import xbmcgui
import pickle
import json
import mechanicalsoup
from platform import node
import pyxbmct
import re
import requests
import uuid
import ssl
from urllib3.poolmanager import PoolManager
from requests.adapters import HTTPAdapter
from pyDes import *
from random import randint
from bs4 import BeautifulSoup
from .l10n import *
from .logging import *
from .configs import *
from .common import Globals, Settings, sleep


def _parseHTML(br):
    soup = br.get_current_page()
    response = soup.__unicode__()
    return response, soup


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
    UAblist = json.loads(getConfig('UABlacklist', json.dumps([])))

    if blacklist:
        UAcur = getConfig('UserAgent')
        if UAcur not in UAblist:
            UAblist.append(UAcur)
            writeConfig('UABlacklist', json.dumps(UAblist))
            Log('UA: %s blacklisted' % UAcur)

    UAwlist = [i for i in UAlist if i not in UAblist]
    if not UAlist or len(UAwlist) < 5:
        Log('Loading list of common UserAgents')
        # [{'pt': int perthousand, 'ua': 'useragent string', 'bw': 'detected browser': 'os': 'detected O/S'}, …]
        rj = getURL('http://www.skydubh.com/pub/useragents.json', rjson=True)
        UAwlist = [ua['ua'] for ua in rj]
    UAnew = UAwlist[randint(0, len(UAwlist) - 1)] if UAwlist else \
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/59.0.3071.115 Safari/537.36'
    writeConfig('UserAgent', UAnew)
    Log('Using UserAgent: ' + UAnew)
    return


def mobileUA(content):
    soup = BeautifulSoup(content, 'html.parser')
    res = soup.find('html')
    res = res.get('class', '') if res else ''
    return True if 'a-mobile' in res or 'a-tablet' in res else False


def getTerritory(user):
    area = [{'atvurl': '', 'baseurl': '', 'mid': '', 'pv': False},
            {'atvurl': 'https://atv-ps-eu.amazon.de', 'baseurl': 'https://www.amazon.de', 'mid': 'A1PA6795UKMFR9', 'pv': False},
            {'atvurl': 'https://atv-ps-eu.amazon.co.uk', 'baseurl': 'https://www.amazon.co.uk', 'mid': 'A1F83G8C2ARO7P', 'pv': False},
            {'atvurl': 'https://atv-ps.amazon.com', 'baseurl': 'https://www.amazon.com', 'mid': 'ATVPDKIKX0DER', 'pv': False},
            {'atvurl': 'https://atv-ps-fe.amazon.co.jp', 'baseurl': 'https://www.amazon.co.jp', 'mid': 'A1VC38T7YXB528', 'pv': False},
            {'atvurl': 'https://atv-ps-eu.primevideo.com', 'baseurl': 'https://www.primevideo.com', 'mid': 'A3K6Y4MI8GDYMT', 'pv': True},
            {'atvurl': 'https://atv-ps-eu.primevideo.com', 'baseurl': 'https://www.primevideo.com', 'mid': 'A2MFUE2XK8ZSSY', 'pv': True},
            {'atvurl': 'https://atv-ps-fe.primevideo.com', 'baseurl': 'https://www.primevideo.com', 'mid': 'A15PK738MTQHSO', 'pv': True},
            {'atvurl': 'https://atv-ps.primevideo.com', 'baseurl': 'https://www.primevideo.com', 'mid': 'ART4WZ8MWBX2Y', 'pv': True}][Settings().region]

    if area['mid']:
        user.update(area)
    else:
        Log('Retrieve territoral config')
        data = getURL('https://na.api.amazonvideo.com/cdp/usage/v2/GetAppStartupConfig?deviceTypeID=A28RQHJKHM2A2W&deviceID=%s&firmware=1&version=1&format=json'
                      % g.deviceID)
        if not hasattr(data, 'keys'):
            return user, False
        if 'customerConfig' in data.keys():
            host = data['territoryConfig']['defaultVideoWebsite']
            reg = data['customerConfig']['homeRegion'].lower()
            reg = '' if 'na' in reg else '-' + reg
            user['atvurl'] = host.replace('www.', '').replace('//', '//atv-ps%s.' % reg)
            user['baseurl'] = data['territoryConfig']['primeSignupBaseUrl']
            user['mid'] = data['territoryConfig']['avMarketplace']
            user['pv'] = 'primevideo' in host

    return user, True


def getURL(url, useCookie=False, silent=False, headers=None, rjson=True, attempt=1, check=False, postdata=None, binary=False):
    if not hasattr(getURL, 'sessions'):
        getURL.sessions = {}  # Keep-Alive sessions

    # Static variable to store last response code. 0 means generic error (like SSL/connection errors),
    # while every other response code is a specific HTTP status code
    getURL.lastResponseCode = 0

    # Create sessions for keep-alives and connection pooling
    host = re.search('://([^/]+)(?:/|$)', url)  # Try to extract the host from the URL
    if None is not host:
        host = host.group(1)
        if host not in getURL.sessions:
            getURL.sessions[host] = requests.Session()
        session = getURL.sessions[host]
    else:
        session = requests.Session()

    cj = requests.cookies.RequestsCookieJar()
    retval = [] if rjson else ''
    if useCookie:
        cj = MechanizeLogin() if isinstance(useCookie, bool) else useCookie
        if isinstance(cj, bool):
            return retval

    from .common import Globals, Settings
    g = Globals()
    s = Settings()
    if (not silent) or s.verbLog:
        dispurl = url
        dispurl = re.sub('(?i)%s|%s|&token=\\w+|&customerId=\\w+' % (g.tvdb, g.tmdb), '', url).strip()
        Log('%sURL: %s' % ('check' if check else 'post' if postdata is not None else 'get', dispurl))

    headers = {} if not headers else headers
    if 'User-Agent' not in headers:
        headers['User-Agent'] = getConfig('UserAgent')
    if 'Host' not in headers:
        headers['Host'] = host
    if 'Accept-Language' not in headers:
        headers['Accept-Language'] = g.userAcceptLanguages

    if 'amazonvideo.com' in host:
        session.mount('https://', MyTLS1Adapter())

    class TryAgain(Exception):
        pass  # Try again on temporary errors

    class NoRetries(Exception):
        pass  # Fail on permanent errors

    try:
        starttime = time.time()
        method = 'POST' if postdata is not None else 'GET'
        r = session.request(method, url, data=postdata, headers=headers, cookies=cj, verify=s.verifySsl, stream=True)
        getURL.lastResponseCode = r.status_code  # Set last response code
        response = 'OK'
        if not check:
            response = r.content if binary else r.text
        Log('Download Time: %s' % (time.time() - starttime), Log.DEBUG)
        # 408 Timeout, 429 Too many requests and 5xx errors are temporary
        # Consider everything else definitive fail (like 404s and 403s)
        if (408 == r.status_code) or (429 == r.status_code) or (500 <= r.status_code):
            raise TryAgain('{0} error'.format(r.status_code))
        if 400 <= r.status_code:
            raise NoRetries('{0} error'.format(r.status_code))
    except (TryAgain,
            NoRetries,
            requests.exceptions.Timeout,
            requests.exceptions.ConnectionError,
            requests.exceptions.SSLError,
            requests.exceptions.HTTPError,
            requests.packages.urllib3.exceptions.SNIMissingWarning,
            requests.packages.urllib3.exceptions.InsecurePlatformWarning) as e:
        eType = e.__class__.__name__
        Log('Error reason: %s (%s)' % (str(e), eType), Log.ERROR)
        if 'SNIMissingWarning' in eType:
            Log('Using a Python/OpenSSL version which doesn\'t support SNI for TLS connections.', Log.ERROR)
            g.dialog.ok('No SNI for TLS', 'Your current Python/OpenSSL environment does not support SNI over TLS connections.',
                        'You can find a Linux guide on how to update Python and its modules for Kodi here: https://goo.gl/CKtygz',
                        'Additionally, follow this guide to update the required modules: https://goo.gl/ksbbU2')
            exit()
        if 'InsecurePlatformWarning' in eType:
            Log('Using an outdated SSL module.', Log.ERROR)
            g.dialog.ok('SSL module outdated', 'The SSL module for Python is outdated.',
                        'You can find a Linux guide on how to update Python and its modules for Kodi here: https://goo.gl/CKtygz',
                        'Additionally, follow this guide to update the required modules: https://goo.gl/ksbbU2')
            exit()
        if (not check) and (3 > attempt) and (('TryAgain' in eType) or ('Timeout' in eType)):
            wait = 10 * attempt if '429' in str(e) else 0
            attempt += 1
            Log('Attempt #{0}{1}'.format(attempt, '' if 0 == wait else ' (Too many requests, pause %s seconds…)' % wait))
            if 0 < wait:
                sleep(wait)
            return getURL(url, useCookie, silent, headers, rjson, attempt, check, postdata, binary)
        return retval
    res = json.loads(response) if rjson else response
    return res


def getURLData(mode, asin, retformat='json', devicetypeid='AOAGZA014O5RE', version=1, firmware='1', opt='', extra=False,
               useCookie=False, retURL=False, vMT='Feature', dRes='PlaybackUrls,SubtitleUrls,ForcedNarratives',
               proxyEndpoint=None, silent=False):
    try:
        from urllib.parse import quote_plus
    except ImportError:
        from urllib import quote_plus

    g = Globals()
    url = g.ATVUrl + '/cdp/' + mode
    url += '?asin=' + asin
    url += '&deviceTypeID=' + devicetypeid
    url += '&firmware=' + firmware
    url += '&deviceID=' + g.deviceID
    url += '&marketplaceID=' + g.MarketID
    url += '&format=' + retformat
    url += '&version=' + str(version)
    url += '&gascEnabled=' + str(g.UsePrimeVideo).lower()
    if 'SubtitleUrls' in dRes.split(','):
        url += "&subtitleFormat=TTMLv2"
    if ('catalog/GetPlaybackResources' == mode) and (g.platform & g.OS_ANDROID):
        url += '&operatingSystemName=Windows'
    if extra:
        url += '&resourceUsage=ImmediateConsumption&consumptionType=Streaming&deviceDrmOverride=CENC' \
               '&deviceStreamingTechnologyOverride=DASH&deviceProtocolOverride=Https' \
               '&deviceBitrateAdaptationsOverride=CVBR%2CCBR&audioTrackId=all'
        url += '&languageFeature=MLFv2'  # Audio Description tracks
        url += '&videoMaterialType=' + vMT
        url += '&desiredResources=' + dRes
        url += '&supportedDRMKeyScheme=DUAL_KEY' if (not g.platform & g.OS_ANDROID) and ('PlaybackUrls' in dRes) else ''
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

    g = Globals()
    s = Settings()
    if '?' in query:
        query = query.split('?')[1]
    if query:
        query = '&IncludeAll=T&AID=1&' + query.replace('HideNum=T', 'HideNum=F')
    pg_mode = pg_mode.split('_')[0]
    if '/' not in pg_mode:
        pg_mode = 'catalog/' + pg_mode
    rem_pos = False if re.search('(?i)rolluptoseason=t|contenttype=tvseason', query) else s.useEpiThumbs

    if 'asinlist=&' not in query:
        titles = 0
        ids = len(_TypeIDs[rem_pos]) - 1
        att = 0
        while titles == 0 and att <= ids:
            deviceTypeID = _TypeIDs[rem_pos][att]
            parameter = '%s&deviceID=%s&format=json&version=%s&formatVersion=3&marketplaceId=%s' % (
                deviceTypeID, g.deviceID, version, g.MarketID)
            if site_id:
                parameter += '&id=' + site_id
            jsondata = getURL('%s/cdp/%s?%s%s' % (g.ATVUrl, pg_mode, parameter, query), useCookie=useCookie)
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
    try:
        from urllib.parse import parse_qs
    except:
        from urlparse import parse_qs

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


def MechanizeLogin():
    from .users import loadUser
    cj = requests.cookies.RequestsCookieJar()
    cookie = loadUser('cookie')

    if cookie:
        try:
            cj.update(requests.utils.cookiejar_from_dict(cookie))
            return cj
        except:
            pass

    return LogIn(False)


def LogIn(ask=True):
    def _insertLF(string, begin=70):
        spc = string.find(' ', begin)
        return string[:spc] + '\n' + string[spc + 1:] if spc > 0 else string

    def _MFACheck(br, email, soup):
        Log('MFA, DCQ or Captcha form')
        uni_soup = soup.__unicode__()
        try:
            form = br.select_form('form[name="signIn"]')
        except mechanicalsoup.LinkNotFoundError:
            form = br.select_form()

        if 'auth-mfa-form' in uni_soup:
            msg = soup.find('form', attrs={'id': 'auth-mfa-form'})
            msgtxt = msg.p.get_text(strip=True)
            kb = xbmc.Keyboard('', msgtxt)
            kb.doModal()
            if kb.isConfirmed() and kb.getText():
                br['otpCode'] = kb.getText()
            else:
                return None
        elif 'ap_dcq_form' in uni_soup:
            msg = soup.find('div', attrs={'id': 'message_warning'})
            g.dialog.ok(g.__plugin__, msg.p.get_text(strip=True))
            dcq = soup.find('div', attrs={'id': 'ap_dcq1a_pagelet'})
            dcq_title = dcq.find('div', attrs={'id': 'ap_dcq1a_pagelet_title'}).get_text(strip=True)
            q_title = []
            q_id = []
            for q in dcq.findAll('div', attrs={'class': 'dcq_question'}):
                if q.span.label:
                    label = q.span.label.get_text(strip=True).replace('  ', '').replace('\n', '')
                    if q.span.label.span:
                        label = label.replace(str(q.span.label.span), q.span.label.span.text)
                    q_title.append(_insertLF(label))
                    q_id.append(q.input['id'])

            sel = g.dialog.select(_insertLF(dcq_title, 60), q_title) if len(q_title) > 1 else 0
            if sel < 0:
                return None

            ret = g.dialog.input(q_title[sel])
            if ret:
                br[q_id[sel]] = ret
            else:
                return None
        elif ('ap_captcha_img_label' in uni_soup) or ('auth-captcha-image-container' in uni_soup):
            # form.find_by_type('input', 'text', {'id': 'ap-credential-autofill-hint'}):
            wnd = _Captcha((getString(30008).split('…')[0]), soup, email)
            wnd.doModal()
            if wnd.email and wnd.cap and wnd.pwd:
                form.set_input({'email': wnd.email, 'password': wnd.pwd, 'guess': wnd.cap})
            else:
                return None
            del wnd
        elif 'claimspicker' in uni_soup:
            msg = soup.find('form', attrs={'name': 'claimspicker'})
            cs_title = msg.find('div', attrs={'class': 'a-row a-spacing-small'}).get_text(strip=True)
            cs_quest = msg.find('label', attrs={'class': 'a-form-label'})
            cs_hint = msg.find(lambda tag: tag.name == 'div' and tag.get('class') == ['a-row']).get_text(strip=True)
            choices = []
            if cs_quest:
                for c in soup.findAll('div', attrs={'data-a-input-name': 'option'}):
                    choices.append((c.span.get_text(strip=True), c.input['name'], c.input['value']))
                sel = g.dialog.select('%s - %s' % (cs_title, cs_quest.get_text(strip=True)), [k[0] for k in choices])
            else:
                sel = 100 if g.dialog.ok(cs_title, cs_hint) else -1

            if sel > -1:
                if sel < 100:
                    form.set_radio({choices[sel][1]: choices[sel][2]})
            else:
                return None
        elif 'fwcim-form' in uni_soup:
            msg = soup.find('div', attrs={'class': 'a-row a-spacing-micro cvf-widget-input-code-label'})
            if msg:
                ret = g.dialog.input(msg.get_text(strip=True))
                if ret:
                    br['code'] = ret
                else:
                    return None
            msg = soup.find('img', attrs={'alt': 'captcha'})
            if msg:
                wnd = _Challenge(msg)
                wnd.doModal()
                if wnd.cap:
                    submit = soup.find('input', value='verifyCaptcha')
                    form.choose_submit(submit)
                    form.set_input({'cvf_captcha_input': wnd.cap})
                else:
                    return None
                del wnd
        return br

    def _setLoginPW():
        keyboard = xbmc.Keyboard('', getString(30003))
        keyboard.doModal(60000)
        if keyboard.isConfirmed() and keyboard.getText():
            password = keyboard.getText()
            return password
        return False

    def _getmac():
        mac = uuid.getnode()
        if (mac >> 40) % 2:
            mac = node()
        return uuid.uuid5(uuid.NAMESPACE_DNS, str(mac)).bytes

    def _encode(data):
        k = triple_des(_getmac(), CBC, b"\0\0\0\0\0\0\0\0", padmode=PAD_PKCS5)
        d = k.encrypt(data)
        return b64encode(d).decode('utf-8')

    def _decode(data):
        if not data:
            return ''
        k = triple_des(_getmac(), CBC, b"\0\0\0\0\0\0\0\0", padmode=PAD_PKCS5)
        d = k.decrypt(b64decode(data))
        return d

    class LoginLocked(Exception):
        pass

    from contextlib import contextmanager
    @contextmanager
    def LoginLock():
        try:
            bLocked = 'false' != getConfig('loginlock', 'false')
            if not bLocked:
                writeConfig('loginlock', 'true')
            yield bLocked
        except LoginLocked:  # Already locked
            pass
        except Exception as e:  # Something went horribly wrong, release and re-raise
            writeConfig('loginlock', 'false')
            raise e
        else:  # All fine, release
            writeConfig('loginlock', 'false')

    with LoginLock() as locked:
        if locked:
            raise LoginLocked

        g = Globals()
        s = Settings()
        Log('Login')
        from .users import loadUser, addUser
        user = loadUser(empty=ask)
        email = user['email']
        password = _decode(user['password'])
        savelogin = False  # g.addon.getSetting('save_login') == 'true'
        useMFA = False

        if not user['baseurl']:
            user = getTerritory(user)
            if False is user[1]:
                return False
            user = user[0]

        if ask:
            keyboard = xbmc.Keyboard(email, getString(30002))
            keyboard.doModal()
            if keyboard.isConfirmed() and keyboard.getText():
                email = keyboard.getText()
                password = _setLoginPW()
        else:
            if not email or not password:
                g.dialog.notification(getString(30200), getString(30216))
                xbmc.executebuiltin('Addon.OpenSettings(%s)' % g.addon.getAddonInfo('id'))
                return False

        if password:
            cj = requests.cookies.RequestsCookieJar()
            br = mechanicalsoup.StatefulBrowser(soup_config={'features': 'html.parser'})
            br.set_cookiejar(cj)
            br.session.verify = s.verifySsl
            caperr = -5
            while caperr:
                Log('Connect to SignIn Page %s attempts left' % -caperr)
                br.session.headers.update({'User-Agent': getConfig('UserAgent')})
                br.open(user['baseurl'] + ('/gp/aw/si.html' if not user['pv'] else '/auth-redirect/'))
                try:
                    form = br.select_form('form[name="signIn"]')
                except mechanicalsoup.LinkNotFoundError:
                    getUA(True)
                    caperr += 1
                    WriteLog(str(br.get_current_page()), 'login-si')
                    xbmc.sleep(randint(750, 1500))
                else:
                    break
            else:
                g.dialog.ok(getString(30200), getString(30213))
                return False

            form.set_input({'email': email, 'password': password})
            if 'true' == g.addon.getSetting('rememberme') and form.find_by_type('input', 'checkbox', {'name': 'rememberMe'}):
                form.set_checkbox({'rememberMe': True})

            br.session.headers.update({'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                                       'Accept-Encoding': 'gzip, deflate',
                                       'Accept-Language': g.userAcceptLanguages,
                                       'Cache-Control': 'max-age=0',
                                       'Connection': 'keep-alive',
                                       'Content-Type': 'application/x-www-form-urlencoded',
                                       'Origin': '/'.join(br.get_url().split('/')[0:3]),
                                       'Upgrade-Insecure-Requests': '1'})

            br.submit_selected()
            response, soup = _parseHTML(br)
            WriteLog(response.replace(py2_decode(email), '**@**'), 'login')

            while any(sp in response for sp in
                      ['auth-mfa-form', 'ap_dcq_form', 'ap_captcha_img_label', 'claimspicker', 'fwcim-form', 'auth-captcha-image-container']):
                br = _MFACheck(br, email, soup)
                if br is None:
                    return False
                useMFA = True if br.get_current_form().form.find('input', {'name': 'otpCode'}) else False
                br.submit_selected()
                response, soup = _parseHTML(br)
                WriteLog(response.replace(py2_decode(email), '**@**'), 'login-mfa')

            if 'accountFixup' in response:
                Log('Login AccountFixup')
                skip_link = br.find_link(id='ap-account-fixup-phone-skip-link')
                br.follow_link(skip_link)
                response, soup = _parseHTML(br)
                WriteLog(response.replace(py2_decode(email), '**@**'), 'login-fixup')

            if 'action=sign-out' in response:
                try:
                    usr = re.search(r'action=sign-out[^"]*"[^>]*>[^?]+\s+([^?]+?)\s*\?', response).group(1)
                except AttributeError:
                    usr = getString(30209)

                if s.multiuser and ask:
                    usr = g.dialog.input(getString(30135), usr)
                    if not usr:
                        return False
                if useMFA:
                    g.addon.setSetting('save_login', 'false')
                    savelogin = False

                user['name'] = usr
                user['email'] = user['password'] = user['cookie'] = ''

                if savelogin:
                    user['email'] = email
                    user['password'] = _encode(password)
                else:
                    user['cookie'] = requests.utils.dict_from_cookiejar(cj)

                if ask:
                    remLoginData(False)
                    g.addon.setSetting('login_acc', usr)
                    if not s.multiuser:
                        g.dialog.ok(getString(30215), '{0} {1}'.format(getString(30014), usr))

                addUser(user)
                g.genID()
                return cj
            elif 'message_error' in response:
                writeConfig('login_pass', '')
                msg = soup.find('div', attrs={'id': 'message_error'})
                Log('Login Error: %s' % msg.get_text(strip=True))
                g.dialog.ok(getString(30200), msg.get_text(strip=True))
            elif 'message_warning' in response:
                msg = soup.find('div', attrs={'id': 'message_warning'})
                Log('Login Warning: %s' % msg.get_text(strip=True))
            elif 'auth-error-message-box' in response:
                msg = soup.find('div', attrs={'id': 'auth-error-message-box'})
                Log('Login MFA: %s' % msg.get_text(strip=True))
                g.dialog.ok(msg.div.h4.get_text(strip=True), msg.div.div.get_text(strip=True))
            elif 'error-slot' in response:
                msg_title = soup.find('div', attrs={'class': 'ap_error_page_title'}).get_text(strip=True)
                msg_cont = soup.find('div', attrs={'class': 'ap_error_page_message'}).get_text(strip=True)
                Log('Login Error: {}'.format(msg_cont))
                g.dialog.ok(msg_title, msg_cont)
            else:
                g.dialog.ok(getString(30200), getString(30213))

    return False


def remLoginData(info=True):
    for fn in xbmcvfs.listdir(g.DATA_PATH)[1]:
        if fn.startswith('cookie'):
            xbmcvfs.delete(OSPJoin(g.DATA_PATH, fn))
    writeConfig('accounts', '')
    writeConfig('login_name', '')
    writeConfig('login_pass', '')

    if info:
        writeConfig('accounts.lst', '')
        g.addon.setSetting('login_acc', '')
        g.dialog.notification(g.__plugin__, getString(30211), xbmcgui.NOTIFICATION_INFO)


class _Captcha(pyxbmct.AddonDialogWindow):
    def __init__(self, title='', soup=None, email=None):
        super(_Captcha, self).__init__(title)
        if soup.find('div', attrs={'id': 'ap_captcha_img_label'}):
            head = soup.find('div', attrs={'id': 'message_warning'})
            if not head:
                head = soup.find('div', attrs={'id': 'message_error'})
            title = soup.find('div', attrs={'id': 'ap_captcha_guess_alert'})
            self.head = head.p.get_text(strip=True)
            self.head = re.sub('(?i)<[^>]*>', '', self.head)
            self.picurl = soup.find('div', attrs={'id': 'ap_captcha_img'}).img.get('src')
        else:
            self.head = soup.find('span', attrs={'class': 'a-list-item'}).get_text(strip=True)
            title = soup.find('div', attrs={'id': 'auth-guess-missing-alert'}).div.div
            self.picurl = soup.find('div', attrs={'id': 'auth-captcha-image-container'}).img.get('src')
        self.setGeometry(500, 550, 9, 2)
        self.email = email
        self.pwd = ''
        self.cap = ''
        self.title = title.get_text(strip=True)
        self.image = pyxbmct.Image('', aspectRatio=2)
        self.tb_head = pyxbmct.TextBox()
        self.fl_title = pyxbmct.FadeLabel(_alignment=pyxbmct.ALIGN_CENTER)
        self.username = pyxbmct.Edit('', _alignment=pyxbmct.ALIGN_LEFT | pyxbmct.ALIGN_CENTER_Y)
        self.password = pyxbmct.Edit('', _alignment=pyxbmct.ALIGN_LEFT | pyxbmct.ALIGN_CENTER_Y)
        self.captcha = pyxbmct.Edit('', _alignment=pyxbmct.ALIGN_LEFT | pyxbmct.ALIGN_CENTER_Y)
        self.btn_submit = pyxbmct.Button(getString(30008).split('…')[0])
        self.btn_cancel = pyxbmct.Button(getString(30123))
        self.set_controls()
        self.set_navigation()

    def set_controls(self):
        self.placeControl(self.tb_head, 0, 0, columnspan=2, rowspan=3)
        self.placeControl(pyxbmct.Label(getString(30002), alignment=pyxbmct.ALIGN_CENTER_Y | pyxbmct.ALIGN_CENTER), 2, 0)
        self.placeControl(pyxbmct.Label(getString(30003), alignment=pyxbmct.ALIGN_CENTER_Y | pyxbmct.ALIGN_CENTER), 3, 0)
        self.placeControl(self.username, 2, 1, pad_y=8)
        self.placeControl(self.password, 3, 1, pad_y=8)
        self.placeControl(self.image, 4, 0, rowspan=2, columnspan=2)
        self.placeControl(self.fl_title, 6, 0, columnspan=2)
        self.placeControl(self.captcha, 7, 0, columnspan=2, pad_y=8)
        self.placeControl(self.btn_submit, 8, 0)
        self.placeControl(self.btn_cancel, 8, 1)
        self.connect(self.btn_cancel, self.close)
        self.connect(self.btn_submit, self.submit)
        self.connect(pyxbmct.ACTION_NAV_BACK, self.close)
        self.username.setText(self.email)
        self.username.setEnabled(False)
        self.tb_head.setText(self.head)
        self.fl_title.addLabel(self.title)
        self.image.setImage(self.picurl, False)

    def set_navigation(self):
        self.username.controlUp(self.btn_submit)
        self.username.controlDown(self.password)
        self.password.controlUp(self.username)
        self.password.controlDown(self.captcha)
        self.captcha.controlUp(self.password)
        self.captcha.controlDown(self.btn_submit)
        self.btn_submit.controlUp(self.captcha)
        self.btn_submit.controlDown(self.username)
        self.btn_cancel.controlUp(self.captcha)
        self.btn_cancel.controlDown(self.username)
        self.btn_submit.controlRight(self.btn_cancel)
        self.btn_submit.controlLeft(self.btn_cancel)
        self.btn_cancel.controlRight(self.btn_submit)
        self.btn_cancel.controlLeft(self.btn_submit)
        self.setFocus(self.password)

    def submit(self):
        self.pwd = self.password.getText()
        self.cap = self.captcha.getText()
        self.email = self.username.getText()
        self.close()


class _Challenge(pyxbmct.AddonDialogWindow):
    def __init__(self, msg):
        box = msg.find_parent('div', class_='a-box-inner a-padding-extra-large')
        self.head = box.find('span', class_='a-size-large').get_text(strip=True)
        self.hint = box.find('span', class_='a-size-base a-color-secondary').get_text(strip=True)
        self.task = box.find('label', class_='a-form-label').get_text(strip=True)
        super(_Challenge, self).__init__(self.head)
        self.setGeometry(500, 400, 7, 2)
        self.cap = ''
        self.tb_hint = pyxbmct.TextBox()
        self.fl_task = pyxbmct.FadeLabel(_alignment=pyxbmct.ALIGN_CENTER)
        self.img_url = pyxbmct.Image(msg['src'], aspectRatio=2)
        self.ed_cap = pyxbmct.Edit('', _alignment=pyxbmct.ALIGN_LEFT | pyxbmct.ALIGN_CENTER_Y)
        self.btn_submit = pyxbmct.Button('OK')
        self.btn_cancel = pyxbmct.Button(getString(30123))
        self.set_controls()

    def set_controls(self):
        self.placeControl(self.tb_hint, 0, 0, 1, 2)
        self.placeControl(self.img_url, 1, 0, 3, 2)
        self.placeControl(self.fl_task, 4, 0, 1, 2)
        self.placeControl(self.ed_cap, 5, 0, 1, 2)
        self.placeControl(self.btn_submit, 6, 0)
        self.placeControl(self.btn_cancel, 6, 1)
        self.connect(self.btn_cancel, self.close)
        self.connect(self.btn_submit, self.submit)
        self.connect(pyxbmct.ACTION_NAV_BACK, self.close)
        self.tb_hint.setText(self.hint)
        self.fl_task.addLabel(self.task)
        self.setFocus(self.ed_cap)

    def submit(self):
        self.cap = self.ed_cap.getText()
        self.close()


class MyTLS1Adapter(HTTPAdapter):
    def init_poolmanager(self, connections, maxsize, block=False):
        Log('TLSv1 Adapter', Log.DEBUG)
        self.poolmanager = PoolManager(num_pools=connections, maxsize=maxsize, block=block, ssl_version=ssl.PROTOCOL_TLSv1)
