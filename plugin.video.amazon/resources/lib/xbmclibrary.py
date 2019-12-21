#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from . import movies as moviesDB
from . import tv as tvDB
from .common import *
from bs4 import BeautifulSoup

cr_nfo = var.addon.getSetting('cr_nfo') == 'true'
ms_mov = var.addon.getSetting('mediasource_movie')
ms_tv = var.addon.getSetting('mediasource_tv')
EXPORT_PATH = pldatapath
if var.addon.getSetting('enablelibraryfolder') == 'true':
    EXPORT_PATH = xbmc.translatePath(var.addon.getSetting('customlibraryfolder'))
sep = '\\' if '\\' in EXPORT_PATH else '/'
MOVIE_PATH = os.path.join(EXPORT_PATH, 'Movies') + sep
TV_SHOWS_PATH = os.path.join(EXPORT_PATH, 'TV') + sep
ms_mov = ms_mov if ms_mov else 'Amazon Movies'
ms_tv = ms_tv if ms_tv else 'Amazon TV'


def UpdateLibrary():
    xbmc.executebuiltin('UpdateLibrary(video)')


def CreateDirectory(dir_path):
    dir_path = cleanName(dir_path.strip(), isfile=False)
    if not xbmcvfs.exists(dir_path):
        return xbmcvfs.mkdirs(dir_path)
    return False


def SetupLibrary():
    CreateDirectory(MOVIE_PATH)
    CreateDirectory(TV_SHOWS_PATH)
    SetupAmazonLibrary()


def streamDetails(Info, content, language='ger', hasSubtitles=False):
    skip_keys = ('ishd', 'isadult', 'audiochannels', 'genre', 'cast', 'duration', 'trailer', 'asins', 'poster', 'seriesasin')
    fileinfo = '<{}>'.format(content)
    fileinfo += '<runtime>{}</runtime>'.format(Info['Duration'])
    if 'Genre' in Info.keys() and Info['Genre']:
        for genre in Info['Genre'].split('/'):
            fileinfo += '<genre>{}</genre>'.format(genre.strip())
    if 'Cast' in Info.keys():
        for actor in Info['Cast']:
            fileinfo += '<actor>'
            fileinfo += '<name>{}</name>'.format(actor.strip())
            fileinfo += '</actor>'
    for key, value in Info.items():
        lkey = key.lower()
        if value:
            if lkey == 'tvshowtitle':
                fileinfo += '<showtitle>{}</showtitle>'.format(value)
            if lkey == 'premiered' and 'TVShowTitle' in Info.keys():
                fileinfo += '<aired>{}</aired>'.format(value)
            elif lkey == 'thumb':
                aspect = '' if 'episode' in content else ' aspect="poster"'
                fileinfo += '<{}{}>{}</{}>'.format(lkey, aspect, value, lkey)
            elif lkey == 'fanart':
                fileinfo += '<{}><thumb>{}</thumb></{}>'.format(lkey, value, lkey)
            elif lkey not in skip_keys:
                fileinfo += '<{}>{}</{}>'.format(lkey, value, lkey)

    fileinfo += '<fileinfo>'
    fileinfo += '<streamdetails>'
    fileinfo += '<audio>'
    fileinfo += '<channels>{}</channels>'.format(Info['AudioChannels'])
    fileinfo += '<codec>aac</codec>'
    fileinfo += '</audio>'
    fileinfo += '<video>'
    fileinfo += '<codec>h264</codec>'
    fileinfo += '<durationinseconds>{}</durationinseconds>'.format(Info['Duration'])
    if Info['isHD']:
        fileinfo += '<height>1080</height>'
        fileinfo += '<width>1920</width>'
    else:
        fileinfo += '<height>480</height>'
        fileinfo += '<width>720</width>'
    fileinfo += '<language>{}</language>'.format(language)
    fileinfo += '<scantype>Progressive</scantype>'
    fileinfo += '</video>'
    if hasSubtitles:
        fileinfo += '<subtitle>'
        fileinfo += '<language>ger</language>'
        fileinfo += '</subtitle>'
    fileinfo += '</streamdetails>'
    fileinfo += '</fileinfo>'
    fileinfo += '</{}>'.format(content)
    return fileinfo


def EXPORT_MOVIE(asin=False, makeNFO=cr_nfo):
    from .listmovie import ADD_MOVIE_ITEM
    SetupLibrary()
    if not asin:
        asin = var.args.get('asin')
    for moviedata in moviesDB.lookupMoviedb(asin, single=False):
        Info = ADD_MOVIE_ITEM(moviedata, onlyinfo=True)
        filename = Info['Title']
        folder = os.path.join(MOVIE_PATH, cleanName(filename))
        Log('Amazon Export: ' + filename)
        strm_file = filename + ".strm"
        u = '{}?{}'.format(sys.argv[0], urlencode({'asin': asin,
                                                   'mode': 'play',
                                                   'name': py2_encode(Info['Title']),
                                                   'sitemode': 'PLAYVIDEO',
                                                   'adult': Info['isAdult'],
                                                   'trailer': 0,
                                                   'selbitrate': 0}))
        SaveFile(strm_file, u, folder)

        if makeNFO:
            nfo_file = filename + ".nfo"
            SaveFile(nfo_file, streamDetails(Info, 'movie'), folder)


def EXPORT_SHOW(asin=None):
    from .listtv import ADD_SHOW_ITEM
    if not asin:
        asin = var.args.get('asin')
    for data in tvDB.lookupTVdb(asin, tbl='shows', single=False):
        Info = ADD_SHOW_ITEM(data, onlyinfo=True)
        for showasin in Info['Asins'].split(','):
            asins = tvDB.lookupTVdb(showasin, rvalue='asin', tbl='seasons', name='seriesasin', single=False)
            for asin in asins:
                if asin:
                    EXPORT_SEASON(asin[0].split(',')[0])


def EXPORT_SEASON(asin=None, dispnotif=True):
    from .listtv import ADD_SEASON_ITEM
    if not asin:
        asin = var.args.get('asin')
    for data in tvDB.lookupTVdb(asin, tbl='seasons', single=False):
        Info = ADD_SEASON_ITEM(data, onlyinfo=True)
        for seasonasin in Info['Asins'].split(','):
            asins = tvDB.lookupTVdb(seasonasin, rvalue='asin', name='seasonasin', single=False)
            for asin in asins:
                if asin:
                    EXPORT_EPISODE(asin[0].split(',')[0], dispnotif=dispnotif)
                    dispnotif = False


def EXPORT_EPISODE(asin=None, makeNFO=cr_nfo, dispnotif=True):
    from .listtv import ADD_EPISODE_ITEM
    if not asin:
        asin = var.args.get('asin')
    for data in tvDB.lookupTVdb(asin, single=False):
        Info = ADD_EPISODE_ITEM(data, onlyinfo=True)
        Info['Title'] = cleanName(Info['EpisodeName'])
        showname = cleanName(Info['TVShowTitle'])
        directorname = os.path.join(TV_SHOWS_PATH, showname)
        name = 'Season ' + str(Info['Season'])
        if dispnotif:
            SetupLibrary()
            Log('Amazon Export: {} {}'.format(showname, name))
        seasonpath = os.path.join(directorname, name)
        filename = '{} - S{:02d}E{:02d} - {}'.format(showname, Info['Season'], Info['Episode'], Info['Title'])
        strm_file = filename + ".strm"
        u = '{}?{}'.format(sys.argv[0], urlencode({'asin': asin,
                                                   'mode': 'play',
                                                   'name': '',
                                                   'sitemode': 'PLAYVIDEO',
                                                   'adult': Info['isAdult'],
                                                   'trailer': 0,
                                                   'selbitrate': 0}))
        SaveFile(strm_file, u, seasonpath)

        if makeNFO:
            nfo_file = filename + u".nfo"
            SaveFile(nfo_file, streamDetails(Info, 'episodedetails'), seasonpath)


def SetupAmazonLibrary():
    from contextlib import closing
    import xml.etree.ElementTree as et
    source_path = xbmc.translatePath('special://profile/sources.xml')
    source_added = False
    source_dict = {ms_mov: MOVIE_PATH, ms_tv: TV_SHOWS_PATH}

    if xbmcvfs.exists(source_path):
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
                if tag.findtext('name') in src_name and tag.findtext('path') not in src_path:
                    tag.find('path').text = src_path
                    Log(src_name + ' source path changed')
                    source_added = True

    if source_added:
        with closing(xbmcvfs.File(source_path, 'w')) as fo:
            fo.write(bytearray(et.tostring(root, 'utf-8')))
        Dialog.ok(getString(30187), getString(30188), getString(30189), getString(30190))
        if Dialog.yesno(getString(30191), getString(30192)):
            xbmc.executebuiltin('RestartApp')
