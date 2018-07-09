#!/usr/bin/env python
# -*- coding: utf-8 -*-
import xbmc
import xbmcplugin
from resources.lib.common import Globals, Settings


def setContentAndView(content, updateListing=False):
    if not hasattr(setContentAndView, 'g'):
        setContentAndView.g = Globals()
    if content == 'movie':
        ctype = 'movies'
        cview = 'movieview'
    elif content == 'series':
        ctype = 'tvshows'
        cview = 'showview'
    elif content == 'season':
        ctype = 'seasons'
        cview = 'seasonview'
    elif content == 'episode':
        ctype = 'episodes'
        cview = 'episodeview'
    elif content == 'videos':
        ctype = 'videos'
        cview = None
    elif content == 'files':
        ctype = 'files'
        cview = None
    else:
        ctype = None
        cview = None

    if None is not ctype:
        xbmcplugin.setContent(setContentAndView.g.pluginhandle, ctype)
    if (None is not cview) and ('true' == setContentAndView.g.addon.getSetting("viewenable")):
        views = [50, 51, 52, 53, 54, 55, 500, 501, 502, -1]
        viewid = views[int(setContentAndView.g.addon.getSetting(cview))]
        if viewid == -1:
            viewid = int(setContentAndView.g.addon.getSetting(cview.replace('view', 'id')))
        xbmc.executebuiltin('Container.SetViewMode(%s)' % viewid)
    xbmcplugin.endOfDirectory(setContentAndView.g.pluginhandle, updateListing=updateListing)


def addDir(name, mode='', url='', infoLabels=None, opt='', catalog='Browse', cm=None, page=1, export=False, thumb=None):
    g = Globals()
    s = Settings()
    if None is thumb:
        thumb = s.DefaultFanart
    u = {'mode': mode, 'url': url.encode('utf-8'), 'page': page, 'opt': opt, 'cat': catalog}
    url = '%s?%s' % (g.pluginid, urllib.urlencode(u))

    if not mode:
        url = g.pluginid

    if export:
        Export(infoLabels, url)
        return
    if infoLabels:
        thumb = infoLabels['Thumb']
        fanart = infoLabels['Fanart']
    else:
        fanart = s.DefaultFanart

    item = xbmcgui.ListItem(name, iconImage=thumb, thumbnailImage=thumb)
    item.setProperty('IsPlayable', 'false')
    item.setArt({'fanart': fanart, 'poster': thumb})

    if infoLabels:
        item.setInfo(type='Video', infoLabels=getInfolabels(infoLabels))
        if 'TotalSeasons' in infoLabels:
            item.setProperty('TotalSeasons', str(infoLabels['TotalSeasons']))
        if 'Poster' in infoLabels.keys():
            item.setArt({'tvshow.poster': infoLabels['Poster']})

    if cm:
        item.addContextMenuItems(cm)
    xbmcplugin.addDirectoryItem(g.pluginhandle, url, item, isFolder=True)


def addVideo(name, asin, infoLabels, cm=[], export=False):
    g = Globals()
    s = Settings()
    u = {'asin': asin, 'mode': 'PlayVideo', 'name': name.encode('utf-8'), 'adult': infoLabels['isAdult']}
    url = '%s?%s' % (g.pluginid, urllib.urlencode(u))

    item = xbmcgui.ListItem(name, thumbnailImage=infoLabels['Thumb'])
    item.setArt({'fanart': infoLabels['Fanart'], 'poster': infoLabels['Thumb']})
    item.addStreamInfo('audio', {'codec': 'ac3', 'channels': int(infoLabels['AudioChannels'])})
    item.setProperty('IsPlayable', str(s.playMethod == 3).lower())

    if 'Poster' in infoLabels.keys():
        item.setArt({'tvshow.poster': infoLabels['Poster']})

    if infoLabels['isHD']:
        item.addStreamInfo('video', {'width': 1920, 'height': 1080})
    else:
        item.addStreamInfo('video', {'width': 720, 'height': 480})

    if infoLabels['TrailerAvailable']:
        infoLabels['Trailer'] = url + '&trailer=1&selbitrate=0'

    url += '&trailer=2' if "live" in infoLabels['contentType'] else '&trailer=0'

    if export:
        url += '&selbitrate=0'
        Export(infoLabels, url)
    else:
        cm.insert(0, (getString(30101), 'Action(ToggleWatched)'))
        cm.insert(1, (getString(30102), 'RunPlugin(%s)' % (url + '&selbitrate=1')))
        url += '&selbitrate=0'
        item.setInfo(type='Video', infoLabels=getInfolabels(infoLabels))
        item.addContextMenuItems(cm)
        xbmcplugin.addDirectoryItem(g.pluginhandle, url, item, isFolder=False)
