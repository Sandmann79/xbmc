#!/usr/bin/env python
# -*- coding: utf-8 -*-
import requests
import re
import pickle
import json
import pyxbmct
from BeautifulSoup import BeautifulSoup
from resources.lib.l10n import *
from resources.lib.logging import *
from resources.lib.configs import *
from resources.lib.common import Globals, sleep


def _parseHTML(br):
    response = br.response().read().decode('utf-8')
    response = re.sub(r'(?i)(<!doctype \w+).*>', r'\1>', response)
    soup = BeautifulSoup(response, convertEntities=BeautifulSoup.HTML_ENTITIES)
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
    _TypeIDs = {'All': 'firmware=fmw:17-app:2.0.45.1210&deviceTypeID=A2M4YX06LWP8WI',
                'GetCategoryList_ftv': 'firmware=fmw:17-app:2.0.45.1210&deviceTypeID=ADVBD696BHNV5'}

    g = Globals()
    if '?' in query:
        query = query.split('?')[1]
    if query:
        query = '&IncludeAll=T&AID=1&' + query.replace('HideNum=T', 'HideNum=F')
    deviceTypeID = _TypeIDs[pg_mode] if pg_mode in _TypeIDs else _TypeIDs['All']
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
    def _MFACheck(br, email, soup):
        Log('MFA, DCQ or Captcha form')
        uni_soup = unicode(soup)
        if 'auth-mfa-form' in uni_soup:
            msg = soup.find('form', attrs={'id': 'auth-mfa-form'})
            msgtxt = msg.p.renderContents().strip()
            kb = xbmc.Keyboard('', msgtxt)
            kb.doModal()
            if kb.isConfirmed() and kb.getText():
                xbmc.executebuiltin('ActivateWindow(busydialog)')
                br.select_form(nr=0)
                br['otpCode'] = kb.getText()
                # br.find_control('rememberDevice').items[0].selected = True
            else:
                return False
        elif 'ap_dcq_form' in uni_soup:
            msg = soup.find('div', attrs={'id': 'message_warning'})
            g.dialog.ok(g.__plugin__, msg.p.contents[0].strip())
            dcq = soup.find('div', attrs={'id': 'ap_dcq1a_pagelet'})
            dcq_title = dcq.find('div', attrs={'id': 'ap_dcq1a_pagelet_title'}).h1.contents[0].strip()
            q_title = []
            q_id = []
            for q in dcq.findAll('div', attrs={'class': 'dcq_question'}):
                if q.span.label:
                    label = q.span.label.renderContents().strip().replace('  ', '').replace('\n', '')
                    if q.span.label.span:
                        label = label.replace(str(q.span.label.span), q.span.label.span.text)
                    q_title.append(insertLF(label))
                    q_id.append(q.input['id'])

            sel = g.dialog.select(insertLF(dcq_title, 60), q_title) if len(q_title) > 1 else 0
            if sel < 0:
                return False

            ret = g.dialog.input(q_title[sel])
            if ret:
                xbmc.executebuiltin('ActivateWindow(busydialog)')
                br.select_form(nr=0)
                br[q_id[sel]] = ret
            else:
                return False
        elif 'ap_captcha_img_label' in uni_soup or 'auth-captcha-image-container' in uni_soup:
            wnd = _Captcha((getString(30008).split('…')[0]), soup, email)
            wnd.doModal()
            if wnd.email and wnd.cap and wnd.pwd:
                xbmc.executebuiltin('ActivateWindow(busydialog)')
                br.select_form(nr=0)
                br['email'] = wnd.email
                br['password'] = wnd.pwd
                br['guess'] = wnd.cap
            else:
                return False
            del wnd
        elif 'claimspicker' in uni_soup:
            msg = soup.find('form', attrs={'name': 'claimspicker'})
            cs_title = msg.find('div', attrs={'class': 'a-row a-spacing-small'})
            cs_title = cs_title.h1.contents[0].strip()
            cs_quest = msg.find('label', attrs={'class': 'a-form-label'})
            cs_hint = msg.find('div', attrs={'class': 'a-row'}).contents[0].strip()
            choices = []
            if cs_quest:
                for c in soup.findAll('div', attrs={'data-a-input-name': 'option'}):
                    choices.append((c.span.contents[0].strip(), c.input['name'], c.input['value']))
                sel = g.dialog.select('%s - %s' % (cs_title, cs_quest.contents[0].strip()), [k[0] for k in choices])
            else:
                sel = 100 if g.dialog.ok(cs_title, cs_hint) else -1

            if sel > -1:
                xbmc.executebuiltin('ActivateWindow(busydialog)')
                br.select_form(nr=0)
                if sel < 100:
                    br[choices[sel][1]] = [choices[sel][2]]
            else:
                return False
        elif 'fwcim-form' in uni_soup:
            msg = soup.find('div', attrs={'class': 'a-row a-spacing-micro cvf-widget-input-code-label'}).contents[0].strip()
            ret = g.dialog.input(msg)
            if ret:
                xbmc.executebuiltin('ActivateWindow(busydialog)')
                br.select_form(nr=0)
                Log(br)
                br['code'] = ret
            else:
                return False
        return br

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
        response, soup = _parseHTML(br)
        xbmc.executebuiltin('Dialog.Close(busydialog)')
        WriteLog(response, 'login')

        while any(s in response for s in ['auth-mfa-form', 'ap_dcq_form', 'ap_captcha_img_label', 'claimspicker', 'fwcim-form', 'auth-captcha-image-container']):
            br = _MFACheck(br, email, soup)
            if not br:
                return False
            useMFA = 'otpCode' in str(list(br.forms())[0])
            br.submit()
            response, soup = _parseHTML(br)
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


class _Captcha(pyxbmct.AddonDialogWindow):
    def __init__(self, title='', soup=None, email=None):
        super(_Captcha, self).__init__(title)
        if 'ap_captcha_img_label' in unicode(soup):
            head = soup.find('div', attrs={'id': 'message_warning'})
            if not head:
                head = soup.find('div', attrs={'id': 'message_error'})
            title = soup.find('div', attrs={'id': 'ap_captcha_guess_alert'})
            self.head = head.p.renderContents().strip()
            self.head = re.sub('(?i)<[^>]*>', '', self.head)
            self.picurl = soup.find('div', attrs={'id': 'ap_captcha_img'}).img.get('src')
        else:
            self.head = soup.find('span', attrs={'class': 'a-list-item'}).renderContents().strip()
            title = soup.find('div', attrs={'id': 'auth-guess-missing-alert'}).div.div
            self.picurl = soup.find('div', attrs={'id': 'auth-captcha-image-container'}).img.get('src')
            pass
        self.setGeometry(500, 550, 9, 2)
        self.email = email
        self.pwd = ''
        self.cap = ''
        self.title = title.renderContents().strip()
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