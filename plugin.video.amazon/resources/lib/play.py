#!/usr/bin/env python
# -*- coding: utf-8 -*-
import re
import time
import urllib
import demjson
import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import os
import subprocess
import resources.lib.common as common

from BeautifulSoup import BeautifulStoneSoup
from BeautifulSoup import BeautifulSoup

try:
    from xml.etree import ElementTree
except:
    from elementtree import ElementTree
    
pluginhandle = common.pluginhandle
settings = xbmcaddon.Addon( id = 'plugin.video.amazon' )
userinput = os.path.join(common.pluginpath, 'tools', 'userinput.exe' )
waitsec = int(settings.getSetting("clickwait")) * 1000
pin = settings.getSetting("pin")
waitpin = int(settings.getSetting("waitpin")) * 1000
osLinux = xbmc.getCondVisibility('system.platform.linux')
osOsx = xbmc.getCondVisibility('system.platform.osx')
osWin = xbmc.getCondVisibility('system.platform.windows')
screenWidth = int(xbmc.getInfoLabel('System.ScreenWidth'))
screenHeight = int(xbmc.getInfoLabel('System.ScreenHeight'))
trailer = common.args.trailer
selbitrate = common.args.selbitrate
isAdult = int(common.args.adult)
playPlugin = ['','plugin.program.browser.launcher', 'plugin.program.chrome.launcher']
selPlugin = playPlugin[int(settings.getSetting("playmethod"))]
amazonUrl = common.BASE_URL + "/dp/" + common.args.asin
Dialog = xbmcgui.Dialog()

def PLAYVIDEO():
    global amazonUrl
    if trailer == '1':
        if selPlugin == '':
            PLAYTRAILER()
            return
        amazonUrl += "/?autoplaytrailer=1"
    else:
        if selPlugin == '':
            PLAYVIDEOINT()
            return
        amazonUrl += "/?autoplay=1"
    kiosk = 'yes'
    if settings.getSetting("kiosk") == 'false': kiosk = 'no'
    
    xbmc.executebuiltin('RunPlugin(plugin://%s/?url=%s&mode=showSite&kiosk=%s)' % (selPlugin, urllib.quote_plus(amazonUrl), kiosk))

    if settings.getSetting("fullscreen") == 'true':
        pininput = 0
        if settings.getSetting("pininput") == 'true': pininput = 1
        input(mousex=-1,mousey=350)
        if isAdult == 1 and pininput == 1:
            xbmc.sleep(int(waitsec*0.75))
            input(keys=pin)
            xbmc.sleep(waitpin)
        else:
            xbmc.sleep(waitsec)
        if isAdult == 0: pininput = 1
        if pininput == 1:
            input(mousex=-1,mousey=350,click=2)
            xbmc.sleep(500)
            #input(mousex=9999,mousey=0)


def input(mousex=0,mousey=0,click=0,keys=False,delay='200'):
    if mousex == -1: mousex = screenWidth/2
    if mousey == -1: mousey = screenHeight/2
    
    if osWin:
        app = userinput
        mouse = ' mouse %s %s' % (mousex,mousey)
        mclk = ' ' + str(click)
        keybd = ' key %s{Enter} %s' % (keys,delay)
    elif osLinux:
        app = 'xdotool'
        mouse = ' mousemove %s %s' % (mousex,mousey)
        mclk = ' click --repeat %s 1' % click
        keybd = ' type --delay %s %s && xdotool key Return' % (delay, keys)
    elif osOsx:
        app = 'cliclick'
        mouse = ' m:'
        if click == 1: mouse = ' c:'
        elif click == 2: mouse = ' dc:'
        mouse += '%s,%s' % (mousex,mousey)
        mclk = ''
        keybd = ' -w %s t:%s kp:return' % (delay, keys)

    if keys:
        cmd = app + keybd
    else:
        cmd = app + mouse
        if click: cmd += mclk
    subprocess.Popen(cmd, shell=True)

def GETSUBTITLES(suc, data):
    if not suc: return
    subtitleLanguages = data['subtitles']['content']['languages']
    if len(subtitleLanguages) > 0:
        subtitleUrl = subtitleLanguages[0]['url']
        subtitles = CONVERTSUBTITLES(subtitleUrl)
        common.SaveFile(os.path.join(common.pldatapath,values['asin']+'.srt'), subtitles)

def CONVERTSUBTITLES(url):
    xml=common.getURL(url)
    tree = BeautifulStoneSoup(xml, convertEntities=BeautifulStoneSoup.XML_ENTITIES)
    lines = tree.find('tt:body').findAll('tt:p')
    stripTags = re.compile(r'<.*?>',re.DOTALL)
    spaces = re.compile(r'\s\s\s+')
    srt_output = ''
    count = 1
    displaycount = 1
    for line in lines:
        sub = line.renderContents()
        sub = stripTags.sub(' ', sub)
        sub = spaces.sub(' ', sub)
        sub = sub.decode('utf-8')
        start = line['begin'].replace('.',',')
        if count < len(lines):
            end = line['end'].replace('.',',')
        line = str(displaycount)+"\n"+start+" --> "+end+"\n"+sub+"\n\n"
        srt_output += line
        count += 1
        displaycount += 1
    return srt_output.encode('utf-8')

def SETSUBTITLES(asin):
    subtitles = os.path.join(common.pldatapath, asin+'.srt')
    if os.path.isfile(subtitles) and xbmc.Player().isPlaying():
        print "AMAZON --> Subtitles Enabled."
        xbmc.Player().setSubtitles(subtitles)
    elif xbmc.Player().isPlaying():
        print "AMAZON --> No Subtitles File Available."
    else:
        print "AMAZON --> No Media Playing. Subtitles Not Assigned."

def GETTRAILERS(suc, rtmpdata):
    if suc:
        sessionId = rtmpdata['streamingURLInfoSet']['sessionId']
        cdn = rtmpdata['streamingURLInfoSet']['cdn']
        rtmpurls = rtmpdata['streamingURLInfoSet']['streamingURLInfo']
        title = rtmpdata['metadata']['title'].replace('[HD]','')
        return rtmpurls, sessionId, cdn, title
    else:
        return False, False, False, rtmpdata

def PLAYTRAILER():
    swfUrl, values = GETFLASHVARS(amazonUrl) 
    if swfUrl == False:        
        return

    rtmpurls, streamSessionID, cdn, videoname = GETTRAILERS(*getUrldata('GetStreamingTrailerUrls', values, useCookie=True))
    if rtmpurls == False:
        Dialog.ok('No Trailer available','')
    elif cdn == 'limelight':
        Dialog.ok('Limelight CDN','Limelight uses swfverfiy2. Playback may fail.')
    else:
        PLAY(rtmpurls, swfUrl=swfUrl, Trailer=True, title=videoname)
        
def GETSTREAMS(suc, rtmpdata):
    if not suc:
        return False, False, False, rtmpdata
    drm = rtmpdata['urlSets']['streamingURLInfoSet'][0]['drm']
    if drm <> 'NONE':
        Dialog.ok('DRM Detected','This video uses %s DRM' % drm)

    sessionId = rtmpdata['urlSets']['streamingURLInfoSet'][0]['sessionId']
    cdn = rtmpdata['urlSets']['streamingURLInfoSet'][0]['cdn']
    rtmpurls = rtmpdata['urlSets']['streamingURLInfoSet'][0]['streamingURLInfo']
    title = rtmpdata['metadata']['title'].replace('[HD]','')
    return rtmpurls, sessionId, cdn, title

def PLAYVIDEOINT():
    if not os.path.isfile(common.COOKIEFILE):
        common.mechanizeLogin()
    swfUrl, values = GETFLASHVARS(amazonUrl)
    if not swfUrl:        
        return
    
    if common.addon.getSetting("enable_captions")=='true':
        GETSUBTITLES(*getUrldata('GetSubtitleUrls', values, opt='&NumberOfResults=1&videoType=content', useCookie=True))
    
    rtmpurls, streamSessionID, cdn, title = GETSTREAMS(*getUrldata('GetStreamingUrlSets', values, useCookie=True))
    if not rtmpurls:
        Dialog.notification("Wiedergabe nicht möglich", title, xbmcgui.NOTIFICATION_ERROR)
        return
    if cdn == 'limelight':
        Dialog.ok('Limelight CDN','Limelight uses swfverfiy2. Playback may fail.')
    if rtmpurls:
        basertmp, ip = PLAY(rtmpurls,swfUrl=swfUrl,title=title)
        if basertmp:
            if common.addon.getSetting("enable_captions")=='true':
                while not xbmc.Player().isPlaying():
                    xbmc.sleep(100)
                SETSUBTITLES(values['asin'])
            
def GETFLASHVARS(pageurl):
    showpage = common.getURL(pageurl, useCookie=True)
    flashVars = re.compile('var config = (.*?);',re.DOTALL).findall(showpage)
    flashVars = demjson.decode(unicode(flashVars[0], errors='ignore'))
    values = flashVars['player']['fl_config']['initParams']
    swfUrl = flashVars['player']['fl_config']['playerSwf']
    csrfToken = urllib.quote_plus(flashVars['general']['csrfToken'])
    values['deviceTypeID'] = flashVars['customer']['deviceTypeId']
    values['deviceID'] = flashVars['customer']['deviceId']
    #values['deviceTypeID']  = 'A13Q6A55DBZB7M'
    values['deviceTypeID']  = 'A324MFXUEZFF7B' # GoogleTV
    #values['deviceTypeID']  = 'A2EUQ1WTGCTBG2'
    #values['userAgent']     = "GoogleTV 162671"
    values['deviceID']      = values['customer'] + str(int(time.time() * 1000)) + values['asin']
    pltoken = common.getURL(common.BASE_URL + "/gp/video/streaming/player-token.json?callback=jQuery&csrftoken=" + csrfToken, useCookie=True)
    try:
        values['token']  = re.compile('"([^"]*).*"([^"]*)"').findall(pltoken)[0][1]
    except:
        Dialog.notification("Fehler beim Login, bitte Benutzername und Passwort überprüfen", "Amazon", xbmcgui.NOTIFICATION_ERROR)
        return False, False
    return swfUrl, values
        
def PLAY(rtmpurls,swfUrl,Trailer=False,title=False):
    lbitrate = int(common.addon.getSetting("bitrate"))
    if selbitrate == '1':
        lbitrate = -1
    mbitrate = 0
    streams = []
    for data in rtmpurls:
        url = data['url']
        bitrate = float(data['bitrate'])
        videoquality = data['contentQuality']
        audioquality = data['audioCodec']
        try:
            formatsplit = re.compile("_video_([^_]*)_.*_audio_([^_]*)_([0-9a-zA-Z]*)").findall(url)
            videoquality += ' ' + formatsplit[0][0]
            audioquality += ' ' + formatsplit[0][2]
        except: pass
        if lbitrate <= 0:
            streams.append([bitrate,url,videoquality,audioquality])
        elif bitrate >= mbitrate and bitrate <= lbitrate:
            mbitrate = bitrate
            rtmpurl = url

    if lbitrate <= 0:
        streamsout = []
        for stream in streams:
            if stream[0] > 999: 
                streamsout.append(str(stream[0]/1000)+' Mbps - '+stream[2]+', '+stream[3])
            else: 
                streamsout.append(str(int(stream[0]))+' Kbps - '+stream[2]+', '+stream[3])
        quality = Dialog.select('Stream Qualität auswählen:', streamsout)
        if quality!=-1:
            mbitrate = streams[quality][0]
            rtmpurl = streams[quality][1]
        else:
            return False, False
    
    rtmpurlSplit = re.compile("([^:]*):\/\/([^\/]+)\/([^\/]+)\/([^\?]+)(\?.*)?").findall(rtmpurl)[0]
    protocol = rtmpurlSplit[0]
    hostname = rtmpurlSplit[1]
    appName =  rtmpurlSplit[2]
    stream = rtmpurlSplit[3]
    auth = rtmpurlSplit[4]

    basertmp = protocol[0:-1] + '://' + hostname + '/' + appName

    if 'edgefcs' in hostname:
        basertmp += auth
    else:
        stream += auth

    finalUrl = '%s app=%s swfUrl=%s pageUrl=%s playpath=%s swfVfy=true' % (basertmp, appName, swfUrl, amazonUrl, stream)
    infoLabels = GetStreamInfo(common.args.asin, title)
    item = xbmcgui.ListItem(path=finalUrl)
    if Trailer:
        infoLabels['Title'] += ' (Trailer)'
    item.setInfo(type="Video", infoLabels=infoLabels)
    if Trailer or lbitrate == -1:
        item.setProperty('IsPlayable', 'true')
        xbmc.Player().play(finalUrl, item)
    else:
        xbmcplugin.setResolvedUrl(pluginhandle, True, item)
    return basertmp, hostname

def GetStreamInfo(asin, finalname):
    import movies
    import listmovie
    import tv
    import listtv
    moviedata = movies.lookupMoviedb(asin)
    if moviedata:
        return listmovie.ADD_MOVIE_ITEM(moviedata, onlyinfo=True)
    else:
        epidata = tv.lookupTVdb(asin)
        if epidata:
            return listtv.ADD_EPISODE_ITEM(epidata, onlyinfo=True)
    return {'Title': finalname}
    
def getUrldata(mode, values, format='json', version=1, firmware='WIN%2016,0,0,235%20PlugIn', opt='', useCookie=False):
    url  = common.ATV_URL + '/cdp/catalog/' + mode
    url += '?asin=' + values['asin']
    url += '&deviceTypeID=' + values['deviceTypeID']
    url += '&firmware=' + firmware
    url += '&customerID=' + values['customer']
    url += '&deviceID=' + values['deviceID']
    url += '&marketplaceID=' + values['marketplace']
    url += '&token=' + values['token']
    url += '&format=' + format
    url += '&version=' + str(version)
    url += '&xws-fa-ov=true'
    url += opt
    data = common.getURL(url, common.ATV_URL.split('//')[1], useCookie=useCookie)
    if data:
        jsondata = demjson.decode(data)
        del data
        if jsondata['message']['statusCode'] != "SUCCESS":
            return False, Error(jsondata['message']['body']['code'])
        return True, jsondata['message']['body']
    return False, 'HTTP Fehler'

def Error(code):
    if 'CDP.InvalidRequest' in code:
        return 'Fehler bei der Suchanfrage'
    elif 'CDP.Playback.NoAvailableStreams' in code:
        return 'Keine Streams zu diesen Video verfügbar, möglicherweise Datenbank veraltet'
    elif 'CDP.Playback.NotOwned' in code:
        return 'Produkt nicht erworben oder Datenbank veraltet'
    elif 'CDP.Authorization.InvalidGeoIP' in code:
        return 'Dieses Video ist in diesen Land nicht verfügbar'
    elif 'CDP.Playback.TemporarilyUnavailable' in code:
        return 'Wiedergabe momentan nicht verfügbar, später erneut versuchen'
    else:
        print code
        return 'Unbekannt: ' + code