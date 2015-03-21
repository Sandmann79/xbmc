#!/usr/bin/env python
# -*- coding: utf-8 -*-
from BeautifulSoup import BeautifulStoneSoup
from BeautifulSoup import BeautifulSoup
import common
import listtv
import listmovie

pluginhandle = common.pluginhandle
xbmc = common.xbmc
xbmcplugin = common.xbmcplugin
urllib = common.urllib
sys = common.sys
xbmcgui = common.xbmcgui
re = common.re
demjson = common.demjson
os = common.os

#Modes
#===============================================================================
# 'catalog/GetCategoryList'
# 'catalog/Browse'
# 'catalog/Search'
# 'catalog/GetSearchSuggestions'
# 'catalog/GetASINDetails'
# 'catalog/GetSimilarities'
# 
# 'catalog/GetStreamingUrls'
# 'catalog/GetStreamingTrailerUrls'
# 'catalog/GetContentUrls'
# 
# 'library/GetLibrary'
# 'library/Purchase'
# 'library/GetRecentPurchases'
# 
# 'link/LinkDevice'
# 'link/UnlinkDevice'
# 'link/RegisterClient'
# 'licensing/Release'
# 
# 'usage/UpdateStream'
# 'usage/ReportLogEvent'
# 'usage/ReportEvent'
# 'usage/GetServerConfig'
#===============================================================================

MAX = 20
common.gen_id()

deviceID = common.addon.getSetting("GenDeviceID")
#Android id: A2W5AJPLW5Q6YM, A1PY8QQU9P0WJV, A1MPSLFC7L5AFK // fmw:{AndroidSDK}-app:{AppVersion}
#deviceTypeID = 'A13Q6A55DBZB7M' #WEB Type
#firmware = 'fmw:15-app:1.1.19' #Android
#firmware = 'fmw:10-app:1.1.23'
deviceTypeID = 'A3VN4E5F7BBC7S' #Roku
firmware = 'fmw:045.01E01164A-app:4.7'
#deviceTypeID = 'A63V4FRV3YUP9'
#firmware = '1'
format = 'json'

PARAMETERS = '?firmware='+firmware+'&deviceTypeID='+deviceTypeID+'&deviceID='+deviceID+'&format='+format

def BUILD_BASE_API(MODE,HOST=common.ATV_URL + '/cdp/'):
    return HOST+MODE+PARAMETERS

def getList(ContentType,start=0,isPrime=True,NumberOfResults=MAX,OrderBy='MostPopular',version=2,AsinList=False):
    if isPrime:
        BROWSE_PARAMS = '&OfferGroups=B0043YVHMY'
    BROWSE_PARAMS +='&NumberOfResults='+str(NumberOfResults)
    BROWSE_PARAMS +='&StartIndex='+str(start)
    if ContentType == 'TVSeason':
        BROWSE_PARAMS +='&ContentType=TVEpisode&RollupToSeason=T'
    else:
        BROWSE_PARAMS +='&ContentType='+ContentType
    BROWSE_PARAMS +='&OrderBy='+OrderBy
    BROWSE_PARAMS +='&IncludeAll=T'
    if ContentType == 'TVEpisode':
        BROWSE_PARAMS +='&Detailed=T'
        BROWSE_PARAMS +='&AID=T'
        BROWSE_PARAMS +='&tag=1'
        BROWSE_PARAMS +='&SeasonASIN='+AsinList
        BROWSE_PARAMS +='&IncludeBlackList=T'
    BROWSE_PARAMS +='&version='+str(version)    
    #&HighDef=F # T or F ??
    #&playbackInformationRequired=false
    #&OrderBy=SalesRank
    #&SuppressBlackedoutEST=T
    #&HideNum=T
    #&Detailed=T
    #&AID=1
    #&IncludeNonWeb=T
    url = BUILD_BASE_API('catalog/Browse')+BROWSE_PARAMS
    return demjson.decode(common.getATVURL(url))

def ASIN_LOOKUP(ASINLIST):
    results = len(ASINLIST.split(','))-1
    BROWSE_PARAMS = '&asinList='+ASINLIST+'&NumberOfResults='+str(results)+'&IncludeAll=T&playbackInformationRequired=true&version=2'
    url = BUILD_BASE_API('catalog/GetASINDetails')+BROWSE_PARAMS
    return demjson.decode(common.getATVURL(url))

def URL_LOOKUP(url):
    return demjson.decode(common.getATVURL(url+PARAMETERS.replace('?','&')))

def SEARCH_DB(searchString=False,results=MAX,index=0):
    if not searchString:
        keyboard = xbmc.Keyboard('')
        keyboard.doModal()
        q = keyboard.getText()
        if (keyboard.isConfirmed()):
            searchString=urllib.quote_plus(keyboard.getText())
            if searchString <> '':
                common.addText('          ----=== ' + common.getString(30104) + ' ===----')
                if not listmovie.LIST_MOVIES(search=True, alphafilter = '%' + searchString + '%'):
                    common.addText(common.getString(30202))
                common.addText('          ----=== ' + common.getString(30107) + ' ===----')
                if not listtv.LIST_TVSHOWS(search=True, alphafilter = '%' + searchString + '%'):
                    common.addText(common.getString(30202))
                common.SetView('tvshows', 'showview')

def ExportWatchlist():
    WatchList(True)

def WatchList(export=False):
    import tv
    asins = common.SCRAP_ASINS()

    for value in asins:
        if listmovie.LIST_MOVIES(search=True, asinfilter = value, cmmode=1, export=export) == 0:
            if listtv.LIST_TVSHOWS(search=True, asinfilter = value, cmmode=1, export=export) == 0:
                for seasondata in tv.lookupTVdb(value, tbl='seasons', single=False):
                    listtv.ADD_SEASON_ITEM(seasondata, disptitle=True, cmmode=1, export=export)
    if not export: common.SetView('tvshows', 'showview')

def getTVDBImages(title, imdb=None, id=None, seasons=False):
    posterurl = fanarturl = None
    splitter = [' - ', ': ', ', ']
    langcodes = ['de', 'en']
    TVDB_URL = 'http://www.thetvdb.com/banners/'
    while not id:
        tv = urllib.quote_plus(title)
        result = common.getURL('http://www.thetvdb.com/api/GetSeries.php?seriesname=%s&language=de' % (tv), silent=True)
        soup = BeautifulSoup(result)
        id = soup.find('seriesid')
        if id:
            id = id.string
        else:
            oldtitle = title
            for splitchar in splitter:
                if title.count(splitchar):
                    title = title.split(splitchar)[0]
                    break
            if title == oldtitle:
                break
    if not id: return None, None, None
    if seasons:
        soup = BeautifulSoup(common.getURL('http://www.thetvdb.com/api/%s/series/%s/banners.xml' % (common.tvdb, id), silent=True))
        seasons = {}
        for lang in langcodes:
            for datalang in soup.findAll('language'):
                if datalang.string == lang:
                    data = datalang.parent
                    if data.bannertype.string == 'fanart' and not fanarturl: fanarturl = TVDB_URL + data.bannerpath.string
                    if data.bannertype.string == 'poster' and not posterurl: posterurl = TVDB_URL + data.bannerpath.string
                    if data.bannertype.string == data.bannertype2.string == 'season':
                        snr = data.season.string
                        if not seasons.has_key(snr):
                            seasons[snr] = TVDB_URL + data.bannerpath.string
        return seasons, posterurl, fanarturl
    else:
        for lang in langcodes:
            result = common.getURL('http://www.thetvdb.com/api/%s/series/%s/%s.xml' % (common.tvdb, id, lang), silent=True)
            soup = BeautifulSoup(result)
            fanart = soup.find('fanart')
            poster = soup.find('poster')
            if len(fanart) and not fanarturl: fanarturl = TVDB_URL + fanart.string
            if len(poster) and not posterurl : posterurl = TVDB_URL + poster.string
            if posterurl and fanarturl: return id, posterurl, fanarturl
        return id, posterurl, fanarturl

def getTMDBImages(title, imdb=None, content='movie', year=None):
    fanart = poster = id = None
    splitter = [' - ', ': ', ', ']
    TMDB_URL = 'http://image.tmdb.org/t/p/original'
    yearorg = year

    while not id:
        str_year = ''
        if year: str_year = '&year=' + str(year)
        movie = urllib.quote_plus(title)
        result = common.getURL('http://api.themoviedb.org/3/search/%s?api_key=%s&language=de&query=%s%s' % (content, common.tmdb, movie, str_year), silent=True)
        if not result:
            print "Amazon Fanart: Pause 5 sec..."
            xbmc.sleep(5000)
            continue
        data = demjson.decode(result)
        if data['total_results'] > 0:
            result = data['results'][0]
            if result['backdrop_path']: fanart = TMDB_URL + result['backdrop_path']
            if result['poster_path']: poster = TMDB_URL + result['poster_path']
            id = result['id']
        elif year:
            year = 0
        else:
            year = yearorg
            oldtitle = title
            for splitchar in splitter:
                if title.count(splitchar):
                    title = title.split(splitchar)[0]
                    break
            if title == oldtitle:
                break
    if content == 'movie' and id and not fanart:
        fanart = 'not available'
    return fanart
    
def updateAll():
    import movies
    import tv
    from datetime import date
    Notif = xbmcgui.Dialog().notification
    Notif(common.__plugin__, common.getString(30106), sound = False)
    tv.addTVdb(full_update = False)
    movies.addMoviesdb(full_update = False)
    NewAsins = common.getNewest()
    movies.setNewest(NewAsins)
    tv.setNewest(NewAsins)
    common.addon.setSetting('last_update', str(date.today()))
    Notif(common.__plugin__, common.getString(30126), sound = False)
