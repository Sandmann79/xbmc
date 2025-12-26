#!/usr/bin/env python
# -*- coding: utf-8 -*-import pyxbmct

import datetime
import os.path
import re

import xbmc, xbmcvfs

from .common import Globals, Settings
from .logging import Log
from .l10n import getString

_s = Settings()
_g = Globals()


def Export(infoLabels, url):
    isEpisode = infoLabels['contentType'] != 'movie'
    isEvent = 'tvshowtitle' not in infoLabels and isEpisode
    isAired = datetime.date.today() >= datetime.date.fromisoformat(infoLabels.get('premiered') or '1970-01-01')
    language = xbmc.convertLanguage(_s.Language, xbmc.ISO_639_2)
    ExportPath = _s.MOVIE_PATH
    nfoType = 'movie'
    title = infoLabels['title']

    if not isAired and not _s.export_not_aired:
        return

    if isEpisode:
        ExportPath = _s.TV_SHOWS_PATH
        if not isEvent:
            title = infoLabels['tvshowtitle']

    tl = title.lower()
    if '[omu]' in tl or '[ov]' in tl or ' omu' in tl:
        language = ''
    filename = re.sub(r'(?i)\[.*| omu| ov', '', title).strip()
    ExportPath = os.path.join(ExportPath, _cleanName(filename))

    if isEpisode:
        infoLabels['tvshowtitle'] = filename
        nfoType = 'episodedetails'
        if not isEvent:
            filename = f"{infoLabels['tvshowtitle']} - S{infoLabels['season']:02}E{infoLabels['episode']:02} - {infoLabels['title']}"
    if _s.cr_nfo == 'true':
        CreateInfoFile(filename, ExportPath, nfoType, infoLabels, language)

    SaveFile(filename + '.strm', url, ExportPath)
    Log('Export: ' + filename)


def _cleanName(name, isfile=True):
    notallowed = ['<', '>', ':', '"', '\\', '/', '|', '*', '?', '´']
    if not isfile:
        notallowed = ['<', '>', '"', '|', '*', '?', '´']
    for c in notallowed:
        name = name.replace(c, '')
    if not os.path.supports_unicode_filenames and not isfile:
        name = name.encode('utf-8')
    return name


def SaveFile(filename, data, isdir=None, mode='w'):
    from contextlib import closing
    if isdir:
        filename = _cleanName(filename)
        filename = os.path.join(isdir, filename)
        if not xbmcvfs.exists(isdir):
            xbmcvfs.mkdirs(_cleanName(isdir.strip(), isfile=False))
    filename = _cleanName(filename, isfile=False)
    with closing(xbmcvfs.File(filename, mode)) as outfile:
        outfile.write(bytearray(data.encode('utf-8')))


def CreateDirectory(dir_path):
    dir_path = _cleanName(dir_path.strip(), isfile=False)
    if not xbmcvfs.exists(dir_path):
        return xbmcvfs.mkdirs(dir_path)
    return False


def SetupLibrary():
    CreateDirectory(_s.MOVIE_PATH)
    CreateDirectory(_s.TV_SHOWS_PATH)
    SetupAmazonLibrary()


def CreateInfoFile(nfofile, path, content, Info, language, hasSubtitles=False):
    skip_keys = ('ishd', 'isadult', 'audiochannels', 'genre', 'cast', 'duration', 'asins', 'contentType', 'seriesasin', 'contenttype', 'mediatype',
                 'poster', 'isprime', 'seasonasin')
    fileinfo = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'
    fileinfo += f'<{content}>\n'
    if 'Duration' in Info.keys():
        fileinfo += f"<runtime>{Info['Duration']}</runtime>\n"
    if 'Genre' in Info.keys():
        for genre in Info['genre'].split('/'):
            fileinfo += f'<genre>{genre.strip()}</genre>\n'
    if 'Cast' in Info.keys():
        for actor in Info['Cast']:
            fileinfo += '<actor>\n'
            fileinfo += f'    <name>{actor.strip()}</name>\n'
            fileinfo += '</actor>\n'
    for key, value in Info.items():
        lkey = key.lower()
        if value:
            if lkey == 'tvshowtitle':
                fileinfo += f'<showtitle>{value}</showtitle>\n'
            elif lkey == 'premiered' and 'tvshowtitle' in Info:
                fileinfo += f'<aired>{value}</aired>\n'
            elif lkey == 'thumb':
                aspect = '' if 'episode' in content else ' aspect="poster"'
                fileinfo += f'<{lkey}{aspect}>{value}</{lkey}>\n'
            elif lkey == 'fanart' and not 'episode' in content:
                fileinfo += f'<{lkey}>\n    <thumb>{value}</thumb>\n</{lkey}>\n'
            elif lkey not in skip_keys:
                fileinfo += f'<{lkey}>{value}</{lkey}>\n'

    if content != 'tvshow':
        fileinfo += '<fileinfo>\n'
        fileinfo += '   <streamdetails>\n'
        if 'audiochannels' in Info:
            fileinfo += '       <audio>\n'
            fileinfo += f"           <channels>{Info['audiochannels']}</channels>\n"
            fileinfo += '           <codec>aac</codec>\n'
            fileinfo += '       </audio>\n'
        fileinfo += '       <video>\n'
        fileinfo += '           <codec>h264</codec>\n'
        if 'duration' in Info:
            fileinfo += f"           <durationinseconds>{Info['duration']}</durationinseconds>\n"
        if 'isHD' in Info:
            if Info['isHD']:
                fileinfo += '           <height>1080</height>\n'
                fileinfo += '           <width>1920</width>\n'
            else:
                fileinfo += '           <height>480</height>\n'
                fileinfo += '           <width>720</width>\n'
        if language:
            fileinfo += f'           <language>{language}</language>\n'
        fileinfo += '           <scantype>Progressive</scantype>\n'
        fileinfo += '       </video>\n'
        fileinfo += '   </streamdetails>\n'
        fileinfo += '</fileinfo>\n'
    fileinfo += f'</{content}>\n'

    SaveFile(nfofile + '.nfo', fileinfo, path)
    return


def SetupAmazonLibrary():
    import xml.etree.ElementTree as et
    from contextlib import closing
    from .common import translatePath
    source_path = translatePath('special://profile/sources.xml')
    source_added = False
    source_dict = {_s.ms_mov: _s.MOVIE_PATH, _s.ms_tv: _s.TV_SHOWS_PATH}

    if xbmcvfs.exists(source_path) and xbmcvfs.Stat(source_path).st_size() > 0:
        with closing(xbmcvfs.File(source_path)) as fo:
            byte_string = bytes(fo.readBytes())
        root = et.fromstring(byte_string)
    else:
        subtags = ['programs', 'video', 'music', 'pictures', 'files']
        root = et.Element('sources')
        for cat in subtags:
            cat_tag = et.SubElement(root, cat)
            et.SubElement(cat_tag, 'default', attrib={'pathversion': '1'})

    for src_name, src_path in source_dict.items():
        video_tag = root.find('video')
        if not any(src_name == i.text for i in video_tag.iter()):
            source_tag = et.SubElement(video_tag, 'source')
            name_tag = et.SubElement(source_tag, 'name')
            path_tag = et.SubElement(source_tag, 'path', attrib={'pathversion': '1'})
            name_tag.text = src_name
            path_tag.text = src_path
            Log(src_name + ' source path added')
            source_added = True
        else:
            for tag in video_tag.iter('source'):
                if tag.findtext('name') == src_name and tag.findtext('path') != src_path:
                    tag.find('path').text = src_path
                    Log(src_name + ' source path changed')
                    source_added = True

    if source_added:
        with closing(xbmcvfs.File(source_path, 'w')) as fo:
            fo.write(bytearray(et.tostring(root, 'utf-8')))
        _g.dialog.ok(getString(30187), getString(30188))
        if _g.dialog.yesno(getString(30191), getString(30192)):
            xbmc.executebuiltin('RestartApp')


