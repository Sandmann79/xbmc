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
mousemove = os.path.join( settings.getAddonInfo( 'path' ), 'amazonscript\\' )+"mousemove.exe"
waitsec = int(settings.getSetting("clickwait")) * 1000
osLinux = xbmc.getCondVisibility('system.platform.linux')
osOsx = xbmc.getCondVisibility('system.platform.osx')
osWin = xbmc.getCondVisibility('system.platform.windows')

def PLAYVIDEO():
    xbmc.Player().stop()
    dialog = xbmcgui.Dialog()
    ok = True
    kiosk='yes'
    if settings.getSetting("kiosk") == 'false':
        kiosk='no'
    url=common.args.url
    finalUrl=url.replace("http://www.amazon.de/gp/product/","http://www.amazon.de/dp/")+"/ref=vod_0_wnzw"
    xbmc.executebuiltin("RunPlugin(plugin://plugin.program.browser.launcher/?url="+urllib.quote_plus(finalUrl)+"&mode=showSite&kiosk="+kiosk)")
    if osWin:
        try:
            xbmc.sleep(waitsec)
            subprocess.Popen(mousemove)
        except:pass
    if osLinux:
        try:
            xbmc.sleep(waitsec)
            subprocess.Popen('xdotool mousemove 9999 0 click 1', shell=True)
            xbmc.sleep(5000)
            subprocess.Popen('xdotool mousemove 9999 0 click 1', shell=True)
            xbmc.sleep(5000)
            subprocess.Popen('xdotool mousemove 9999 0 click 1', shell=True)
            xbmc.sleep(5000)
            subprocess.Popen('xdotool mousemove 9999 0 click 1', shell=True)
        except:pass
    if osOsx:
        try:
            xbmc.sleep(waitsec)
            subprocess.Popen('cliclick c:500,500', shell=True)
            xbmc.sleep(5000)
            subprocess.Popen('cliclick c:500,500', shell=True)
            xbmc.sleep(5000)
            subprocess.Popen('cliclick c:500,500', shell=True)
            xbmc.sleep(5000)
            subprocess.Popen('cliclick c:500,500', shell=True)
        except:pass
