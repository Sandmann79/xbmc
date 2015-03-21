#!/usr/bin/env python
# -*- coding: utf-8 -*-
from BeautifulSoup import BeautifulSoup
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
import demjson

import binascii
import hmac
try:
    import hashlib.sha1 as sha1
except:
    import sha as sha1

addon = xbmcaddon.Addon()
__plugin__ = addon.getAddonInfo('name')
__authors__ = addon.getAddonInfo('author')
__credits__ = ""
__version__ = addon.getAddonInfo('version')
profilpath = xbmc.translatePath('special://profile')
pluginpath = addon.getAddonInfo('path').decode('utf-8')
pldatapath = xbmc.translatePath('special://profile/addon_data/' + addon.getAddonInfo('id')).decode('utf-8')
dbpath = xbmc.translatePath('special://home/addons/script.module.amazon.database/lib').decode('utf-8')
pluginhandle = int(sys.argv[1])
tmdb = base64.b64decode('YjM0NDkwYzA1NmYwZGQ5ZTNlYzlhZjIxNjdhNzMxZjQ=')
tvdb = base64.b64decode('MUQ2MkYyRjkwMDMwQzQ0NA==')
COOKIEFILE = os.path.join(pldatapath, 'cookies.lwp')
def_fanart = os.path.join(pluginpath, 'fanart.jpg')
BASE_URL = 'https://www.amazon.de'
#ATV_URL = 'https://atv-ps-eu.amazon.com'
ATV_URL = 'https://atv-ext-eu.amazon.com'
#UserAgent = 'Mozilla/5.0 (Windows NT 6.1; WOW64; Trident/7.0; rv:11.0) like Gecko'
UserAgent = 'Mozilla/5.0 (X11; U; Linux i686; en-US) AppleWebKit/533.4 (KHTML, like Gecko) Chrome/5.0.375.127 Large Screen Safari/533.4 GoogleTV/162671'

class _Info:
    def __init__( self, *args, **kwargs ):
        print "common.args"
        print kwargs
        self.__dict__.update( kwargs )
exec "args = _Info(%s)" % urllib.unquote_plus(sys.argv[2][1:].replace('&', ', ')).replace('<','"').replace('>','"')

def getURL( url, host=BASE_URL.split('//')[1], useCookie=False, silent=False, headers=None):
    cj = cookielib.LWPCookieJar()
    if useCookie and os.path.isfile(COOKIEFILE):
        cj.load(COOKIEFILE, ignore_discard=True, ignore_expires=True)
    if not silent:
        print 'getURL: '+url
    if not headers:
        headers = [('User-Agent', UserAgent ), ('Host', host)]
    try:
        opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cj),urllib2.HTTPRedirectHandler)
        opener.addheaders = headers
        usock = opener.open(url)
        response = usock.read()
        usock.close()
    except urllib2.URLError, e:
        print 'Error reason: ', e
        return False
    return response

def getATVURL( url , values = None ):
    try:
        opener = urllib2.build_opener()
        print 'ATVURL --> url = '+url
        opener.addheaders = [('x-android-sign', androidsig(url) )]
        if values == None:
            usock=opener.open(url)
        else:
            data = urllib.urlencode(values)
            usock=opener.open(url,postdata)
        response=usock.read()
        usock.close()
    except urllib2.URLError, e:
        print 'Error reason: ', e
        return False
    else:
        return response

def WriteLog(data, path=os.path.join(profilpath, 'amazon.log')):
    mode = 'w'
    if os.path.isfile(path):
        mode = 'a'
    file = open(path, mode)
    file.write(data.encode('ascii', 'ignore'))
    file.close()
    
def Log(data):
    print BeautifulSoup(data)
    
def SaveFile(path, data):
    file = open(path,'w')
    file.write(data)
    file.close()

def androidsig(url):
    hmac_key = binascii.unhexlify('f5b0a28b415e443810130a4bcb86e50d800508cc')
    sig = hmac.new(hmac_key, url, sha1)
    return base64.encodestring(sig.digest()).replace('\n','')

def addDir(name, mode, sitemode, url='', thumb='', fanart='', infoLabels=False, totalItems=0, cm=False ,page=1,isHD=False, options=''):
    u = '%s?url=<%s>&mode=<%s>&sitemode=<%s>&name=<%s>&page=<%s>&opt=<%s>' % (sys.argv[0], urllib.quote_plus(url), mode, sitemode, urllib.quote_plus(name), urllib.quote_plus(str(page)), options)
    if fanart == '' or fanart == None:
        try:fanart = args.fanart
        except:fanart = def_fanart
    else:u += '&fanart=<%s>' % urllib.quote_plus(fanart)
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
    if fanart:
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
        print asin + " added"

def removeWatchlist(asin=False):
    if not asin:
        asin=args.asin
    url = BASE_URL + '/gp/video/watchlist/?toggleOnWatchlist=1&action=remove&ASIN=' + asin
    data = getURL(url,useCookie=True)
    if asin not in data:
        xbmc.executebuiltin('Container.Refresh')
        print asin + " removed"
        
def makeGUID():
    import random
    guid = ''
    for i in range(3):
        number = "%X" % (int( ( 1.0 + random.random() ) * 0x10000) | 0)
        guid += number[1:]
    return guid

def gen_id():
    if not addon.getSetting("GenDeviceID"): 
        addon.setSetting("GenDeviceID",makeGUID()) 

def mechanizeLogin():
    succeeded = dologin()
    retrys = 0
    while succeeded == False:
        xbmc.sleep(1000)
        retrys += 1
        print 'Login Retry: '+str(retrys)
        succeeded = dologin()
        if retrys >= 2:
            xbmcgui.Dialog().ok('Login Error','Failed to Login')
            succeeded=True

def dologin():
    br = mechanize.Browser()  
    content = br.open(BASE_URL).read()
    if '"isPrime":1' in content:
        return True
    del content
    email = addon.getSetting('login_name')
    password = base64.b64decode(addon.getSetting('login_pass'))
    
    if addon.getSetting('save_login') == 'false' or email == '' or password == '':
        keyboard = xbmc.Keyboard('', getString(30002))
        keyboard.doModal()
        if keyboard.isConfirmed() and keyboard.getText():
            email = keyboard.getText()
            password = setLoginPW(False)
    if password:            
        if os.path.isfile(COOKIEFILE):
            os.remove(COOKIEFILE)
        cj = cookielib.LWPCookieJar()
        br.set_handle_robots(False)
        br.set_cookiejar(cj)
        br.set_debug_http(True)
        br.set_debug_responses(True)
        br.addheaders = [('User-agent', UserAgent)]  
        sign_in = br.open(BASE_URL + "/gp/flex/sign-out.html") 
        br.select_form(name="signIn")  
        br["email"] = email
        br["password"] = password
        logged_in = br.submit()  
        error_str = "message_error"
        if error_str in logged_in.read():
            xbmcgui.Dialog().ok(getString(30200), getString(30201))
            return True
        else:
            if addon.getSetting('save_login') == 'true':
                addon.setSetting('login_name', email)
                addon.setSetting('login_pass', base64.b64encode(password))
            cj.save(COOKIEFILE, ignore_discard=True, ignore_expires=True)
            gen_id()
            return True
    return False
    
def setLoginPW(save=True):
    keyboard = xbmc.Keyboard('', getString(30003), True)
    keyboard.doModal()
    if keyboard.isConfirmed() and keyboard.getText():
        password = keyboard.getText()
        if save:
            addon.setSetting('login_pass', base64.b64encode(password))
        return password
    return False
        
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
        for c in notallowed:
            name = name.replace(c,'')
    #name = BeautifulSoup(name, convertEntities=None).contents
    return name.strip().decode('utf-8')
    
def GET_ASINS(content):
    asins = ''
    hd_key = False
    prime_key = True
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
    del content
    return asins, hd_key, prime_key, channels
    
def SCRAP_ASINS():
    asins = []
    url = BASE_URL + '/gp/video/watchlist/?show=all&sort=DATE_ADDED_DESC&_encoding=UTF8'
    content = getURL(url, useCookie=True)
    asins += re.compile('class="innerItem" id="(.+?)."', re.DOTALL).findall(content)
    return asins
    
def getString(id):
    return addon.getLocalizedString(id).encode('utf-8')

def remLoginData():
    if os.path.isfile(COOKIEFILE):
        os.remove(COOKIEFILE)
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
    for type in data['message']['body']['categories']:
        if type['id'] == 'movies' or type['id'] == 'tv_shows':
            for cat in type['categories']:
                if cat['id'] == 'prime':
                    for subcat in cat['categories']:
                        if subcat['title'] == 'Neuerscheinungen':
                            asins.update({type['id']: urlparse.parse_qs(subcat['query'])['ASINList'][0].split(',')})
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
        xbmc.executebuiltin('Container.SetViewMode(%s)' % viewid)
    xbmcplugin.endOfDirectory(pluginhandle,updateListing=updateListing)
