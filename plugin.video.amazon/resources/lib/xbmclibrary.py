#!/usr/bin/env python
# -*- coding: utf-8 -*-
import common
import movies as moviesDB
import tv as tvDB
import listtv
import listmovie

from BeautifulSoup import BeautifulStoneSoup
from BeautifulSoup import BeautifulSoup , Tag, NavigableString

pluginhandle = common.pluginhandle
xbmc = common.xbmc
xbmcplugin = common.xbmcplugin
urllib = common.urllib
sys = common.sys
xbmcgui = common.xbmcgui
os = common.os
dialog = xbmcgui.Dialog()

if (common.addon.getSetting('enablelibraryfolder') == 'true'):
    MOVIE_PATH = os.path.join(xbmc.translatePath(common.addon.getSetting('customlibraryfolder')),'Movies').decode('utf-8')
    TV_SHOWS_PATH = os.path.join(xbmc.translatePath(common.addon.getSetting('customlibraryfolder')),'TV').decode('utf-8')
else:
    MOVIE_PATH = os.path.join(common.pldatapath,'Movies')
    TV_SHOWS_PATH = os.path.join(common.pldatapath,'TV')
    
def UpdateLibrary():
    xbmc.executebuiltin('UpdateLibrary(video)')
    
def SaveFile(filename, data, dir=False):
    filename = common.cleanName(filename)
    if dir:
        filename = os.path.join(dir, filename)
    file = open(filename,'w')
    file.write(data)
    file.close()

def CreateDirectory(dir_path):
    dir_path = dir_path.strip()
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
        return True
    return False

def SetupLibrary():
    if CreateDirectory(MOVIE_PATH):
        CreateDirectory(TV_SHOWS_PATH) 
        SetupAmazonLibrary()

def streamDetails(Info, language='ger', hasSubtitles=False):
    skip_keys = ('ishd', 'isadult', 'audiochannels', 'genre', 'cast', 'duration', 'trailer', 'asins')
    fileinfo  = '<runtime>%s</runtime>' % Info['Duration']
    if Info.has_key('Genre'):
        for genre in Info['Genre'].split('/'):
            fileinfo += '<genre>%s</genre>' % genre.strip()
    if Info.has_key('Cast'):
        for actor in Info['Cast']:
            fileinfo += '<actor>'
            fileinfo += '<name>%s</name>' % actor.strip()
            fileinfo += '</actor>'
    for key, value in Info.items():
        lkey = key.lower()
        if lkey == 'premiered' and Info.has_key('TVShowTitle'):
            fileinfo += '<aired>%s</aired>' % value
        elif lkey == 'fanart':
            fileinfo += '<%s><thumb>%s</thumb></%s>' % (lkey, value, lkey)
        elif lkey not in skip_keys:
            fileinfo += '<%s>%s</%s>' % (lkey, value, lkey)
    fileinfo += '<fileinfo>'
    fileinfo += '<streamdetails>'
    fileinfo += '<audio>'
    fileinfo += '<channels>%s</channels>' % Info['AudioChannels']
    fileinfo += '<codec>aac</codec>'
    fileinfo += '</audio>'
    fileinfo += '<video>'
    fileinfo += '<codec>h264</codec>'
    fileinfo += '<durationinseconds>%s</durationinseconds>' % (int(Info['Duration']) * 60)
    if Info['isHD'] == True:
        fileinfo += '<height>720</height>'
        fileinfo += '<width>1280</width>'
    else:
        fileinfo += '<height>480</height>'
        fileinfo += '<width>720</width>'        
    fileinfo += '<language>%s</language>' % language
    #fileinfo += '<longlanguage>German</longlanguage>'
    fileinfo += '<scantype>Progressive</scantype>'
    fileinfo += '</video>'
    if hasSubtitles == True:
        fileinfo += '<subtitle>'
        fileinfo += '<language>ger</language>'
        fileinfo += '</subtitle>'
    fileinfo += '</streamdetails>'
    fileinfo += '</fileinfo>'
    return fileinfo

def EXPORT_MOVIE(asin=False, makeNFO=True):
    SetupLibrary()
    if not asin: asin = common.args.asin
    for moviedata in moviesDB.lookupMoviedb(asin, single=False):
        Info = listmovie.ADD_MOVIE_ITEM(moviedata, onlyinfo=True)
        filename = Info['Title']
        if Info['Year']:
            filename = '%s (%s)' % (Info['Title'], Info['Year'])
        #dialog.notification('Export', filename, sound = False)
        common.Log('Amazon Export: ' + filename)
        strm_file = filename + ".strm"
        u  = '%s?asin=<%s>&mode=<play>&name=<%s>&sitemode=<PLAYVIDEO>&adult=<%s>&trailer=<0>&selbitrate=<0>' % (sys.argv[0], asin, urllib.quote_plus(Info['Title']), Info['isAdult'])
        SaveFile(strm_file, u, MOVIE_PATH)
        
        if makeNFO:
            nfo_file = filename + ".nfo"
            nfo = '<movie>'
            nfo+= streamDetails(Info)
            nfo+= '</movie>'
            SaveFile(nfo_file, nfo, MOVIE_PATH)
        
def EXPORT_SHOW(asin=False, dispnotif = True):
    SetupLibrary()
    if not asin: asin=common.args.asin
    for data in tvDB.lookupTVdb(asin, tbl='shows', single=False):
        Info = listtv.ADD_SHOW_ITEM(data, onlyinfo=True)
        directorname = os.path.join(TV_SHOWS_PATH, common.cleanName(Info['Title']))
        CreateDirectory(directorname)
        for showasin in Info['Asins'].split(','):
            asins = tvDB.lookupTVdb(showasin, rvalue='asin', tbl='seasons', name='seriesasin', single=False)
            for asin in asins:
                if asin:
                    EXPORT_SEASON(asin[0].split(',')[0])
    
def EXPORT_SEASON(asin=False, dispnotif = True):
    SetupLibrary()
    if not asin: asin=common.args.asin
    for data in tvDB.lookupTVdb(asin, tbl='seasons', single=False):
        Info = listtv.ADD_SEASON_ITEM(data, onlyinfo=True)
        directorname = os.path.join(TV_SHOWS_PATH, common.cleanName(Info['Title']))
        CreateDirectory(directorname)
        name = 'Season '+str(Info['Season'])
        seasonpath = os.path.join(directorname,name)
        CreateDirectory(seasonpath)
        for seasonasin in Info['Asins'].split(','):
            asins = tvDB.lookupTVdb(seasonasin, rvalue='asin', name='seasonasin', single=False)
            for asin in asins:
                if asin:
                    EXPORT_EPISODE(asin[0].split(',')[0], dispnotif=dispnotif)
                    dispnotif = False
def EXPORT_EPISODE(asin=False, makeNFO=True, dispnotif = True):
    SetupLibrary()
    if not asin: asin=common.args.asin
    for data in tvDB.lookupTVdb(asin, single=False):
        Info = listtv.ADD_EPISODE_ITEM(data, onlyinfo=True)
        showname = common.cleanName(Info['TVShowTitle'])
        directorname = os.path.join(TV_SHOWS_PATH, showname)
        CreateDirectory(directorname)
        name = 'Season '+str(Info['Season'])
        if dispnotif:
            common.Log('Amazon Export: %s %s' %(showname, name))
            #dialog.notification('Export', showname + ' ' + name, sound = False)
            dispnotif = False
        seasonpath = os.path.join(directorname,name)
        CreateDirectory(seasonpath)
        filename = 'S%02dE%02d - %s' % (Info['Season'], Info['Episode'], Info['Title'])
        strm_file = filename + ".strm"
        u  = '%s?asin=<%s>&mode=<play>&name=<%s>&sitemode=<PLAYVIDEO>&adult=<%s>&trailer=<0>&selbitrate=<0>' % (sys.argv[0], asin, urllib.quote_plus(Info['Title']), Info['isAdult']) 
        SaveFile(strm_file, u, seasonpath)

        if makeNFO:
            nfo_file = filename + ".nfo"
            nfo = '<episodedetails>'
            nfo+= streamDetails(Info)
            nfo+= '</episodedetails>'
            SaveFile(nfo_file, nfo, seasonpath)

def SetupAmazonLibrary():
    print "Trying to add Amazon source paths..."
    source_path = os.path.join(xbmc.translatePath('special://masterprofile/'), 'sources.xml').decode('utf-8')
    source_added = False
    
    try:
        file = open(source_path)
        soup = BeautifulSoup(file)
        file.close()
    except:
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
        
    if len(soup.findAll(text="Amazon Movies")) < 1:
        movie_source_tag = Tag(soup, "source")
        movie_name_tag = Tag(soup, "name")
        movie_name_tag.insert(0, "Amazon Movies")
        movie_path_tag = Tag(soup, "path")
        movie_path_tag['pathversion'] = 1
        movie_path_tag.insert(0, MOVIE_PATH)
        movie_source_tag.insert(0, movie_name_tag)
        movie_source_tag.insert(1, movie_path_tag)
        video.insert(2, movie_source_tag)
        source_added = True

    if len(soup.findAll(text="Amazon TV")) < 1: 
        tvshow_source_tag = Tag(soup, "source")
        tvshow_name_tag = Tag(soup, "name")
        tvshow_name_tag.insert(0, "Amazon TV")
        tvshow_path_tag = Tag(soup, "path")
        tvshow_path_tag['pathversion'] = 1
        tvshow_path_tag.insert(0, TV_SHOWS_PATH)
        tvshow_source_tag.insert(0, tvshow_name_tag)
        tvshow_source_tag.insert(1, tvshow_path_tag)
        video.insert(2, tvshow_source_tag)
        source_added = True
    
    if source_added:
        print "Source paths added!"
        SaveFile(source_path, str(soup))
        dialog.ok(common.getString(30187), common.getString(30188), common.getString(30189), common.getString(30190))
        if dialog.yesno(common.getString(30191), common.getString(30192)):
            xbmc.executebuiltin('RestartApp')