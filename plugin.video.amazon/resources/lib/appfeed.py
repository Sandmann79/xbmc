#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from common import *
import listtv
import listmovie

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

deviceID = gen_id()

# Android id: A2W5AJPLW5Q6YM, A1PY8QQU9P0WJV, A1MPSLFC7L5AFK // fmw:{AndroidSDK}-app:{AppVersion}
# deviceTypeID = 'A13Q6A55DBZB7M' #WEB Type
firmware = 'fmw:17-app:2.0.45.1210'  # Android
deviceTypeID = 'A2M4YX06LWP8WI'

PARAMETERS = '?firmware=' + firmware + '&deviceTypeID=' + deviceTypeID + '&deviceID=' + deviceID + '&format=json'


def BUILD_BASE_API(MODE, HOST=ATV_URL + '/cdp/'):
    return HOST + MODE + PARAMETERS


def getList(ContentType=None, start=0, isPrime=True, NumberOfResults=0, OrderBy='MostPopular', version=2,
            AsinList=None, catalog='Browse', asin=None):

    ContentFilter = '&ContractID=UX*'
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

    if not AsinList and not asin and 'tvseries' not in ContentType:
        BROWSE_PARAMS += ContentFilter

    if AsinList:
        BROWSE_PARAMS += '&SeasonASIN=' + AsinList

    if asin:
        BROWSE_PARAMS += '&asin=' + asin

    BROWSE_PARAMS += '&IncludeBlackList=T'
    BROWSE_PARAMS += '&HideNum=T'
    BROWSE_PARAMS += '&AID=1'
    BROWSE_PARAMS += "&IncludeNonWeb=T"
    BROWSE_PARAMS += '&IncludeAll=T'
    BROWSE_PARAMS += '&version=' + str(version)
    # &HighDef=F # T or F ??
    # &playbackInformationRequired=false
    # &OrderBy=SalesRank
    # &SuppressBlackedoutEST=T
    # &HideNum=T
    # &Detailed=T
    # &AID=1
    url = BUILD_BASE_API('catalog/%s' % catalog) + BROWSE_PARAMS
    return getURL(url)


def ASIN_LOOKUP(ASINLIST):
    results = len(ASINLIST.split(',')) - 1
    BROWSE_PARAMS = '&asinList=' + ASINLIST + '&NumberOfResults=' + str(
        results) + '&IncludeAll=T&playbackInformationRequired=true&version=2'
    url = BUILD_BASE_API('catalog/GetASINDetails') + BROWSE_PARAMS
    return getURL(url)


def SEARCH_DB():
    searchString = Dialog.input(getString(24121), '')
    if searchString != '':
        addText('          ----=== ' + getString(30104) + ' ===----')
        if not listmovie.LIST_MOVIES('movietitle', searchString, search=True):
            addText(getString(30202))
        addText('          ----=== ' + getString(30107) + ' ===----')
        if not listtv.LIST_TVSHOWS('seriestitle', searchString, search=True):
            addText(getString(30202))
        SetView('tvshows', 'showview')


def ExportList():
    asinlist = args.get('url')
    ListCont(movielib % asinlist)
    ListCont(tvlib % asinlist)


def getSimilarities():
    import tv
    data = getList(NumberOfResults=250, catalog='GetSimilarities', asin=args.get('asin'))
    for title in data['message']['body']['titles']:
        asin = title['titleId']
        if not listmovie.LIST_MOVIES('asin', asin, search=True):
            for seasondata in tv.lookupTVdb(asin, tbl='seasons', single=False):
                if seasondata:
                    listtv.ADD_SEASON_ITEM(seasondata, disptitle=True)

    SetView('tvshows', 'showview')


def ListMenu():
    l = args.get('url')
    addDir(getString(30104), 'appfeed', 'ListCont', movielib % l)
    addDir(getString(30107), 'appfeed', 'ListCont', tvlib % l)
    xbmcplugin.endOfDirectory(pluginhandle)


def ListCont(export=False):
    import tv
    showonly = False
    rvalue = 'distinct *'
    if export:
        url = export
        export = True
    else:
        url = args.get('url')

    mov = True if 'movie' in url else False

    if addon.getSetting('disptvshow') == 'true':
        showonly = True
        rvalue = 'seriesasin'

    cj = MechanizeLogin()
    if not cj:
        return False

    asins = SCRAP_ASINS(url, cj)
    if not asins:
        SetView('movies', 'movieview')
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
            SetView('movies', 'movieview')
        else:
            SetView('tvshows', 'showview')


def RefreshList():
    cj = MechanizeLogin()
    if not cj:
        return

    import tv
    import movies
    l = args.get('url')
    mvlist = []
    tvlist = []
    pDialog = xbmcgui.DialogProgress()
    pDialog.create(pluginname, getString(30117))

    for asin in SCRAP_ASINS(movielib % l, cj):
        if not movies.lookupMoviedb(asin):
            mvlist.append(asin)

    for asin in SCRAP_ASINS(tvlib % l, cj):
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
        tv = urllib.quote_plus(title.encode('utf-8'))
        result = getURL('http://www.thetvdb.com/api/GetSeries.php?seriesname=%s&language=de' % tv, silent=True, rjson=False)
        if not result:
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
        result = getURL('http://www.thetvdb.com/api/%s/series/%s/banners.xml' % (tvdb, tvdbid), silent=True, rjson=False)
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
            result = getURL('http://www.thetvdb.com/api/%s/series/%s/%s.xml' % (tvdb, tvdbid, lang), silent=True, rjson=False)
            if result:
                soup = BeautifulSoup(result)
                fanart = soup.find('fanart')
                poster = soup.find('poster')
                if fanart and fanart.string and not fanarturl:
                    fanarturl = TVDB_URL + fanart.string

                if poster and poster.string and not posterurl:
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

        movie = urllib.quote_plus(title.encode('utf-8'))
        data = getURL('http://api.themoviedb.org/3/search/%s?api_key=%s&language=de&query=%s%s' % (
            content, tmdb, movie, str_year), silent=True)
        if not data:
            continue

        if data.get('total_results', 0) > 0:
            result = data['results'][0]
            if result.get('backdrop_path'):
                fanart = TMDB_URL + result['backdrop_path']
            tmdbid = result.get('id')
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
        fanart = na
    return fanart


def updateAll():
    from service import updateRunning
    if updateRunning():
        return

    cj = MechanizeLogin()
    if not cj:
        return

    import movies
    import tv
    from datetime import datetime

    writeConfig('update_running', datetime.today().strftime('%Y-%m-%d %H:%M'))
    Log('Starting DBUpdate')
    Notif(getString(30106))
    xbmc.executebuiltin('Container.Refresh')

    tvresult = tv.addTVdb(False, cj=cj)
    mvresult = movies.addMoviesdb(False, cj=cj)
    NewAsins = getCategories()

    if tvresult and mvresult:
        writeConfig('last_update', datetime.today().strftime('%Y-%m-%d'))

    if mvresult:
        movies.setNewest(NewAsins)
        movies.updateFanart()
    if tvresult:
        tv.setNewest(NewAsins)
        tv.updateFanart()

    writeConfig('update_running', 'false')
    if xbmc.getInfoLabel('Container.FolderPath') == 'plugin://plugin.video.amazon/':
        xbmc.executebuiltin('Container.Refresh')
    Notif(getString(30126))
    Log('DBUpdate finished')
