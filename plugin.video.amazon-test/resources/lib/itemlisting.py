#!/usr/bin/env python
# -*- coding: utf-8 -*-
import xbmc
import xbmcplugin
import xbmcgui
from urllib.parse import urlencode

from .common import Globals, Settings
from .l10n import getString
from .export import Export

# names the rest of the addon expects
_g = Globals()
_s = Settings()

# ---------------------------------------------------------------------------
# content / view
# ---------------------------------------------------------------------------
def setContentAndView(content, updateListing=False):
    mapping = {
        'movie':   ('movies',  'movieview'),
        'series':  ('tvshows', 'showview'),
        'season':  ('seasons', 'seasonview'),
        'episode': ('episodes','episodeview'),
        'videos':  ('videos',  None),
        'files':   ('files',   None),
    }
    ctype, cview = mapping.get(content, (None, None))

    if ctype:
        xbmcplugin.setContent(_g.pluginhandle, ctype)

    if cview and _s.viewenable == 'true':
        views = [50, 51, 52, 53, 54, 55, 500, 501, 502, -1]
        view_idx = int(getattr(_s, cview))
        view_id = views[view_idx]
        if view_id == -1:
            view_id = int(getattr(_s, cview.replace('view', 'id')))
        xbmc.executebuiltin('Container.SetViewMode({})'.format(view_id))

    xbmcplugin.endOfDirectory(_g.pluginhandle, updateListing=updateListing)


# ---------------------------------------------------------------------------
# helpers: track enrichment
# ---------------------------------------------------------------------------
def _build_track_summary(info):
    """
    Short, list-friendly line.
    """
    if not info:
        return ''
    audio = info.get('audio_tracks') or []
    subs = info.get('subtitle_tracks') or []

    parts = []

    if audio:
        a_parts = []
        for tr in audio[:2]:
            lang = tr.get('lang') or 'und'
            ch = tr.get('channels')
            a_parts.append('{} {}'.format(lang, ch) if ch else lang)
        parts.append('Audio: ' + ', '.join(a_parts))

    if subs:
        s_parts = []
        for tr in subs[:2]:
            lang = tr.get('lang') or 'und'
            feats = tr.get('features') or []
            s_parts.append('{} {}'.format(lang, ' '.join(feats)) if feats else lang)
        parts.append('Subs: ' + ', '.join(s_parts))

    return ' | '.join(parts)


def _append_tracks_to_plot(info):
    """
    Make tracks visible in info dialog.
    """
    if not info:
        return info
    audio = info.get('audio_tracks') or []
    subs = info.get('subtitle_tracks') or []
    if not audio and not subs:
        return info

    lines = []
    if audio:
        lines.append('Audio tracks:')
        for tr in audio:
            lang = tr.get('lang') or 'und'
            line = lang
            ch = tr.get('channels')
            feats = tr.get('features') or []
            if ch:
                line += ' ({})'.format(ch)
            if feats:
                line += ' - {}'.format(', '.join(feats))
            lines.append('  ' + line)
    if subs:
        lines.append('Subtitles:')
        for tr in subs:
            lang = tr.get('lang') or 'und'
            line = lang
            stype = tr.get('type')
            feats = tr.get('features') or []
            if stype:
                line += ' ({})'.format(stype)
            if feats:
                line += ' - {}'.format(', '.join(feats))
            lines.append('  ' + line)

    extra = '\n'.join(lines)
    base = info.get('plot') or ''
    info['plot'] = (base + '\n\n' + extra).strip()
    if not info.get('plotoutline'):
        info['plotoutline'] = info['plot']
    return info


def _set_track_properties(listitem, info):
    """
    Expose track info via ListItem properties for skins.
    """
    if not info:
        return
    audio = info.get('audio_tracks') or []
    subs = info.get('subtitle_tracks') or []
    flags = info.get('audioflags') or []

    if audio:
        rendered = []
        for tr in audio:
            lang = tr.get('lang') or 'und'
            feats = tr.get('features') or []
            ch = tr.get('channels')
            if feats:
                rendered.append('{} - {}'.format(lang, ', '.join(feats)))
            elif ch:
                rendered.append('{} - {}'.format(lang, ch))
            else:
                rendered.append(lang)
        listitem.setProperty('AudioTracks', '\n'.join(rendered))

    if subs:
        rendered = []
        for tr in subs:
            lang = tr.get('lang') or 'und'
            feats = tr.get('features') or []
            stype = tr.get('type')
            if feats:
                rendered.append('{} - {}'.format(lang, ', '.join(feats)))
            elif stype:
                rendered.append('{} - {}'.format(lang, stype))
            else:
                rendered.append(lang)
        listitem.setProperty('SubtitleTracks', '\n'.join(rendered))

    if flags:
        listitem.setProperty('AudioFlags', ', '.join(flags))


# ---------------------------------------------------------------------------
# helpers: common listitem setup
# ---------------------------------------------------------------------------
def _apply_art(listitem, info, thumb_fallback):
    thumb = info.get('thumb', thumb_fallback)
    fanart = info.get('fanart', _g.DefaultFanart)
    poster = info.get('poster', thumb)
    listitem.setArt({'fanart': fanart, 'poster': poster, 'icon': thumb, 'thumb': thumb})
    if 'poster' in info:
        listitem.setArt({'tvshow.poster': info['poster']})


# ---------------------------------------------------------------------------
# public: directory item
# ---------------------------------------------------------------------------
def addDir(name, mode='', url='', infoLabels=None, opt='', catalog='Browse', cm=None,
           page=1, export=False, thumb=None):
    """
    Directory item — kept compatible with the original addon.
    """
    infoLabels = infoLabels or {}

    # original plugin's export paging
    if export and mode == 'getPage':
        exec('_g.pv.{}("{}", "{}", {}, export={})'.format(mode, url, opt, page, export))
        return

    useatv = (_s.data_source == 1)
    folder = mode not in ['switchUser', 'text'] if useatv else mode == 'True'
    sep = '?' if useatv else ''
    u = urlencode({'mode': mode, 'url': url, 'page': page, 'opt': opt, 'cat': catalog}) if useatv else url
    final_url = '{}{}{}'.format(_g.pluginid, sep, u) if mode != 'text' else _g.pluginid

    if mode == '' and useatv:
        final_url = _g.pluginid

    if export:
        Export(infoLabels, final_url)
        return

    item = ListItem_InfoTag(name)
    item.setProperty('IsPlayable', 'false')

    # art
    _apply_art(item, infoLabels, thumb)

    # second line
    summary = _build_track_summary(infoLabels)
    if summary:
        item.setLabel2(summary)

    if infoLabels:
        infoLabels = _append_tracks_to_plot(infoLabels)
        item.set_Info('Video', infoLabels)
        if 'totalseasons' in infoLabels:
            item.setProperty('totalseasons', str(infoLabels['totalseasons']))
        _set_track_properties(item, infoLabels)

    if cm:
        item.addContextMenuItems(cm)

    xbmcplugin.addDirectoryItem(_g.pluginhandle, final_url, item, isFolder=folder)


# ---------------------------------------------------------------------------
# public: playable item
# ---------------------------------------------------------------------------
def addVideo(name, asin, infoLabels, cm=None, export=False):
    infoLabels = infoLabels or {}

    params = {'asin': asin, 'mode': 'PlayVideo', 'name': name, 'adult': infoLabels.get('isAdult', 0)}
    url = '{}?{}'.format(_g.pluginid, urlencode(params))
    bitrate = '0'
    streamtypes = {'live': 2, 'event': 3}

    item = ListItem_InfoTag(name)
    item.setProperty('IsPlayable', 'true')
    _apply_art(item, infoLabels, _g.DefaultFanart)

    # visible line
    summary = _build_track_summary(infoLabels)
    if summary:
        item.setLabel2(summary)

    # audio hint
    if 'audiochannels' in infoLabels:
        item.add_StreamInfo('audio', {'codec': 'ac3', 'channels': int(infoLabels['audiochannels'])})

    # trailer
    if infoLabels.get('TrailerAvailable'):
        infoLabels['trailer'] = url + '&trailer=1&selbitrate=0'
    url += '&trailer={}'.format(streamtypes.get(infoLabels.get('contentType'), 0))

    # resolution hint
    title_mix = (infoLabels.get('tvshowtitle', '') + name).lower()
    if any(k in title_mix for k in ('4k', 'uhd', 'ultra hd')):
        item.add_StreamInfo('video', {'width': 3840, 'height': 2160})
    elif infoLabels.get('isHD'):
        item.add_StreamInfo('video', {'width': 1920, 'height': 1080})

    # pass selected tracks to player
    selaudio = infoLabels.get('selected_audio_id')
    selsub = infoLabels.get('selected_subtitle_id')
    if selaudio:
        url += '&selaudio={}'.format(selaudio)
    if selsub:
        url += '&selsub={}'.format(selsub)

    if export:
        url += '&selbitrate=' + bitrate
        Export(infoLabels, url)
        return

    # normal item
    cm = cm if cm else []
    cm.insert(0, (getString(30101), 'Action(ToggleWatched)'))

    infoLabels = _append_tracks_to_plot(infoLabels)
    item.set_Info('Video', infoLabels)
    _set_track_properties(item, infoLabels)
    item.addContextMenuItems(cm)

    url += '&selbitrate=' + bitrate
    xbmcplugin.addDirectoryItem(_g.pluginhandle, url, item, isFolder=False)


# ---------------------------------------------------------------------------
# listitem wrapper
# ---------------------------------------------------------------------------
class ListItem_InfoTag(xbmcgui.ListItem):
    """
    Map our info_labels dict onto Kodi's InfoTagVideo API (Kodi 19+),
    with fallback to classic setInfo for older Kodi versions.
    """
    def __init__(self, *args, **kwargs):
        super(ListItem_InfoTag, self).__init__(*args, **kwargs)
        self.info_tag = None
        self.map = {
            'date':         {'attr': 'setDateAdded',     'convert': str},
            'genre':        {'attr': 'setGenres',        'convert': list},
            'country':      {'attr': 'setCountries',     'convert': list},
            'year':         {'attr': 'setYear',          'convert': int},
            'episode':      {'attr': 'setEpisode',       'convert': int},
            'season':       {'attr': 'setSeason',        'convert': int},
            'sortepisode':  {'attr': 'setSortEpisode',   'convert': int},
            'sortseason':   {'attr': 'setSortSeason',    'convert': int},
            'episodeguide': {'attr': 'setEpisodeGuide',  'convert': str},
            'showlink':     {'attr': 'setShowLinks',     'convert': list},
            'top250':       {'attr': 'setTop250',        'convert': int},
            'setid':        {'attr': 'setSetId',         'convert': int},
            'tracknumber':  {'attr': 'setTrackNumber',   'convert': int},
            'rating':       {'attr': 'setRating',        'convert': float},
            'userrating':   {'attr': 'setUserRating',    'convert': int},
            'playcount':    {'attr': 'setPlaycount',     'convert': int},
            'cast': {
                'attr': 'setCast',
                'convert': lambda seq: [xbmc.Actor(name) for name in seq],
            },
            'director':     {'attr': 'setDirectors',     'convert': list},
            'mpaa':         {'attr': 'setMpaa',          'convert': str},
            'plot':         {'attr': 'setPlot',          'convert': str},
            'plotoutline':  {'attr': 'setPlotOutline',   'convert': str},
            'title':        {'attr': 'setTitle',         'convert': str},
            'originaltitle':{'attr': 'setOriginalTitle', 'convert': str},
            'sorttitle':    {'attr': 'setSortTitle',     'convert': str},
            'duration':     {'attr': 'setDuration',      'convert': int},
            'studio':       {'attr': 'setStudios',       'convert': list},
            'tagline':      {'attr': 'setTagLine',       'convert': str},
            'writer':       {'attr': 'setWriters',       'convert': list},
            'tvshowtitle':  {'attr': 'setTvShowTitle',   'convert': str},
            'premiered':    {'attr': 'setPremiered',     'convert': str},
            'status':       {'attr': 'setTvShowStatus',  'convert': str},
            'set':          {'attr': 'setSet',           'convert': str},
            'setoverview':  {'attr': 'setSetOverview',   'convert': str},
            'tag':          {'attr': 'setTags',          'convert': list},
            'imdbnumber':   {'attr': 'setIMDBNumber',    'convert': str},
            'code':         {'attr': 'setProductionCode','convert': str},
            'aired':        {'attr': 'setFirstAired',    'convert': str},
            'credits':      {'attr': 'setWriters',       'convert': list},
            'lastplayed':   {'attr': 'setLastPlayed',    'convert': str},
            'album':        {'attr': 'setAlbum',         'convert': str},
            'artist':       {'attr': 'setArtists',       'convert': list},
            'votes':        {'attr': 'setVotes',         'convert': int},
            'path':         {'attr': 'setPath',          'convert': str},
            'trailer':      {'attr': 'setTrailer',       'convert': str},
            'dateadded':    {'attr': 'setDateAdded',     'convert': str},
            'mediatype':    {'attr': 'setMediaType',     'convert': str},
            'dbid':         {'attr': 'setDbId',          'convert': int},
        }

    def set_Info(self, ctype, infos):
        # Kodi 19+ path
        if _g.KodiVersion > 19:
            if self.info_tag is None:
                self.info_tag = self.getVideoInfoTag()
            for key, value in infos.items():
                if value is None:
                    continue
                mapper = self.map.get(key)
                if not mapper:
                    continue
                # ← this was the line that was broken before
                setter = getattr(self.info_tag, mapper['attr'])
                setter(mapper['convert'](value))
        else:
            # older Kodi
            self.setInfo(ctype, self._clean_infos(infos))

    def add_StreamInfo(self, ctype, infos):
        ct = ctype.capitalize()
        if _g.KodiVersion > 19:
            if self.info_tag is None:
                self.info_tag = self.getVideoInfoTag()
            add_stream = getattr(self.info_tag, 'add{}Stream'.format(ct))
            stream_detail = getattr(xbmc, '{}StreamDetail'.format(ct))
            add_stream(stream_detail(**infos))
        else:
            self.addStreamInfo(ctype, infos)

    def _clean_infos(self, infos):
        if not infos:
            return {}
        allowed = {k.lower() for k in self.map.keys()}
        return {k: v for k, v in infos.items() if k.lower() in allowed}
