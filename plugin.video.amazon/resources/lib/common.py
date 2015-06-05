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
try: from demjson import demjson
except: import demjson

addon = xbmcaddon.Addon()
__plugin__ = addon.getAddonInfo('name')
__authors__ = addon.getAddonInfo('author')
__credits__ = ""
__version__ = addon.getAddonInfo('version')
profilpath = xbmc.translatePath('special://masterprofile/').decode('utf-8')
pluginpath = addon.getAddonInfo('path').decode('utf-8')
pldatapath = xbmc.translatePath('special://profile/addon_data/' + addon.getAddonInfo('id')).decode('utf-8')
homepath = xbmc.translatePath('special://home').decode('utf-8')
dbplugin = 'script.module.amazon.database'
dbpath = os.path.join(homepath, 'addons', dbplugin, 'lib')
pluginhandle = int(sys.argv[1])
tmdb = base64.b64decode('YjM0NDkwYzA1NmYwZGQ5ZTNlYzlhZjIxNjdhNzMxZjQ=')
tvdb = base64.b64decode('MUQ2MkYyRjkwMDMwQzQ0NA==')
COOKIEFILE = os.path.join(pldatapath, 'cookies.lwp')
def_fanart = os.path.join(pluginpath, 'fanart.jpg')
na = 'not available'
BASE_URL = 'https://www.amazon.de'
#ATV_URL = 'https://atv-ps-eu.amazon.com'
ATV_URL = 'https://atv-ext-eu.amazon.com'
#UserAgent = 'Mozilla/5.0 (Windows NT 6.1; WOW64; Trident/7.0; rv:11.0) like Gecko'
UserAgent = 'Mozilla/5.0 (X11; U; Linux i686; de-DE) AppleWebKit/533.4 (KHTML, like Gecko) Chrome/5.0.375.127 Large Screen Safari/533.4 GoogleTV/162671'
movielib = '/gp/aw/%s/?filter=movie'
tvlib = '/gp/aw/%s/?filter=tv'
lib = 'yvl'
wl = 'wl'
winid = xbmcgui.getCurrentWindowId()
kodi_mjver = int(xbmc.getInfoLabel('System.BuildVersion')[0:2])
Dialog = xbmcgui.Dialog()
    
class _Info:
    def __init__( self, *args, **kwargs ):
        self.__dict__.update( kwargs )

def getURL( url, host=BASE_URL.split('//')[1], useCookie=False, silent=False, headers=None):
    cj = cookielib.LWPCookieJar()
    if useCookie:
        if isinstance(useCookie, bool): cj = mechanizeLogin()
        else: cj = useCookie
        if isinstance(cj, bool): return False
    dispurl = url
    #dispurl = re.sub(tvdb+'|'+tmdb+'|&token=\w+', '', url, flags=re.IGNORECASE).strip()
    if not silent: Log('getURL: '+dispurl)
    if not headers: headers = [('User-Agent', UserAgent ), ('Host', host)]
    try:
        opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cj),urllib2.HTTPRedirectHandler)
        opener.addheaders = headers
        usock = opener.open(url)
        response = usock.read()
        usock.close()
    except urllib2.URLError, e:
        Log('Error reason: %s' % e, xbmc.LOGERROR)
        return False
    return response

def getATVURL( url , values = None ):
    try:
        opener = urllib2.build_opener()
        Log('ATVURL --> url = '+url)
        opener.addheaders = [('x-android-sign', androidsig(url) )]
        if values == None:
            usock=opener.open(url)
        else:
            data = urllib.urlencode(values)
            usock=opener.open(url,postdata)
        response=usock.read()
        usock.close()
    except urllib2.URLError, e:
        Log('Error reason: %s' % e, xbmc.LOGERROR)
        return False
    else:
        return response

def WriteLog(data, fn='', mode='a'):
    if addon.getSetting('logging') != 'true': return
    if fn: fn = '-' + fn
    fn = __plugin__ + fn + '.log'
    path = os.path.join(homepath, fn)
    if type(data) == type(unicode()): data = data.encode('utf-8')
    file = open(path, mode)
    data = time.strftime('[%d.%m/%H:%M:%S] ', time.localtime()) + data.__str__()
    file.write(data)
    file.write('\n')
    file.close()
    
def Log(msg, level=xbmc.LOGNOTICE):
    if type(msg) == type(unicode()):
        msg = msg.encode('utf-8')
    WriteLog(msg)
    xbmc.log('[%s] %s' % (__plugin__, msg.__str__()), level)
    
def SaveFile(path, data):
    file = open(path,'w')
    file.write(data)
    file.close()

def androidsig(url):
    hmac_key = binascii.unhexlify('f5b0a28b415e443810130a4bcb86e50d800508cc')
    sig = hmac.new(hmac_key, url, hashlib.sha1)
    return base64.encodestring(sig.digest()).replace('\n','')

def addDir(name, mode, sitemode, url='', thumb='', fanart='', infoLabels=False, totalItems=0, cm=False ,page=1,isHD=False, options=''):
    u = '%s?url=<%s>&mode=<%s>&sitemode=<%s>&name=<%s>&page=<%s>&opt=<%s>' % (sys.argv[0], urllib.quote_plus(url), mode, sitemode, urllib.quote_plus(name), urllib.quote_plus(str(page)), options)
    try:fanart = args.fanart
    except:pass
    if fanart == '' or fanart == None or fanart == na: fanart = def_fanart
    else: u += '&fanart=<%s>' % urllib.quote_plus(fanart)
    if thumb == '' or thumb == None:
        try:thumb = args.thumb
        except:thumb = def_fanart
    else:
        u += '&thumb=<%s>' % urllib.quote_plus(thumb)
    item=xbmcgui.ListItem(name, iconImage="DefaultFolder.png", thumbnailImage=thumb)
    item.setProperty('fanart_image',fanart)
    item.setProperty('IsPlayable', 'false')
    try: 
        item.setProperty('TotalSeasons', str(infoLabels['TotalSeasons']))
    except: pass
    if infoLabels:
        item.setInfo(type='Video', infoLabels=infoLabels)
    if cm:
        item.addContextMenuItems( cm, replaceItems=False  )
    xbmcplugin.addDirectoryItem(handle=pluginhandle,url=u,listitem=item,isFolder=True,totalItems=totalItems)

def addVideo(name,asin,poster=False,fanart=False,infoLabels=False,totalItems=0,cm=False,trailer=False,isAdult=False,isHD=False):
    if not infoLabels:
        infoLabels={ "Title": name}
    u  = '%s?asin=<%s>&mode=<play>&name=<%s>&sitemode=<PLAYVIDEO>&adult=<%s>' % (sys.argv[0], asin, urllib.quote_plus(name), str(isAdult))
    if poster:
        liz=xbmcgui.ListItem(name, thumbnailImage=poster)
    else:
        liz=xbmcgui.ListItem(name)
    if fanart == '' or fanart == None or fanart == na: fanart = def_fanart
    liz.setProperty('fanart_image',fanart)
    liz.setProperty('IsPlayable', 'false')
    if not cm:
        cm = []
    if int(addon.getSetting("playmethod")) == 0:
        liz.setProperty('IsPlayable', 'true')
        cm.insert(0, (getString(30109), 'XBMC.RunPlugin(%s&trailer=<0>&selbitrate=<1>)' % u) )
        cm.insert(1, (getString(30113), 'XBMC.RunPlugin(%s&trailer=<0>&selbitrate=<org>)' % u) )
    if isHD:
        liz.addStreamInfo('video', { 'width':1280 ,'height' : 720 })
    else:
        liz.addStreamInfo('video', { 'width':720 ,'height' : 480 })
    if infoLabels['AudioChannels']: liz.addStreamInfo('audio', { 'codec': 'ac3' ,'channels': int(infoLabels['AudioChannels']) })
    if trailer:
        infoLabels['Trailer'] = u + '&trailer=<1>&selbitrate=<0>'
    u += '&trailer=<0>&selbitrate=<0>'
    if infoLabels.has_key('Poster'): liz.setArt({'tvshow.poster': infoLabels['Poster']})
    else: liz.setArt({'poster': poster})
    liz.setInfo(type='Video', infoLabels=infoLabels)
    liz.addContextMenuItems( cm , replaceItems=False )
    xbmcplugin.addDirectoryItem(handle=pluginhandle,url=u,listitem=liz,isFolder=False,totalItems=totalItems)     

def addText(name):
    item = xbmcgui.ListItem(name)
    item.setProperty('IsPlayable', 'false')
    xbmcplugin.addDirectoryItem(handle=pluginhandle,url=sys.argv[0],listitem=item)

def addWatchlist(asin=False):
    if not asin:
        asin=args.asin
    url = BASE_URL + '/gp/video/watchlist/?toggleOnWatchlist=1&action=add&ASIN=' + asin
    data = getURL(url,useCookie=True)
    if asin in data:
        Log(asin + ' added')

def removeWatchlist(asin=False):
    if not asin:
        asin=args.asin
    url = BASE_URL + '/gp/video/watchlist/?toggleOnWatchlist=1&action=remove&ASIN=' + asin
    data = getURL(url,useCookie=True)
    if asin not in data:
        xbmc.executebuiltin('Container.Refresh')
        Log(asin + ' removed')
        
def makeGUID():
    import random
    guid = ''
    for i in range(3):
        number = "%X" % (int( ( 1.0 + random.random() ) * 0x10000) | 0)
        guid += number[1:]
    return guid

def gen_id():
    guid = addon.getSetting("GenDeviceID")
    if not guid: 
        guid = makeGUID()
        addon.setSetting("GenDeviceID", guid)
    return guid

def mechanizeLogin():
    cj = cookielib.LWPCookieJar()
    if os.path.isfile(COOKIEFILE):
        cj.load(COOKIEFILE, ignore_discard=True, ignore_expires=True)
        return cj
    Log('Login')
    succeeded = dologin()
    retrys = 0
    while succeeded == False:
        xbmc.sleep(1000)
        retrys += 1
        Log('Login Retry: %s' % retrys)
        succeeded = dologin()
        if retrys >= 2:
            Dialog.ok('Login Error','Failed to Login')
            succeeded=True
    return succeeded

def dologin():
    email = addon.getSetting('login_name')
    password = decode(addon.getSetting('login_pass'))
    changed = False
    
    if addon.getSetting('save_login') == 'false' or email == '' or password == '':
        keyboard = xbmc.Keyboard(addon.getSetting('login_name'), getString(30002))
        keyboard.doModal()
        if keyboard.isConfirmed() and keyboard.getText():
            email = keyboard.getText()
            password = setLoginPW()
            if password: changed = True
    if password:
        if os.path.isfile(COOKIEFILE):
            os.remove(COOKIEFILE)
        cj = cookielib.LWPCookieJar()
        br = mechanize.Browser()  
        br.set_handle_robots(False)
        br.set_cookiejar(cj)
        #br.set_debug_http(True)
        #br.set_debug_responses(True)
        br.addheaders = [('User-agent', UserAgent)]  
        sign_in = br.open(BASE_URL + "/gp/aw/si.html") 
        br.select_form(name="signIn")  
        br["email"] = email
        br["password"] = password
        logged_in = br.submit()
        error_str = "message error"
        if error_str in logged_in.read():
            Dialog.ok(getString(30200), getString(30201))
            return False
        else:
            if addon.getSetting('save_login') == 'true' and changed:
                addon.setSetting('login_name', email)
                addon.setSetting('login_pass', encode(password))
            if addon.getSetting('no_cookie') != 'true':
                cj.save(COOKIEFILE, ignore_discard=True, ignore_expires=True)
            gen_id()
            return cj
    return True
    
def setLoginPW():
    keyboard = xbmc.Keyboard('', getString(30003), True)
    keyboard.doModal()
    if keyboard.isConfirmed() and keyboard.getText():
        password = keyboard.getText()
        return password
    return False
        
def encode(data):
    k = triple_des((str(uuid.getnode())*2)[0:24], CBC, "\0\0\0\0\0\0\0\0", padmode=PAD_PKCS5)
    d = k.encrypt(data)
    return base64.b64encode(d)

def decode(data):
    if not data: return ''
    k = triple_des((str(uuid.getnode())*2)[0:24], CBC, "\0\0\0\0\0\0\0\0", padmode=PAD_PKCS5)
    d = k.decrypt(base64.b64decode(data))
    return d
    
def cleanData(data):
    if type(data) == type(str()) or type(data) == type(unicode()):
        if data.replace('-','').strip() == '': data = ''
        data = data.replace(u'\u00A0', ' ').replace(u'\u2013', '-')
        data = data.strip()
        if data == '': data = None
    return data
    
def cleanName(name, file=True):
    if file:
        notallowed = ['<', '>', ':', '"', '\\', '/', '|', '*', '?']
        name = name.decode('utf-8')
    else:
        notallowed = ['<', '>', '"', '|', '*', '?']
        if not os.path.supports_unicode_filenames: name = name.encode('utf-8')
    for c in notallowed:
        name = name.replace(c,'')
    return name
    
def GET_ASINS(content):
    asins = ''
    hd_key = False
    prime_key = False
    channels = 1
    if content.has_key('titleId'):
        asins += content['titleId']
        titleId = content['titleId']
    for format in content['formats']:
        hasprime = False
        for offer in format['offers']:
            if offer['offerType'] == 'SUBSCRIPTION':
                hasprime = True
                prime_key = True
            elif offer.has_key('asin'):
                newasin = offer['asin']
                if format['videoFormatType'] == 'HD':
                    if (newasin == titleId) and (hasprime):
                        hd_key = True
                if newasin not in asins:
                    asins += ',' + newasin
        if 'STEREO' in format['audioFormatTypes']: channels = 2
        if 'AC_3_5_1' in format['audioFormatTypes']: channels = 6
    """
    if content['childTitles']:
        feedurl = content['childTitles'][0]['feedUrl']
        fasins = re.compile('[\?|&].*ASIN=([^&]*)').findall(feedurl)
        if fasins: feedasins = fasins[0]
        if titleId not in feedasins:
            feedasins = titleId + ',' + feedasins
        titleId = feedasins
    """
    del content
    return asins, hd_key, prime_key, channels
    
def SCRAP_ASINS(url):
    asins = []
    url = BASE_URL + url + '&pageSize=1000&sortBy=date'
    content = getURL(url, useCookie=True)
    if content:
        asins += re.compile('data-asin="(.+?)"', re.DOTALL).findall(content)
        return asins
    return []
    
def getString(id, enc=False):
    if enc: return addon.getLocalizedString(id).encode('utf-8')
    return addon.getLocalizedString(id)

def remLoginData():
    if os.path.isfile(COOKIEFILE): os.remove(COOKIEFILE)
    addon.setSetting('login_name', '')
    addon.setSetting('login_pass', '')

def checkCase(title):
    if title.isupper():
        title = title.title().replace('[Ov]', '[OV]').replace('Bc', 'BC')
    return title
    
def getNewest():
    import urlparse
    response = getURL(ATV_URL + '/cdp/catalog/GetCategoryList?firmware=fmw:15-app:1.1.23&deviceTypeID=A1MPSLFC7L5AFK&deviceID=%s&format=json&OfferGroups=B0043YVHMY&IncludeAll=T&version=2' % addon.getSetting("GenDeviceID"))
    data = demjson.decode(response)
    asins = {}
    for type in data['message']['body']['categories'][0]['categories'][0]['categories']:
        subPageType = None
        if type.has_key('subPageType'): subPageType = type['subPageType']
        if subPageType == 'PrimeMovieRecentlyAdded' or subPageType == 'PrimeTVRecentlyAdded':
            asins.update({subPageType: urlparse.parse_qs(type['query'])['ASINList'][0].split(',')})
    return asins

def SetView(content, view=False, updateListing=False):
    # 501-POSTER WRAP 503-MLIST3 504=MLIST2 508-FANARTPOSTER 
    confluence_views = [500,501,502,503,504,508,-1]
    xbmcplugin.setContent(pluginhandle, content)
    viewenable = addon.getSetting("viewenable")
    if viewenable == 'true' and view:
        viewid = confluence_views[int(addon.getSetting(view))]
        if viewid == -1:
            viewid = int(addon.getSetting(view.replace('view', 'id')))
        if kodi_mjver >= 14: xbmc.executebuiltin('ActivateWindow(%s)' % winid)
        xbmc.executebuiltin('Container.SetViewMode(%s)' % viewid)
    xbmcplugin.endOfDirectory(pluginhandle,updateListing=updateListing)
    
def compasin(list, searchstring):
    ret = False
    for index, array in enumerate(list):
        if searchstring.lower() in array[0].lower():
            list[index][1] = 1
            ret = True
    return ret, list
    
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
    list = []
    lowlist = []
    for data in items:
        data = data[0]
        if type(data) == type(str()):
            if 'Rated' in data:
                item = data.split('for')[0]
                if item not in list and item <> '' and item <> 0 and item <> 'Inc.' and item <> 'LLC.':
                    list.append(item)
            else:
                if 'genres' in col: data = data.split('/')
                else: data = re.split(r'[,;/]', data)
                for item in data:
                    item = item.strip()
                    if item.lower() not in lowlist and item <> '' and item <> 0 and item <> 'Inc.' and item <> 'LLC.':
                        list.append(item)
                        lowlist.append(item.lower())
        elif data <> 0:
            if data is not None:
                strdata = str(data)[0:-1] + '0 -'
                if strdata not in list:
                    list.append(strdata)
    return list
    
def updateRunning():
    from datetime import datetime, timedelta
    update = addon.getSetting('update_running')
    if update != 'false':
        starttime = datetime.strptime(update, '%Y-%m-%d %H:%M')
        if (starttime + timedelta(hours=6)) <= datetime.today():
            addon.setSetting('update_running', 'false')
            Log('DB Cancel update - duration > 6 hours')
        else:
            Log('DB Update already running', xbmc.LOGDEBUG)
            return True
    return False
            
def copyDB(ask=False):
    import shutil
    if ask:
        if not Dialog.yesno(getString(30193), getString(30194)):
            shutil.copystat(org_tvDBfile, tvDBfile)
            shutil.copystat(org_MovieDBfile, MovieDBfile)
            return
    import tv, movies
    tv.tvDB.close()
    movies.MovieDB.close()
    shutil.copy2(org_tvDBfile, tvDBfile)
    shutil.copy2(org_MovieDBfile, MovieDBfile)
    
org_tvDBfile = os.path.join(dbpath, 'tv.db')
org_MovieDBfile = os.path.join(dbpath, 'movies.db')
if addon.getSetting('customdbfolder') == 'true': 
    dbpath = xbmc.translatePath(addon.getSetting('dbfolder')).decode('utf-8')
tvDBfile = os.path.join(dbpath, 'tv.db')
MovieDBfile = os.path.join(dbpath, 'movies.db')

if addon.getSetting('customdbfolder') == 'true':
    if os.path.isfile(org_tvDBfile) and os.path.isfile(org_MovieDBfile):
        if not os.path.isdir(dbpath): 
            os.makedirs(dbpath)
        if not os.path.isfile(tvDBfile) or not os.path.isfile(MovieDBfile):
            copyDB()
        org_fileacc = int(os.path.getmtime(org_tvDBfile) + os.path.getmtime(org_MovieDBfile))
        cur_fileacc = int(os.path.getmtime(tvDBfile) + os.path.getmtime(MovieDBfile))
        if org_fileacc > cur_fileacc:
            copyDB(True)
    
urlargs =  urllib.unquote_plus(sys.argv[2][1:].replace('&', ', ')).replace('<','"').replace('>','"')
Log('Args: %s' % urlargs)
exec "args = _Info(%s)" % urlargs