#!/usr/bin/env python
# -*- coding: utf-8 -*-
import time
import subprocess
import common
import random

from BeautifulSoup import BeautifulStoneSoup
from BeautifulSoup import BeautifulSoup

try:
    from xml.etree import ElementTree
except:
    from elementtree import ElementTree
    
pluginhandle = common.pluginhandle
xbmc = common.xbmc
xbmcplugin = common.xbmcplugin
urllib = common.urllib
urllib2 = common.urllib2
sys = common.sys
xbmcgui = common.xbmcgui
re = common.re
demjson = common.demjson
settings = common.addon
os = common.os
hashlib = common.hashlib

userinput = os.path.join(common.pluginpath, 'tools', 'userinput.exe' )
waitsec = int(settings.getSetting("clickwait")) * 1000
pin = settings.getSetting("pin")
waitpin = int(settings.getSetting("waitpin")) * 1000
waitprepin = int(settings.getSetting("waitprepin")) * 1000
osLinux = xbmc.getCondVisibility('system.platform.linux')
osOsx = xbmc.getCondVisibility('system.platform.osx')
osWin = xbmc.getCondVisibility('system.platform.windows')
screenWidth = int(xbmc.getInfoLabel('System.ScreenWidth'))
screenHeight = int(xbmc.getInfoLabel('System.ScreenHeight'))
playPlugin = ['plugin.program.browser.launcher', 'plugin.program.chrome.launcher']
selPlugin = playPlugin[int(settings.getSetting("playmethod"))]
StrProt = int(settings.getSetting("protocol"))
trailer = common.args.trailer
selbitrate = common.args.selbitrate
isAdult = int(common.args.adult)
amazonUrl = common.BASE_URL + "/dp/" + common.args.asin
Dialog = xbmcgui.Dialog()
Player = xbmc.Player()

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
    
    url = 'plugin://%s/?url=%s&mode=showSite&kiosk=%s' % (selPlugin, urllib.quote_plus(amazonUrl), kiosk)
    common.Log('Run plugin: %s' % url)
    xbmc.executebuiltin('RunPlugin(%s)' % url)

    pininput = 0
    fullscr = 0
    if settings.getSetting("pininput") == 'true': pininput = 1
    if settings.getSetting("fullscreen") == 'true': fullscr = 1

    if isAdult == 1 and pininput == 1:
        if fullscr == 1: waitsec = waitsec*0.75 
        else: waitsec = waitprepin
        xbmc.sleep(int(waitsec))
        Input(keys=pin)
        if fullscr == 1: xbmc.sleep(waitpin)
        
    if fullscr == 1:
        xbmc.sleep(waitsec)
        Input(mousex=-1,mousey=350)
        if isAdult == 0: pininput = 1
        if pininput == 1:
            Input(mousex=-1,mousey=350,click=2)
            xbmc.sleep(500)
            Input(mousex=9999,mousey=350)

def Input(mousex=0,mousey=0,click=0,keys=False,delay='200'):
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