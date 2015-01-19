#!/usr/bin/env python
# -*- coding: utf-8 -*-
import re
import time
import urllib
import demjson
import xbmcplugin
import xbmc
import xbmcaddon
import xbmcgui
import os
import subprocess
import sys
import resources.lib.common as common

from BeautifulSoup import BeautifulStoneSoup
from BeautifulSoup import BeautifulSoup

try:
    from xml.etree import ElementTree
except:
    from elementtree import ElementTree

settings = xbmcaddon.Addon( id = 'plugin.video.amazon' )
userinput = os.path.join(common.pluginpath, 'tools', 'userinput.exe' )
waitsec = int(settings.getSetting("clickwait")) * 1000
pin = settings.getSetting("pin")
waitpin = int(settings.getSetting("waitpin")) * 1000
osLinux = xbmc.getCondVisibility('system.platform.linux')
osOsx = xbmc.getCondVisibility('system.platform.osx')
osWin = xbmc.getCondVisibility('system.platform.windows')
playPlugin = ['','plugin.program.browser.launcher', 'plugin.program.chrome.launcher']
screenWidth = int(xbmc.getInfoLabel('System.ScreenWidth'))
screenHeight = int(xbmc.getInfoLabel('System.ScreenHeight'))
amazonurl = common.BASE_URL + "/dp/" + common.args.asin
trailer = common.args.trailer
selbitrate = common.args.selbitrate
isAdult = int(common.args.adult)
selPlugin = playPlugin[int(settings.getSetting("playmethod"))]
xbmc.Player().stop()

def PLAYVIDEO():
    kiosk = 'yes'
    if settings.getSetting("kiosk") == 'false': kiosk = 'no'
    if trailer == '1':
        if selPlugin == '':
            PLAYTRAILER()
            return
        amazonurl += "/?autoplaytrailer=1"
    else:
        if selPlugin == '':
            PLAYVIDEOINT()
            return
        amazonurl += "/?autoplay=1"
    
    xbmc.executebuiltin("RunPlugin(plugin://" + selPlugin + "/?url=" + urllib.quote_plus(amazonurl) + "&mode=showSite&kiosk=" + kiosk + ")")

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
    print cmd
    subprocess.Popen(cmd, shell=True)

def GETSUBTITLES(values):
    getsubs  = 'https://atv-ps-eu.amazon.com/cdp/catalog/GetSubtitleUrls'
    getsubs += '?NumberOfResults=1'
    getsubs += '&firmware=WIN%2016,0,0,235%20PlugIn'
    getsubs += '&deviceTypeID='+values['deviceTypeID']
    getsubs += '&customerID='+values['customerID']
    getsubs += '&deviceID='+values['deviceID']
    getsubs += '&format=json'
    getsubs += '&asin='+values['asin']
    getsubs += '&version=2'
    getsubs += '&token='+values['token']
    getsubs += '&videoType=content'
    data = common.getURL(getsubs,'atv-ps-eu.amazon.com',useCookie=True)
    subtitleLanguages = demjson.decode(data)['message']['body']['subtitles']['content']['languages']
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

def GETTRAILERS(getstream):
    data = common.getURL(getstream,'atv-ps-eu.amazon.com')
    rtmpdata = demjson.decode(data)
    if rtmpdata['message']['statusCode'] == "SUCCESS":
        sessionId = rtmpdata['message']['body']['streamingURLInfoSet']['sessionId']
        cdn = rtmpdata['message']['body']['streamingURLInfoSet']['cdn']
        rtmpurls = rtmpdata['message']['body']['streamingURLInfoSet']['streamingURLInfo']
        title = rtmpdata['message']['body']['metadata']['title'].replace('[HD]','')
        return rtmpurls, sessionId, cdn, title
    else:
        return False, False, False

def PLAYTRAILER():
    swfUrl, values, owned = GETFLASHVARS(amazonurl) 
    if swfUrl == False:        
        return
    values['deviceID'] = values['customerID'] + str(int(time.time() * 1000)) + values['asin']
    getstream  = 'https://atv-ps-eu.amazon.com/cdp/catalog/GetStreamingTrailerUrls'
    getstream += '?asin='+values['asin']
    getstream += '&deviceTypeID='+values['deviceTypeID']
    getstream += '&deviceID='+values['deviceID']
    getstream += '&firmware=WIN%2016,0,0,235%20PlugIn'
    getstream += '&format=json'
    getstream += '&version=1'
    rtmpurls, streamSessionID, cdn, videoname = GETTRAILERS(getstream)
    if rtmpurls == False:
        xbmcgui.Dialog().ok('Kein Trailer verfügbar','')
    elif cdn == 'limelight':
        xbmcgui.Dialog().ok('Limelight CDN','Limelight uses swfverfiy2. Playback may fail.')
    else:
        PLAY(rtmpurls,swfUrl=swfUrl,Trailer=videoname)
        
def GETSTREAMS(getstream):
    data = common.getURL(getstream,'atv-ps-eu.amazon.com',useCookie=True)
    rtmpdata = demjson.decode(data)
    if rtmpdata['message']['statusCode'] != "SUCCESS":
        return False, False, rtmpdata['message']['statusCode'], rtmpdata['message']['body']['code']
       
    drm = rtmpdata['message']['body']['urlSets']['streamingURLInfoSet'][0]['drm']
    if drm <> 'NONE':
        xbmcgui.Dialog().ok('DRM Detected','This video uses %s DRM' % drm)

    sessionId = rtmpdata['message']['body']['urlSets']['streamingURLInfoSet'][0]['sessionId']
    cdn = rtmpdata['message']['body']['urlSets']['streamingURLInfoSet'][0]['cdn']
    rtmpurls = rtmpdata['message']['body']['urlSets']['streamingURLInfoSet'][0]['streamingURLInfo']
    title = rtmpdata['message']['body']['metadata']['title'].replace('[HD]','')
    return rtmpurls, sessionId, cdn, title


def PLAYVIDEOINT():
    if not os.path.isfile(common.COOKIEFILE):
        common.mechanizeLogin()
    swfUrl, values, owned = GETFLASHVARS(amazonurl)
    if swfUrl == False:        
        return
    values['deviceID'] = values['customerID'] + str(int(time.time() * 1000)) + values['asin']
    
    if common.addon.getSetting("enable_captions")=='true':
        GETSUBTITLES(values)
    getstream  = 'https://atv-ps-eu.amazon.com/cdp/catalog/GetStreamingUrlSets'
    getstream += '?asin='+values['asin']
    getstream += '&deviceTypeID='+values['deviceTypeID']
    getstream += '&firmware=WIN%2016,0,0,235%20PlugIn'
    getstream += '&customerID='+values['customerID']
    getstream += '&deviceID='+values['deviceID']
    getstream += '&token='+values['token']
    getstream += '&format=json'
    getstream += '&version=1'
    
    rtmpurls, streamSessionID, cdn, title = GETSTREAMS(getstream)
    if not rtmpurls:
        xbmcgui.Dialog().ok("Fehler beim Laden, bitte Datenbank aktualisieren\n%s: %s" % (cdn,title), "Amazon")
        return
    if cdn == 'limelight':
        xbmcgui.Dialog().ok('Limelight CDN','Limelight uses swfverfiy2. Playback may fail.')
    if rtmpurls <> False:
        basertmp, ip = PLAY(rtmpurls,swfUrl=swfUrl,title=title)
        if basertmp:
            """if values['pageType'] == 'movie':
                import movies as moviesDB
                moviesDB.watchMoviedb(values['asin'])
            if values['pageType'] == 'tv':
                import tv as tvDB
                tvDB.watchEpisodedb(values['asin'])
            """    
            if common.addon.getSetting("enable_captions")=='true':
                while not xbmc.Player().isPlaying():
                    xbmc.sleep(100)
                SETSUBTITLES(values['asin'])
            
def GETFLASHVARS(pageurl):
    swfUrl = ''
    showpage = common.getURL(pageurl,useCookie=True)
    #print showpage
    flashVars = re.compile('var config = {"general":{(.*?)}.*"fl_config":{"initParams":{(.*?)}(.*?){',re.DOTALL).findall(showpage)
    flashVars =(flashVars[0][0] + flashVars[0][1] + flashVars[0][2]).split(',')

    values={'token'          :'',
            'deviceTypeID'   :'A13Q6A55DBZB7M',
            #'deviceTypeID'   :'A324MFXUEZFF7B', # GoogleTV
            'version'        :'1',
            'firmware'       :'1',       
            'customerID'     :'',
            'format'         :'json',
            'deviceID'       :'',
            'asin'           :''      
            }
    if '<div class="avod-post-purchase">' in showpage:
        owned=True
    else:
        owned=False
    for item in flashVars:
        item = item.replace('"','').split(':',1)
        if item[0]      == 'csrfToken':
            csrfToken               = urllib.quote_plus(item[1])
        elif item[0]    == 'customer':
            values['customerID']    = item[1]
        elif item[0]    == 'ASIN':
            values['asin']          = item[1]
        elif item[0]    == 'pageType':
            values['pageType']      = item[1]        
        elif item[0]    == 'UBID':
            values['UBID']          = item[1]
        elif item[0]    == 'sessionID':
            values['sessionID']     = item[1]
        elif item[0]    == 'userAgent':
            values['userAgent']     = item[1]
            #values['userAgent']     = "GoogleTV 162671"
        elif item[0]    == 'playerSwf':
            swfUrl                  = item[1]
            
    pltoken = common.getURL("https://www.amazon.de/gp/video/streaming/player-token.json?callback=jQuery&csrftoken=" + csrfToken, useCookie=True)
    print pltoken
    try:
        values['token']  = re.compile('"([^"]*).*"([^"]*)"').findall(pltoken)[0][1]
    except:
        xbmcgui.Dialog().ok("Fehler beim Laden, bitte später erneut versuchen", "Amazon")
        return False, False, False
    return swfUrl, values, owned
        
def PLAY(rtmpurls,swfUrl,Trailer=False,title=False):
    lbitrate = int(common.addon.getSetting("bitrate"))
    if common.args.selbitrate == '1':
        lbitrate = 0
    mbitrate = 0
    streams = []
    for data in rtmpurls:
        url = data['url']
        bitrate = float(data['bitrate'])
        videoquality = data['contentQuality']
        audioquality = data['audioCodec']
        formatsplit = re.compile("_video_([^_]*)_.*_audio_([^_]*)_([0-9a-zA-Z]*)").findall(url)
        try:
            videoquality += ' ' + formatsplit[0][0]
            audioquality += ' ' + formatsplit[0][2]
        except: pass
        if lbitrate == 0:
            streams.append([bitrate,url,videoquality,audioquality])
        elif bitrate >= mbitrate and bitrate <= lbitrate:
            mbitrate = bitrate
            rtmpurl = url

    if lbitrate == 0:
        streamsout = []
        for stream in streams:
            if stream[0] > 999: 
                streamsout.append(str(stream[0]/1000)+' Mbps - '+stream[2]+', '+stream[3])
            else: 
                streamsout.append(str(int(stream[0]))+' Kbps - '+stream[2]+', '+stream[3])
        quality=xbmcgui.Dialog().select('Stream Qualität auswählen:', streamsout)
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
        
    basertmp = 'rtmp://'+hostname+'/'+appName

    if 'edgefcs' in hostname:
        basertmp += auth
    else:
        stream += auth

    if Trailer:
        finalname = 'Trailer - ' + Trailer
    else:
        finalname = title
    
    finalUrl = '%s app=%s swfUrl=%s pageUrl=%s playpath=%s swfVfy=true' % (basertmp, appName, swfUrl, amazonurl, stream)
    item = xbmcgui.ListItem(finalname, path=finalUrl)
    item.setInfo( type="Video", infoLabels={ "Title": finalname})
    item.setProperty('IsPlayable', 'true')
    print xbmc.Player().play(finalUrl, item)
    """
    item = xbmcgui.ListItem(path=basertmp)
    item.setProperty('PlayPath', stream)
    item.setProperty('app', appName)
    item.setProperty('swfUrl', swfUrl)
    item.setProperty('pageUrl', amazonurl)
    item.setProperty('swfVfy', 'true')
    xbmcplugin.setResolvedUrl(common.pluginhandle, True, item)
    """
    return basertmp, hostname
