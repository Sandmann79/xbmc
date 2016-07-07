#!/usr/bin/env python
# -*- coding: utf-8 -*-
from BeautifulSoup import BeautifulSoup
from pyDes import *
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
import urlparse
import base64
import binascii
import hmac
import time
import hashlib
import json
import xbmcvfs
import pyxbmct
from platform import node

addon = xbmcaddon.Addon()
__plugin__ = addon.getAddonInfo('name')
__authors__ = addon.getAddonInfo('author')
__credits__ = ""
__version__ = addon.getAddonInfo('version')
pluginpath = addon.getAddonInfo('path').decode('utf-8')
pldatapath = xbmc.translatePath(addon.getAddonInfo('profile')).decode('utf-8')
homepath = xbmc.translatePath('special://home').decode('utf-8')
dbplugin = 'script.module.amazon.database'
dbpath = os.path.join(homepath, 'addons', dbplugin, 'lib')
pluginhandle = int(sys.argv[1])
tmdb = base64.b64decode('YjM0NDkwYzA1NmYwZGQ5ZTNlYzlhZjIxNjdhNzMxZjQ=')
tvdb = base64.b64decode('MUQ2MkYyRjkwMDMwQzQ0NA==')
COOKIEFILE = os.path.join(pldatapath, 'cookies.lwp')
def_fanart = os.path.join(pluginpath, 'fanart.jpg')
AgePin = addon.getSetting('age_pin')
PinReq = int('0' + addon.getSetting('pin_req'))
na = 'not available'
BASE_URL = 'https://www.amazon.de'
ATV_URL = 'https://atv-eu.amazon.com'
UserAgent = 'Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36'
movielib = '/gp/video/%s/movie/'
tvlib = '/gp/video/%s/tv/'
lib = 'video-library'
wl = 'watchlist'
Ages = [('FSK 0', 'FSK 0'), ('FSK 6', 'FSK 6'), ('FSK 12', 'FSK 12'), ('FSK 16', 'FSK 16'), ('FSK 18', 'FSK 18')]
RestrAges = ','.join(a[1] for a in Ages[PinReq:]) if AgePin else ''
winid = xbmcgui.getCurrentWindowId()
verbLog = addon.getSetting('logging') == 'true'
kodi_mjver = int(xbmc.getInfoLabel('System.BuildVersion')[0:2])
Dialog = xbmcgui.Dialog()

class _Info:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


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
        addon.setSetting('age_pin', self.pin.getText().strip())
        addon.setSetting('pin_req', str(self.pin_req))
        self.close()

    def select_age(self):
        sel = Dialog.select(getString(30121), self.age_list)
        if sel > -1:
            self.pin_req = sel
            self.btn_ages.setLabel(self.age_list[self.pin_req])


def getURL(url, host=BASE_URL.split('//')[1], useCookie=False, silent=False, headers=None):
    cj = cookielib.LWPCookieJar()
    if useCookie:
        cj = mechanizeLogin() if isinstance(useCookie, bool) else useCookie
        if isinstance(cj, bool):
            return False
    if not silent or verbLog:
        dispurl = url
        dispurl = re.sub('(?i)%s|%s|&token=\w+' % (tvdb, tmdb), '', url).strip()
        Log('getURL: ' + dispurl)
    if not headers:
        headers = [('User-Agent', UserAgent), ('Host', host)]
    try:
        opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cj), urllib2.HTTPRedirectHandler)
        opener.addheaders = headers
        usock = opener.open(url)
        response = usock.read()
        usock.close()
    except urllib2.URLError, e:
        Log('Error reason: %s' % e, xbmc.LOGERROR)
        return False
    return response


def getATVURL(url, values=None):
    try:
        opener = urllib2.build_opener()
        Log('ATVURL --> url = ' + url)
        opener.addheaders = [('x-android-sign', androidsig(url))]
        if not values:
            usock = opener.open(url)
        else:
            postdata = urllib.urlencode(values)
            usock = opener.open(url, postdata)
        response = usock.read()
        usock.close()
    except urllib2.URLError, e:
        Log('Error reason: %s' % e, xbmc.LOGERROR)
        return False
    else:
        return response


def WriteLog(data, fn=''):
    if not verbLog:
        return
    if fn:
        fn = '-' + fn
    fn = __plugin__ + fn + '.log'
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
    xbmc.log('[%s] %s' % (__plugin__, msg.__str__()), level)


def SaveFile(path, data):
    f = xbmcvfs.File(path, 'w')
    f.write(data)
    f.close()


def androidsig(url):
    hmac_key = binascii.unhexlify('f5b0a28b415e443810130a4bcb86e50d800508cc')
    sig = hmac.new(hmac_key, url, hashlib.sha1)
    return base64.encodestring(sig.digest()).replace('\n', '')


def addDir(name, mode, sitemode, url='', thumb='', fanart='', infoLabels=None, totalItems=0, cm=None, page=1, options=''):
    u = '%s?url=<%s>&mode=<%s>&sitemode=<%s>&name=<%s>&page=<%s>&opt=<%s>' % (
        sys.argv[0], urllib.quote_plus(url), mode, sitemode, urllib.quote_plus(name), urllib.quote_plus(str(page)), options)

    if fanart == '' or fanart is None or fanart == na:
        fanart = def_fanart
    if thumb == '' or thumb is None:
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
        item.addContextMenuItems(cm, replaceItems=False)

    xbmcplugin.addDirectoryItem(handle=pluginhandle, url=u, listitem=item, isFolder=True, totalItems=totalItems)


def addVideo(name, asin, poster=None, fanart=None, infoLabels=None, totalItems=0, cm=None, trailer=False,
             isAdult=False, isHD=False):
    if not cm:
        cm = []
    u = '%s?asin=<%s>&mode=<play>&name=<%s>&sitemode=<PLAYVIDEO>&adult=<%s>' % (
        sys.argv[0], asin, urllib.quote_plus(name), str(isAdult))
    if not infoLabels:
        infoLabels = {"Title": name}
    if fanart == '' or fanart is None or fanart == na:
        fanart = def_fanart

    item = xbmcgui.ListItem(name, thumbnailImage=poster)
    item.setProperty('fanart_image', fanart)
    cm.insert(0, (getString(30101), 'Action(ToggleWatched)'))

    if int(addon.getSetting("playmethod")) == 3:
        item.setProperty('IsPlayable', 'true')
    else:
        item.setProperty('IsPlayable', 'false')

    if isHD:
        item.addStreamInfo('video', {'width': 1920, 'height': 1080})
    else:
        item.addStreamInfo('video', {'width': 720, 'height': 480})

    if infoLabels['AudioChannels']:
        item.addStreamInfo('audio', {'codec': 'ac3', 'channels': int(infoLabels['AudioChannels'])})

    if trailer:
        infoLabels['Trailer'] = u + '&trailer=<1>&selbitrate=<0>'
    u += '&trailer=<0>&selbitrate=<0>'

    if 'Poster' in infoLabels.keys():
        item.setArt({'tvshow.poster': infoLabels['Poster']})
    else:
        item.setArt({'Poster': poster})
    item.addContextMenuItems(cm, replaceItems=False)
    item.setInfo(type='Video', infoLabels=infoLabels)
    xbmcplugin.addDirectoryItem(handle=pluginhandle, url=u, listitem=item, isFolder=False, totalItems=totalItems)


def addText(name):
    item = xbmcgui.ListItem(name)
    item.setProperty('IsPlayable', 'false')
    xbmcplugin.addDirectoryItem(handle=pluginhandle, url=sys.argv[0], listitem=item)


def toogleWatchlist(asin=None, action='add'):
    if not asin:
        asin = args.asin
        action = 'remove' if args.remove == '1' else 'add'

    cookie = mechanizeLogin()
    if not cookie:
        return

    token = getToken(asin, cookie)
    url = BASE_URL + '/gp/video/watchlist/ajax/addRemove.html?ASIN=%s&dataType=json&token=%s&action=%s' % (
        asin, token, action)
    data = json.loads(getURL(url, useCookie=cookie))

    if data['success'] == 1:
        Log(asin + ' ' + data['status'])
        if data['AsinStatus'] == 0:
            xbmc.executebuiltin('Container.Refresh')
    else:
        Log(data['status'] + ': ' + data['reason'])


def getToken(asin, cookie):
    url = BASE_URL + '/gp/video/watchlist/ajax/hoverbubble.html?ASIN=' + asin
    data = getURL(url, useCookie=cookie)
    if data:
        tree = BeautifulSoup(data, convertEntities=BeautifulSoup.HTML_ENTITIES)
        form = tree.find('form', attrs={'id': 'watchlistForm'})
        token = form.find('input', attrs={'id': 'token'})['value']
        return urllib.quote_plus(token)
    return ''


def gen_id():
    guid = addon.getSetting("GenDeviceID")
    if not guid or len(guid) != 56:
        guid = hmac.new(UserAgent, uuid.uuid4().bytes, hashlib.sha224).hexdigest()
        addon.setSetting("GenDeviceID", guid)
    return guid


def mechanizeLogin():
    cj = cookielib.LWPCookieJar()
    if xbmcvfs.exists(COOKIEFILE):
        cj.load(COOKIEFILE, ignore_discard=True, ignore_expires=True)
        return cj
    Log('Login')

    return LogIn(False)


def LogIn(ask=True):
    addon.setSetting('login_acc', '')
    email = addon.getSetting('login_name')
    password = decode(addon.getSetting('login_pass'))
    savelogin = addon.getSetting('save_login') == 'true'
    useMFA = False

    if ask:
        keyboard = xbmc.Keyboard(email, getString(30002))
        keyboard.doModal()
        if keyboard.isConfirmed() and keyboard.getText():
            email = keyboard.getText()
            password = setLoginPW()
    else:
        if not email or not password:
            Dialog.notification(getString(30200), getString(30216))
            addon.openSettings()
            return False

    if password:
        if xbmcvfs.exists(COOKIEFILE):
            xbmcvfs.delete(COOKIEFILE)
        cj = cookielib.LWPCookieJar()
        br = mechanize.Browser()
        br.set_handle_robots(False)
        br.set_cookiejar(cj)
        br.set_handle_gzip(True)
        br.addheaders = [('User-Agent', UserAgent)]
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
                         ('User-Agent', UserAgent),
                         ('Upgrade-Insecure-Requests', '1')]
        br.submit()
        response = br.response().read()
        soup = BeautifulSoup(response, convertEntities=BeautifulSoup.HTML_ENTITIES)

        if 'auth-mfa-form' in response:
            msg = soup.find('form', attrs={'id': 'auth-mfa-form'})
            msgtxt = msg.p.renderContents().strip()
            kb = xbmc.Keyboard('', msgtxt)
            kb.doModal()
            if kb.isConfirmed() and kb.getText():
                br.select_form(nr=0)
                br['otpCode'] = kb.getText()
                br.submit()
                response = br.response().read()
                soup = BeautifulSoup(response, convertEntities=BeautifulSoup.HTML_ENTITIES)
                useMFA = True
            else:
                return False

        if 'action=sign-out' in response:
            msg = soup.body.findAll('center')
            wlc = msg[1].renderContents().strip()
            usr = wlc.split(',', 1)[1][:-1].strip()
            addon.setSetting('login_acc', usr)
            if useMFA:
                addon.setSetting('save_login', 'false')
                savelogin = False
            if savelogin:
                addon.setSetting('login_name', email)
                addon.setSetting('login_pass', encode(password))
            else:
                cj.save(COOKIEFILE, ignore_discard=True, ignore_expires=True)
            if ask:
                addon.setSetting('use_mfa', str(useMFA).lower())
                Dialog.ok(getString(30215), wlc)
            gen_id()
            return cj
        elif 'message_error' in response:
            addon.setSetting('login_pass', '')
            msg = soup.find('div', attrs={'id': 'message_error'})
            Log('Login Error: %s' % msg.p.renderContents().strip())
            Dialog.ok(getString(30200), getString(30201))
        elif 'message_warning' in response:
            msg = soup.find('div', attrs={'id': 'message_warning'})
            Log('Login Warning: %s' % msg.p.renderContents().strip())
            Dialog.ok(getString(30200), getString(30212))
        elif 'auth-error-message-box' in response:
            msg = soup.find('div', attrs={'class': 'a-alert-content'})
            Log('Login MFA: %s' % msg.ul.li.span.renderContents().strip())
            Dialog.ok(getString(30200), getString(30214))
        else:
            WriteLog(response, 'login')
            Dialog.ok(getString(30200), getString(30213))
    return False


def setLoginPW():
    keyboard = xbmc.Keyboard('', getString(30003), True)
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
        name = name.decode('utf-8')
    else:
        notallowed = ['<', '>', '"', '|', '*', '?']
        if not os.path.supports_unicode_filenames:
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


def SCRAP_ASINS(url, cj=True):
    asins = []
    url = BASE_URL + url + '?ie=UTF8&sortBy=DATE_ADDED_DESC'
    content = getURL(url, useCookie=cj)
    if content:
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
        addon.setSetting('login_name', '')
        addon.setSetting('login_pass', '')

    if info:
        addon.setSetting('login_acc', '')
        addon.setSetting('use_mfa', 'false')
        Dialog.notification(__plugin__, getString(30211), xbmcgui.NOTIFICATION_INFO)


def checkCase(title):
    if title.isupper():
        title = title.title().replace('[Ov]', '[OV]').replace('Bc', 'BC')
    title = title.replace('[dt./OV]', '')
    return title


def getCategories():
    response = getURL(
        ATV_URL + '/cdp/catalog/GetCategoryList?firmware=fmw:15-app:1.1.23&deviceTypeID=A1MPSLFC7L5AFK&deviceID=%s'
                  '&format=json&OfferGroups=B0043YVHMY&IncludeAll=T&version=2' % gen_id())
    data = json.loads(response)
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


def compasin(asinlist, searchstring):
    ret = False
    for index, array in enumerate(asinlist):
        if searchstring.lower() in array[0].lower():
            asinlist[index][1] = 1
            ret = True
    return ret, asinlist


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


def updateRunning():
    from datetime import datetime, timedelta
    update = addon.getSetting('update_running')
    if update != 'false':
        starttime = datetime(*(time.strptime(update, '%Y-%m-%d %H:%M')[0:6]))
        if (starttime + timedelta(hours=6)) <= datetime.today():
            addon.setSetting('update_running', 'false')
            Log('DB Cancel update - duration > 6 hours')
        else:
            Log('DB Update already running', xbmc.LOGDEBUG)
            return True
    return False


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
    old_dbpath = xbmc.translatePath(addon.getSetting('old_dbfolder')).decode('utf-8')
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
        addon.setSetting('old_dbfolder', cur_dbpath)

    if custdb:
        org_fileacc = int(xbmcvfs.Stat(orgDBfile['tv']).st_mtime() + xbmcvfs.Stat(orgDBfile['movie']).st_mtime())
        cur_fileacc = int(xbmcvfs.Stat(DBfile['tv']).st_mtime() + xbmcvfs.Stat(DBfile['movie']).st_mtime())
        if org_fileacc > cur_fileacc:
            copyDB(orgDBfile, DBfile, True)

    return DBfile[retvar]


def openSettings():
    xbmcaddon.Addon(args.url).openSettings()


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


remLoginData(addon.getSetting('save_login') == 'true', False)

urlargs = urllib.unquote_plus(sys.argv[2][1:].replace('&', ', ')).replace('<', '"').replace('>', '"')
Log('Args: %s' % urlargs)
exec "args = _Info(%s)" % urlargs
