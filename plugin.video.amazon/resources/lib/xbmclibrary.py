#!/usr/bin/env python
# -*- coding: utf-8 -*-
from common import *
import movies as moviesDB
import tv as tvDB
import listtv
import listmovie

from BeautifulSoup import BeautifulSoup, Tag

cr_nfo = addon.getSetting('cr_nfo') == 'true'
ms_mov = addon.getSetting('mediasource_movie')
ms_tv = addon.getSetting('mediasource_tv')
ms_mov = ms_mov if ms_mov else 'Amazon Movies'
ms_tv = ms_tv if ms_tv else 'Amazon TV'

if addon.getSetting('enablelibraryfolder') == 'true':
    MOVIE_PATH = os.path.join(xbmc.translatePath(addon.getSetting('customlibraryfolder')), 'Movies').decode('utf-8')
    TV_SHOWS_PATH = os.path.join(xbmc.translatePath(addon.getSetting('customlibraryfolder')), 'TV').decode('utf-8')
else:
    MOVIE_PATH = os.path.join(pldatapath, 'Movies')
    TV_SHOWS_PATH = os.path.join(pldatapath, 'TV')


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


def streamDetails(Infol, language='ger', hasSubtitles=False):
    Info = {}
    for k,v in Infol.items():
        if isinstance(v, str):
            v = unicode(v.decode('utf-8'))
        if isinstance(v, list):
            v = [i.decode('utf-8') for i in v if isinstance(i, str)]
        Info.update({k: v})

    skip_keys = ('ishd', 'isadult', 'audiochannels', 'genre', 'cast', 'duration', 'trailer', 'asins')
    fileinfo = u'<runtime>%s</runtime>' % Info['Duration']
    if 'Genre' in Info.keys() and Info['Genre']:
        for genre in Info['Genre'].split('/'):
            fileinfo += u'<genre>%s</genre>' % genre.strip()
    if 'Cast' in Info.keys():
        for actor in Info['Cast']:
            fileinfo += u'<actor>'
            fileinfo += u'<name>%s</name>' % actor.strip()
            fileinfo += u'</actor>'
    for key, value in Info.items():
        lkey = key.lower()
        if lkey == 'premiered' and 'TVShowTitle' in Info.keys():
            fileinfo += u'<aired>%s</aired>' % value
        elif lkey == 'fanart':
            fileinfo += u'<%s><thumb>%s</thumb></%s>' % (lkey, value, lkey)
        elif lkey not in skip_keys:
            fileinfo += u'<%s>%s</%s>' % (lkey, value, lkey)
    fileinfo += u'<fileinfo>'
    fileinfo += u'<streamdetails>'
    fileinfo += u'<audio>'
    fileinfo += u'<channels>%s</channels>' % Info['AudioChannels']
    fileinfo += u'<codec>aac</codec>'
    fileinfo += u'</audio>'
    fileinfo += u'<video>'
    fileinfo += u'<codec>h264</codec>'
    fileinfo += u'<durationinseconds>%s</durationinseconds>' % Info['Duration']
    if Info['isHD']:
        fileinfo += u'<height>1080</height>'
        fileinfo += u'<width>1920</width>'
    else:
        fileinfo += u'<height>480</height>'
        fileinfo += u'<width>720</width>'
    fileinfo += u'<language>%s</language>' % language
    fileinfo += u'<scantype>Progressive</scantype>'
    fileinfo += u'</video>'
    if hasSubtitles:
        fileinfo += u'<subtitle>'
        fileinfo += u'<language>ger</language>'
        fileinfo += u'</subtitle>'
    fileinfo += u'</streamdetails>'
    fileinfo += u'</fileinfo>'
    return fileinfo


def EXPORT_MOVIE(asin=False, makeNFO=cr_nfo):
    SetupLibrary()
    if not asin:
        asin = args.get('asin')
    for moviedata in moviesDB.lookupMoviedb(asin, single=False):
        Info = listmovie.ADD_MOVIE_ITEM(moviedata, onlyinfo=True)
        filename = Info['Title']
        folder = os.path.join(MOVIE_PATH, cleanName(filename))
        Log('Amazon Export: ' + filename)
        strm_file = filename + ".strm"
        u = '%s?%s' % (sys.argv[0], urllib.urlencode({'asin': asin,
                                                      'mode': 'play',
                                                      'name': Info['Title'],
                                                      'sitemode': 'PLAYVIDEO',
                                                      'adult': Info['isAdult'],
                                                      'trailer': 0,
                                                      'selbitrate': 0}))
        SaveFile(strm_file, u, folder)

        if makeNFO:
            nfo_file = filename + ".nfo"
            nfo = '<movie>'
            nfo += streamDetails(Info)
            nfo += '</movie>'
            SaveFile(nfo_file, nfo, folder)


def EXPORT_SHOW(asin=None):
    if not asin:
        asin = args.get('asin')
    for data in tvDB.lookupTVdb(asin, tbl='shows', single=False):
        Info = listtv.ADD_SHOW_ITEM(data, onlyinfo=True)
        for showasin in Info['Asins'].split(','):
            asins = tvDB.lookupTVdb(showasin, rvalue='asin', tbl='seasons', name='seriesasin', single=False)
            for asin in asins:
                if asin:
                    EXPORT_SEASON(asin[0].split(',')[0])


def EXPORT_SEASON(asin=None, dispnotif=True):
    if not asin:
        asin = args.get('asin')
    for data in tvDB.lookupTVdb(asin, tbl='seasons', single=False):
        Info = listtv.ADD_SEASON_ITEM(data, onlyinfo=True)
        for seasonasin in Info['Asins'].split(','):
            asins = tvDB.lookupTVdb(seasonasin, rvalue='asin', name='seasonasin', single=False)
            for asin in asins:
                if asin:
                    EXPORT_EPISODE(asin[0].split(',')[0], dispnotif=dispnotif)
                    dispnotif = False


def EXPORT_EPISODE(asin=None, makeNFO=cr_nfo, dispnotif=True):
    if not asin:
        asin = args.get('asin')
    for data in tvDB.lookupTVdb(asin, single=False):
        Info = listtv.ADD_EPISODE_ITEM(data, onlyinfo=True)
        Info['Title'] = cleanName(Info['EpisodeName'])
        showname = cleanName(Info['TVShowTitle'])
        directorname = os.path.join(TV_SHOWS_PATH, showname)
        name = 'Season ' + str(Info['Season'])
        if dispnotif:
            SetupLibrary()
            Log('Amazon Export: %s %s' % (showname, name))
        seasonpath = os.path.join(directorname, name)
        filename = '%s - S%02dE%02d - %s' % (showname, Info['Season'], Info['Episode'], Info['Title'])
        strm_file = filename + ".strm"
        u = '%s?%s' % (sys.argv[0], urllib.urlencode({'asin': asin,
                                                      'mode': 'play',
                                                      'name': '',
                                                      'sitemode': 'PLAYVIDEO',
                                                      'adult': Info['isAdult'],
                                                      'trailer': 0,
                                                      'selbitrate': 0}))
        SaveFile(strm_file, u, seasonpath)

        if makeNFO:
            nfo_file = filename + u".nfo"
            nfo = u'<episodedetails>'
            nfo += streamDetails(Info)
            nfo += u'</episodedetails>'
            SaveFile(nfo_file, nfo, seasonpath)


def SetupAmazonLibrary():
    source_path = xbmc.translatePath('special://profile/sources.xml').decode('utf-8')
    source_added = False
    source = {ms_mov: MOVIE_PATH, ms_tv: TV_SHOWS_PATH}

    if xbmcvfs.exists(source_path):
        srcfile = xbmcvfs.File(source_path)
        soup = BeautifulSoup(srcfile)
        srcfile.close()
    else:
        subtags = ['programs', 'video', 'music', 'pictures', 'files']
        soup = BeautifulSoup('<sources></sources>')
        root = soup.sources
        for cat in subtags:
            cat_tag = Tag(soup, cat)
            def_tag = Tag(soup, 'default')
            def_tag['pathversion'] = 1
            cat_tag.append(def_tag)
            root.append(cat_tag)

    video = soup.find("video")

    for name, path in source.items():
        path_tag = Tag(soup, "path")
        path_tag['pathversion'] = 1
        path_tag.append(path)
        source_text = soup.find(text=name)
        if not source_text:
            source_tag = Tag(soup, "source")
            name_tag = Tag(soup, "name")
            name_tag.append(name)
            source_tag.append(name_tag)
            source_tag.append(path_tag)
            video.append(source_tag)
            Log(name + ' source path added')
            source_added = True
        else:
            source_tag = source_text.findParent('source')
            old_path = source_tag.find('path').contents[0]
            if path not in old_path:
                source_tag.find('path').replaceWith(path_tag)
                Log(name + ' source path changed')
                source_added = True

    if source_added:
        SaveFile(source_path, str(soup))
        Dialog.ok(getString(30187), getString(30188), getString(30189), getString(30190))
        if Dialog.yesno(getString(30191), getString(30192)):
            xbmc.executebuiltin('RestartApp')
