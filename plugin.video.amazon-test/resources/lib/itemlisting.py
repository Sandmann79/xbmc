#!/usr/bin/env python
# -*- coding: utf-8 -*-
import xbmc, xbmcplugin, xbmcgui
from urllib.parse import urlencode

from .common import Globals, Settings
from .l10n import getString
from .export import Export

_g = Globals()
_s = Settings()


def setContentAndView(content, updateListing=False):
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

    if ctype is not None:
        xbmcplugin.setContent(_g.pluginhandle, ctype)
    if (cview is not None) and (_s.viewenable == 'true'):
        views = [50, 51, 52, 53, 54, 55, 500, 501, 502, -1]
        viewid = views[int(getattr(_s, cview))]
        if viewid == -1:
            viewid = int(getattr(_s, cview.replace('view', 'id')))
        xbmc.executebuiltin('Container.SetViewMode({})'.format(viewid))
    xbmcplugin.endOfDirectory(_g.pluginhandle, updateListing=updateListing)


# --- helper: push extended track info into ListItem properties ---
def _apply_extra_media_props(item, infoLabels):
    if not infoLabels:
        return
    audio_tracks = infoLabels.get('audio_tracks')
    subtitle_tracks = infoLabels.get('subtitle_tracks')
    audioflags = infoLabels.get('audioflags')
    if audio_tracks:
        # store as newline so skins can split
        item.setProperty('AudioTracks', '\n'.join(
            ['{lang} - {desc}'.format(
                lang=(a.get('lang') or 'und'),
                desc=(', '.join(a.get('features') or []) or (str(a.get('channels')) if a.get('channels') else '')).strip()
            ).strip(' -') for a in audio_tracks]
        ))
    if subtitle_tracks:
        item.setProperty('SubtitleTracks', '\n'.join(
            ['{lang} - {desc}'.format(
                lang=(s.get('lang') or 'und'),
                desc=(', '.join(s.get('features') or []) or s.get('type') or '').strip()
            ).strip(' -') for s in subtitle_tracks]
        ))
    if audioflags:
        item.setProperty('AudioFlags', ', '.join(audioflags))


def addDir(name, mode='', url='', infoLabels=None, opt='', catalog='Browse', cm=None, page=1, export=False, thumb=None):
    if export and mode == 'getPage':
        exec('_g.pv.{}("{}", "{}", {}, export={})'.format(mode, url, opt, page, export))
        return

    useatv = _s.data_source == 1
    folder = mode not in ['switchUser', 'text'] if useatv else mode == 'True'
    sep = '?' if useatv else ''
    u = urlencode({'mode': mode, 'url': url, 'page': page, 'opt': opt, 'cat': catalog}) if useatv else url
    url = '{}{}{}'.format(_g.pluginid, sep, u) if mode != 'text' else _g.pluginid

    if not infoLabels:
        infoLabels = {}
    if mode == '' and useatv:
        url = _g.pluginid
    if export:
        Export(infoLabels, url)
        return
    thumb = infoLabels.get('thumb', thumb)
    fanart = infoLabels.get('fanart', _g.DefaultFanart)
    poster = infoLabels.get('poster', thumb)

    item = ListItem_InfoTag(name)
    item.setProperty('IsPlayable', 'false')
    item.setArt({'fanart': fanart, 'poster': poster, 'icon': thumb, 'thumb': thumb})

    if infoLabels:
        item.set_Info('Video', infoLabels)
        if 'totalseasons' in infoLabels:
            item.setProperty('totalseasons', str(infoLabels['totalseasons']))
        if 'poster' in infoLabels:
            item.setArt({'tvshow.poster': infoLabels['poster']})
        _apply_extra_media_props(item, infoLabels)

    if cm:
        item.addContextMenuItems(cm)
    xbmcplugin.addDirectoryItem(_g.pluginhandle, url, item, isFolder=folder)


def addVideo(name, asin, infoLabels, cm=None, export=False):
    u = {'asin': asin, 'mode': 'PlayVideo', 'name': name, 'adult': infoLabels.get('isAdult', 0)}
    url = '{}?{}'.format(_g.pluginid, urlencode(u))
    bitrate = '0'
    streamtypes = {'live': 2, 'event': 3}
    thumb = infoLabels.get('thumb', _g.DefaultFanart)
    fanart = infoLabels.get('fanart', _g.DefaultFanart)
    poster = infoLabels.get('poster', thumb)

    item = ListItem_InfoTag(name)
    item.setArt({'fanart': fanart, 'poster': poster, 'thumb': thumb})
    item.setProperty('IsPlayable', 'true')

    # audio stream hint for Kodi
    if 'audiochannels' in infoLabels:
        item.add_StreamInfo('audio', {'codec': 'ac3', 'channels': int(infoLabels['audiochannels'])})

    if 'poster' in infoLabels:
        item.setArt({'tvshow.poster': infoLabels['poster']})

    # trailer support
    if infoLabels.get('TrailerAvailable'):
        infoLabels['trailer'] = url + '&trailer=1&selbitrate=0'

    # add video stream hints
    url += '&trailer=%s' % streamtypes.get(infoLabels['contentType'], 0)
    title_mix = (infoLabels.get('tvshowtitle', '') + name).lower()
    if any(k in title_mix for k in ['4k', 'uhd', 'ultra hd']):
        item.add_StreamInfo('video', {'width': 3840, 'height': 2160})
    elif infoLabels.get('isHD'):
        item.add_StreamInfo('video', {'width': 1920, 'height': 1080})

    selaudio = infoLabels.get('selected_audio_id')
    selsub = infoLabels.get('selected_subtitle_id')
    if selaudio:
        url += '&selaudio={}'.format(selaudio)
    if selsub:
        url += '&selsub={}'.format(selsub)

    if export:
        url += '&selbitrate=' + bitrate
        Export(infoLabels, url)
    else:
        cm = cm if cm else []
        cm.insert(0, (getString(30101), 'Action(ToggleWatched)'))
        item.set_Info('Video', infoLabels)
        _apply_extra_media_props(item, infoLabels)
        item.addContextMenuItems(cm)
        url += '&selbitrate=' + bitrate
        xbmcplugin.addDirectoryItem(_g.pluginhandle, url, item, isFolder=False)


class ListItem_InfoTag(xbmcgui.ListItem):
    """ adapted from https://github.com/jurialmunkey/script.module.infotagger """
    def __init__(self, *args, **kwargs):
        super(ListItem_InfoTag, self).__init__(*args, **kwargs)
        self.InfoTag = None
        self.map = {
            'date': {'attr': 'setDateAdded', 'convert': str, 'classinfo': str},
            'genre': {'attr': 'setGenres', 'convert': list, 'classinfo': (list, tuple)},
            'country': {'attr': 'setCountries', 'convert': list, 'classinfo': (list, tuple)},
            'year': {'attr': 'setYear', 'convert': int, 'classinfo': int},
            'episode': {'attr': 'setEpisode', 'convert': int, 'classinfo': int},
            'season': {'attr': 'setSeason', 'convert': int, 'classinfo': int},
            'sortepisode': {'attr': 'setSortEpisode', 'convert': int, 'classinfo': int},
            'sortseason': {'attr': 'setSortSeason', 'convert': int, 'classinfo': int},
            'episodeguide': {'attr': 'setEpisodeGuide', 'convert': str, 'classinfo': str},
            'showlink': {'attr': 'setShowLinks', 'convert': list, 'classinfo': (list, tuple)},
            'top250': {'attr': 'setTop250', 'convert': int, 'classinfo': int},
            'setid': {'attr': 'setSetId', 'convert': int, 'classinfo': int},
            'tracknumber': {'attr': 'setTrackNumber', 'convert': int, 'classinfo': int},
            'rating': {'attr': 'setRating', 'convert': float, 'classinfo': float},
            'userrating': {'attr': 'setUserRating', 'convert': int, 'classinfo': int},
            'playcount': {'attr': 'setPlaycount', 'convert': int, 'classinfo': int},
            'cast': {'attr': 'setCast', 'convert': lambda x: [xbmc.Actor(x) for x in x], 'classinfo': (list, tuple)},
            'director': {'attr': 'setDirectors', 'convert': list, 'classinfo': (list, tuple)},
            'mpaa': {'attr': 'setMpaa', 'convert': str, 'classinfo': str},
            'plot': {'attr': 'setPlot', 'convert': str, 'classinfo': str},
            'plotoutline': {'attr': 'setPlotOutline', 'convert': str, 'classinfo': str},
            'title': {'attr': 'setTitle', 'convert': str, 'classinfo': str},
            'originaltitle': {'attr': 'setOriginalTitle', 'convert': str, 'classinfo': str},
            'sorttitle': {'attr': 'setSortTitle', 'convert': str, 'classinfo': str},
            'duration': {'attr': 'setDuration', 'convert': int, 'classinfo': int},
            'studio': {'attr': 'setStudios', 'convert': list, 'classinfo': (list, tuple)},
            'tagline': {'attr': 'setTagLine', 'convert': str, 'classinfo': str},
            'writer': {'attr': 'setWriters', 'convert': list, 'classinfo': (list, tuple)},
            'tvshowtitle': {'attr': 'setTvShowTitle', 'convert': str, 'classinfo': str},
            'premiered': {'attr': 'setPremiered', 'convert': str, 'classinfo': str},
            'status': {'attr': 'setTvShowStatus', 'convert': str, 'classinfo': str},
            'set': {'attr': 'setSet', 'convert': str, 'classinfo': str},
            'setoverview': {'attr': 'setSetOverview', 'convert': str, 'classinfo': str},
            'tag': {'attr': 'setTags', 'convert': list, 'classinfo': (list, tuple)},
            'imdbnumber': {'attr': 'setIMDBNumber', 'convert': str, 'classinfo': str},
            'code': {'attr': 'setProductionCode', 'convert': str, 'classinfo': str},
            'aired': {'attr': 'setFirstAired', 'convert': str, 'classinfo': str},
            'credits': {'attr': 'setWriters', 'convert': list, 'classinfo': (list, tuple)},
            'lastplayed': {'attr': 'setLastPlayed', 'convert': str, 'classinfo': str},
            'album': {'attr': 'setAlbum', 'convert': str, 'classinfo': str},
            'artist': {'attr': 'setArtists', 'convert': list, 'classinfo': (list, tuple)},
            'votes': {'attr': 'setVotes', 'convert': int, 'classinfo': int},
            'path': {'attr': 'setPath', 'convert': str, 'classinfo': str},
            'trailer': {'attr': 'setTrailer', 'convert': str, 'classinfo': str},
            'dateadded': {'attr': 'setDateAdded', 'convert': str, 'classinfo': str},
            'mediatype': {'attr': 'setMediaType', 'convert': str, 'classinfo': str},
            'dbid': {'attr': 'setDbId', 'convert': int, 'classinfo': int}}

    def set_Info(self, ctype, infos):
        if _g.KodiVersion > 19:
            if self.InfoTag is None:
                self.InfoTag = self.getVideoInfoTag()
            for k, v in infos.items():
                attr = self.map[k].get('attr') if k in self.map else None
                if attr is not None and v is not None:
                    f = getattr(self.InfoTag, attr)
                    f(self.map[k]['convert'](v))
        else:
            self.setInfo(ctype, self._cleanInfos(infos))

    def add_StreamInfo(self, ctype, infos):
        ct = ctype.capitalize()
        if _g.KodiVersion > 19:
            if self.InfoTag is None:
                self.InfoTag = self.getVideoInfoTag()
            addStrm = getattr(self.InfoTag, 'add{}Stream'.format(ct))
            StrmDetail = getattr(xbmc, '{}StreamDetail'.format(ct))
            addStrm(StrmDetail(**infos))
        else:
            self.addStreamInfo(ctype, infos)

    def _cleanInfos(self, infos):
        if not infos:
            return
        return {k: v for k, v in infos.items() if k.lower() in self.map}

