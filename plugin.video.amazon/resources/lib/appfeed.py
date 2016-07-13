#!/usr/bin/env python
# -*- coding: utf-8 -*-
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

# Modes
# ===============================================================================
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
# ===============================================================================

deviceID = common.gen_id()

# Android id: A2W5AJPLW5Q6YM, A1PY8QQU9P0WJV, A1MPSLFC7L5AFK // fmw:{AndroidSDK}-app:{AppVersion}
# deviceTypeID = 'A13Q6A55DBZB7M' #WEB Type
firmware = 'fmw:15-app:1.1.19'  # Android
# firmware = 'fmw:10-app:1.1.23'
# deviceTypeID = 'A3VN4E5F7BBC7S' #Roku
# firmware = 'fmw:045.01E01164A-app:4.7'
deviceTypeID = 'A1MPSLFC7L5AFK'

PARAMETERS = '?firmware=' + firmware + '&deviceTypeID=' + deviceTypeID + '&deviceID=' + deviceID + '&format=json'


def BUILD_BASE_API(MODE, HOST=common.ATV_URL + '/cdp/'):
    return HOST + MODE + PARAMETERS


def getList(ContentType=None, start=0, isPrime=True, NumberOfResults=0, OrderBy='MostPopular', version=2,
            AsinList=None, catalog='Browse', asin=None):
    BROWSE_PARAMS = '&StartIndex=' + str(start)
    if NumberOfResults:
        BROWSE_PARAMS += '&NumberOfResults=' + str(NumberOfResults)

    if ContentType:
        BROWSE_PARAMS += '&ContentType=' + ContentType
        BROWSE_PARAMS += '&OrderBy=' + OrderBy

    if isPrime:
        BROWSE_PARAMS += '&OfferGroups=B0043YVHMY'

    if ContentType == 'TVEpisode':
        BROWSE_PARAMS += '&Detailed=T'
        BROWSE_PARAMS += '&AID=T'
        BROWSE_PARAMS += '&tag=1'
        BROWSE_PARAMS += '&IncludeBlackList=T'

    if AsinList:
        BROWSE_PARAMS += '&SeasonASIN=' + AsinList

    if asin:
        BROWSE_PARAMS += '&asin=' + asin

    BROWSE_PARAMS += '&IncludeAll=T&version=' + str(version)
    # &HighDef=F # T or F ??
    # &playbackInformationRequired=false
    # &OrderBy=SalesRank
    # &SuppressBlackedoutEST=T
    # &HideNum=T
    # &Detailed=T
    # &AID=1
    # &IncludeNonWeb=T
    url = BUILD_BASE_API('catalog/%s' % catalog) + BROWSE_PARAMS
    return json.loads(common.getATVURL(url))


def ASIN_LOOKUP(ASINLIST):
    results = len(ASINLIST.split(',')) - 1
    BROWSE_PARAMS = '&asinList=' + ASINLIST + '&NumberOfResults=' + str(
        results) + '&IncludeAll=T&playbackInformationRequired=true&version=2'
    url = BUILD_BASE_API('catalog/GetASINDetails') + BROWSE_PARAMS
    return json.loads(common.getATVURL(url))


def URL_LOOKUP(url):
    return json.loads(common.getATVURL(url + PARAMETERS.replace('?', '&')))


def SEARCH_DB(searchString=None):
    if not searchString:
        keyboard = xbmc.Keyboard('', common.getString(24121))
        keyboard.doModal()
        if keyboard.isConfirmed():
            searchString = keyboard.getText()
            if searchString != '':
                common.addText('          ----=== ' + common.getString(30104) + ' ===----')
                if not listmovie.LIST_MOVIES('movietitle', searchString, search=True):
                    common.addText(common.getString(30202))
                common.addText('          ----=== ' + common.getString(30107) + ' ===----')
                if not listtv.LIST_TVSHOWS('seriestitle', searchString, search=True):
                    common.addText(common.getString(30202))
                common.SetView('tvshows', 'showview')
        xbmc.executebuiltin('Action(Close)')


def ExportList():
    asinlist = common.args.url
    ListCont(common.movielib % asinlist)
    ListCont(common.tvlib % asinlist)


def getSimilarities():
    import tv
    data = getList(NumberOfResults=250, catalog='GetSimilarities', asin=common.args.asin)
    for title in data['message']['body']['titles']:
        asin = title['titleId']
        if not listmovie.LIST_MOVIES('asin', asin, search=True):
            for seasondata in tv.lookupTVdb(asin, tbl='seasons', single=False):
                if seasondata:
                    listtv.ADD_SEASON_ITEM(seasondata, disptitle=True)

    common.SetView('tvshows', 'showview')


def ListMenu():
    l = common.args.url
    common.addDir(common.getString(30104), 'appfeed', 'ListCont', common.movielib % l)
    common.addDir(common.getString(30107), 'appfeed', 'ListCont', common.tvlib % l)
    common.xbmcplugin.endOfDirectory(common.pluginhandle)


def ListCont(export=False):
    import tv
    showonly = False
    rvalue = 'distinct *'
    if export:
        url = export
        export = True
    else:
        url = common.args.url

    mov = True if 'movie' in url else False

    if common.addon.getSetting('disptvshow') == 'true':
        showonly = True
        rvalue = 'seriesasin'

    cj = common.mechanizeLogin()
    if not cj:
        return False

    asins = common.SCRAP_ASINS(url, cj)
    if not asins:
        common.SetView('movies', 'movieview')
        return

    asinlist = []
    for value in asins:
        ret = listmovie.LIST_MOVIES('asin', value, search=True, cmmode=1, export=export) if mov else 0

        if ret == 0 and not mov:
            for seasondata in tv.lookupTVdb(value, tbl='seasons', rvalue=rvalue, single=False):
                if seasondata:
                    if showonly:
                        ret = 0
                        value = seasondata[0]
                        for asin in tv.lookupTVdb(value, tbl='shows', rvalue='asin').split(','):
                            if asin in asinlist:
                                ret = 1
                    else:
                        ret = 1
                        listtv.ADD_SEASON_ITEM(seasondata, disptitle=True, cmmode=1, export=export)
        if ret == 0 and not mov:
            listtv.LIST_TVSHOWS('asin', value, search=True, cmmode=1, export=export)

        asinlist.append(value)

    if not export:
        if mov:
            common.SetView('movies', 'movieview')
        else:
            common.SetView('tvshows', 'showview')


def RefreshList():
    cj = common.mechanizeLogin()
    if not cj:
        return

    import tv
    import movies
    l = common.args.url
    mvlist = []
    tvlist = []
    pDialog = xbmcgui.DialogProgress()
    pDialog.create(common.__plugin__, common.getString(30117))

    for asin in common.SCRAP_ASINS(common.movielib % l, cj):
        if not movies.lookupMoviedb(asin):
            mvlist.append(asin)

    for asin in common.SCRAP_ASINS(common.tvlib % l, cj):
        if not tv.lookupTVdb(asin, tbl='seasons'):
            tvlist.append(asin)

    if mvlist:
        movies.updateLibrary(mvlist)

    if tvlist:
        tv.addTVdb(False, tvlist, None)

    pDialog.close()

    if mvlist:
        movies.updateFanart()

    if tvlist:
        tv.updateFanart()


def getTVDBImages(title, tvdbid=None, seasons=False):
    posterurl = fanarturl = None
    splitter = [' - ', ': ', ', ']
    langcodes = ['de', 'en']
    TVDB_URL = 'http://www.thetvdb.com/banners/'
    while not tvdbid and title:
        tv = urllib.quote_plus(title)
        result = common.getURL('http://www.thetvdb.com/api/GetSeries.php?seriesname=%s&language=de' % tv, silent=True)
        if not result:
            common.Log('Fanart: Pause 20 sec...')
            xbmc.sleep(20000)
            continue
        soup = BeautifulSoup(result)
        tvdbid = soup.find('seriesid')
        if tvdbid:
            tvdbid = tvdbid.string
        else:
            oldtitle = title
            for splitchar in splitter:
                if title.count(splitchar):
                    title = title.split(splitchar)[0]
                    break
            if title == oldtitle:
                break
    if not tvdbid:
        return None, None, None

    if seasons:
        seasons = {}
        result = common.getURL('http://www.thetvdb.com/api/%s/series/%s/banners.xml' % (common.tvdb, tvdbid), silent=True)
        if result:
            soup = BeautifulSoup(result)
            for lang in langcodes:
                for datalang in soup.findAll('language'):
                    if datalang.string == lang:
                        data = datalang.parent
                        if data.bannertype.string == 'fanart' and not fanarturl:
                            fanarturl = TVDB_URL + data.bannerpath.string

                        if data.bannertype.string == 'poster' and not posterurl:
                            posterurl = TVDB_URL + data.bannerpath.string

                        if data.bannertype.string == data.bannertype2.string == 'season':
                            snr = data.season.string
                            if snr not in seasons.keys():
                                seasons[snr] = TVDB_URL + data.bannerpath.string
        return seasons, posterurl, fanarturl
    else:
        for lang in langcodes:
            result = common.getURL('http://www.thetvdb.com/api/%s/series/%s/%s.xml' % (common.tvdb, tvdbid, lang),
                                   silent=True)
            if result:
                soup = BeautifulSoup(result)
                fanart = soup.find('fanart')
                poster = soup.find('poster')
                if fanart and not fanarturl:
                    fanarturl = TVDB_URL + fanart.string

                if poster and not posterurl:
                    posterurl = TVDB_URL + poster.string

                if posterurl and fanarturl:
                    return tvdbid, posterurl, fanarturl

        return tvdbid, posterurl, fanarturl


def getTMDBImages(title, content='movie', year=None):
    fanart = tmdbid = None
    splitter = [' - ', ': ', ', ']
    TMDB_URL = 'http://image.tmdb.org/t/p/original'
    yearorg = year

    while not tmdbid and title:
        str_year = ''
        if year:
            str_year = '&year=' + str(year)

        movie = urllib.quote_plus(title)
        result = common.getURL('http://api.themoviedb.org/3/search/%s?api_key=%s&language=de&query=%s%s' % (
            content, common.tmdb, movie, str_year), silent=True)
        if not result:
            common.Log('Fanart: Pause 20 sec...')
            xbmc.sleep(20000)
            continue
        data = json.loads(result)
        if data['total_results'] > 0:
            result = data['results'][0]
            if result['backdrop_path']:
                fanart = TMDB_URL + result['backdrop_path']
            tmdbid = result['id']
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
    if content == 'movie' and tmdbid and not fanart:
        fanart = common.na
    return fanart


def updateAll():
    if common.updateRunning():
        return

    cj = common.mechanizeLogin()
    if not cj:
        return

    import movies
    import tv
    from datetime import datetime

    common.addon.setSetting('update_running', datetime.today().strftime('%Y-%m-%d %H:%M'))
    common.Log('Starting DBUpdate')
    Notif = xbmcgui.Dialog().notification
    Notif(common.__plugin__, common.getString(30106), sound=False)
    tv.addTVdb(False, cj=cj)
    movies.addMoviesdb(False, cj=cj)
    NewAsins = common.getCategories()
    movies.setNewest(NewAsins)
    tv.setNewest(NewAsins)
    movies.updateFanart()
    tv.updateFanart()
    common.addon.setSetting('last_update', datetime.today().strftime('%Y-%m-%d'))
    common.addon.setSetting('update_running', 'false')
    Notif(common.__plugin__, common.getString(30126), sound=False)
    common.Log('DBUpdate finished')
