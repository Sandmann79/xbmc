#!/usr/bin/env python
# -*- coding: utf-8 -*-
from BeautifulSoup import BeautifulStoneSoup
from BeautifulSoup import BeautifulSoup
import cookielib
import mechanize
#import operator
import sys
import urllib
import urllib2
import re
import os.path
import xbmcplugin
import xbmcgui
import xbmcaddon
import xbmc

import binascii
import hmac
try:
    import hashlib.sha1 as sha1
except:
    import sha as sha1

import base64
import demjson

print sys.argv
addon = xbmcaddon.Addon('plugin.video.amazon')
pluginpath = addon.getAddonInfo('path')

pluginhandle = int(sys.argv[1])

COOKIEFILE = os.path.join(xbmc.translatePath(pluginpath),'resources','cache','cookies.lwp')

BASE_URL = 'http://www.amazon.de'
                     
class _Info:
    def __init__( self, *args, **kwargs ):
        print "common.args"
        print kwargs
        self.__dict__.update( kwargs )
exec "args = _Info(%s)" % urllib.unquote_plus(sys.argv[2][1:].replace('&', ', ')).replace('<','"').replace('>','"')

def getURL( url , host='www.amazon.de',useCookie=False):
    print 'getURL: '+url
    cj = cookielib.LWPCookieJar()
    if useCookie and os.path.isfile(COOKIEFILE):
        cj.load(COOKIEFILE, ignore_discard=True, ignore_expires=True)
    opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cj))
    opener.addheaders = [('User-Agent', 'Mozilla/5.0 (Windows NT 6.1; WOW64; Trident/7.0; rv:11.0) like Gecko'),
                         ('Host', host)]
    usock = opener.open(url)#,timeout=30)
    response = usock.read()
    usock.close()
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

def SaveFile(path, data):
    file = open(path,'w')
    file.write(data)
    file.close()

def androidsig(url):
    hmac_key = binascii.unhexlify('f5b0a28b415e443810130a4bcb86e50d800508cc')
    sig = hmac.new(hmac_key, url, sha1)
    return base64.encodestring(sig.digest()).replace('\n','')

def addDir(name, mode, sitemode, url='', thumb='', fanart='', infoLabels=False, totalItems=0, cm=False ,page=1,isHD=False):
    u = '%s?url=<%s>&mode=<%s>&sitemode=<%s>&name=<%s>&page=<%s>' % (sys.argv[0], urllib.quote_plus(url), mode, sitemode, urllib.quote_plus(name), urllib.quote_plus(str(page)))
    if fanart == '' or fanart == None:
        try:fanart = args.fanart
        except:fanart = os.path.join(addon.getAddonInfo('path'),'fanart.jpg')
    else:u += '&fanart=<%s>' % urllib.quote_plus(fanart)
    if thumb == '' or thumb == None:
        try:thumb = args.thumb
        except:thumb = os.path.join(addon.getAddonInfo('path'),'icon.png')
    else:u += '&thumb=<%s>' % urllib.quote_plus(thumb)
    item=xbmcgui.ListItem(name, iconImage="DefaultFolder.png", thumbnailImage=thumb)
    item.setProperty('fanart_image',fanart)
    item.setProperty('IsPlayable', 'false')
    try: 
        item.setProperty('TotalSeasons', str(infoLabels['TotalSeasons']))
    except: pass
    if infoLabels:
        item.setInfo(type='Video', infoLabels=infoLabels)
    if cm:
        item.addContextMenuItems( cm, replaceItems=True  )
    xbmcplugin.addDirectoryItem(handle=pluginhandle,url=u,listitem=item,isFolder=True,totalItems=totalItems)

def addVideo(name,asin,poster='',fanart='',infoLabels=False,totalItems=0,cm=False,trailer=False,isAdult=False,isHD=False):
    if not infoLabels:
        infoLabels={ "Title": name}
    u  = '%s?asin=<%s>&mode=<play>&name=<%s>&sitemode=<PLAYVIDEO>&adult=<%s>' % (sys.argv[0], asin, urllib.quote_plus(name), str(isAdult))
    if trailer:
        infoLabels['Trailer'] = u + '&trailer=<1>'
    u += '&trailer=<0>'
    try:
	liz=xbmcgui.ListItem(name, thumbnailImage=poster)
    except:
	liz=xbmcgui.ListItem(name)
    liz.setInfo(type='Video', infoLabels=infoLabels)
    try:
        if fanart <> '' or fanart <> None:
            liz.setProperty('fanart_image',fanart)
    except:
        print 'invalid fanart'
    liz.setProperty('IsPlayable', 'false')
    if isHD:
        liz.addStreamInfo('video', { 'width':1280 ,'height' : 720 })
    else:
        liz.addStreamInfo('video', { 'width':720 ,'height' : 576 })
    if infoLabels['AudioChannels']: liz.addStreamInfo('audio', { 'codec': 'ac3' ,'channels': int(infoLabels['AudioChannels']) })
    if cm:
        liz.addContextMenuItems( cm , replaceItems=True )
    xbmcplugin.addDirectoryItem(handle=pluginhandle,url=u,listitem=liz,isFolder=False,totalItems=totalItems)     

def addText(name):
    item = xbmcgui.ListItem(name)
    item.setProperty('IsPlayable', 'false')
    xbmcplugin.addDirectoryItem(handle=pluginhandle,url=sys.argv[0],listitem=item)

def setCustomer(check=False):
    if check:
        url = 'http://www.amazon.de'
        data = getURL(url,useCookie=True)
        customerId = re.compile('"customerId":"(.*?)"').findall(data)[0]
        if customerId <> addon.getSetting("customerId"):
            addon.setSetting("customerId",customerId)
            return False
        else:
            return True
    elif addon.getSetting("customerId"):
        return addon.getSetting("customerId")
    else:
        url = 'http://www.amazon.de'
        data = getURL(url,useCookie=True)
        customerId = re.compile('"customerId":"(.*?)"').findall(data)[0]
        addon.setSetting("customerId",customerId)
        return customerId

def addMovieWatchlist():
    addWatchlist('movie')

def addTVWatchlist():
    addWatchlist('tv')

def addWatchlist(prodType,asin=False):
    if not asin:
        asin=args.asin
    #customerid=setCustomer()
    url = 'http://www.amazon.de/gp/video/watchlist/ajax/hoverbubble.html?ASIN='+asin
    data = getURL(url,useCookie=True)
    tree = BeautifulSoup(data, convertEntities=BeautifulSoup.HTML_ENTITIES)
    form = tree.find('form',attrs={'id':'watchlistForm'})
    token = form.find('input',attrs={'id':'token'})['value']
    url = 'http://www.amazon.de/gp/video/watchlist/ajax/addRemove.html'
    url += '?dataType=json'
    #url += '&addItem=0'
    url += '&ASIN='+asin
    url += '&token='+token
    url += '&prodType='+prodType #movie or tv
    data = getURL(url,useCookie=True)
    json = demjson.decode(data)
    if json['AsinStatus'] == '0':
        getURL(url,useCookie=True)

def removeMovieWatchlist():
    removeWatchlist('movie')

def removeTVWatchlist():
    removeWatchlist('tv')

def removeWatchlist(prodType,asin=False):
    if not asin:
        asin=args.asin
    #customerid=setCustomer()
    url = 'http://www.amazon.de/gp/video/watchlist/ajax/hoverbubble.html?ASIN='+asin
    data = getURL(url,useCookie=True)
    tree = BeautifulSoup(data, convertEntities=BeautifulSoup.HTML_ENTITIES)
    form = tree.find('form',attrs={'id':'watchlistForm'})
    token = form.find('input',attrs={'id':'token'})['value']
    url = 'http://www.amazon.de/gp/video/watchlist/ajax/addRemove.html'
    url += '?dataType=json'
    url += '&ASIN='+asin
    url += '&token='+token
    url += '&prodType='+prodType #movie or tv
    data = getURL(url,useCookie=True)
    json = demjson.decode(data)
    if json['AsinStatus'] == '1':
        getURL(url,useCookie=True)
        
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
    try:
        if os.path.isfile(COOKIEFILE):
            os.remove(COOKIEFILE)
        cj = cookielib.LWPCookieJar()
        br = mechanize.Browser()  
        br.set_handle_robots(False)
        br.set_cookiejar(cj)
        br.addheaders = [('User-agent', 'Mozilla/4.0 (compatible; MSIE 8.0; Windows NT 6.1)')]  
        sign_in = br.open("http://www.amazon.de/gp/flex/sign-out.html") 
        br.select_form(name="sign-in")  
        br["email"] = addon.getSetting("login_name")
        br["password"] = addon.getSetting("login_pass")
        logged_in = br.submit()  
        error_str = "The e-mail address and password you entered do not match any accounts on record."  
        if error_str in logged_in.read():
            xbmcgui.Dialog().ok('Login Error',error_str)
            print error_str
            return True
        else:
            cj.save(COOKIEFILE, ignore_discard=True, ignore_expires=True)
            #setCustomer(check=True)
            gen_id()
            return True
    except:
        return False
        
def cleanData(data):
    if type(data) == type(str()) or type(data) == type(unicode()):
        if data.replace('-','').strip() == '': data = ''
        data = data.replace(u'\u00A0', ' ') #non-breaking space
        data = data.strip()
        if data == '': data = None
    return data