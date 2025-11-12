#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Kodi item listing helpers for the Prime Video addon.

- Creates directory items and playable items.
- Surfaces rich audio/subtitle metadata to both InfoTag and ListItem properties.
- Passes preselected audio/subtitle IDs to the playback handler.
- Applies configured content type and view.
"""
import xbmc
import xbmcplugin
import xbmcgui
from urllib.parse import urlencode

from .common import Globals, Settings
from .l10n import getString
from .export import Export

# ---------------------------------------------------------------------------
# singletons
# ---------------------------------------------------------------------------
_globals = Globals()
_settings = Settings()


# ---------------------------------------------------------------------------
# content / view
# ---------------------------------------------------------------------------
def setContentAndView(content_type, updateListing=False):
    """
    Map a logical content type ("movie", "series", ...) to Kodi content + view.
    """
    content_map = {
        'movie':   ('movies',  'movieview'),
        'series':  ('tvshows', 'showview'),
        'season':  ('seasons', 'seasonview'),
        'episode': ('episodes','episodeview'),
        'videos':  ('videos',  None),
        'files':   ('files',   None),
    }

    kodi_content, view_key = content_map.get(content_type, (None, None))

    if kodi_content:
        xbmcplugin.setContent(_globals.pluginhandle, kodi_content)

    if view_key and _settings.viewenable == 'true':
        view_ids = [50, 51, 52, 53, 54, 55, 500, 501, 502, -1]
        idx = int(getattr(_settings, view_key))
        view_id = view_ids[idx]
        if view_id == -1:
            view_id = int(getattr(_settings, view_key.replace('view', 'id')))
        xbmc.executebuiltin(f'Container.SetViewMode({view_id})')

    xbmcplugin.endOfDirectory(_globals.pluginhandle, updateListing=updateListing)


# ---------------------------------------------------------------------------
# helper: build plugin URL
# ---------------------------------------------------------------------------
def _build_plugin_url(mode, url, page, opt, catalog):
    """
    Build navigation URL depending on data source mode.
    Returns: (final_url: str, using_atv: bool)
    """
    using_atv = (_settings.data_source == 1)
    if not using_atv:
        return (url if mode != 'text' else _globals.pluginid), False

    query = urlencode({
        'mode': mode,
        'url': url,
        'page': page,
        'opt': opt,
        'cat': catalog,
    })
    final_url = f'{_globals.pluginid}?{query}' if mode != 'text' else _globals.pluginid
    return final_url, True


# ---------------------------------------------------------------------------
# helper: short label summary so it actually shows in list view
# ---------------------------------------------------------------------------
def _build_track_summary(info_labels):
    """
    Build a short one-line description of audio/subtitle tracks for label2.
    Example: "Audio: en 5.1, de 2.0 | Subs: en SDH"
    """
    if not info_labels:
        return ''
    audio_tracks = info_labels.get('audio_tracks') or []
    subtitle_tracks = info_labels.get('subtitle_tracks') or []

    parts = []

    if audio_tracks:
        rendered = []
        for track in audio_tracks[:2]:  # keep it short
            lang = track.get('lang') or 'und'
            ch = track.get('channels')
            if ch:
                rendered.append(f'{lang} {ch}')
            else:
                rendered.append(lang)
        parts.append('Audio: ' + ', '.join(rendered))

    if subtitle_tracks:
        rendered = []
        for track in subtitle_tracks[:2]:
            lang = track.get('lang') or 'und'
            feats = track.get('features') or []
            if feats:
                rendered.append(f'{lang} {" ".join(feats)}')
            else:
                rendered.append(lang)
        parts.append('Subs: ' + ', '.join(rendered))

    return ' | '.join(parts)


# ---------------------------------------------------------------------------
# helper: make track info visible in basic skins
# ---------------------------------------------------------------------------
def _enrich_plot_with_tracks(info_labels):
    """
    Append human-readable audio/subtitle info to plot/plotoutline.
    """
    if not info_labels:
        return info_labels

    audio_tracks = info_labels.get('audio_tracks') or []
    subtitle_tracks = info_labels.get('subtitle_tracks') or []
    if not audio_tracks and not subtitle_tracks:
        return info_labels

    lines = []

    if audio_tracks:
        lines.append('Audio tracks:')
        for track in audio_tracks:
            lang = track.get('lang') or 'und'
            line = lang
            channels = track.get('channels')
            features = track.get('features') or []
            if channels:
                line += f' ({channels})'
            if features:
                line += ' - ' + ', '.join(features)
            lines.append('  ' + line)

    if subtitle_tracks:
        lines.append('Subtitles:')
        for track in subtitle_tracks:
            lang = track.get('lang') or 'und'
            line = lang
            stype = track.get('type')
            features = track.get('features') or []
            if stype:
                line += f' ({stype})'
            if features:
                line += ' - ' + ', '.join(features)
            lines.append('  ' + line)

    extra_text = '\n'.join(lines)
    current_plot = info_labels.get('plot') or ''
    info_labels['plot'] = f'{current_plot}\n\n{extra_text}'.strip()

    if not info_labels.get('plotoutline'):
        info_labels['plotoutline'] = info_labels['plot']

    return info_labels


# ---------------------------------------------------------------------------
# helper: set ListItem properties for rich media
# ---------------------------------------------------------------------------
def _apply_extra_media_props(listitem, info_labels):
    if not info_labels:
        return

    audio_tracks = info_labels.get('audio_tracks') or []
    subtitle_tracks = info_labels.get('subtitle_tracks') or []
    audio_flags = info_labels.get('audioflags') or []

    if audio_tracks:
        rendered = []
        for track in audio_tracks:
            lang = track.get('lang') or 'und'
            features = track.get('features') or []
            channels = track.get('channels')
            if features:
                rendered.append(f'{lang} - {", ".join(features)}')
            elif channels:
                rendered.append(f'{lang} - {channels}')
            else:
                rendered.append(lang)
        listitem.setProperty('AudioTracks', '\n'.join(rendered))

    if subtitle_tracks:
        rendered = []
        for track in subtitle_tracks:
            lang = track.get('lang') or 'und'
            features = track.get('features') or []
            stype = track.get('type')
            if features:
                rendered.append(f'{lang} - {", ".join(features)}')
            elif stype:
                rendered.append(f'{lang} - {stype}')
            else:
                rendered.append(lang)
        listitem.setProperty('SubtitleTracks', '\n'.join(rendered))

    if audio_flags:
        listitem.setProperty('AudioFlags', ', '.join(audio_flags))


# ---------------------------------------------------------------------------
# directory item
# ---------------------------------------------------------------------------
def addDir(
    name,
    mode='',
    url='',
    info_labels=None,
    opt='',
    catalog='Browse',
    cm=None,
    page=1,
    export=False,
    thumb=None
):
    info_labels = info_labels or {}

    if export and mode == 'getPage':
        exec('_globals.pv.{}("{}", "{}", {}, export={})'.format(mode, url, opt, page, export))
        return

    plugin_url, using_atv = _build_plugin_url(mode, url, page, opt, catalog)

    if export:
        Export(info_labels, plugin_url)
        return

    thumb = info_labels.get('thumb', thumb)
    fanart = info_labels.get('fanart', _globals.DefaultFanart)
    poster = info_labels.get('poster', thumb)

    listitem = ListItem_InfoTag(name)
    listitem.setProperty('IsPlayable', 'false')
    listitem.setArt({
        'fanart': fanart,
        'poster': poster,
        'icon': thumb,
        'thumb': thumb
    })

    # NEW: force a visible line in list view
    track_summary = _build_track_summary(info_labels)
    if track_summary:
        listitem.setLabel2(track_summary)

    if info_labels:
        info_labels = _enrich_plot_with_tracks(info_labels)
        listitem.set_Info('Video', info_labels)

        total_seasons = info_labels.get('totalseasons')
        if total_seasons is not None:
            listitem.setProperty('totalseasons', str(total_seasons))

        if poster:
            listitem.setArt({'tvshow.poster': poster})

        _apply_extra_media_props(listitem, info_labels)

    if cm:
        listitem.addContextMenuItems(cm)

    is_folder = (mode not in ('switchUser', 'text')) if using_atv else (mode == 'True')
    xbmcplugin.addDirectoryItem(_globals.pluginhandle, plugin_url, listitem, isFolder=is_folder)


# ---------------------------------------------------------------------------
# video item
# ---------------------------------------------------------------------------
def addVideo(name, asin, info_labels, cm=None, export=False):
    info_labels = info_labels or {}

    base_params = {
        'asin': asin,
        'mode': 'PlayVideo',
        'name': name,
        'adult': info_labels.get('isAdult', 0),
    }
    url = f'{_globals.pluginid}?{urlencode(base_params)}'

    bitrate = '0'
    stream_types = {'live': 2, 'event': 3}

    thumb = info_labels.get('thumb', _globals.DefaultFanart)
    fanart = info_labels.get('fanart', _globals.DefaultFanart)
    poster = info_labels.get('poster', thumb)

    listitem = ListItem_InfoTag(name)
    listitem.setArt({'fanart': fanart, 'poster': poster, 'thumb': thumb})
    listitem.setProperty('IsPlayable', 'true')

    # NEW: force a visible line in list view
    track_summary = _build_track_summary(info_labels)
    if track_summary:
        listitem.setLabel2(track_summary)

    audio_channels = info_labels.get('audiochannels')
    if audio_channels:
        listitem.add_StreamInfo('audio', {'codec': 'ac3', 'channels': int(audio_channels)})

    if poster:
        listitem.setArt({'tvshow.poster': poster})

    if info_labels.get('TrailerAvailable'):
        info_labels['trailer'] = url + '&trailer=1&selbitrate=0'

    content_type = info_labels.get('contentType')
    url += f'&trailer={stream_types.get(content_type, 0)}'

    name_mix = (info_labels.get('tvshowtitle', '') + name).lower()
    if any(tag in name_mix for tag in ('4k', 'uhd', 'ultra hd')):
        listitem.add_StreamInfo('video', {'width': 3840, 'height': 2160})
    elif info_labels.get('isHD'):
        listitem.add_StreamInfo('video', {'width': 1920, 'height': 1080})

    selected_audio_id = info_labels.get('selected_audio_id')
    selected_subtitle_id = info_labels.get('selected_subtitle_id')
    if selected_audio_id:
        url += f'&selaudio={selected_audio_id}'
    if selected_subtitle_id:
        url += f'&selsub={selected_subtitle_id}'

    if export:
        url += '&selbitrate=' + bitrate
        Export(info_labels, url)
        return

    context_menu = cm[:] if cm else []
    context_menu.insert(0, (getString(30101), 'Action(ToggleWatched)'))

    info_labels = _enrich_plot_with_tracks(info_labels)
    listitem.set_Info('Video', info_labels)
    _apply_extra_media_props(listitem, info_labels)
    listitem.addContextMenuItems(context_menu)

    url += '&selbitrate=' + bitrate
    xbmcplugin.addDirectoryItem(_globals.pluginhandle, url, listitem, isFolder=False)


# ---------------------------------------------------------------------------
# listitem wrapper
# ---------------------------------------------------------------------------
class ListItem_InfoTag(xbmcgui.ListItem):
    """
    Map our info_labels dict onto Kodi's InfoTagVideo API (Kodi 19+),
    with fallback to classic setInfo for older Kodis.
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
        if _globals.KodiVersion > 19:
            if self.info_tag is None:
                self.info_tag = self.getVideoInfoTag()
            for key, value in infos.items():
                if value is None:
                    continue
                mapped = self.map.get(key)
                if not mapped:
                    continue
                setattr_fn = getattr(self.info_tag, mapped['attr'])
                setattr_fn(mapped['convert'](value))
        else:
            self.setInfo(ctype, self._clean_infos(infos))

    def add_StreamInfo(self, ctype, infos):
        if _globals.KodiVersion > 19:
            if self.info_tag is None:
                self.info_tag = self.getVideoInfoTag()
            add_stream = getattr(self.info_tag, f'add{ctype.capitalize()}Stream')
            stream_detail = getattr(xbmc, f'{ctype.capitalize()}StreamDetail')
            add_stream(stream_detail(**infos))
        else:
            self.addStreamInfo(ctype, infos)

    def _clean_infos(self, infos):
        if not infos:
            return {}
        allowed = {k.lower() for k in self.map.keys()}
        return {k: v for k, v in infos.items() if k.lower() in allowed}
