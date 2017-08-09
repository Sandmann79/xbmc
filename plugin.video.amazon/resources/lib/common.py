#!/usr/bin/env python
# -*- coding: utf-8 -*-
from BeautifulSoup import BeautifulSoup
from pyDes import *
from platform import node
import uuid
import cookielib
import mechanize
import sys
import urllib
import urllib2
import re
import os
import xbmcplugin
import xbmcgui
import xbmcaddon
import xbmc
import base64
import urlparse
import hmac
import hashlib
import json
import xbmcvfs
import pyxbmct
import socket
import ssl
import time
import random

addon = xbmcaddon.Addon()
pluginname = addon.getAddonInfo('name')
pluginpath = addon.getAddonInfo('path').decode('utf-8')
pldatapath = xbmc.translatePath(addon.getAddonInfo('profile')).decode('utf-8')
configpath = os.path.join(pldatapath, 'config')
homepath = xbmc.translatePath('special://home').decode('utf-8')
dbplugin = 'script.module.amazon.database'
dbpath = os.path.join(homepath, 'addons', dbplugin, 'lib')
tmdb = base64.b64decode('YjM0NDkwYzA1NmYwZGQ5ZTNlYzlhZjIxNjdhNzMxZjQ=')
tvdb = base64.b64decode('MUQ2MkYyRjkwMDMwQzQ0NA==')
COOKIEFILE = os.path.join(pldatapath, 'cookies.lwp')
def_fanart = os.path.join(pluginpath, 'fanart.jpg')
na = 'not available'
BASE_URL = 'https://www.amazon.de'
ATV_URL = 'https://atv-eu.amazon.com'
movielib = '/gp/video/%s/movie/'
tvlib = '/gp/video/%s/tv/'
lib = 'video-library'
wl = 'watchlist'
def_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/59.0.3071.115 Safari/537.36'
Ages = [('FSK 0', 'FSK 0'), ('FSK 6', 'FSK 6'), ('FSK 12', 'FSK 12'), ('FSK 16', 'FSK 16'), ('FSK 18', 'FSK 18')]
verbLog = addon.getSetting('logging') == 'true'
playMethod = int(addon.getSetting("playmethod"))
onlyGer = addon.getSetting('content_filter') == 'true'
kodi_mjver = int(xbmc.getInfoLabel('System.BuildVersion')[0:2])
Dialog = xbmcgui.Dialog()
socket.setdefaulttimeout(30)

try:
    pluginhandle = int(sys.argv[1])
    params = re.sub('<|>', '', sys.argv[2])
except IndexError:
    pluginhandle = -1
    params = ''
args = dict(urlparse.parse_qsl(urlparse.urlparse(params).query))

if addon.getSetting('ssl_verif') == 'true' and hasattr(ssl, '_create_unverified_context'):
    ssl._create_default_https_context = ssl._create_unverified_context


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


def getURL(url, useCookie=False, silent=False, headers=None, attempt=0, retjson=True, check=False):
    cj = cookielib.LWPCookieJar()
    falseval = [] if retjson else ''
    if useCookie:
        cj = mechanizeLogin() if isinstance(useCookie, bool) else useCookie
        if isinstance(cj, bool):
            return falseval
    if not silent or verbLog:
        dispurl = url
        dispurl = re.sub('(?i)%s|%s|&token=\w+|&customerId=\w+' % (tvdb, tmdb), '', url).strip()
        Log('getURL: ' + dispurl)
    if not headers:
        headers = [('User-Agent', getConfig('UserAgent', def_UA)), ('Host', BASE_URL.split('//')[1])]
    try:
        opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cj), urllib2.HTTPRedirectHandler)
        opener.addheaders = headers
        usock = opener.open(url)
        response = usock.read() if not check else 'OK'
        usock.close()
    except (socket.timeout, ssl.SSLError, urllib2.URLError), e:
        Log('Error reason: %s' % e, xbmc.LOGERROR)
        if '429' or 'timed out' in e:
            attempt += 1 if not check else 10
            logout = 'Attempt #%s' % attempt
            if '429' in e:
                logout += '. Too many requests - Pause 10 sec'
                xbmc.sleep(10000)
            Log(logout)
            if attempt < 3:
                return getURL(url, useCookie, silent, headers, attempt, retjson)
        return falseval

    return json.loads(response) if retjson else response


def WriteLog(data, fn=''):
    if not verbLog:
        return
    if fn:
        fn = '-' + fn
    fn = pluginname + fn + '.log'
    path = os.path.join(homepath, fn)
    if isinstance(data, unicode):
        data = data.encode('utf-8')
    logfile = xbmcvfs.File(path, 'w')
    # data = time.strftime('[%d.%m/%H:%M:%S] ', time.localtime()) + data.__str__()
    logfile.write(data.__str__())
    logfile.write('\n')
    logfile.close()


def Log(msg, level=xbmc.LOGNOTICE):
    if level == xbmc.LOGDEBUG and verbLog:
        level = xbmc.LOGNOTICE
    if isinstance(msg, unicode):
        msg = msg.encode('utf-8')
    xbmc.log('[%s] %s' % (pluginname, msg.__str__()), level)


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
    u = {'url': url, 'mode': mode, 'sitemode': sitemode, 'name': name, 'page': page, 'opt': options}
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
        item.setInfo(type='Video', infoLabels=infoLabels)
        if 'TotalSeasons' in infoLabels.keys():
            item.setProperty('TotalSeasons', str(infoLabels['TotalSeasons']))
    if cm:
        item.addContextMenuItems(cm)

    xbmcplugin.addDirectoryItem(handle=pluginhandle, url=url, listitem=item, isFolder=True, totalItems=totalItems)


def addVideo(name, asin, poster=None, fanart=None, infoLabels=None, totalItems=0, cm=[], trailer=False,
             isAdult=False, isHD=False):
    u = {'asin': asin, 'mode': 'play', 'name': name, 'sitemode': 'PLAYVIDEO', 'adult': isAdult}
    url = '%s?%s' % (sys.argv[0], urllib.urlencode(u))

    if not infoLabels:
        infoLabels = {'Title': name}
    if not fanart or fanart == na:
        fanart = def_fanart

    item = xbmcgui.ListItem(name, thumbnailImage=poster)
    item.setProperty('fanart_image', fanart)
    item.setProperty('IsPlayable', str(playMethod == 3).lower())
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

    cm.insert(1, (getString(30118), 'RunPlugin(%s)' % (url + '&forcefb=1')))
    item.addContextMenuItems(cm)
    item.setInfo(type='Video', infoLabels=infoLabels)
    xbmcplugin.addDirectoryItem(handle=pluginhandle, url=url, listitem=item, isFolder=False, totalItems=totalItems)


def addText(name):
    item = xbmcgui.ListItem(name)
    item.setProperty('IsPlayable', 'false')
    xbmcplugin.addDirectoryItem(handle=pluginhandle, url=sys.argv[0], listitem=item)


def toogleWatchlist(asin=None, action='add'):
    if not asin:
        asin = args.get('asin')
        action = 'remove' if args.get('remove') == '1' else 'add'

    cookie = mechanizeLogin()
    if not cookie:
        return

    token = getToken(asin, cookie)
    url = BASE_URL + '/gp/video/watchlist/ajax/addRemove.html?ASIN=%s&dataType=json&csrfToken=%s&action=%s' % (
        asin, token, action)
    data = getURL(url, useCookie=cookie)

    if data['success'] == 1:
        Log(asin + ' ' + data['status'])
        if data['AsinStatus'] == 0:
            xbmc.executebuiltin('Container.Refresh')
    else:
        Log(data['status'] + ': ' + data['reason'])


def getToken(asin, cookie):
    url = BASE_URL + '/dp/video/' + asin
    data = getURL(url, useCookie=cookie, retjson=False)
    if data:
        tree = BeautifulSoup(data, convertEntities=BeautifulSoup.HTML_ENTITIES)
        form = tree.find('form', attrs={'class': 'dv-watchlist-toggle'})
        token = form.find('input', attrs={'name': 'csrfToken'})['value']
        return urllib.quote_plus(token)
    return ''


def gen_id(renew=False):
    guid = getConfig("GenDeviceID") if not renew else False
    if not guid or len(guid) != 56:
        guid = hmac.new(getConfig('UserAgent', def_UA), uuid.uuid4().bytes, hashlib.sha224).hexdigest()
        writeConfig("GenDeviceID", guid)
    return guid


def mechanizeLogin():
    cj = cookielib.LWPCookieJar()
    if xbmcvfs.exists(COOKIEFILE):
        cj.load(COOKIEFILE, ignore_discard=True, ignore_expires=True)
        return cj
    Log('Login')

    return LogIn(False)


def LogIn(ask=True, ue=None, up=None, attempt=1):
    Log('Login attempt #%s' % attempt)
    addon.setSetting('login_acc', '')
    email = getConfig('login_name') if not ue else ue
    password = decode(getConfig('login_pass')) if not up else up
    savelogin = addon.getSetting('save_login') == 'true'
    useMFA = False

    if ask:
        writeConfig('login', 'true')
        keyboard = xbmc.Keyboard(email, getString(30002))
        keyboard.doModal()
        if keyboard.isConfirmed() and keyboard.getText():
            email = keyboard.getText()
            password = setLoginPW()
        writeConfig('login', 'false')
    else:
        if not email or not password:
            if getConfig('login', 'false') == 'false':
                Dialog.notification(getString(30200), getString(30216))
                xbmc.executebuiltin('Addon.OpenSettings(%s)' % addon.getAddonInfo('id'))
            return False

    if password:
        writeConfig('login', 'true')
        xbmc.executebuiltin('ActivateWindow(busydialog)')
        if xbmcvfs.exists(COOKIEFILE):
            xbmcvfs.delete(COOKIEFILE)
        cj = cookielib.LWPCookieJar()
        br = mechanize.Browser()
        br.set_handle_robots(False)
        br.set_cookiejar(cj)
        br.set_handle_gzip(True)
        br.addheaders = [('User-Agent', getConfig('UserAgent', def_UA))]
        br.open(BASE_URL + "/gp/aw/si.html")
        br.select_form(name="signIn")
        br["email"] = email
        br["password"] = password
        br.addheaders = [('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'),
                         ('Accept-Encoding', 'gzip, deflate'),
                         ('Accept-Language', 'de,en-US;q=0.8,en;q=0.6'),
                         ('Cache-Control', 'max-age=0'),
                         ('Connection', 'keep-alive'),
                         ('Content-Type', 'application/x-www-form-urlencoded'),
                         ('Host', BASE_URL.split('//')[1]),
                         ('Origin', BASE_URL),
                         ('User-Agent', getConfig('UserAgent', def_UA)),
                         ('Upgrade-Insecure-Requests', '1')]
        br.submit()
        response = br.response().read()
        soup = parseHTML(response)
        xbmc.executebuiltin('Dialog.Close(busydialog)')

        if mobileUA(response) and attempt < 4:
            getUA(True)
            return LogIn(False, email, password, attempt + 1)

        while 'auth-mfa-form' in response or 'ap_dcq_form' in response:
            Log('MFA or DCQ form')
            if 'auth-mfa-form' in response:
                msg = soup.find('form', attrs={'id': 'auth-mfa-form'})
                msgtxt = msg.p.renderContents().strip()
                kb = xbmc.Keyboard('', msgtxt)
                kb.doModal()
                if kb.isConfirmed() and kb.getText():
                    xbmc.executebuiltin('ActivateWindow(busydialog)')
                    br.select_form(nr=0)
                    br['otpCode'] = kb.getText()
                else:
                    return False
            elif 'ap_dcq_form' in response:
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
                    xbmc.executebuiltin('ActivateWindow(busydialog)')
                    br.select_form(nr=0)
                    br[q_id[sel]] = ret
                else:
                    return False

            br.submit()
            response = br.response().read()
            soup = parseHTML(response)
            WriteLog(response, 'login-mfa')
            xbmc.executebuiltin('Dialog.Close(busydialog)')

        if 'action=sign-out' in response:
            msg = soup.body.findAll('center')
            wlc = msg[1].renderContents().strip()
            usr = wlc.split(',', 1)[1][:-1].strip()
            addon.setSetting('login_acc', usr)
            addon.setSetting('use_mfa', str(useMFA).lower())
            if useMFA:
                addon.setSetting('save_login', 'false')
                savelogin = False
            if savelogin:
                writeConfig('login_name', email)
                writeConfig('login_pass', encode(password))
            else:
                cj.save(COOKIEFILE, ignore_discard=True, ignore_expires=True)
            if ask or (ue and up):
                Dialog.ok(getString(30215), wlc)
            gen_id()
            writeConfig('login', 'false')
            return cj
        elif 'message_error' in response:
            writeConfig('login_pass', '')
            msg = soup.find('div', attrs={'id': 'message_error'})
            Log('Login Error: %s' % msg.p.renderContents().strip())
            Dialog.ok(getString(30200), getString(30201))
        elif 'message_warning' in response:
            msg = soup.find('div', attrs={'id': 'message_warning'})
            Log('Login Warning: %s' % msg.p.renderContents().strip())
            if attempt > 3:
                Dialog.ok(getString(30200), getString(30212))
            else:
                getUA(True)
                return LogIn(False, email, password, attempt + 1)
        elif 'auth-error-message-box' in response:
            msg = soup.find('div', attrs={'class': 'a-alert-content'})
            Log('Login MFA: %s' % msg.ul.li.span.renderContents().strip())
            Dialog.ok(getString(30200), getString(30214))
        else:
            WriteLog(response, 'login')
            Dialog.ok(getString(30200), getString(30213))
        writeConfig('login', 'false')
    return False


def setLoginPW():
    keyboard = xbmc.Keyboard('', getString(30003))
    keyboard.doModal()
    if keyboard.isConfirmed() and keyboard.getText():
        password = keyboard.getText()
        return password
    return False


def encode(data):
    k = triple_des(getmac(), CBC, "\0\0\0\0\0\0\0\0", padmode=PAD_PKCS5)
    d = k.encrypt(data)
    return base64.b64encode(d)


def decode(data):
    if not data:
        return ''
    k = triple_des(getmac(), CBC, "\0\0\0\0\0\0\0\0", padmode=PAD_PKCS5)
    d = k.decrypt(base64.b64decode(data))
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

    data = data.replace(u'\u00A0', ' ').replace(u'\u2013', '-').strip()
    return None if data == '' else data


def cleanName(name, isfile=True):
    if isfile:
        notallowed = ['<', '>', ':', '"', '\\', '/', '|', '*', '?']
        if isinstance(name, str):
            name = name.decode('utf-8')
    else:
        notallowed = ['<', '>', '"', '|', '*', '?']
        if not os.path.supports_unicode_filenames and isinstance(name, unicode):
            name = name.encode('utf-8')
    for c in notallowed:
        name = name.replace(c, '')
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


def SCRAP_ASINS(aurl, cj=True, attempt = 1):
    wl_order = ['DATE_ADDED_DESC', 'TITLE_DESC', 'TITLE_ASC'][int('0'+addon.getSetting("wl_order"))]
    asins = []
    url = BASE_URL + aurl + '?ie=UTF8&sort=' + wl_order
    content = getURL(url, useCookie=cj, retjson=False)
    if content:
        if mobileUA(content) and attempt < 4:
            getUA(True)
            return SCRAP_ASINS(aurl, cj, attempt + 1)
        asins += re.compile('data-asin="(.+?)"', re.DOTALL).findall(content)
    return asins


def getString(string_id):
    src = xbmc if string_id < 30000 else addon
    locString = src.getLocalizedString(string_id)
    if isinstance(locString, unicode):
        return locString.encode('utf-8')
    return locString


def remLoginData(savelogin=False, info=True):
    if savelogin or info:
        if xbmcvfs.exists(COOKIEFILE):
            xbmcvfs.delete(COOKIEFILE)

    if not savelogin or info:
        writeConfig('login_name', '')
        writeConfig('login_pass', '')

    if info:
        addon.setSetting('login_acc', '')
        addon.setSetting('use_mfa', 'false')
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
    # 501-POSTER WRAP 503-MLIST3 504=MLIST2 508-FANARTPOSTER 
    confluence_views = [500, 501, 502, 503, 504, 508, -1]
    xbmcplugin.setContent(pluginhandle, content)
    viewenable = addon.getSetting("viewenable")

    if viewenable == 'true' and view:
        viewid = confluence_views[int(addon.getSetting(view))]
        if viewid == -1:
            viewid = int(addon.getSetting(view.replace('view', 'id')))
        xbmc.executebuiltin('Container.SetViewMode(%s)' % viewid)
    xbmcplugin.endOfDirectory(pluginhandle, updateListing=updateListing)


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
        if item[1] == returnval:
            removeAsins.append(item[0])
    return removeAsins


def waitforDB(database):
    if database == 'tv':
        import tv
        c = tv.tvDB.cursor()
        tbl = 'shows'
    else:
        import movies
        c = movies.MovieDB.cursor()
        tbl = 'movies'
    error = True
    while error:
        error = False
        try:
            c.execute('select distinct * from ' + tbl).fetchone()
        except:
            error = True
            xbmc.sleep(1000)
            Log('Database locked')
    c.close()


def getTypes(items, col):
    studiolist = []
    lowlist = []
    for data in items:
        data = data[0]
        if isinstance(data, str):
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
        elif data != 0:
            if data is not None:
                strdata = str(data)[0:-1] + '0 -'
                if strdata not in studiolist:
                    studiolist.append(strdata)
    return studiolist


def copyDB(source, dest, ask=False):
    import shutil
    if ask:
        if not Dialog.yesno(getString(30193), getString(30194)):
            shutil.copystat(source['tv'], dest['tv'])
            shutil.copystat(source['movie'], dest['movie'])
            return
    shutil.copy2(source['tv'], dest['tv'])
    shutil.copy2(source['movie'], dest['movie'])


def getDBlocation(retvar):
    custdb = addon.getSetting('customdbfolder') == 'true'
    old_dbpath = xbmc.translatePath(getConfig('old_dbfolder')).decode('utf-8')
    cur_dbpath = dbpath

    if not old_dbpath:
        old_dbpath = cur_dbpath
    if custdb:
        cur_dbpath = xbmc.translatePath(addon.getSetting('dbfolder')).decode('utf-8')
    else:
        addon.setSetting('dbfolder', dbpath)

    orgDBfile = {'tv': os.path.join(dbpath, 'tv.db'), 'movie': os.path.join(dbpath, 'movies.db')}
    oldDBfile = {'tv': os.path.join(old_dbpath, 'tv.db'), 'movie': os.path.join(old_dbpath, 'movies.db')}
    DBfile = {'tv': os.path.join(cur_dbpath, 'tv.db'), 'movie': os.path.join(cur_dbpath, 'movies.db')}

    if old_dbpath != cur_dbpath:
        Log('DBPath changed')
        if xbmcvfs.exists(oldDBfile['tv']) and xbmcvfs.exists(oldDBfile['movie']):
            if not xbmcvfs.exists(cur_dbpath):
                xbmcvfs.mkdir(cur_dbpath)
            if not xbmcvfs.exists(DBfile['tv']) or not xbmcvfs.exists(DBfile['movie']):
                copyDB(oldDBfile, DBfile)
        writeConfig('old_dbfolder', cur_dbpath)

    if custdb:
        org_fileacc = int(xbmcvfs.Stat(orgDBfile['tv']).st_mtime() + xbmcvfs.Stat(orgDBfile['movie']).st_mtime())
        cur_fileacc = int(xbmcvfs.Stat(DBfile['tv']).st_mtime() + xbmcvfs.Stat(DBfile['movie']).st_mtime())
        if org_fileacc > cur_fileacc:
            copyDB(orgDBfile, DBfile, True)

    return DBfile[retvar]


def openSettings():
    aid = args.get('url')
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


def getConfig(cfile, value=''):
    cfgfile = os.path.join(configpath, cfile)

    if xbmcvfs.exists(cfgfile):
        f = xbmcvfs.File(cfgfile, 'r')
        value = f.read()
        f.close()

    return value


def writeConfig(cfile, value):
    cfgfile = os.path.join(configpath, cfile)
    cfglockfile = os.path.join(configpath, cfile + '.lock')

    if not xbmcvfs.exists(configpath):
        xbmcvfs.mkdirs(configpath)

    while True:
        if not xbmcvfs.exists(cfglockfile):
            l = xbmcvfs.File(cfglockfile, 'w')
            l.write(str(time.time()))
            l.close()
            f = xbmcvfs.File(cfgfile, 'w')
            f.write(value.__str__())
            f.close()
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


def parseHTML(response):
    response = re.sub(r'(?i)(<!doctype \w+).*>', r'\1>', response)
    soup = BeautifulSoup(response, convertEntities=BeautifulSoup.HTML_ENTITIES)
    return soup


def AddonEnabled(addon_id):
    result = xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Addons.GetAddonDetails","id":1,\
                                   "params":{"addonid":"%s", "properties": ["enabled"]}}' % addon_id)
    return False if '"error":' in result or '"enabled":false' in result else True


def getUA(blacklist=False):
    Log('Switching UserAgent')
    UAlist = json.loads(getConfig('UAlist', json.dumps([])))
    UAblist = json.loads(getConfig('UABlacklist', json.dumps([])))

    if blacklist:
        UAcur = getConfig('UserAgent', def_UA)
        if UAcur not in UAblist:
            UAblist.append(UAcur)
            writeConfig('UABlacklist', json.dumps(UAblist))
            Log('UA: %s blacklisted' % UAcur)

    UAwlist = [i for i in UAlist if i not in UAblist]
    if not UAlist or len(UAwlist) < 5:
        Log('Loading list of common UserAgents')
        html = getURL('https://techblog.willshouse.com/2012/01/03/most-common-user-agents/', retjson=False)
        soup = BeautifulSoup(html, convertEntities=BeautifulSoup.HTML_ENTITIES)
        text = soup.find('textarea')
        UAlist = text.string.split('\n')
        UAblist = []
        writeConfig('UABlacklist', json.dumps(UAblist))
        writeConfig('UAlist', json.dumps(UAlist[0:len(UAlist) - 1]))
        UAwlist = [i for i in UAlist if i not in UAblist]

    UAnew = UAwlist[random.randint(0, len(UAwlist) - 1)]
    writeConfig('UserAgent', UAnew)
    Log('Using UserAgent: ' + UAnew)
    return


def mobileUA(content):
    soup = BeautifulSoup(content, convertEntities=BeautifulSoup.HTML_ENTITIES)
    res = soup.find('html')['class']
    return True if 'a-mobile' in res or 'a-tablet' in res else False


if AddonEnabled('inputstream.adaptive'):
    is_addon = 'inputstream.adaptive'
elif AddonEnabled('inputstream.mpd'):
    is_addon = 'inputstream.mpd'
else:
    is_addon = None

if not getConfig('UserAgent'):
    getUA()

UserAgent = getConfig('UserAgent', def_UA)
AgePin = getConfig('age_pin')
PinReq = int(getConfig('pin_req', '0'))
RestrAges = ','.join(a[1] for a in Ages[PinReq:]) if AgePin else ''

remLoginData(addon.getSetting('save_login') == 'true', False)
Log('Args: %s' % args)