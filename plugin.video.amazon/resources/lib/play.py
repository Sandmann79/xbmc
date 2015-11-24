#!/usr/bin/env python
# -*- coding: utf-8 -*-
import subprocess
import common
import random

pluginhandle = common.pluginhandle
xbmc = common.xbmc
xbmcplugin = common.xbmcplugin
urllib = common.urllib
urllib2 = common.urllib2
sys = common.sys
xbmcgui = common.xbmcgui
re = common.re
demjson = common.demjson
addon = common.addon
os = common.os
hashlib = common.hashlib
Dialog = xbmcgui.Dialog()
osLinux = xbmc.getCondVisibility('system.platform.linux')
osOsx = xbmc.getCondVisibility('system.platform.osx')
osWin = xbmc.getCondVisibility('system.platform.windows')
    
def PLAYVIDEO():
    waitsec = int(addon.getSetting("clickwait")) * 1000
    pin = addon.getSetting("pin")
    waitpin = int(addon.getSetting("waitpin")) * 1000
    waitprepin = int(addon.getSetting("waitprepin")) * 1000
    playPlugin = ['plugin.program.browser.launcher', 'plugin.program.chrome.launcher', '']
    selPlugin = playPlugin[int(addon.getSetting("playmethod"))]
    scr_path = addon.getSetting("scr_path")
    scr_param = addon.getSetting("scr_param").strip()
    trailer = common.args.trailer
    isAdult = int(common.args.adult)
    amazonUrl = common.BASE_URL + "/dp/" + common.args.asin
    pininput = fullscr = getfr = False
    kiosk = 'yes'
    if addon.getSetting("pininput") == 'true': pininput = True
    if addon.getSetting("fullscreen") == 'true': fullscr = True
    if addon.getSetting("kiosk") == 'false': kiosk = 'no'

    if trailer == '1':
        videoUrl = amazonUrl + "/?autoplaytrailer=1"
    else:
        videoUrl = amazonUrl + "/?autoplay=1"
    
    if selPlugin == '':
        url = scr_path + ' ' + scr_param.replace('{f}', getPlaybackInfo(amazonUrl)).replace('{u}', videoUrl)
        common.Log('Executing: %s' % url)
        if osWin:
            subprocess.Popen(url, startupinfo=getStartupInfo())
        else:
            subprocess.Popen(url, shell=True)            
    else:
        url = 'plugin://%s/?url=%s&mode=showSite&kiosk=%s' % (selPlugin, urllib.quote_plus(videoUrl), kiosk)
        common.Log('Run plugin: %s' % url)
        xbmc.executebuiltin('RunPlugin(%s)' % url)

    if isAdult == 1 and pininput:
        if fullscr: waitsec = waitsec*0.75
        else: waitsec = waitprepin
        xbmc.sleep(int(waitsec))
        Input(keys=pin)
        if fullscr: xbmc.sleep(waitpin)
        
    if fullscr:
        xbmc.sleep(int(waitsec))
        Input(mousex=-1,mousey=350)
        if isAdult == 0: pininput = True
        if pininput:
            Input(mousex=-1,mousey=350,click=2)
            xbmc.sleep(500)
            Input(mousex=9999,mousey=350)

def Input(mousex=0,mousey=0,click=0,keys=False,delay='200'):
    userinput = os.path.join(common.pluginpath, 'tools', 'userinput.exe' )
    screenWidth = int(xbmc.getInfoLabel('System.ScreenWidth'))
    screenHeight = int(xbmc.getInfoLabel('System.ScreenHeight'))

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
    common.Log('Run command: %s' % cmd)
    subprocess.Popen(cmd, shell=True)

def getStartupInfo():
    si = subprocess.STARTUPINFO()
    si.dwFlags = subprocess.STARTF_USESHOWWINDOW
    if addon.getSetting("scr_hide") == 'false': si.wShowWindow = 10
    return si
    
def getStreams(suc, data):
    if not suc:
        return ''
        
    for cdn in data['audioVideoUrls']['avCdnUrlSets']:
        for urlset in cdn['avUrlInfoList']:
            data = common.getURL(urlset['url'])
            fr = eval(re.compile('frameRate="([^"]*)').findall(data)[0])
            if fr < 25: fr = 24
            return str(fr)
            
    return ''
    
def getPlaybackInfo(url):
    if addon.getSetting("framerate") == 'false': return ''
    values = getFlashVars(url)
    if not values: return ''
    return getStreams(*getUrldata('catalog/GetPlaybackResources', values, extra=True))


def getFlashVars(url):
    cookie = common.mechanizeLogin()
    showpage = common.getURL(url, useCookie=cookie)
    #common.WriteLog(showpage, 'flashvars', 'w')
    if not showpage:
        Dialog.notification(common.__plugin__, Error('CDP.InvalidRequest'), xbmcgui.NOTIFICATION_ERROR)
        return False
    values = {}
    search = {'asin'       : '"pageAsin":"(.*?)"',
              'sessionID'  : "ue_sid='(.*?)'",
              'marketplace': "ue_mid='(.*?)'",
              'customer'   : '"customerID":"(.*?)"'}
    if 'var config' in showpage:
        flashVars = re.compile('var config = (.*?);',re.DOTALL).findall(showpage)
        flashVars = demjson.decode(unicode(flashVars[0], errors='ignore'))
        values = flashVars['player']['fl_config']['initParams']
    else:
        for key, pattern in search.items():
            result = re.compile(pattern, re.DOTALL).findall(showpage)
            if result: values[key] = result[0]
    
    for key in values.keys():
        if not values.has_key(key):
            Dialog.notification(common.getString(30200), common.getString(30210), xbmcgui.NOTIFICATION_ERROR)
            return False

    values['deviceTypeID']  = 'AOAGZA014O5RE'
    values['userAgent']     = common.UserAgent
    values['deviceID']      = common.hmac.new(common.UserAgent, common.gen_id(), hashlib.sha224).hexdigest()
    rand = 'onWebToken_' + str(random.randint(0,484))
    pltoken = common.getURL(common.BASE_URL + "/gp/video/streaming/player-token.json?callback=" + rand, useCookie=cookie)
    try:
        values['token']  = re.compile('"([^"]*).*"([^"]*)"').findall(pltoken)[0][1]
    except:
        Dialog.notification(common.getString(30200), common.getString(30201), xbmcgui.NOTIFICATION_ERROR)
        return False
    return values
    
def getUrldata(mode, values, format='json', devicetypeid=False, version=1, firmware='1', opt='', extra=False, useCookie=False):
    if not devicetypeid:
        devicetypeid = values['deviceTypeID']
    url  = common.ATV_URL + '/cdp/' + mode
    url += '?asin=' + values['asin']
    url += '&deviceTypeID=' + devicetypeid
    url += '&firmware=' + firmware
    url += '&customerID=' + values['customer']
    url += '&deviceID=' + values['deviceID']
    url += '&marketplaceID=' + values['marketplace']
    url += '&token=' + values['token']
    url += '&format=' + format
    url += '&version=' + str(version)
    url += opt
    if extra:
        url += '&resourceUsage=ImmediateConsumption&videoMaterialType=Feature&consumptionType=Streaming&desiredResources=AudioVideoUrls&deviceDrmOverride=CENC&deviceStreamingTechnologyOverride=DASH&deviceProtocolOverride=Http&deviceBitrateAdaptationsOverride=CVBR%2CCBR&audioTrackId=all'
    data = common.getURL(url, common.ATV_URL.split('//')[1], useCookie=useCookie)
    if data:
        jsondata = demjson.decode(data)
        del data
        if jsondata.has_key('error'):
            return False, Error(jsondata['error'])
        return True, jsondata
    return False, 'HTTP Fehler'
    
def Error(data):
    code = data['errorCode']
    common.Log('%s (%s) ' %(data['message'], code), xbmc.LOGERROR)
    if 'CDP.InvalidRequest' in code:
        return common.getString(30204)
    elif 'CDP.Playback.NoAvailableStreams' in code:
        return common.getString(30205)
    elif 'CDP.Playback.NotOwned' in code:
        return common.getString(30206)
    elif 'CDP.Authorization.InvalidGeoIP' in code:
        return common.getString(30207)
    elif 'CDP.Playback.TemporarilyUnavailable' in code:
        return common.getString(30208)
    else:
        return '%s (%s) ' %(data['message'], code)
