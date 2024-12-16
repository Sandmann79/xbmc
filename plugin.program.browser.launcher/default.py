#!/usr/bin/python
# -*- coding: utf-8 -*-
import sys
import re
import os
import subprocess
import xbmcplugin
import xbmcgui
import xbmcaddon
try:
    from xbmcvfs import translatePath
except ImportError:
    from xbmc import translatePath
try:
    from urllib.parse import unquote_plus, quote_plus
except ImportError:
    from urllib import unquote_plus, quote_plus


addon = xbmcaddon.Addon()
pluginhandle = int(sys.argv[1])
addonID = addon.getAddonInfo('id')
addonPath = addon.getAddonInfo('path')
translation = addon.getLocalizedString
useOwnProfile = addon.getSetting("useOwnProfile") == "true"
useCustomPath = addon.getSetting("useCustomPath") == "true"
customPath = translatePath(addon.getSetting("customPath"))
winBrowser = int(addon.getSetting("winBrowser"))
#prio_values = ['LOW', 'BELOWNORMAL', 'NORMAL', 'ABOVENORMAL', 'HIGH', 'REALTIME' ]
prio_values = [ 0x00000040, 0x00004000, 0x00000020, 0x00008000, 0x00000080, 0x00000100 ]
priority = prio_values[int(addon.getSetting("priority"))]
userDataFolder = translatePath("special://profile/addon_data/"+addonID)
profileFolder = os.path.join(userDataFolder, 'profile')
siteFolder = os.path.join(userDataFolder, 'sites')
avBrowsers = ['Standard', 'Internet Explorer', 'Kylo', 'Chrome', 'Firefox', 'Opera']
Dialog = xbmcgui.Dialog()

if not os.path.isdir(userDataFolder):
    os.mkdir(userDataFolder)
if not os.path.isdir(profileFolder):
    os.mkdir(profileFolder)
if not os.path.isdir(siteFolder):
    os.mkdir(siteFolder)

youtubeUrl = "http://www.youtube.com/leanback"
vimeoUrl = "http://www.vimeo.com/couchmode"

bPath = ['C:\\Program Files\\Internet Explorer\\iexplore.exe',
         'C:\\Program Files\\Hillcrest Labs\\Kylo\\Kylo.exe',
         'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
         'C:\\Program Files\\Mozilla Firefox\\firefox.exe',
         'C:\\Program Files\\Opera\\opera.exe']
bKiosk = ['-k ', '', '--kiosk ', '', '-fullscreen ']
bProfile = ['', '', '--user-data-dir=', '-profile ', '-pd ']
bAgent = ['', '', '--user-agent=', '', '']
bExtra = ['',
          '', 
          '--start-maximized --disable-translate --disable-new-tab-first-run --no-default-browser-check --no-first-run ',
          '',
          '']

def index():
    files = os.listdir(siteFolder)
    for file in files:
        if file.endswith(".link"):
            fh = open(os.path.join(siteFolder, file), 'r')
            title = ""
            url = ""
            thumb = ""
            kiosk = "yes"
            stopPlayback = "no"
            custBrowser = ""
            userAgent = ""
            for line in fh.readlines():
                entry = line[:line.find("=")]
                content = line[line.find("=")+1:]
                if entry == "title":
                    title = content.strip()
                elif entry == "url":
                    url = content.strip()
                elif entry == "thumb":
                    thumb = content.strip()
                elif entry == "kiosk":
                    kiosk = content.strip()
                elif entry == "stopPlayback":
                    stopPlayback = content.strip()
                elif entry == "custBrowser":
                    custBrowser = content.strip()
                elif entry == "userAgent":
                    userAgent = content.strip()
            fh.close()
            addSiteDir(title, url, 'showSite', os.path.join(siteFolder,thumb), stopPlayback, kiosk, custBrowser, userAgent)
    addDir("[B]- "+translation(30001)+"[/B]", "", 'addSite', "")
    xbmcplugin.endOfDirectory(pluginhandle)


def addSite(site="", title=""):
    if site:
        filename = getFileName(title)
        content = "title="+title+"\nurl="+site+"\nthumb=DefaultFolder.png\nstopPlayback=no\nkiosk=yes\ncustBrowser=\nuserAgent="
        fh = open(os.path.join(siteFolder, filename+".link"), 'w')
        fh.write(content)
        fh.close()
    else:
        keyboard = xbmc.Keyboard('', translation(30003))
        keyboard.doModal()
        if keyboard.isConfirmed() and keyboard.getText():
            title = keyboard.getText()
            keyboard = xbmc.Keyboard('http://', translation(30004))
            keyboard.doModal()
            if keyboard.isConfirmed() and keyboard.getText():
                url = keyboard.getText()
                keyboard = xbmc.Keyboard('no', translation(30009))
                keyboard.doModal()
                if keyboard.isConfirmed() and keyboard.getText():
                    stopPlayback = keyboard.getText()
                    keyboard = xbmc.Keyboard('yes', translation(30016))
                    keyboard.doModal()
                    if keyboard.isConfirmed() and keyboard.getText():
                        kiosk = keyboard.getText()
                        custBrowser = Dialog.select(translation(30017), avBrowsers)
                        if custBrowser > -1:
                            content = "title={}\nurl={}\nthumb=DefaultFolder.png\nstopPlayback={}\nkiosk={}\nuserAgent=".format(title, url, stopPlayback, kiosk)
                            if custBrowser > 0: content += "\ncustBrowser={}".format(custBrowser-1)
                            fh = open(os.path.join(siteFolder, getFileName(title)+".link"), 'w')
                            fh.write(content)
                            fh.close()
    xbmc.executebuiltin("Container.Refresh")


def getFileName(title):
    try:
        title = unicode(title, 'utf-8')
    except NameError:
        pass
    return (''.join(c for c in title if c not in '/\\:?"*|<>')).strip()


def getFullPath(path, url, useKiosk, userAgent, selBrowser):
    profile = ""
    if (useOwnProfile) and (bProfile[selBrowser]):
        profile = bProfile[selBrowser]+'"'+os.path.join(profileFolder,str(selBrowser))+'" '
    kiosk = ""
    if (useKiosk=="yes") and (bKiosk[selBrowser]):
        kiosk = bKiosk[selBrowser]
    if (userAgent) and (bAgent[selBrowser]):
        userAgent = bAgent[selBrowser]+'"'+userAgent+'" '
    return '"'+path+'" '+profile+userAgent+bExtra[selBrowser]+kiosk+'"'+url+'"'


def showSite(url, stopPlayback, kiosk, userAgent, custBrowser):
    if stopPlayback == "yes": xbmc.Player().stop()
    selBrowser = winBrowser
    if custBrowser: selBrowser = int(custBrowser)
    path = bPath[selBrowser]
    fullUrl = False
    path86 = path.replace("\\Program Files\\", "\\Program Files (x86)\\")
    if useCustomPath and os.path.exists(customPath) and not custBrowser:
        fullUrl = getFullPath(customPath, url, kiosk, userAgent, selBrowser)
    elif os.path.exists(path):
        fullUrl = getFullPath(path, url, kiosk, userAgent, selBrowser)
    elif os.path.exists(path86):
        fullUrl = getFullPath(path86, url, kiosk, userAgent, selBrowser)
    if fullUrl:
        print(fullUrl)
        if xbmc.getCondVisibility('system.platform.windows'):
            subprocess.Popen(fullUrl, creationflags=priority)
        else:
            subprocess.Popen(fullUrl, shell=True)
    else:
        xbmc.executebuiltin('XBMC.Notification(Info:,'+str(translation(30005))+'!,5000)')
        addon.openSettings()

def removeSite(title):
    os.remove(os.path.join(siteFolder, getFileName(title)+".link"))
    xbmc.executebuiltin("Container.Refresh")


def editSite(title):
    filenameOld = getFileName(title)
    file = os.path.join(siteFolder, filenameOld+".link")
    fh = open(file, 'r')
    title = ""
    url = ""
    kiosk = "yes"
    thumb = "DefaultFolder.png"
    stopPlayback = "no"
    custBrowser = ""
    for line in fh.readlines():
        entry = line[:line.find("=")]
        content = line[line.find("=")+1:]
        if entry == "title":
            title = content.strip()
        elif entry == "url":
            url = content.strip()
        elif entry == "kiosk":
            kiosk = content.strip()
        elif entry == "thumb":
            thumb = content.strip()
        elif entry == "stopPlayback":
            stopPlayback = content.strip()
        elif entry == "custBrowser":
            custBrowser = content.strip()
        elif entry == "userAgent":
            userAgent = content.strip()
    fh.close()

    oldTitle = title
    keyboard = xbmc.Keyboard(title, translation(30003))
    keyboard.doModal()
    if keyboard.isConfirmed() and keyboard.getText():
        title = keyboard.getText()
        keyboard = xbmc.Keyboard(url, translation(30004))
        keyboard.doModal()
        if keyboard.isConfirmed() and keyboard.getText():
            url = keyboard.getText()
            keyboard = xbmc.Keyboard(stopPlayback, translation(30009))
            keyboard.doModal()
            if keyboard.isConfirmed() and keyboard.getText():
                stopPlayback = keyboard.getText()
                keyboard = xbmc.Keyboard(kiosk, translation(30016))
                keyboard.doModal()
                if keyboard.isConfirmed() and keyboard.getText():
                    kiosk = keyboard.getText()
                    custBrowser = Dialog.select(translation(30017), avBrowsers)
                    if custBrowser > -1:
                        content = "title="+title+"\nurl="+url+"\nthumb="+thumb+"\nstopPlayback="+stopPlayback+"\nkiosk="+kiosk+"\nuserAgent="+userAgent
                        if custBrowser > 0: content += "\ncustBrowser={}".format(custBrowser-1)
                        fh = open(os.path.join(siteFolder, getFileName(title)+".link"), 'w')
                        fh.write(content)
                        fh.close()
                        if title != oldTitle:
                            os.remove(os.path.join(siteFolder, filenameOld+".link"))
    xbmc.executebuiltin("Container.Refresh")


def parameters_string_to_dict(parameters):
    paramDict = {}
    if parameters:
        paramPairs = parameters[1:].split("&")
        for paramsPair in paramPairs:
            paramSplits = paramsPair.split('=')
            if (len(paramSplits)) == 2:
                paramDict[paramSplits[0]] = paramSplits[1]
    return paramDict


def addDir(name, url, mode, iconimage, stopPlayback="", kiosk="", custBrowser="", userAgent=""):
    u = sys.argv[0]+"?url="+quote_plus(url)+"&mode="+quote_plus(mode)+"&stopPlayback="+quote_plus(stopPlayback)+"&kiosk="+quote_plus(kiosk)+"&custBrowser="+quote_plus(custBrowser)+"&userAgent="+quote_plus(userAgent)
    ok = True
    liz = xbmcgui.ListItem(name)
    liz.setInfo(type="Video", infoLabels={"Title": name})
    liz.setArt({"icon": iconimage, "thumb": "DefaultFolder.png"})
    ok = xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=u, listitem=liz, isFolder=False)
    return ok


def addSiteDir(name, url, mode, iconimage, stopPlayback, kiosk, custBrowser, userAgent):
    u = sys.argv[0]+"?url="+quote_plus(url)+"&mode="+quote_plus(mode)+"&stopPlayback="+quote_plus(stopPlayback)+"&kiosk="+quote_plus(kiosk)+"&custBrowser="+quote_plus(custBrowser)+"&userAgent="+quote_plus(userAgent)
    ok = True
    liz = xbmcgui.ListItem(name)
    liz.setInfo(type="Video", infoLabels={"Title": name})
    liz.setArt({"icon": iconimage, "thumb": "DefaultFolder.png"})
    liz.addContextMenuItems([(translation(30006), 'RunPlugin(plugin://'+addonID+'/?mode=editSite&url='+quote_plus(name)+')',), (translation(30002), 'RunPlugin(plugin://'+addonID+'/?mode=removeSite&url='+quote_plus(name)+')',)])
    ok = xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=u, listitem=liz, isFolder=False)
    return ok

params = parameters_string_to_dict(sys.argv[2])
mode = unquote_plus(params.get('mode', ''))
name = unquote_plus(params.get('name', ''))
url = unquote_plus(params.get('url', ''))
stopPlayback = unquote_plus(params.get('stopPlayback', 'no'))
kiosk = unquote_plus(params.get('kiosk', 'yes'))
userAgent = unquote_plus(params.get('userAgent', ''))
custBrowser = unquote_plus(params.get('custBrowser', ''))

if mode == 'addSite':
    addSite()
elif mode == 'showSite':
    showSite(url, stopPlayback, kiosk, userAgent, custBrowser)
elif mode == 'removeSite':
    removeSite(url)
elif mode == 'editSite':
    editSite(url)
else:
    index()
