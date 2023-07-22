#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from kodi_six import xbmcplugin, xbmcgui
from kodi_six.utils import py2_encode
from .common import Globals, Settings
from .l10n import *
from .export import Export
import sys

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
    useatv = s.data_source == 1
    folder = mode not in ['switchUser', 'text'] if useatv else mode == 'True'
    sep = '?' if useatv else ''
    u = urlencode({'mode': mode, 'url': py2_encode(url), 'page': page, 'opt': opt, 'cat': catalog}) if useatv else url
    url = '{}{}{}'.format(g.pluginid, sep, u) if mode != 'text' else sys.argv[0]

    if not infoLabels:
        infoLabels = {}
    if mode == '' and useatv:
        url = g.pluginid
    if export:
        Export(infoLabels, url)
        return
    thumb = infoLabels.get('thumb', thumb)
    fanart = infoLabels.get('fanart', s.DefaultFanart)
    poster = infoLabels.get('poster', thumb)

    item = xbmcgui.ListItem(name)
    item.setProperty('IsPlayable', 'false')
    item.setArt({'fanart': fanart, 'poster': poster, 'icon': thumb, 'thumb': thumb})

    if infoLabels:
        item.setInfo(type='Video', infoLabels=getInfolabels(infoLabels))
        if 'totalseasons' in infoLabels:
            item.setProperty('totalseasons', str(infoLabels['totalseasons']))
        if 'poster' in infoLabels:
            item.setArt({'tvshow.poster': infoLabels['poster']})

    if cm:
        item.addContextMenuItems(cm)
    xbmcplugin.addDirectoryItem(g.pluginhandle, url, item, isFolder=folder)


def addVideo(name, asin, infoLabels, cm=None, export=False):
    g = Globals()
    s = Settings()
    u = {'asin': asin, 'mode': 'PlayVideo', 'name': py2_encode(name), 'adult': infoLabels.get('isAdult', 0)}
    url = '{}?{}'.format(g.pluginid, urlencode(u))
    bitrate = '0'
    streamtypes = {'live': 2}
    thumb = infoLabels.get('thumb', s.DefaultFanart)
    fanart = infoLabels.get('fanart', s.DefaultFanart)
    poster = infoLabels.get('poster', thumb)

    item = xbmcgui.ListItem(name)
    item.setArt({'fanart': fanart, 'poster': poster, 'thumb': thumb})
    item.setProperty('IsPlayable', 'true')  # always true, to view watched state

    if 'audiochannels' in infoLabels:
        item.addStreamInfo('audio', {'codec': 'ac3', 'channels': int(infoLabels['audiochannels'])})

    if 'poster' in infoLabels.keys():
        item.setArt({'tvshow.poster': infoLabels['poster']})

    if infoLabels.get('TrailerAvailable'):
        infoLabels['trailer'] = url + '&trailer=1&selbitrate=0'

    url += '&trailer=%s' % streamtypes.get(infoLabels['contentType'], 0)

    if [k for k in ['4k', 'uhd', 'ultra hd'] if k in (infoLabels.get('tvshowtitle', '') + name).lower()]:
        item.addStreamInfo('video', {'width': 3840, 'height': 2160})
    elif infoLabels.get('isHD'):
        item.addStreamInfo('video', {'width': 1920, 'height': 1080})

    if export:
        url += '&selbitrate=' + bitrate
        Export(infoLabels, url)
    else:
        cm = cm if cm else []
        cm.insert(0, (getString(30101), 'Action(ToggleWatched)'))
        item.setInfo(type='Video', infoLabels=getInfolabels(infoLabels))
        item.addContextMenuItems(cm)
        url += '&selbitrate=' + bitrate
        xbmcplugin.addDirectoryItem(g.pluginhandle, url, item, isFolder=False)


def getInfolabels(Infos):
    rem_keys = ('ishd', 'isprime', 'asins', 'audiochannels', 'banner', 'displaytitle', 'fanart', 'poster', 'seasonasin',
                'thumb', 'traileravailable', 'contenttype', 'isadult', 'totalseasons', 'seriesasin', 'episodename', 'isuhd')
    if not Infos:
        return
    return {k: v for k, v in Infos.items() if k.lower() not in rem_keys}
