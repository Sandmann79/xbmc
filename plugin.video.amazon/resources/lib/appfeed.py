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
json = common.json
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
deviceID = common.gen_id()

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
    BROWSE_PARAMS ='&NumberOfResults='+str(NumberOfResults)
    BROWSE_PARAMS +='&StartIndex='+str(start)
    BROWSE_PARAMS +='&ContentType='+ContentType
    BROWSE_PARAMS +='&OrderBy='+OrderBy
    BROWSE_PARAMS +='&IncludeAll=T'
    if isPrime: BROWSE_PARAMS += '&OfferGroups=B0043YVHMY'
    if ContentType == 'TVEpisode':
        BROWSE_PARAMS +='&Detailed=T'
        BROWSE_PARAMS +='&AID=T'
        BROWSE_PARAMS +='&tag=1'
        BROWSE_PARAMS +='&IncludeBlackList=T'
    if AsinList: BROWSE_PARAMS +='&SeasonASIN='+AsinList
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
    return json.loads(common.getATVURL(url))

def ASIN_LOOKUP(ASINLIST):
    results = len(ASINLIST.split(','))-1
    BROWSE_PARAMS = '&asinList='+ASINLIST+'&NumberOfResults='+str(results)+'&IncludeAll=T&playbackInformationRequired=true&version=2'
    url = BUILD_BASE_API('catalog/GetASINDetails')+BROWSE_PARAMS
    return json.loads(common.getATVURL(url))

def URL_LOOKUP(url):
    return json.loads(common.getATVURL(url+PARAMETERS.replace('?','&')))

def SEARCH_DB(searchString=False):
    if not searchString:
        keyboard = xbmc.Keyboard('')
        keyboard.doModal()
        q = keyboard.getText()
        if (keyboard.isConfirmed()):
            searchString=keyboard.getText()
            if searchString <> '':
                common.addText('          ----=== ' + common.getString(30104) + ' ===----')
                if not listmovie.LIST_MOVIES('movietitle', searchString, search=True):
                    common.addText(common.getString(30202))
                common.addText('          ----=== ' + common.getString(30107) + ' ===----')
                if not listtv.LIST_TVSHOWS('seriestitle', searchString, search=True):
                    common.addText(common.getString(30202))
                common.SetView('tvshows', 'showview')

def ExportList():
    list = common.args.url
    ListCont(common.movielib % list)
    ListCont(common.tvlib % list)
    
def ListMenu():
    list = common.args.url
    common.addDir(common.getString(30104), 'appfeed', 'ListCont', common.movielib % list)
    common.addDir(common.getString(30107), 'appfeed', 'ListCont', common.tvlib % list)
    common.xbmcplugin.endOfDirectory(common.pluginhandle)

def ListCont(export=False):
    import tv
    mov = False
    showonly = False
    rvalue = 'distinct *'
    if export:
        url = export
        export = True
    else: url = common.args.url
    if 'movie' in url: mov = True
    if common.addon.getSetting('disptvshow') == 'true':
        showonly = True
        rvalue = 'seriesasin'
    asins = common.SCRAP_ASINS(url)
    if not asins:
        xbmcgui.Dialog().notification(common.__plugin__, common.getString(30199), sound = False)
        return

    asinlist = []
    for value in asins:
        ret = 0
        if mov: ret = listmovie.LIST_MOVIES('asin', value, search=True, cmmode=1, export=export)
        if ret == 0 and not mov:
            for seasondata in tv.lookupTVdb(value, tbl='seasons', rvalue=rvalue, single=False):
                if seasondata:
                    if showonly:
                        ret = 0
                        value = seasondata[0]
                        for asin in tv.lookupTVdb(value, tbl='shows', rvalue='asin').split(','):
                            if asin in asinlist: ret = 1
                    else:
                        ret = 1
                        listtv.ADD_SEASON_ITEM(seasondata, disptitle=True, cmmode=1, export=export)
        if ret == 0 and not mov: listtv.LIST_TVSHOWS('asin', value, search=True, cmmode=1, export=export)
        asinlist.append(value)

    if not export:
        if mov: common.SetView('movies', 'movieview')
        else: common.SetView('tvshows', 'showview')

def RefreshList():
    import tv
    import movies
    list = common.args.url
    mvlist = []
    tvlist = []
    pDialog = xbmcgui.DialogProgress()
    pDialog.create(common.__plugin__, common.getString(30117))
    
    for asin in common.SCRAP_ASINS(common.movielib % list):
        if not movies.lookupMoviedb(asin): mvlist.append(asin)

    for asin in common.SCRAP_ASINS(common.tvlib % list):
        if not tv.lookupTVdb(asin, tbl='seasons'): tvlist.append(asin)

    if mvlist: movies.updateLibrary(mvlist)
    if tvlist: tv.addTVdb(False, tvlist)
    pDialog.close()
    
    if mvlist: movies.updateFanart()
    if tvlist: tv.updateFanart()

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
            common.Log('Fanart: Pause 5 sec...')
            xbmc.sleep(5000)
            continue
        data = json.loads(result)
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
        fanart = common.na
    return fanart
    
def updateAll():
    if common.updateRunning(): return
    import movies
    import tv
    from datetime import datetime
    common.addon.setSetting('update_running', datetime.today().strftime('%Y-%m-%d %H:%M'))
    common.Log('Starting DBUpdate')
    Notif = xbmcgui.Dialog().notification
    Notif(common.__plugin__, common.getString(30106), sound = False)
    tv.addTVdb(False)
    movies.addMoviesdb(False)
    NewAsins = common.getCategories()
    movies.setNewest(NewAsins)
    movies.updateFanart()
    tv.setNewest(NewAsins)
    tv.updateFanart()
    common.addon.setSetting('last_update', datetime.today().strftime('%Y-%m-%d'))
    common.addon.setSetting('update_running', 'false')
    Notif(common.__plugin__, common.getString(30126), sound = False)
    common.Log('DBUpdate finished')
