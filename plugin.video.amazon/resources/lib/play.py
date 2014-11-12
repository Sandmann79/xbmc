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
import resources.lib.common as common
import urllib2

from BeautifulSoup import BeautifulStoneSoup
from BeautifulSoup import BeautifulSoup

try:
    from xml.etree import ElementTree
except:
    from elementtree import ElementTree

settings = xbmcaddon.Addon( id = 'plugin.video.amazon' )
userinput = os.path.join( settings.getAddonInfo( 'path' ), 'amazonscript/userinput.exe' )
waitsec = int(settings.getSetting("clickwait")) * 1000
pin = settings.getSetting("pin")
waitpin = int(settings.getSetting("waitpin")) * 1000
osLinux = xbmc.getCondVisibility('system.platform.linux')
osOsx = xbmc.getCondVisibility('system.platform.osx')
osWin = xbmc.getCondVisibility('system.platform.windows')
browserPlugin = ['plugin.program.browser.launcher', 'plugin.program.chrome.launcher']
screenWidth = int(xbmc.getInfoLabel('System.ScreenWidth'))
screenHeight = int(xbmc.getInfoLabel('System.ScreenHeight'))

def PLAYVIDEO():
    xbmc.Player().stop()
    dialog = xbmcgui.Dialog()
    ok = True
    kiosk = 'yes'
    if settings.getSetting("kiosk") == 'false':
        kiosk = 'no'
    asin = common.args.asin
    trailer = common.args.trailer
    isAdult = int(common.args.adult)
    
    url = common.BASE_URL + "/dp/" + asin
    if trailer == '1':
        url += "/?autoplaytrailer=1"
    else:
        #url += "/ref=_wnzw"
        url += "/?autoplay=1"
    selPlugin = int(settings.getSetting("browser"))
    xbmc.executebuiltin("RunPlugin(plugin://" + browserPlugin[selPlugin] + "/?url=" + urllib.quote_plus(url) + "&mode=showSite&kiosk=" + kiosk + ")")

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
