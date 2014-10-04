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
userinput = os.path.join( settings.getAddonInfo( 'path' ), 'amazonscript\\' )+"userinput.exe"
waitsec = int(settings.getSetting("clickwait")) * 1000
pin = settings.getSetting("pin")
waitpin = int(settings.getSetting("waitpin")) * 1000
osLinux = xbmc.getCondVisibility('system.platform.linux')
osOsx = xbmc.getCondVisibility('system.platform.osx')
osWin = xbmc.getCondVisibility('system.platform.windows')

def PLAYVIDEO():
    xbmc.Player().stop()
    dialog = xbmcgui.Dialog()
    ok = True
    kiosk = 'yes'
    if settings.getSetting("kiosk") == 'false':
        kiosk = 'no'
    url = common.args.url
    isAdult = int(common.args.adult)
    pininput = 0
    if settings.getSetting("pininput") == 'true': pininput = 1
    if settings.getSetting("browser") == '1':
        xbmc.executebuiltin("RunPlugin(plugin://plugin.program.chrome.launcher/?url="+urllib.quote_plus(url)+"&mode=showSite&kiosk="+kiosk+")")
    else:
        xbmc.executebuiltin("RunPlugin(plugin://plugin.program.browser.launcher/?url="+urllib.quote_plus(url)+"&mode=showSite&kiosk="+kiosk+")")
    xbmc.sleep(waitsec)
    if osWin:
        subprocess.Popen(userinput + ' mouse -1 350')
        if isAdult == 1 and pininput == 1:
            subprocess.Popen(userinput + ' key ' + pin + '{Enter} 200')
            xbmc.sleep(waitpin)
        if isAdult == 0: pininput = 1
        if pininput == 1:
            subprocess.Popen(userinput + ' mouse -1 350 2')
            xbmc.sleep(500)
            subprocess.Popen(userinput + ' mouse 9999 0')
    if osLinux:
        try:
            subprocess.Popen('xdotool mousemove 9999 0 click 1', shell=True)
            xbmc.sleep(5000)
            subprocess.Popen('xdotool mousemove 9999 0 click 1', shell=True)
            xbmc.sleep(5000)
            subprocess.Popen('xdotool mousemove 9999 0 click 1', shell=True)
            xbmc.sleep(5000)
            subprocess.Popen('xdotool mousemove 9999 0 click 1', shell=True)
        except: pass
    if osOsx:
        try:
            subprocess.Popen('cliclick c:500,500', shell=True)
            xbmc.sleep(5000)
            subprocess.Popen('cliclick c:500,500', shell=True)
            xbmc.sleep(5000)
            subprocess.Popen('cliclick c:500,500', shell=True)
            xbmc.sleep(5000)
            subprocess.Popen('cliclick c:500,500', shell=True)
        except: pass

