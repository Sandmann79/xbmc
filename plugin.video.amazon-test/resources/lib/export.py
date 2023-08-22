#!/usr/bin/env python
# -*- coding: utf-8 -*-import pyxbmct
from __future__ import unicode_literals
import os.path
import re

from kodi_six import xbmc, xbmcvfs
from kodi_six.utils import py2_decode

from .common import Globals, Settings
from .logging import Log
from .l10n import getString

_s = Settings()
_g = Globals()


def Export(infoLabels, url):
    isEpisode = infoLabels['contentType'] != 'movie'
    isEvent = 'tvshowtitle' not in infoLabels and isEpisode
    language = xbmc.convertLanguage(_s.Language, xbmc.ISO_639_2)
    ExportPath = _s.MOVIE_PATH
    nfoType = 'movie'
    title = infoLabels['title']

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
            filename = '%s - S%02dE%02d - %s' % (infoLabels['tvshowtitle'], infoLabels['season'],
                                                 infoLabels['episode'], infoLabels['title'])

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
        outfile.write(bytearray(py2_decode(data).encode('utf-8')))


def CreateDirectory(dir_path):
    dir_path = _cleanName(dir_path.strip(), isfile=False)
    if not xbmcvfs.exists(dir_path):
        return xbmcvfs.mkdirs(dir_path)
    return False


def SetupLibrary():
    CreateDirectory(_s.MOVIE_PATH)
    CreateDirectory(_g.HOME_PATH)
    SetupAmazonLibrary()


def CreateInfoFile(nfofile, path, content, Info, language, hasSubtitles=False):
    skip_keys = ('ishd', 'isadult', 'audiochannels', 'genre', 'cast', 'duration', 'asins', 'contentType', 'seriesasin', 'contenttype', 'mediatype',
                 'poster', 'isprime', 'seasonasin')
    fileinfo = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'
    fileinfo += '<%s>\n' % content
    if 'Duration' in Info.keys():
        fileinfo += '<runtime>%s</runtime>\n' % Info['Duration']
    if 'Genre' in Info.keys():
        for genre in Info['genre'].split('/'):
            fileinfo += '<genre>%s</genre>\n' % genre.strip()
    if 'Cast' in Info.keys():
        for actor in Info['Cast']:
            fileinfo += '<actor>\n'
            fileinfo += '    <name>%s</name>\n' % actor.strip()
            fileinfo += '</actor>\n'
    for key, value in Info.items():
        lkey = key.lower()
        if value:
            if lkey == 'tvshowtitle':
                fileinfo += '<showtitle>%s</showtitle>\n' % value
            elif lkey == 'premiered' and 'tvshowtitle' in Info:
                fileinfo += '<aired>%s</aired>\n' % value
            elif lkey == 'thumb':
                aspect = '' if 'episode' in content else ' aspect="poster"'
                fileinfo += '<%s%s>%s</%s>\n' % (lkey, aspect, value, lkey)
            elif lkey == 'fanart' and not 'episode' in content:
                fileinfo += '<%s>\n    <thumb>%s</thumb>\n</%s>\n' % (lkey, value, lkey)
            elif lkey not in skip_keys:
                fileinfo += '<%s>%s</%s>\n' % (lkey, value, lkey)

    if content != 'tvshow':
        fileinfo += '<fileinfo>\n'
        fileinfo += '   <streamdetails>\n'
        if 'audiochannels' in Info:
            fileinfo += '       <audio>\n'
            fileinfo += '           <channels>%s</channels>\n' % Info['audiochannels']
            fileinfo += '           <codec>aac</codec>\n'
            fileinfo += '       </audio>\n'
        fileinfo += '       <video>\n'
        fileinfo += '           <codec>h264</codec>\n'
        if 'duration' in Info:
            fileinfo += '           <durationinseconds>%s</durationinseconds>\n' % Info['duration']
        if 'isHD' in Info:
            if Info['isHD']:
                fileinfo += '           <height>1080</height>\n'
                fileinfo += '           <width>1920</width>\n'
            else:
                fileinfo += '           <height>480</height>\n'
                fileinfo += '           <width>720</width>\n'
        if language:
            fileinfo += '           <language>%s</language>\n' % language
        fileinfo += '           <scantype>Progressive</scantype>\n'
        fileinfo += '       </video>\n'
        fileinfo += '   </streamdetails>\n'
        fileinfo += '</fileinfo>\n'
    fileinfo += '</%s>\n' % content

    SaveFile(nfofile + '.nfo', fileinfo, path)
    return


def SetupAmazonLibrary():
    import xml.etree.ElementTree as et
    from contextlib import closing
    from .common import translatePath
    source_path = py2_decode(translatePath('special://profile/sources.xml'))
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


