#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import os
from base64 import urlsafe_b64encode, b16encode
from kodi_six.utils import py2_decode
from kodi_six import xbmcgui
import json
import mechanicalsoup
import pyxbmct
import re
import requests

from timeit import default_timer as timer
from random import randint
from bs4 import BeautifulSoup
from hashlib import sha256
from copy import deepcopy

from .l10n import *
from .logging import *
from .configs import *
from .common import Globals, Settings, sleep
from .metrics import addNetTime

try:
    from urlparse import urlparse, parse_qs
    from urllib import urlencode
except ImportError:
    from urllib.parse import urlparse, parse_qs, urlencode

domain_regex = r'[^\.]+\.([^/]+)(?:/|$)'


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
    if len(user.get('deviceid', '')) != 32:
        from uuid import uuid4
        user['deviceid'] = uuid4().hex

    areas = [{'atvurl': '', 'baseurl': '', 'mid': '', 'pv': False, 'country': ''},
             {'atvurl': 'https://atv-ps-eu.amazon.de', 'baseurl': 'https://www.amazon.de', 'mid': 'A1PA6795UKMFR9', 'pv': False, 'country': 'de'},
             {'atvurl': 'https://atv-ps-eu.amazon.co.uk', 'baseurl': 'https://www.amazon.co.uk', 'mid': 'A1F83G8C2ARO7P', 'pv': False, 'country': 'uk'},
             {'atvurl': 'https://atv-ps.amazon.com', 'baseurl': 'https://www.amazon.com', 'mid': 'ATVPDKIKX0DER', 'pv': False, 'country': 'us'},
             {'atvurl': 'https://atv-ps-fe.amazon.co.jp', 'baseurl': 'https://www.amazon.co.jp', 'mid': 'A1VC38T7YXB528', 'pv': False, 'country': 'jp'},
             {'atvurl': 'https://atv-ps-eu.primevideo.com', 'baseurl': 'https://www.primevideo.com', 'mid': 'A3K6Y4MI8GDYMT', 'pv': True, 'country': 'us'},
             {'atvurl': 'https://atv-ps-eu.primevideo.com', 'baseurl': 'https://www.primevideo.com', 'mid': 'A2MFUE2XK8ZSSY', 'pv': True, 'country': 'us'},
             {'atvurl': 'https://atv-ps-fe.primevideo.com', 'baseurl': 'https://www.primevideo.com', 'mid': 'A15PK738MTQHSO', 'pv': True, 'country': 'us'},
             {'atvurl': 'https://atv-ps.primevideo.com', 'baseurl': 'https://www.primevideo.com', 'mid': 'ART4WZ8MWBX2Y', 'pv': True, 'country': 'us'}]
    area = areas[Settings().region]

    if area['mid']:
        user.update(area)
    else:
        Log('Retrieve territoral config')
        data = getURL('https://atv-ps.amazon.com/cdp/usage/v2/GetAppStartupConfig?deviceTypeID=A28RQHJKHM2A2W&deviceID=%s&firmware=1&version=1&format=json'
                      % user['deviceid'])
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
            user['country'] = [a['country'] for a in areas if user['mid'] in a['mid']][0]
    return user, True


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

    from .common import Globals, Settings
    g = Globals()
    s = Settings()
    if (not silent) or s.verbLog:
        dispurl = re.sub('(?i)%s|%s|&token=\\w+|&customerId=\\w+' % (g.tvdb, g.tmdb), '', url).strip()
        Log('%sURL: %s' % ('check' if check else 'post' if postdata is not None else 'get', dispurl))

    if 'User-Agent' not in headers:
        headers['User-Agent'] = getConfig('UserAgent')
    """
    # This **breaks** redirections. Host header OVERRIDES the host in the URL:
    # if the URL is web.eu, but the Host is web.com, request will fetch web.com
    if 'Host' not in headers:
        headers['Host'] = host
    """
    if 'Accept-Language' not in headers:
        headers['Accept-Language'] = g.userAcceptLanguages
    if '/api/' in url:
        headers['X-Requested-With'] = 'XMLHttpRequest'

    class TryAgain(Exception):
        pass  # Try again on temporary errors

    class NoRetries(Exception):
        pass  # Fail on permanent errors

    try:
        starttime = timer()
        method = 'POST' if postdata is not None else 'GET'
        r = session.request(method, url, data=postdata, headers=headers, verify=s.verifySsl, stream=True, allow_redirects=allow_redirects)
        getURL.lastResponseCode = r.status_code  # Set last response code
        response = 'OK' if 400 > r.status_code >= 200 else ''
        if not check:
            response = r.content.decode('utf-8') if binary else r.text
        else:
            rjson = False
        if useCookie and 'auth-cookie-warning-message' in response:
            Log('Cookie invalid', Log.ERROR)
            g.dialog.notification(g.__plugin__, getString(30266), xbmcgui.NOTIFICATION_ERROR)
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


def getURLData(mode, asin, retformat='json', devicetypeid=g.dtid_web, version=2, firmware='1', opt='', extra=False,
               useCookie=False, retURL=False, vMT='Feature', dRes='PlaybackUrls,SubtitleUrls,ForcedNarratives',
               proxyEndpoint=None, silent=False):
    try:
        from urllib.parse import quote_plus
    except ImportError:
        from urllib import quote_plus

    g = Globals()
    playback_req = 'PlaybackUrls' in dRes or 'Widevine2License' in dRes
    url = g.ATVUrl + '/cdp/' + mode
    url += '?asin=' + asin
    url += '&deviceTypeID=' + devicetypeid
    url += '&firmware=' + firmware
    url += '&deviceID=' + g.deviceID
    url += '&marketplaceID=' + g.MarketID
    url += '&format=' + retformat
    url += '&version=' + str(version)
    url += '&gascEnabled=' + str(g.UsePrimeVideo).lower()
    url += "&subtitleFormat=TTMLv2" if 'SubtitleUrls' in dRes else ''
    url += '&operatingSystemName=Windows' if playback_req and (g.platform & g.OS_ANDROID) and devicetypeid == g.dtid_web else ''  # cookie auth on android
    if extra:
        url += '&resourceUsage=ImmediateConsumption&consumptionType=Streaming&deviceDrmOverride=CENC' \
               '&deviceStreamingTechnologyOverride=DASH&deviceProtocolOverride=Https' \
               '&deviceBitrateAdaptationsOverride=CVBR%2CCBR&audioTrackId=all'
        url += '&languageFeature=MLFv2'  # Audio Description tracks
        url += '&videoMaterialType=' + vMT
        url += '&desiredResources=' + dRes
        url += '&supportedDRMKeyScheme=DUAL_KEY' if playback_req else ''
        if devicetypeid == g.dtid_android:
            url += '&deviceVideoCodecOverride=H264' + (',H265' if s.uhd else '')
            url += '&deviceHdrFormatsOverride=' + supported_hdr()
            url += '&deviceVideoQualityOverride=' + ('UHD' if s.uhd else 'HD')

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
    g = Globals()
    hdr = []
    if g.addon.getSetting('enable_dovi') == 'true':
        hdr.append('DolbyVision')
    if g.addon.getSetting('enable_hdr10') == 'true':
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


def MechanizeLogin(preferToken=False):
    if preferToken:  # and g.platform & g.OS_ANDROID
        token = getToken()
        if token:
            return token

    # if Token not requested or not avaiable use cookie
    from .users import loadUser
    cj = requests.cookies.RequestsCookieJar()
    cookie = loadUser('cookie')
    if cookie:
        try:
            cj.update(requests.utils.cookiejar_from_dict(cookie))
            return cj
        except:
            pass

    return LogIn(preferToken)


def LogIn(retToken=False):
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
        elif 'auth-select-device-form' in uni_soup:
            sd_form = soup.find('form', attrs={'id': 'auth-select-device-form'})
            sd_hint = sd_form.parent.p.get_text(strip=True)
            choices = []
            for c in sd_form.findAll('label'):
                choices.append((c.span.get_text(strip=True), c.input['name'], c.input['value']))
            sel = g.dialog.select(sd_hint, [k[0] for k in choices])

            if sel > -1:
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
            if soup.find('img', attrs={'alt': 'captcha'}):
                wnd = _Challenge(soup)
                wnd.doModal()
                if wnd.cap:
                    submit = soup.find('input', value='verifyCaptcha')
                    form.choose_submit(submit)
                    form.set_input({'cvf_captcha_input': wnd.cap})
                else:
                    return None
                del wnd
        elif 'validateCaptcha' in uni_soup:
            wnd = _Challenge(soup)
            wnd.doModal()
            if wnd.cap:
                # MechanicalSoup is using the field names, not IDs
                # id is captchacharacters, which causes exception to be raised
                form.set_input({'field-keywords': wnd.cap})
            else:
                return None
            del wnd
        elif 'pollingForm' in uni_soup:
            msg = soup.find('span', attrs={'class': 'transaction-approval-word-break'}).get_text(strip=True)
            msg += '\n'
            rows = soup.find('div', attrs={'id': re.compile('.*channelDetails.*')})
            for row in rows.find_all('div', attrs={'class': 'a-row'}):
                msg += re.sub('\\s{2,}', ': ', row.get_text())
            pd = _ProgressDialog(msg)
            pd.show()
            refresh = time.time()
            form_id = form_poll = 'pollingForm'
            per = 0
            while True:
                if per > 99:
                    val = -5
                if per < 1:
                    val = 5
                per += val
                pd.sl_progress.setPercent(per)
                if pd.iscanceled:
                    br = None
                    break
                if time.time() > refresh + 5:
                    url = br.get_url()
                    br.select_form('form[id="{}"]'.format(form_id))
                    br.submit_selected()
                    response, soup = _parseHTML(br)
                    form_id = form_poll
                    WriteLog(response.replace(py2_decode(email), '**@**'), 'login-pollingform')
                    stat = soup.find('input', attrs={'name': 'transactionApprovalStatus'})['value']
                    if stat in ['TransactionCompleted', 'TransactionCompletionTimeout']:
                        parsed_url = urlparse(url)
                        query = parse_qs(parsed_url.query)
                        br.open(query['openid.return_to'][0])
                        break
                    elif stat in ['TransactionExpired', 'TransactionResponded']:
                        form_id = 'resend-approval-form'
                    else:
                        refresh = time.time()
                    br.open(url)
                sleep(0.1)
            pd.close()
        return br

    def _setLoginPW(visible):
        keyboard = xbmc.Keyboard('', getString(30003))
        keyboard.setHiddenInput(visible is False)
        keyboard.doModal(60000)
        if keyboard.isConfirmed() and keyboard.getText():
            password = keyboard.getText()
            return password
        return False

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
        user = getTerritory(loadUser(empty=True))
        if False is user[1]:
            return False
        user = user[0]
        password = ''
        keyboard = xbmc.Keyboard('', getString(30002))
        keyboard.doModal()
        if keyboard.isConfirmed() and keyboard.getText():
            email = keyboard.getText()
            password = _setLoginPW(s.show_pass)

        if password:
            cj = requests.cookies.RequestsCookieJar()
            br = mechanicalsoup.StatefulBrowser(soup_config={'features': 'html.parser'})
            br.set_cookiejar(cj)
            br.session.verify = s.verifySsl
            br.set_verbose(2)
            clientid = b16encode(user['deviceid'].encode() + b'#' + g.dtid_android.encode()).decode().lower()
            verifier = urlsafe_b64encode(os.urandom(32)).rstrip(b"=")
            challenge = urlsafe_b64encode(sha256(verifier).digest()).rstrip(b"=")
            br.session.headers.update(g.headers_android)
            params = {
                "openid.oa2.response_type": "code",
                "openid.oa2.code_challenge_method": "S256",
                "openid.oa2.code_challenge": challenge.decode(),
                "openid.return_to": '{}/ap/maplanding'.format(user['baseurl']),
                "openid.assoc_handle": "amzn_piv_android_v2_" + user['country'],
                "openid.identity": "http://specs.openid.net/auth/2.0/identifier_select",
                "pageId": "amzn_device_common_dark",
                "accountStatusPolicy": "P1",
                "openid.claimed_id": "http://specs.openid.net/auth/2.0/identifier_select",
                "openid.mode": "checkid_setup",
                "openid.ns.oa2": "http://www.amazon.com/ap/ext/oauth/2",
                "openid.oa2.client_id": "device:{}".format(clientid),
                "openid.ns.pape": "http://specs.openid.net/extensions/pape/1.0",
                "openid.oa2.scope": "device_auth_access",
                "forceMobileLayout": "true",
                "openid.ns": "http://specs.openid.net/auth/2.0",
                "openid.pape.max_auth_age": "0"
            }

            caperr = -5
            while caperr:
                Log('Connect to SignIn Page %s attempts left' % -caperr)
                br.open(user['baseurl'] + ('/ap/signin?' if not user['pv'] else '/auth-redirect/?') + urlencode(params))
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
            if 'true' == g.addon.getSetting('rememberme'):
                try:
                    form.set_checkbox({'rememberMe': True})
                except: pass
            br.submit_selected()
            response, soup = _parseHTML(br)
            WriteLog(response.replace(py2_decode(email), '**@**'), 'login')

            while any(sp in response for sp in
                      ['auth-mfa-form', 'ap_dcq_form', 'ap_captcha_img_label', 'claimspicker', 'fwcim-form', 'auth-captcha-image-container', 'validateCaptcha',
                       'pollingForm', 'auth-select-device-form']):
                br = _MFACheck(br, email, soup)
                if br is None:
                    return False
                if not br.get_current_form() is None:
                    br.submit_selected()
                response, soup = _parseHTML(br)
                WriteLog(response.replace(py2_decode(email), '**@**'), 'login-mfa')

            url = br.get_url()
            if 'accountFixup' in response:
                Log('Login AccountFixup')
                skip_link = br.find_link(id='ap-account-fixup-phone-skip-link')
                br.follow_link(skip_link)
                response, soup = _parseHTML(br)
                WriteLog(response.replace(py2_decode(email), '**@**'), 'login-fixup')

            # Some PrimeVideo endpoints still return you to the store, directly
            if url.endswith('?ref_=av_auth_return_redir') or ('action=sign-out' in response) or ('openid.oa2.authorization_code' in url):
                if 'openid.oa2.authorization_code' in url:
                    user = registerDevice(url, user, verifier, clientid)
                else:  # Raw HTML
                    try:
                        name = re.search(r'action=sign-out[^"]*"[^>]*>[^?]+\s+([^?]+?)\s*\?', response).group(1)
                    except AttributeError:
                        name = getString(30209)
                    from requests.utils import dict_from_cookiejar as dfcj
                    user = {
                        "name": name,
                        "cookie": dfcj(cj)
                    }

                if s.multiuser:
                    user['name'] = g.dialog.input(getString(30135), user['name'])
                    if not user['name']:
                        return False

                remLoginData(False)
                g.addon.setSetting('login_acc', user['name'])
                if not s.multiuser:
                    g.dialog.ok(getString(30215), '{0} {1}'.format(getString(30014), user['name']))

                addUser(user)
                return getToken(user) if retToken else cj
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


def registerDevice(url, user, verifier, clientid):
    parsed_url = parse_qs(urlparse(url).query)
    auth_code = parsed_url["openid.oa2.authorization_code"][0]
    domain = re.compile(domain_regex).search(user['baseurl']).group(1)

    data = {
        'auth_data': {
            'client_id': clientid,
            'authorization_code': auth_code,
            'code_verifier': verifier.decode(),
            'code_algorithm': 'SHA-256',
            'client_domain': 'DeviceLegacy',
        },
        'registration_data': deviceData(user),
        'requested_token_type': [
            'bearer',
            'website_cookies',
        ],
        'requested_extensions': [
            'device_info',
            'customer_info',
        ],
        'cookies': {
            'domain': '.' + domain,
            'website_cookies': [],
        },
    }

    resp = getURL('https://api.{}/auth/register'.format(domain), headers=g.headers_android, postdata=json.dumps(data))
    WriteLog(str(resp), 'login-register')

    if 'error' in resp['response']:
        g.dialog.notification(g.__plugin__, resp['response']['error']['message'], xbmcgui.NOTIFICATION_INFO)
        return False

    data = resp['response']['success']
    bearer = data['tokens']['bearer']
    customer = data['extensions']['customer_info']
    user['name'] = customer.get('given_name', customer.get('name', getString(30209)))
    user['token'] = {'access': bearer['access_token'], 'refresh': bearer['refresh_token'], 'expires': int(time.time()) + int(bearer['expires_in'])}
    user['cookie'] = {c['Name']: c['Value'] for c in data['tokens']['website_cookies']}
    return user


def deviceData(user):
    return {
        'domain': 'DeviceLegacy',
        'device_type': g.dtid_android,
        'device_serial': user['deviceid'],
        'app_name': 'com.amazon.avod.thirdpartyclient',
        'app_version': '296016847',
        'device_model': 'mdarcy/nvidia/SHIELD Android TV',
        'os_version': 'NVIDIA/mdarcy/mdarcy:11/RQ1A.210105.003/7094531_2971.7725:user/release-keys'
    }


def getToken(user=None):
    from .users import loadUser, addUser
    if user is None:
        user = loadUser()
    token = user.get('token')
    if token is not None:
        if int(time.time()) > token['expires']:
            user['token'] = refreshToken(user)
            addUser(user)
        return {'Authorization': 'Bearer ' + user['token']['access']}
    return False


def refreshToken(user):
    domain = re.compile(domain_regex).search(user['baseurl']).group(1)
    token = user['token']
    data = deviceData(user)
    data['requested_token_type'] = 'access_token'
    data['source_token_type'] = 'refresh_token'
    data['source_token'] = token['refresh']
    response = getURL('https://api.{}/auth/token'.format(domain), headers=g.headers_android, postdata=data)
    if 'access_token' in response:
        token['access'] = response['access_token']
        token['expires'] = int(time.time() + int(response['expires_in']))
        Log('Token renewed')
        return token
    else:
        Log('Token not renewed, registering device again', xbmc.LOGERROR)
    return False


def remLoginData(info=True):
    for fn in xbmcvfs.listdir(g.DATA_PATH)[1]:
        if py2_decode(fn).startswith('cookie'):
            xbmcvfs.delete(OSPJoin(g.DATA_PATH, fn))
    writeConfig('accounts', '')
    writeConfig('login_name', '')
    writeConfig('login_pass', '')
    writeConfig('GenDeviceID', '')

    if info:
        writeConfig('accounts.lst', '')
        g.addon.setSetting('login_acc', '')
        g.dialog.notification(g.__plugin__, getString(30211), xbmcgui.NOTIFICATION_INFO)


def FQify(URL):
    g = Globals()
    """ Makes sure to provide correct fully qualified URLs """
    base = g.BaseUrl
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

    s = Settings()

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
                if s.dumpJSONCollisions:
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
        """ Wrapper to facilitate logging """
        if re.match(r'/(?:gp/video/)?search(?:Default)?/', url):
            up = urlparse(url)
            qs = parse_qs(up.query)
            if 'from' in list(qs):  # list() instead of .keys() to avoid py3 iteration errors
                qs['startIndex'] = qs['from']
                del qs['from']
            if (url.startswith('/gp/video')):
                newPath = '/gp/video/api' + up.path.replace('/gp/video', '')
            else:
                newPath = '/api' + up.path.replace('/search/', '/searchDefault/')
            up = up._replace(path=newPath, query=urlencode([(k, v) for k, l in qs.items() for v in l]))
            url = up.geturl()
        r = getURL(FQify(url), silent=True, useCookie=True, rjson=False, postdata=postData)
        if not r:
            return None
        try:
            r = r.strip()
            if '{' == r[0:1]:
                o = json.loads(Unescape(r))
                if s.refineJSON:
                    Prune(o)
                return o
        except:
            pass
        matches = [r] if r.startswith('{') else re.findall(r'\s*(?:<script[^>]+type="(?:text/template|application/json)"[^>]*>|state:)\s*({[^\n]+})\s*(?:,|</script>)\s*', r)
        if not matches:
            Log('No JSON objects found in the page', Log.ERROR)
            return None

        # Create a single object containing all the data from the multiple JSON objects in the page
        o = {}
        for m in matches:
            m = json.loads(Unescape(m))

            if ('widgets' in m) and ('Storefront' in m['widgets']):
                m = m['widgets']['Storefront']
            elif 'props' in m:
                m = m['props']

                if s.refineJSON:
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
            if s.refineJSON:
                Prune(m)
            Merge(o, m)
        return o if o else None

    j = do(url, postData)
    LogJSON(j, url)
    return j


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
        self._s = Settings()
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
        self.password.setType(0 if self._s.show_pass else 6, '')
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
        self.head = msg.find('title').get_text(strip=True)
        img = msg.find('img', attrs={'alt': 'captcha'})
        box = img.find_parent('div', class_='a-box-inner a-padding-extra-large') if img else None
        if box is None:
            self.hint = msg.find('p', class_='a-last').get_text(strip=True)
            form = msg.find('form').find('div', class_='a-box-inner')
            self.task = form.h4.get_text(strip=True)
            self.img_url = pyxbmct.Image(form.find('img')['src'], aspectRatio=2)
        else:
            self.hint = '\n'.join([box.find('span', class_=cl).get_text() for cl in ['a-size-large', 'a-size-base a-color-secondary']
                                   if box.find('span', class_=cl)])
            self.task = box.find('label', class_='a-form-label').get_text(strip=True)
            self.img_url = pyxbmct.Image(img['src'], aspectRatio=2)

        super(_Challenge, self).__init__(self.head)
        self.setGeometry(500, 450, 8, 2)
        self.cap = ''
        self.tb_hint = pyxbmct.TextBox()
        self.fl_task = pyxbmct.FadeLabel(_alignment=pyxbmct.ALIGN_CENTER)
        self.ed_cap = pyxbmct.Edit('', _alignment=pyxbmct.ALIGN_LEFT | pyxbmct.ALIGN_CENTER_Y)
        self.btn_submit = pyxbmct.Button('OK')
        self.btn_cancel = pyxbmct.Button(getString(30123))
        self.set_controls()
        self.set_navigation()

    def set_controls(self):
        self.placeControl(self.tb_hint, 0, 0, 2, 2)
        self.placeControl(self.img_url, 2, 0, 3, 2)
        self.placeControl(self.fl_task, 5, 0, 1, 2)
        self.placeControl(self.ed_cap, 6, 0, 1, 2)
        self.placeControl(self.btn_submit, 7, 0)
        self.placeControl(self.btn_cancel, 7, 1)
        self.connect(self.btn_cancel, self.close)
        self.connect(self.btn_submit, self.submit)
        self.connect(pyxbmct.ACTION_NAV_BACK, self.close)
        self.tb_hint.setText(self.hint)
        self.fl_task.addLabel(self.task)
        self.setFocus(self.ed_cap)

    def set_navigation(self):
        self.ed_cap.controlUp(self.btn_submit)
        self.ed_cap.controlDown(self.btn_submit)
        self.btn_submit.controlUp(self.ed_cap)
        self.btn_submit.controlDown(self.ed_cap)
        self.btn_cancel.controlUp(self.ed_cap)
        self.btn_cancel.controlDown(self.ed_cap)
        self.btn_submit.controlRight(self.btn_cancel)
        self.btn_submit.controlLeft(self.btn_cancel)
        self.btn_cancel.controlRight(self.btn_submit)
        self.btn_cancel.controlLeft(self.btn_submit)

    def submit(self):
        self.cap = self.ed_cap.getText()
        self.close()


class _ProgressDialog(pyxbmct.AddonDialogWindow):
    def __init__(self, msg):
        super(_ProgressDialog, self).__init__('Amazon')
        self.sl_progress = pyxbmct.Slider(textureback=OSPJoin(g.PLUGIN_PATH, 'resources', 'art', 'transp.png'))
        self.btn_cancel = pyxbmct.Button(getString(30123))
        self.tb_msg = pyxbmct.TextBox()
        self.iscanceled = False
        self.connect(self.btn_cancel, self.cancel)
        self.setGeometry(500, 400, 6, 3)
        self.placeControl(self.tb_msg, 0, 0, 4, 3)
        self.placeControl(self.sl_progress, 4, 0, 0, 3)
        self.placeControl(self.btn_cancel, 5, 1, 1, 1)
        self.tb_msg.setText(msg)
        self.sl_progress.setEnabled(False)

    def cancel(self):
        self.iscanceled = True
