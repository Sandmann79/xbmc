#!/usr/bin/env python
# -*- coding: utf-8 -*-
import requests
import re
import pickle
import json
from resources.lib.logging import Log
from resources.lib.configs import *
from resources.lib.common import Globals, sleep


def getURL(url, useCookie=False, silent=False, headers=None, rjson=True, attempt=1, check=False, postdata=None):
    if not hasattr(getURL, 'sessions'):
        getURL.sessions = {}  # Keep-Alive sessions

    # Try to extract the host from the URL
    host = re.search('://([^/]+)/', url)

    # Create sessions for keep-alives and connection pooling
    if None is not host:
        host = host.group(1)
        if host in getURL.sessions:
            session = getURL.sessions[host]
        else:
            session = requests.Session()
            getURL.sessions[host] = session
    else:
        session = requests.Session()

    cj = requests.cookies.RequestsCookieJar()
    retval = [] if rjson else ''
    if useCookie:
        cj = MechanizeLogin() if isinstance(useCookie, bool) else useCookie
        if isinstance(cj, bool):
            return retval

    from resources.lib.common import Globals, Settings
    g = Globals()
    s = Settings()
    if (not silent) or s.verbLog:
        dispurl = url
        dispurl = re.sub('(?i)%s|%s|&token=\w+|&customerId=\w+' % (g.tvdb, g.tmdb), '', url).strip()
        Log('%sURL: %s' % ('check' if check else 'post' if postdata is not None else 'get', dispurl))

    headers = {} if not headers else headers
    if 'User-Agent' not in headers:
        headers['User-Agent'] = getConfig('UserAgent')
    if 'Host' not in headers:
        headers['Host'] = host
    if 'Accept-Language' not in headers:
        headers['Accept-Language'] = g.userAcceptLanguages

    try:
        method = 'POST' if postdata is not None else 'GET'
        r = session.request(method, url, data=postdata, headers=headers, cookies=cj, verify=s.verifySsl)
        response = r.text if not check else 'OK'
        if r.status_code >= 400:
            Log('Error %s' % r.status_code)
            raise requests.exceptions.HTTPError('429')
    except (requests.exceptions.Timeout,
            requests.exceptions.ConnectionError,
            requests.exceptions.SSLError,
            requests.exceptions.HTTPError,
            requests.packages.urllib3.exceptions.SNIMissingWarning,
            requests.packages.urllib3.exceptions.InsecurePlatformWarning), e:
        eType = e.__class__.__name__
        Log('Error reason: %s (%s)' % (e, eType), Log.ERROR)
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
        if (('429' in e) or ('Timeout' in eType)) and (3 > attempt):
            attempt += 1 if not check else 10
            logout = 'Attempt #%s' % attempt
            if '429' in e:
                logout += '. Too many requests - Pause 10 sec'
                sleep(10)
            Log(logout)
            return getURL(url, useCookie, silent, headers, rjson, attempt, check, postdata)
        return retval
    return json.loads(response) if rjson else response


def getURLData(mode, asin, retformat='json', devicetypeid='AOAGZA014O5RE', version=1, firmware='1', opt='', extra=False,
            useCookie=False, retURL=False, vMT='Feature', dRes='PlaybackUrls,SubtitleUrls,ForcedNarratives'):
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
    if extra:
        url += '&resourceUsage=ImmediateConsumption&consumptionType=Streaming&deviceDrmOverride=CENC' \
               '&deviceStreamingTechnologyOverride=DASH&deviceProtocolOverride=Https' \
               '&deviceBitrateAdaptationsOverride=CVBR%2CCBR&audioTrackId=all'
        url += '&videoMaterialType=' + vMT
        url += '&desiredResources=' + dRes
        url += '&supportedDRMKeyScheme=DUAL_KEY' if (not g.platform & g.OS_ANDROID) and ('PlaybackUrls' in dRes) else ''
    url += opt
    if retURL:
        return url
    data = getURL(url, useCookie=useCookie, postdata='')
    if data:
        if 'error' in data.keys():
            return False, Error(data['error'])
        elif 'AudioVideoUrls' in data.get('errorsByResource', ''):
            return False, Error(data['errorsByResource']['AudioVideoUrls'])
        elif 'PlaybackUrls' in data.get('errorsByResource', ''):
            return False, Error(data['errorsByResource']['PlaybackUrls'])
        else:
            return True, data
    return False, 'HTTP Error'


def getATVData(pg_mode, query='', version=2, useCookie=False, site_id=None):
    g = Globals()
    if '?' in query:
        query = query.split('?')[1]
    if query:
        query = '&IncludeAll=T&AID=1&' + query.replace('HideNum=T', 'HideNum=F')
    deviceTypeID = TypeIDs[pg_mode] if pg_mode in TypeIDs else TypeIDs['All']
    pg_mode = pg_mode.split('_')[0]
    if '/' not in pg_mode:
        pg_mode = 'catalog/' + pg_mode
    parameter = '%s&deviceID=%s&format=json&version=%s&formatVersion=3&marketplaceId=%s' % (
        deviceTypeID, deviceID, version, g.MarketID)
    if site_id:
        parameter += '&id=' + site_id
    jsondata = getURL('%s/cdp/%s?%s%s' % (g.ATVUrl, pg_mode, parameter, query), useCookie=useCookie)
    if not jsondata:
        return False

    if jsondata['message']['statusCode'] != "SUCCESS":
        Log('Error Code: ' + jsondata['message']['body']['code'], Log.ERROR)
        return None
    return jsondata['message']['body']
   

def MechanizeLogin():
    from resources.lib.users import loadUser
    cj = requests.cookies.RequestsCookieJar()
    cookie = loadUser('cookie')

    if cookie:
        cj.update(pickle.loads(cookie))
        return cj

    Log('Login')
    return LogIn(False)


def LogIn(ask=True):
    g = Globals()
    from resources.lib.users import loadUser
    user = loadUser(empty=ask)
    email = user['email']
    password = decode(user['password'])
    savelogin = g.addon.getSetting('save_login') == 'true'
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
            password = setLoginPW()
    else:
        if not email or not password:
            g.dialog.notification(getString(30200), getString(30216))
            xbmc.executebuiltin('g.addon.OpenSettings(%s)' % g.addon.getAddonInfo('id'))
            return False

    if password:
        xbmc.executebuiltin('ActivateWindow(busydialog)')
        cj = requests.cookies.RequestsCookieJar()
        br = mechanize.Browser()
        br.set_handle_robots(False)
        br.set_cookiejar(cj)
        br.set_handle_gzip(True)
        caperr = -5
        while caperr:
            Log('Connect to SignIn Page %s attempts left' % -caperr)
            br.addheaders = [('User-Agent', getConfig('UserAgent'))]
            br.open(user['baseurl'] + ('/gp/aw/si.html' if not user['pv'] else '/auth-redirect/'))
            response = br.response().read()
            if mobileUA(response) or 'signIn' not in [i.name for i in br.forms()]:
                getUA(True)
                caperr += 1
                WriteLog(response, 'login-si')
                xbmc.sleep(randint(750, 1500))
            else:
                break
        else:
            xbmc.executebuiltin('Dialog.Close(busydialog)')
            g.dialog.ok(getString(30200), getString(30213))
            return False

        br.select_form(name='signIn')
        br['email'] = email
        br['password'] = password
        if 'true' == g.addon.getSetting('rememberme') and user['pv']:
            br.find_control(name='rememberMe').items[0].selected = True
        br.addheaders = [('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'),
                         ('Accept-Encoding', 'gzip, deflate'),
                         ('Accept-Language', userAcceptLanguages),
                         ('Cache-Control', 'max-age=0'),
                         ('Connection', 'keep-alive'),
                         ('Content-Type', 'application/x-www-form-urlencoded'),
                         ('Host', user['baseurl'].split('//')[1]),
                         ('Origin', user['baseurl']),
                         ('User-Agent', getConfig('UserAgent')),
                         ('Upgrade-Insecure-Requests', '1')]
        br.submit()
        response, soup = parseHTML(br)
        xbmc.executebuiltin('Dialog.Close(busydialog)')
        WriteLog(response, 'login')

        while any(s in response for s in ['auth-mfa-form', 'ap_dcq_form', 'ap_captcha_img_label', 'claimspicker', 'fwcim-form', 'auth-captcha-image-container']):
            br = MFACheck(br, email, soup)
            if not br:
                return False
            useMFA = 'otpCode' in str(list(br.forms())[0])
            br.submit()
            response, soup = parseHTML(br)
            WriteLog(response, 'login-mfa')
            xbmc.executebuiltin('Dialog.Close(busydialog)')

        if 'action=sign-out' in response:
            regex = r'action=sign-out[^"]*"[^>]*>[^?]+\s+([^?]+?)\s*\?' if user['pv'] else r'config.customerName[^"]*"([^"]*)'
            try:
                usr = re.search(regex, response).group(1)
            except AttributeError:
                usr = getString(30209)

            if multiuser and ask:
                usr = g.dialog.input(getString(30135), usr).decode('utf-8')
                if not usr:
                    return False
            if useMFA:
                g.addon.setSetting('save_login', 'false')
                savelogin = False

            user['name'] = usr
            user['email'] = user['password'] = user['cookie'] = ''

            if savelogin:
                user['email'] = email
                user['password'] = encode(password)
            else:
                user['cookie'] = pickle.dumps(cj)

            if ask:
                remLoginData(False)
                g.addon.setSetting('login_acc', usr)
                if not multiuser:
                    g.dialog.ok(getString(30215), '{0} {1}'.format(getString(30014), usr))

            addUser(user)
            genID()
            return cj
        elif 'message_error' in response:
            writeConfig('login_pass', '')
            msg = soup.find('div', attrs={'id': 'message_error'})
            Log('Login Error: %s' % msg.p.renderContents(None).strip())
            g.dialog.ok(getString(30200), getString(30201))
        elif 'message_warning' in response:
            msg = soup.find('div', attrs={'id': 'message_warning'})
            Log('Login Warning: %s' % msg.p.renderContents(None).strip())
        elif 'auth-error-message-box' in response:
            msg = soup.find('div', attrs={'class': 'a-alert-content'})
            Log('Login MFA: %s' % msg.ul.li.span.renderContents(None).strip())
            g.dialog.ok(getString(30200), getString(30214))
        else:
            g.dialog.ok(getString(30200), getString(30213))

    return False
