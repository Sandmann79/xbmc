#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from kodi_six import xbmcplugin, xbmcgui
from kodi_six.utils import py2_encode
from .common import Globals, Settings
from .l10n import *

try:
    from urllib.parse import urlencode
except ImportError:
    from urllib import urlencode


def setContentAndView(content, updateListing=False):
    g = Globals()
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
        xbmcplugin.setContent(g.pluginhandle, ctype)
    if (None is not cview) and ('true' == g.addon.getSetting("viewenable")):
        views = [50, 51, 52, 53, 54, 55, 500, 501, 502, -1]
        viewid = views[int(g.addon.getSetting(cview))]
        if viewid == -1:
            viewid = int(g.addon.getSetting(cview.replace('view', 'id')))
        xbmc.executebuiltin('Container.SetViewMode({})'.format(viewid))
    xbmcplugin.endOfDirectory(g.pluginhandle, updateListing=updateListing)


def addDir(name, mode='', url='', infoLabels=None, opt='', catalog='Browse', cm=None, page=1, export=False, thumb=None):
    g = Globals()
    s = Settings()
    if None is thumb:
        thumb = s.DefaultFanart
    u = {'mode': mode, 'url': py2_encode(url), 'page': page, 'opt': opt, 'cat': catalog}
    url = '{}?{}'.format(g.pluginid, urlencode(u))

    if not mode:
        url = g.pluginid

    if export:
        g.amz.Export(infoLabels, url)
        return
    if infoLabels:
        thumb = infoLabels['Thumb']
        fanart = infoLabels['Fanart']
    else:
        fanart = s.DefaultFanart

    item = xbmcgui.ListItem(name)
    item.setProperty('IsPlayable', 'false')
    item.setArt({'fanart': fanart, 'poster': thumb, 'icon': thumb, 'thumb': thumb})

    if infoLabels:
        item.setInfo(type='Video', infoLabels=getInfolabels(infoLabels))
        if 'TotalSeasons' in infoLabels:
            item.setProperty('TotalSeasons', str(infoLabels['TotalSeasons']))
        if 'Poster' in infoLabels.keys():
            item.setArt({'tvshow.poster': infoLabels['Poster']})

    if cm:
        item.addContextMenuItems(cm)
    xbmcplugin.addDirectoryItem(g.pluginhandle, url, item, isFolder=mode != 'switchUser')


def addVideo(name, asin, infoLabels, cm=None, export=False):
    g = Globals()
    s = Settings()
    u = {'asin': asin, 'mode': 'PlayVideo', 'name': py2_encode(name), 'adult': infoLabels['isAdult']}
    url = '{}?{}'.format(g.pluginid, urlencode(u))
    bitrate = '0'

    item = xbmcgui.ListItem(name)
    item.setArt({'fanart': infoLabels['Fanart'], 'poster': infoLabels['Thumb'], 'thumb': infoLabels['Thumb']})
    item.addStreamInfo('audio', {'codec': 'ac3', 'channels': int(infoLabels['AudioChannels'])})
    item.setProperty('IsPlayable', str(s.playMethod == 3).lower())

    if 'Poster' in infoLabels.keys():
        item.setArt({'tvshow.poster': infoLabels['Poster']})

    if infoLabels['TrailerAvailable']:
        infoLabels['Trailer'] = url + '&trailer=1&selbitrate=0'

    url += '&trailer=2' if "live" in infoLabels['contentType'] else '&trailer=0'

    if [k for k in ['4k', 'uhd', 'ultra hd'] if k in (infoLabels.get('TVShowTitle', '') + name).lower()]:
        bitrate = '-1'
        item.addStreamInfo('video', {'width': 3840, 'height': 2160})
        if s.uhdAndroid:
            item.setProperty('IsPlayable', 'false')
    elif infoLabels['isHD']:
        item.addStreamInfo('video', {'width': 1920, 'height': 1080})
    else:
        item.addStreamInfo('video', {'width': 720, 'height': 480})

    if export:
        url += '&selbitrate=' + bitrate
        g.amz.Export(infoLabels, url)
    else:
        cm = cm if cm else []
        cm.insert(0, (getString(30101), 'Action(ToggleWatched)'))
        cm.insert(1, (getString(30102), 'RunPlugin({})'.format(url + '&selbitrate=1')))
        item.setInfo(type='Video', infoLabels=getInfolabels(infoLabels))
        item.addContextMenuItems(cm)
        url += '&selbitrate=' + bitrate
        xbmcplugin.addDirectoryItem(g.pluginhandle, url, item, isFolder=False)


def getInfolabels(Infos):
    rem_keys = ('ishd', 'isprime', 'asins', 'audiochannels', 'banner', 'displaytitle', 'fanart', 'poster', 'seasonasin',
                'thumb', 'traileravailable', 'contenttype', 'isadult', 'totalseasons', 'seriesasin', 'episodename')
    if not Infos:
        return
    return {k: v for k, v in Infos.items() if k.lower() not in rem_keys}
