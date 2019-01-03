#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from BeautifulSoup import BeautifulSoup
from pyDes import *
from platform import node
from random import randint
from base64 import b64encode, b64decode
import uuid
import mechanize
import sys
import urllib
import re
import os
import xbmcplugin
import xbmcgui
import xbmcaddon
import xbmc
import urlparse
import hmac
import hashlib
import json
import xbmcvfs
import pyxbmct
import socket
import time
import requests
import pickle
import warnings


class variables:
    def __init__(self):
        self.addon = xbmcaddon.Addon()
        self.multiuser = self.addon.getSetting('multiuser') == 'true'
        self.verifySsl = self.addon.getSetting('ssl_verif') == 'false'
        self.playMethod = int(self.addon.getSetting('playmethod'))
        self.onlyGer = self.addon.getSetting('content_filter') == 'true'
        self.hasExtRC = xbmc.getCondVisibility('System.HasAddon(script.chromium_remotecontrol)')
        self.useIntRC = self.addon.getSetting("remotectrl") == 'true'
        self.browser = int(self.addon.getSetting("browser"))
        self.RMC_vol = self.addon.getSetting("remote_vol") == 'true'
        self.verbLog = self.addon.getSetting('logging') == 'true'
        self.usesqlite = self.addon.getSetting('dbsystem') == '0'
        self.showfanart = self.addon.getSetting("useshowfanart") == 'true'
        self.tvdb_art = self.addon.getSetting("tvdb_art")
        self.tmdb_art = self.addon.getSetting("tmdb_art")

        self.sessions = {}

        try:
            self.pluginhandle = int(sys.argv[1])
            params = re.sub('<|>', '', sys.argv[2])
        except IndexError:
            self.pluginhandle = -1
            params = ''

        self.args = dict(urlparse.parse_qsl(urlparse.urlparse(params).query))


var = variables()
KodiK = int(xbmc.getInfoLabel('System.BuildVersion').split('.')[0]) < 18
pluginname = var.addon.getAddonInfo('name')
pluginpath = var.addon.getAddonInfo('path').decode('utf-8')
pldatapath = xbmc.translatePath(var.addon.getAddonInfo('profile')).decode('utf-8')
configpath = os.path.join(pldatapath, 'config')
homepath = xbmc.translatePath('special://home').decode('utf-8')
CookieFile = os.path.join(pldatapath, 'cookies.lwp')
def_fanart = os.path.join(pluginpath, 'fanart.jpg')
BaseUrl = 'https://www.amazon.de'
ATV_URL = 'https://atv-ps-eu.amazon.de'
movielib = '/gp/video/%s/movie/'
tvlib = '/gp/video/%s/tv/'
lib = 'video-library'
wl = 'watchlist'
is_addon = 'inputstream.adaptive'
tmdb = b64decode('YjM0NDkwYzA1NmYwZGQ5ZTNlYzlhZjIxNjdhNzMxZjQ=')
tvdb = b64decode('MUQ2MkYyRjkwMDMwQzQ0NA==')
na = 'not available'
Dialog = xbmcgui.Dialog()
regex_ovf = "((?i)(\[|\()(omu|ov).*(\)|\]))|\sOmU"
Ages = [('FSK 0', 'FSK 0'), ('FSK 6', 'FSK 6'), ('FSK 12', 'FSK 12'), ('FSK 16', 'FSK 16'), ('FSK 18', 'FSK 18')]

socket.setdefaulttimeout(30)
warnings.simplefilter('error', requests.packages.urllib3.exceptions.SNIMissingWarning)
warnings.simplefilter('error', requests.packages.urllib3.exceptions.InsecurePlatformWarning)


class AgeSettings(pyxbmct.AddonDialogWindow):

    def __init__(self, title=''):
        super(AgeSettings, self).__init__(title)
        self.age_list = [age[0] for age in Ages]
        self.pin_req = PinReq
        self.pin = pyxbmct.Edit('', _alignment=pyxbmct.ALIGN_CENTER)
        self.btn_ages = pyxbmct.Button(self.age_list[self.pin_req])
        self.btn_save = pyxbmct.Button(getString(30222))
        self.btn_close = pyxbmct.Button(getString(30223))
        self.setGeometry(500, 300, 5, 2)
        self.set_controls()
        self.set_navigation()

    def set_controls(self):
        self.placeControl(pyxbmct.Label(getString(30220), alignment=pyxbmct.ALIGN_CENTER_Y), 1, 0)
        self.placeControl(self.pin, 1, 1)
        self.placeControl(pyxbmct.Label(getString(30221), alignment=pyxbmct.ALIGN_CENTER_Y), 2, 0)
        self.placeControl(self.btn_ages, 2, 1)
        self.placeControl(self.btn_save, 4, 0)
        self.placeControl(self.btn_close, 4, 1)
        self.connect(self.btn_close, self.close)
        self.connect(self.btn_ages, self.select_age)
        self.connect(self.btn_save, self.save_settings)
        self.connect(pyxbmct.ACTION_NAV_BACK, self.close)
        self.pin.setText(AgePin)

    def set_navigation(self):
        self.pin.controlUp(self.btn_save)
        self.pin.controlDown(self.btn_ages)
        self.btn_save.setNavigation(self.btn_ages, self.pin, self.btn_close, self.btn_close)
        self.btn_close.setNavigation(self.btn_ages, self.pin, self.btn_save, self.btn_save)
        self.btn_ages.setNavigation(self.pin, self.btn_save, self.btn_save, self.btn_close)
        self.setFocus(self.pin)

    def save_settings(self):
        writeConfig('age_pin', self.pin.getText().strip())
        writeConfig('pin_req', str(self.pin_req))
        self.close()

    def select_age(self):
        sel = Dialog.select(getString(30121), self.age_list)
        if sel > -1:
            self.pin_req = sel
            self.btn_ages.setLabel(self.age_list[self.pin_req])


class _Captcha(pyxbmct.AddonDialogWindow):
    def __init__(self, title='', soup=None, email=None):
        super(Captcha, self).__init__(title)
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
        self.btn_submit = pyxbmct.Button(getString(30004).split('.')[0])
        self.btn_cancel = pyxbmct.Button(getString(30223))
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


def getURL(url, useCookie=False, silent=False, headers=None, rjson=True, attempt=1, check=False, postdata=None):
    # Try to extract the host from the URL
    host = re.search('://([^/]+)/', url)
    method = 'POST' if postdata is not None else 'GET'

    # Create sessions for keep-alives and connection pooling
    if None is not host:
        host = host.group(1)
        if host in var.sessions:
            session = var.sessions[host]
        else:
            session = requests.Session()
            var.sessions[host] = session
    else:
        session = requests.Session()

    cj = requests.cookies.RequestsCookieJar()
    retval = [] if rjson else ''
    if useCookie:
        cj = MechanizeLogin() if isinstance(useCookie, bool) else useCookie
        if isinstance(cj, bool):
            return retval
    if (not silent) or var.verbLog:
        dispurl = url
        dispurl = re.sub('(?i)%s|%s|&token=\w+|&customerId=\w+' % (tvdb, tmdb), '', url).strip()
        Log('%sURL: %s' % ('check' if check else method.lower(), dispurl))

    headers = {} if not headers else headers
    if 'User-Agent' not in headers:
        headers['User-Agent'] = getConfig('UserAgent')
    if 'Host' not in headers:
        headers['Host'] = host
    if 'Accept-Language' not in headers:
        headers['Accept-Language'] = 'de-de, en-gb;q=0.2, en;q=0.1'

    try:
        r = session.request(method, url, data=postdata, headers=headers, cookies=cj, verify=var.verifySsl)
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
        Log('Error reason: %s (%s)' % (e, eType), xbmc.LOGERROR)
        if 'SNIMissingWarning' in eType:
            Log('Using a Python/OpenSSL version which doesn\'t support SNI for TLS connections.', xbmc.LOGERROR)
            Dialog.ok('No SNI for TLS', 'Your current Python/OpenSSL environment does not support SNI over TLS connections.',
                      'You can find a Linux guide on how to update Python and its modules for Kodi here: https://goo.gl/CKtygz',
                      'Additionally, follow this guide to update the required modules: https://goo.gl/ksbbU2')
            exit()
        if 'InsecurePlatformWarning' in eType:
            Log('Using an outdated SSL module.', xbmc.LOGERROR)
            Dialog.ok('SSL module outdated', 'The SSL module for Python is outdated.',
                      'You can find a Linux guide on how to update Python and its modules for Kodi here: https://goo.gl/CKtygz',
                      'Additionally, follow this guide to update the required modules: https://goo.gl/ksbbU2')
            exit()
        if ('429' in e) or ('Timeout' in eType):
            attempt += 1 if not check else 10
            logout = 'Attempt #%s' % attempt
            if '429' in e:
                logout += '. Too many requests - Pause 10 sec'
                sleep(10)
            Log(logout)
            if attempt < 4:
                return getURL(url, useCookie, silent, headers, rjson, attempt, check, postdata)
        return retval
    return json.loads(response) if rjson else response


def WriteLog(data, fn=''):
    if not var.verbLog:
        return
    if fn:
        fn = '-' + fn
    fn = pluginname + fn + '.log'
    path = os.path.join(homepath, fn)
    if isinstance(data, unicode):
        data = data.encode('utf-8')
    logfile = xbmcvfs.File(path, 'w')
    logfile.write(data.__str__())
    logfile.close()


def Log(msg, level=xbmc.LOGNOTICE):
    if level == xbmc.LOGDEBUG and var.verbLog:
        level = xbmc.LOGNOTICE
    msg = '[%s] %s' % (pluginname, msg)
    xbmc.log(msg.encode('utf-8'), level)


def SaveFile(filename, data, dirname=None):
    if isinstance(data, unicode):
        data = data.encode('utf-8')
    if dirname:
        filename = cleanName(filename)
        filename = os.path.join(dirname, filename)
        if not xbmcvfs.exists(dirname):
            xbmcvfs.mkdirs(cleanName(dirname.strip(), isfile=False))
    filename = cleanName(filename, isfile=False)
    f = xbmcvfs.File(filename, 'w')
    f.write(data)
    f.close()


def addDir(name, mode, sitemode, url='', thumb='', fanart='', infoLabels=None, totalItems=0, cm=None, page=1, options=''):
    u = {'url': url.encode('utf-8'), 'mode': mode, 'sitemode': sitemode, 'name': name.encode('utf-8'), 'page': page, 'opt': options}
    url = '%s?%s' % (sys.argv[0], urllib.urlencode(u))

    if not fanart or fanart == na:
        fanart = def_fanart
    if not thumb:
        thumb = def_fanart

    item = xbmcgui.ListItem(name, thumbnailImage=thumb)
    item.setProperty('fanart_image', fanart)
    item.setProperty('IsPlayable', 'false')
    item.setArt({'Poster': thumb})

    if infoLabels:
        item.setInfo(type='Video', infoLabels=getInfolabels(infoLabels))
        if 'TotalSeasons' in infoLabels.keys():
            item.setProperty('TotalSeasons', str(infoLabels['TotalSeasons']))
    if cm:
        item.addContextMenuItems(cm)

    xbmcplugin.addDirectoryItem(var.pluginhandle, url=url, listitem=item, isFolder=sitemode not in ('switchUser', 'updateAll'), totalItems=totalItems)


def addVideo(name, asin, poster=None, fanart=None, infoLabels=None, totalItems=0, cm=None, trailer=False,
             isAdult=False, isHD=False):
    u = {'asin': asin, 'mode': 'play', 'name': name.encode('utf-8'), 'sitemode': 'PLAYVIDEO', 'adult': isAdult}
    url = '%s?%s' % (sys.argv[0], urllib.urlencode(u))

    if not infoLabels:
        infoLabels = {'Title': name}
    if not fanart or fanart == na:
        fanart = def_fanart

    item = xbmcgui.ListItem(name, thumbnailImage=poster)
    item.setProperty('fanart_image', fanart)
    item.setProperty('IsPlayable', str(var.playMethod == 3).lower())
    cm.insert(0, (getString(30101), 'Action(ToggleWatched)'))

    item.addStreamInfo('video', {'width': 1920, 'height': 1080} if isHD else {'width': 720, 'height': 480})

    if infoLabels['AudioChannels']:
        item.addStreamInfo('audio', {'codec': 'ac3', 'channels': int(infoLabels['AudioChannels'])})

    if trailer:
        infoLabels['Trailer'] = url + '&trailer=1'
    url += '&trailer=0'

    if 'Poster' in infoLabels.keys():
        item.setArt({'tvshow.poster': infoLabels['Poster']})
    else:
        item.setArt({'Poster': poster})

    cm = cm if cm else []
    cm.insert(1, (getString(30118), 'RunPlugin(%s)' % (url + '&forcefb=1')))
    item.addContextMenuItems(cm)
    item.setInfo(type='Video', infoLabels=getInfolabels(infoLabels))
    xbmcplugin.addDirectoryItem(var.pluginhandle, url=url, listitem=item, isFolder=False, totalItems=totalItems)


def addText(name):
    item = xbmcgui.ListItem(name)
    item.setProperty('IsPlayable', 'false')
    xbmcplugin.addDirectoryItem(var.pluginhandle, url=sys.argv[0], listitem=item)


def toogleWatchlist(asin=None, action='add'):
    if not asin:
        asin = var.args.get('asin')
        action = 'remove' if var.args.get('remove') == '1' else 'add'

    cookie = MechanizeLogin()
    if not cookie:
        return

    par = getParams(asin, cookie)
    data = getURL(par['data-%s-url' % action],
                  postdata={'ASIN': asin,
                            'dataType': 'json',
                            'csrfToken': par['data-csrf-token'],
                            'action': action,
                            'pageType': par['data-page-type'],
                            'subPageType': par['data-sub-page-type']},
                  useCookie=cookie, headers={'x-requested-with': 'XMLHttpRequest'})

    if data['success'] == 1:
        Log(asin + ' ' + data['status'])
        if data['AsinStatus'] == 0:
            xbmc.executebuiltin('Container.Refresh')
    else:
        Log(data['status'] + ': ' + data['reason'])


def getParams(asin, cookie):
    url = BaseUrl + '/gp/video/hover/%s?format=json&refTag=dv-hover&requesterPageType=Detail' % asin
    data = getURL(url, useCookie=cookie, rjson=False)
    if data:
        data = re.compile('(<form.*</form>)').findall(data)[0]
        form = BeautifulSoup(data.replace('\\\"', '"'), convertEntities=BeautifulSoup.HTML_ENTITIES)
        return form.button
    return ''


def gen_id(renew=False):
    guid = getConfig("GenDeviceID") if not renew else False
    if not guid or len(guid) != 56:
        guid = hmac.new(getConfig('UserAgent'), uuid.uuid4().bytes, hashlib.sha224).hexdigest()
        writeConfig("GenDeviceID", guid)
    return guid


def MechanizeLogin():
    ask = var.args.get('ask') == 'true'
    if not ask:
        cj = requests.cookies.RequestsCookieJar()
        user = loadUser()
        if user['cookie']:
            cj.update(pickle.loads(user['cookie']))
            return cj

    Log('Login')
    res = False
    if not getConfig('login'):
        writeConfig('login', 'true')
        res = LogIn(ask)
        writeConfig('login')
    return res


def LogIn(ask):
    user = loadUser()
    email = user['email']
    password = decode(user['password'])
    savelogin = var.addon.getSetting('save_login') == 'true'
    useMFA = False
    if ask and var.multiuser:
        email = ''

    if ask:
        keyboard = xbmc.Keyboard(email, getString(30002))
        keyboard.doModal()
        if keyboard.isConfirmed() and keyboard.getText():
            email = keyboard.getText()
            password = setLoginPW()
    else:
        if not email or not password:
            Dialog.notification(getString(30200), getString(30216))
            xbmc.executebuiltin('Addon.OpenSettings(%s)' % var.addon.getAddonInfo('id'))
            return False

    if password:
        cj = requests.cookies.RequestsCookieJar()
        br = mechanize.Browser()
        br.set_handle_robots(False)
        br.set_cookiejar(cj)
        br.set_handle_gzip(True)
        caperr = -5
        while caperr:
            Log('Connect to SignIn Page %s attempts left' % -caperr)
            br.addheaders = [('User-Agent', getConfig('UserAgent'))]
            br.open(BaseUrl + '/gp/aw/si.html')
            response = br.response().read()
            if 'signIn' not in [i.name for i in br.forms()]:
                getUA(True)
                caperr += 1
                WriteLog(response, 'login-si')
                xbmc.sleep(randint(750, 1500))
            else:
                break
        else:
            Dialog.ok(getString(30200), getString(30213))
            return False

        br.select_form(name='signIn')
        br['email'] = email
        br['password'] = password
        br.addheaders = [('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'),
                         ('Accept-Encoding', 'gzip, deflate'),
                         ('Accept-Language', 'de,en-US;q=0.8,en;q=0.6'),
                         ('Cache-Control', 'max-age=0'),
                         ('Connection', 'keep-alive'),
                         ('Content-Type', 'application/x-www-form-urlencoded'),
                         ('Host', BaseUrl.split('//')[1]),
                         ('Origin', BaseUrl),
                         ('User-Agent', getConfig('UserAgent')),
                         ('Upgrade-Insecure-Requests', '1')]
        br.submit()
        response, soup = parseHTML(br)
        WriteLog(response, 'login')

        while any(s in response for s in ['auth-mfa-form', 'ap_dcq_form', 'ap_captcha_img_label', 'claimspicker', 'fwcim-form', 'auth-captcha-image-container']):
            br = MFACheck(br, email, soup)
            if not br:
                return False
            useMFA = 'otpCode' in str(list(br.forms())[0])
            br.submit()
            response, soup = parseHTML(br)
            WriteLog(response, 'login-mfa')

        if 'action=sign-out' in response:
            try:
                usr = re.search(r'config.customerName[^"]*"([^"]*)', response).group(1)
            except AttributeError:
                usr = getString(30209)

            if not ask:
                usr = user['name']

            if var.multiuser and ask:
                usr = Dialog.input(getString(30179), usr).decode('utf-8')
                if not usr:
                    return False
            if useMFA:
                var.addon.setSetting('save_login', 'false')
                savelogin = False

            user = loadUser(True)
            user['name'] = usr

            if savelogin:
                user['email'] = email
                user['password'] = encode(password)
            else:
                user['cookie'] = pickle.dumps(cj)

            if ask:
                remLoginData(False)
                var.addon.setSetting('login_acc', usr)
                if not var.multiuser:
                    Dialog.ok(getString(30215), '{0} {1}'.format(getString(30014), usr))

            addUser(user)
            gen_id()
            return cj
        elif 'message_error' in response:
            writeConfig('login_pass', '')
            msg = soup.find('div', attrs={'id': 'message_error'})
            Log('Login Error: %s' % msg.p.renderContents(None).strip())
            Dialog.ok(getString(30200), getString(30201))
        elif 'message_warning' in response:
            msg = soup.find('div', attrs={'id': 'message_warning'})
            Log('Login Warning: %s' % msg.p.renderContents(None).strip())
        elif 'auth-error-message-box' in response:
            msg = soup.find('div', attrs={'class': 'a-alert-content'})
            Log('Login MFA: %s' % msg.ul.li.span.renderContents(None).strip())
            Dialog.ok(getString(30200), getString(30214))
        else:
            Dialog.ok(getString(30200), getString(30213))

    return False


def loadUsers():
    users = json.loads(getConfig('accounts.lst', '[]'))
    if not users:
        var.addon.setSetting('login_acc', '')
    return users


def loadUser(empty=False):
    cur_user = var.addon.getSetting('login_acc').decode('utf-8')
    users = loadUsers()
    user = None if empty else [i for i in users if cur_user == i['name']]
    return user[0] if user else {'email': '', 'password': '', 'name': '', 'save': '', 'cookie': ''}


def addUser(user):
    user['save'] = var.addon.getSetting('save_login')
    users = loadUsers() if var.multiuser else []
    num = [n for n, i in enumerate(users) if user['name'] == i['name']]
    if num:
        users[num[0]] = user
    else:
        users.append(user)
    writeConfig('accounts.lst', json.dumps(users))
    if xbmc.getInfoLabel('Container.FolderPath') == sys.argv[0]:
        xbmc.executebuiltin('Container.Refresh')


def switchUser():
    users, sel = selectUser()
    if sel > -1:
        if loadUser()['name'] == users[sel]['name']:
            return False
        user = users[sel]
        var.addon.setSetting('save_login', user['save'])
        var.addon.setSetting('login_acc', user['name'])
        if xbmc.getInfoLabel('Container.FolderPath') == sys.argv[0]:
            xbmc.executebuiltin('RunPlugin(%s)' % sys.argv[0])
            xbmc.executebuiltin('Container.Refresh')
    return -1 < sel


def removeUser():
    cur_user = loadUser()['name']
    users, sel = selectUser()
    if sel > -1:
        user = users[sel]
        users.remove(user)
        writeConfig('accounts.lst', json.dumps(users))
        if user['name'] == cur_user:
            var.addon.setSetting('login_acc', '')
            if not switchUser():
                xbmc.executebuiltin('Container.Refresh')


def renameUser():
    cur_user = loadUser()['name']
    users, sel = selectUser()
    if sel > -1:
        keyboard = xbmc.Keyboard(users[sel]['name'], getString(30135))
        keyboard.doModal()
        if keyboard.isConfirmed() and keyboard.getText():
            usr = keyboard.getText()
            if users[sel]['name'] == cur_user:
                var.addon.setSetting('login_acc', usr)
                xbmc.executebuiltin('Container.Refresh')
            users[sel]['name'] = usr
            writeConfig('accounts.lst', json.dumps(users))


def selectUser():
    users = loadUsers()
    sel = Dialog.select(getString(30177), [i['name'] for i in users])
    return users, sel


def MFACheck(br, email, soup):
    Log('MFA, DCQ or Captcha form')
    uni_soup = soup.__unicode__()
    if 'signIn' in [i.name for i in br.forms()]:
        br.select_form(name='signIn')
    else:
        br.select_form(nr=0)

    if 'auth-mfa-form' in uni_soup:
        msg = soup.find('form', attrs={'id': 'auth-mfa-form'})
        msgtxt = msg.p.renderContents().strip()
        kb = xbmc.Keyboard('', msgtxt)
        kb.doModal()
        if kb.isConfirmed() and kb.getText():
            br['otpCode'] = kb.getText()
        else:
            return False
    elif 'ap_dcq_form' in uni_soup:
        msg = soup.find('div', attrs={'id': 'message_warning'})
        Dialog.ok(pluginname, msg.p.contents[0].strip())
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

        sel = Dialog.select(insertLF(dcq_title, 60), q_title) if len(q_title) > 1 else 0
        if sel < 0:
            return False

        ret = Dialog.input(q_title[sel])
        if ret:
            br[q_id[sel]] = ret
        else:
            return False
    elif ('ap_captcha_img_label' in uni_soup) or ('auth-captcha-image-container' in uni_soup):
        wnd = Captcha((getString(30008).split('.')[0]), soup, email)
        wnd.doModal()
        if wnd.email and wnd.cap and wnd.pwd:
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
            sel = Dialog.select('%s - %s' % (cs_title, cs_quest.contents[0].strip()), [k[0] for k in choices])
        else:
            sel = 100 if Dialog.ok(cs_title, cs_hint) else -1

        if sel > -1:
            if sel < 100:
                br[choices[sel][1]] = [choices[sel][2]]
        else:
            return False
    elif 'fwcim-form' in uni_soup:
        msg = soup.find('div', attrs={'class': 'a-row a-spacing-micro cvf-widget-input-code-label'}).contents[0].strip()
        ret = Dialog.input(msg)
        if ret:
            br['code'] = ret
        else:
            return False
    return br


def setLoginPW():
    keyboard = xbmc.Keyboard('', getString(30003))
    keyboard.doModal()
    if keyboard.isConfirmed() and keyboard.getText():
        password = keyboard.getText()
        return password
    return False


def encode(data):
    k = triple_des(getmac(), CBC, b"\0\0\0\0\0\0\0\0", padmode=PAD_PKCS5)
    d = k.encrypt(data)
    return b64encode(d)


def decode(data):
    if not data:
        return ''
    k = triple_des(getmac(), CBC, b"\0\0\0\0\0\0\0\0", padmode=PAD_PKCS5)
    d = k.decrypt(b64decode(data))
    return d


def getmac():
    mac = uuid.getnode()
    if (mac >> 40) % 2:
        mac = node()
    return uuid.uuid5(uuid.NAMESPACE_DNS, str(mac)).bytes


def cleanData(data):
    if isinstance(data, str):
        data = data.decode('utf-8')
    elif not isinstance(data, unicode):
        return data

    data = data.replace('\u00A0', ' ').replace('\u2013', '-').strip()
    return None if data == '' else data


def cleanName(name, isfile=True):
    notallowed = ['<', '>', ':', '"', '\\', '/', '|', '*', '?']
    if not isfile:
        notallowed = ['<', '>', '"', '|', '*', '?']
    for c in notallowed:
        name = name.replace(c, '')
    if not os.path.supports_unicode_filenames and not isfile:
        name = name.encode('utf-8')
    return name


def GET_ASINS(content):
    hd_key = False
    prime_key = False
    channels = 1
    asins = content.get('titleId', '')
    for movformat in content['formats']:
        for offer in movformat['offers']:
            if movformat['videoFormatType'] == 'HD' and movformat['hasEncode']:
                hd_key = True
            if offer['offerType'] == 'SUBSCRIPTION':
                prime_key = True
            elif 'asin' in offer.keys():
                newasin = offer['asin']
                if newasin not in asins:
                    asins += ',' + newasin
        if 'STEREO' in movformat['audioFormatTypes']:
            channels = 2
        if 'AC_3_5_1' in movformat['audioFormatTypes']:
            channels = 6

    del content
    return asins, hd_key, prime_key, channels


def SCRAP_ASINS(aurl, cj=True):
    asins = []
    wl_order = ['DATE_ADDED_DESC', 'TITLE_DESC', 'TITLE_ASC'][int('0' + var.addon.getSetting("wl_order"))]
    url = BaseUrl + aurl + '?ie=UTF8&sort=' + wl_order
    content = getURL(url, useCookie=cj, rjson=False)
    WriteLog(content, 'watchlist')
    if content:
        if mobileUA(content):
            getUA(True)
        for asin in re.compile('(?:data-asin|data-asinlist)="(.+?)"', re.DOTALL).findall(content):
            if asin not in asins:
                asins.append(asin)
    return asins


def getString(string_id):
    src = xbmc if string_id < 30000 else var.addon
    locString = src.getLocalizedString(string_id)
    return locString


def remLoginData(info=True):
    xbmcvfs.delete(CookieFile)
    writeConfig('accounts', '')
    writeConfig('login_name', '')
    writeConfig('login_pass', '')

    if info:
        var.addon.setSetting('login_acc', '')
        writeConfig('accounts.lst', '')
        Dialog.notification(pluginname, getString(30211), xbmcgui.NOTIFICATION_INFO)


def checkCase(title):
    if title.isupper():
        title = title.title().replace('[Ov]', '[OV]').replace('Bc', 'BC')
    title = title.replace('[dt./OV]', '')
    return title


def getCategories():
    data = getURL(ATV_URL + '/cdp/catalog/GetCategoryList?firmware=fmw:15-app:1.1.23&deviceTypeID=A1MPSLFC7L5AFK'
                  '&deviceID=%s&format=json&OfferGroups=B0043YVHMY&IncludeAll=T&version=2' % gen_id())
    asins = {}
    for maincat in data['message']['body']['categories']:
        mainCatId = maincat.get('id')
        if mainCatId == 'movies' or mainCatId == 'tv_shows':
            asins.update({mainCatId: {}})
            for cattype in maincat['categories'][0]['categories']:
                subPageType = cattype.get('subPageType')
                subCatId = cattype.get('id')
                if subPageType == 'PrimeMovieRecentlyAdded' or subPageType == 'PrimeTVRecentlyAdded':
                    asins[mainCatId].update({subPageType: urlparse.parse_qs(cattype['query'])['ASINList'][0].split(',')})
                elif 'prime_editors_picks' in subCatId:
                    for picks in cattype['categories']:
                        query = picks.get('query').upper()
                        title = picks.get('title')
                        if title and ('ASINLIST' in query):
                            querylist = urlparse.parse_qs(query)
                            alkey = None
                            for key in querylist.keys():
                                if 'ASINLIST' in key:
                                    alkey = key
                            asins[mainCatId].update({title: urlparse.parse_qs(query)[alkey][0]})
    return asins


def SetView(content, view=None, updateListing=False):
    views = [50, 51, 52, 53, 54, 55, 500, 501, 502, -1]
    xbmcplugin.setContent(var.pluginhandle, content)
    viewenable = var.addon.getSetting("viewenable")

    if viewenable == 'true' and view:
        viewid = views[int(var.addon.getSetting(view))]
        if viewid == -1:
            viewid = int(var.addon.getSetting(view.replace('view', 'id')))
        xbmc.executebuiltin('Container.SetViewMode(%s)' % viewid)
    xbmcplugin.endOfDirectory(var.pluginhandle, updateListing=updateListing)


def compasin(asinlist, searchstring, season=False):
    ret = False
    for index, array in enumerate(asinlist):
        season = False if len(array) < 3 else season
        for asin in searchstring.lower().split(','):
            if (not season and asin and asin in array[0].lower()) or \
               (season and asin and asin in array[0].lower() and season == array[1]):
                asinlist[index][-1] = 1
                ret = True
    return ret, asinlist


def getcompresult(asinlist, returnval=0):
    removeAsins = []
    for item in asinlist:
        if item[-1] == returnval:
            removeAsins.append(item[0])
    return removeAsins


def getTypes(items, col):
    studiolist = []
    lowlist = []
    for data in items:
        data = data[0]
        if isinstance(data, unicode):
            if 'Rated' in data:
                item = data.split('for')[0]
                if item not in studiolist and item != '' and item != 0 and item != 'Inc.' and item != 'LLC.':
                    studiolist.append(item)
            else:
                if 'genres' in col:
                    data = data.split('/')
                else:
                    data = re.split(r'[,;/]', data)
                for item in data:
                    item = item.strip()
                    if item.lower() not in lowlist and item != '' and item != 0 and item != 'Inc.' and item != 'LLC.':
                        studiolist.append(item)
                        lowlist.append(item.lower())
        elif 1800 < data < 2200:
            unidata = unicode(data)[0:-1] + '0 -'
            if unidata not in studiolist:
                studiolist.append(unidata)
    return studiolist


def openSettings():
    aid = var.args.get('url')
    aid = is_addon if aid == 'is' else aid
    xbmcaddon.Addon(aid).openSettings()


def RequestPin():
    if AgePin:
        pin = Dialog.input('PIN', type=xbmcgui.INPUT_ALPHANUM, option=xbmcgui.ALPHANUM_HIDE_INPUT)
        return True if pin == AgePin else False
    return True


def ageSettings():
    if RequestPin():
        window = AgeSettings(getString(30063).split('.')[0])
        window.doModal()
        del window


def getConfig(cfile, defvalue=''):
    cfgfile = os.path.join(configpath, cfile)

    value = ''
    if xbmcvfs.exists(cfgfile):
        f = xbmcvfs.File(cfgfile, 'r')
        value = f.read()
        f.close()

    return value if value else defvalue


def writeConfig(cfile, value=''):
    cfgfile = os.path.join(configpath, cfile)
    cfglockfile = os.path.join(configpath, cfile + '.lock')

    if not xbmcvfs.exists(configpath):
        xbmcvfs.mkdirs(configpath)

    while True:
        if not xbmcvfs.exists(cfglockfile):
            l = xbmcvfs.File(cfglockfile, 'w')
            l.write(str(time.time()))
            l.close()
            if value == '':
                xbmcvfs.delete(cfgfile)
            else:
                f = xbmcvfs.File(cfgfile, 'w')
                f.write(value.__str__())
                f.close()
            xbmcvfs.delete(cfglockfile)
            xbmcvfs.delete(cfglockfile)
            return True
        else:
            l = xbmcvfs.File(cfglockfile)
            modified = float(l.read())
            l.close()
            if time.time() - modified > 0.1:
                xbmcvfs.delete(cfglockfile)


def Notif(message):
    if not xbmc.Player().isPlaying():
        Dialog.notification(pluginname, message, sound=False)


def insertLF(string, begin=70):
    spc = string.find(' ', begin)
    return string[:spc] + '\n' + string[spc + 1:] if spc > 0 else string


def parseHTML(br):
    response = br.response().read().decode('utf-8')
    response = re.sub(r'(?i)(<!doctype \w+).*>', r'\1>', response)
    soup = BeautifulSoup(response, convertEntities=BeautifulSoup.HTML_ENTITIES)
    return response, soup


def AddonEnabled(addon_id):
    res = jsonRPC('Addons.GetAddonDetails', 'enabled', {'addonid': addon_id})
    return res['addon'].get('enabled', False) if 'addon' in res.keys() else False


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
        html = getURL('https://techblog.willshouse.com/2012/01/03/most-common-user-agents/', rjson=False)
        soup = BeautifulSoup(html, convertEntities=BeautifulSoup.HTML_ENTITIES)
        text = soup.find('textarea')
        if text:
            UAlist = text.string.split('\n')
            UAblist = []
            writeConfig('UABlacklist', json.dumps(UAblist))
            writeConfig('UAlist', json.dumps(UAlist[0:len(UAlist) - 1]))
            UAwlist = UAlist

    UAnew = UAwlist[randint(0, len(UAwlist) - 1)] if UAwlist else \
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/59.0.3071.115 Safari/537.36'
    writeConfig('UserAgent', UAnew)
    Log('Using UserAgent: ' + UAnew)
    return


def mobileUA(content):
    soup = BeautifulSoup(content, convertEntities=BeautifulSoup.HTML_ENTITIES)
    res = soup.find('html')
    res = res.get('class', '') if res else ''
    return True if 'a-mobile' in res or 'a-tablet' in res else False


def sleep(sec):
    if xbmc.Monitor().waitForAbort(sec):
        Log('Abort requested - exiting addon')
        sys.exit()


def getInfolabels(Infos):
    rem_keys = ('ishd', 'isprime', 'asins', 'audiochannels', 'banner', 'displaytitle', 'fanart', 'poster', 'seasonasin',
                'thumb', 'traileravailable', 'contenttype', 'isadult', 'totalseasons', 'seriesasin', 'episodename')
    if not Infos:
        return
    return {k: v for k, v in Infos.items() if k.lower() not in rem_keys}


def jsonRPC(method, props='', param=None):
    rpc = {'jsonrpc': '2.0',
           'method': method,
           'params': {},
           'id': 1}

    if props:
        rpc['params']['properties'] = props.split(',')
    if param:
        rpc['params'].update(param)
        if 'playerid' in param.keys():
            res_pid = xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Player.GetActivePlayers","id": 1}')
            pid = [i['playerid'] for i in json.loads(res_pid)['result'] if i['type'] == 'video']
            pid = pid[0] if pid else 0
            rpc['params']['playerid'] = pid

    res = json.loads(xbmc.executeJSONRPC(json.dumps(rpc)))
    if 'error' in res.keys():
        Log(res['error'])
        return res['error']

    return res['result'].get(props, res['result'])


if not getConfig('UserAgent'):
    getUA()

UserAgent = getConfig('UserAgent')
AgePin = getConfig('age_pin')
PinReq = int(getConfig('pin_req', '0'))
RestrAges = ','.join(a[1] for a in Ages[PinReq:]) if AgePin else ''

Log('Args: %s' % var.args)
