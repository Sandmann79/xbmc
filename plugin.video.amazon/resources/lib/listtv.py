#!/usr/bin/env python
# -*- coding: utf-8 -*-
import common
import xbmclibrary

pluginhandle = common.pluginhandle
xbmc = common.xbmc
xbmcplugin = common.xbmcplugin
urllib = common.urllib
sys = common.sys
xbmcgui = common.xbmcgui
showfanart = common.addon.getSetting("useshowfanart") == 'true'


def LIST_TV_ROOT():
    common.addDir(common.getString(30100), 'listtv', 'LIST_TVSHOWS_SORTED', 'popularity')
    common.addDir(common.getString(30110), 'listtv', 'LIST_TVSEASON_SORTED', 'recent')
    common.addDir(common.getString(30149), 'listtv', 'LIST_TVSHOWS_CATS')
    common.addDir(common.getString(30160), 'listtv', 'LIST_TVSHOWS')
    common.addDir(common.getString(30144), 'listtv', 'LIST_TVSHOWS_TYPES', 'genres')
    common.addDir(common.getString(30158), 'listtv', 'LIST_TVSHOWS_TYPES', 'actors')
    common.addDir(common.getString(30145), 'listtv', 'LIST_TVSHOWS_TYPES', 'year')
    common.addDir(common.getString(30161), 'listtv', 'LIST_TVSHOWS_TYPES', 'network')
    common.addDir(common.getString(30162), 'listtv', 'LIST_TVSHOWS_TYPES', 'mpaa')
    xbmcplugin.endOfDirectory(pluginhandle)


def LIST_TVSHOWS_CATS():
    import tv as tvDB
    catid = common.args.url
    if catid:
        asins = tvDB.lookupTVdb(catid, rvalue='asins', name='title', tbl='categories')
        epidb = tvDB.lookupTVdb('', name='asin', rvalue='asin, seasonasin', tbl='episodes', single=False)
        if not asins:
            return

        for asin in asins.split(','):
            seasonasin = None
            for epidata in epidb:
                if asin in str(epidata):
                    seasonasin = epidata[1]
                    break
            if not seasonasin:
                seasonasin = asin

            for seasondata in tvDB.loadTVSeasonsdb(seasonasin=seasonasin).fetchall():
                ADD_SEASON_ITEM(seasondata, disptitle=True)
        common.SetView('seasons', 'seasonview')
        del epidb
    else:
        for title in tvDB.lookupTVdb('', name='asins', tbl='categories', single=False):
            if title:
                common.addDir(title[0], 'listtv', 'LIST_TVSHOWS_CATS', title[0])

        xbmcplugin.endOfDirectory(pluginhandle, updateListing=False)


def LIST_TVSHOWS_TYPES(tvtype=None):
    import tv as tvDB
    if not tvtype:
        tvtype = common.args.url
    if tvtype:
        mode = 'LIST_TVSHOWS_FILTERED'
        items = tvDB.getShowTypes(tvtype)
        for item in items:
            common.addDir(item, 'listtv', mode, tvtype)
        xbmcplugin.addSortMethod(pluginhandle, xbmcplugin.SORT_METHOD_LABEL)
        xbmcplugin.endOfDirectory(pluginhandle, updateListing=False)


def LIST_TVSHOWS_FILTERED():
    LIST_TVSHOWS(common.args.url, common.args.name)


def LIST_TVSHOWS_SORTED():
    LIST_TVSHOWS(sortaz=False, sortcol=common.args.url)


def LIST_TVSHOWS(filterobj='', value=None, sortcol=False, sortaz=True, search=False, cmmode=0, export=False):
    import tv as tvDB
    if 'year' in filterobj:
        value = value.replace('0 -', '')

    shows = tvDB.loadTVShowdb(filterobj=filterobj, value=value, sortcol=sortcol)
    count = 0
    for showdata in shows:
        count += 1
        ADD_SHOW_ITEM(showdata, cmmode=cmmode, export=export)
    if not search:
        if sortaz:
            if 'year' not in filterobj:
                xbmcplugin.addSortMethod(pluginhandle, xbmcplugin.SORT_METHOD_LABEL)

            xbmcplugin.addSortMethod(pluginhandle, xbmcplugin.SORT_METHOD_VIDEO_YEAR)
            xbmcplugin.addSortMethod(pluginhandle, xbmcplugin.SORT_METHOD_VIDEO_RATING)
            xbmcplugin.addSortMethod(pluginhandle, xbmcplugin.SORT_METHOD_STUDIO_IGNORE_THE)
        common.SetView('tvshows', 'showview')
    return count


def ADD_SHOW_ITEM(showdata, mode='listtv', submode='LIST_TV_SEASONS', cmmode=0, onlyinfo=False, export=False):
    asin, seriestitle, plot, network, mpaa, genres, actors, premiered, year, stars, votes, seasontotal, episodetotal, \
        audio, isHD, isprime, empty, empty, empty, poster, banner, fanart = showdata
    submode = 'LIST_TV_SEASONS' if mode == 'listtv' else submode
    poster = '' if not poster else poster
    infoLabels = {'Title': seriestitle,
                  'Plot': plot,
                  'mediatype': 'tvshow',
                  'MPAA': mpaa,
                  'Cast': actors.split(',') if actors else None,
                  'Year': year,
                  'Premiered': premiered,
                  'Rating': stars,
                  'Votes': votes,
                  'Genre': genres,
                  'Episode': episodetotal,
                  'TotalSeasons': seasontotal,
                  'Studio': network,
                  'AudioChannels': audio,
                  'Thumb': poster,
                  'Fanart': fanart,
                  'Asins': asin
                  }
    infoLabels = {k: v for k, v in infoLabels.items() if v}
    asin = asin.split(',')[0]

    if export:
        xbmclibrary.EXPORT_SHOW(asin)
        return

    cm = [(common.getString(30180 + cmmode) % common.getString(30166),
           'RunPlugin(%s?mode=<common>&sitemode=<toogleWatchlist>&asin=<%s>&remove=<%s>)' % (sys.argv[0], asin, cmmode)),
          (common.getString(30185) % common.getString(30166),
          'RunPlugin(%s?mode=<xbmclibrary>&sitemode=<EXPORT_SHOW>&asin=<%s>)' % (sys.argv[0], asin)),
          (common.getString(30183), 'Container.Update(%s?mode=<appfeed>&sitemode=<getSimilarities>&asin=<%s>)' % (sys.argv[0], asin)),
          (common.getString(30186), 'RunPlugin(%s?mode=<xbmclibrary>&sitemode=<UpdateLibrary>)' % sys.argv[0]),
          (common.getString(30155) % common.getString(30166), 'RunPlugin(%s?mode=<tv>&sitemode=<delfromTVdb>&asins=<%s>&table=<shows>&title=<%s>)' % (
           sys.argv[0], urllib.quote_plus(infoLabels['Asins']), urllib.quote_plus(seriestitle)))]

    if onlyinfo:
        return infoLabels
    else:
        common.addDir(seriestitle, mode, submode, infoLabels['Asins'], poster, fanart, infoLabels, cm=cm)


def LIST_TV_SEASONS():
    seriesasin = common.args.url
    import tv as tvDB
    for asin in seriesasin.split(','):
        seasons = tvDB.loadTVSeasonsdb(seriesasin=asin).fetchall()
        for seasondata in seasons:
            ADD_SEASON_ITEM(seasondata)
    xbmcplugin.addSortMethod(pluginhandle, xbmcplugin.SORT_METHOD_LABEL)
    common.SetView('seasons', 'seasonview')


def LIST_TVSEASON_SORTED(seasons=False, cmmode=0):
    import tv as tvDB
    if not seasons:
        seasons = tvDB.loadTVSeasonsdb(sortcol=common.args.url).fetchall()
    for seasondata in seasons:
        ADD_SEASON_ITEM(seasondata, disptitle=True, cmmode=cmmode)
    common.SetView('seasons', 'seasonview')


def ADD_SEASON_ITEM(seasondata, mode='listtv', submode='LIST_EPISODES_DB', disptitle=False, cmmode=0, onlyinfo=False, export=False):
    asin, seriesASIN, season, seriestitle, plot, actors, network, mpaa, genres, premiered, year, stars, votes, \
        episodetotal, audio, empty, empty, isHD, isprime, empty, poster, banner, fanart = seasondata
    fanart, cover = getFanart(seriesASIN) if showfanart else None
    infoLabels = {'Title': seriestitle,
                  'TVShowTitle': seriestitle,
                  'Plot': plot,
                  'mediatype': 'season',
                  'MPAA': mpaa,
                  'Cast': actors.split(',') if actors else None,
                  'Year': year,
                  'Premiered': premiered,
                  'Rating': stars,
                  'Votes': votes,
                  'Genre': genres,
                  'Episode': episodetotal,
                  'Season': season,
                  'Studio': network,
                  'AudioChannels': audio,
                  'TotalSeasons': 1,
                  'Thumb': poster,
                  'Fanart': fanart,
                  'Asins': asin
                  }
    infoLabels = {k: v for k, v in infoLabels.items() if v}
    asin = asin.split(',')[0]

    displayname = seriestitle + ' - ' if disptitle else ''

    if season != 0 and len(str(season)) < 3:
        displayname += common.getString(30167) + ' ' + str(season)
    elif len(str(season)) > 2:
        displayname += common.getString(30168) + str(season)
    else:
        displayname += common.getString(30169)

    if export:
        xbmclibrary.EXPORT_SEASON(asin)
        return

    cm = [(common.getString(30180 + cmmode) % common.getString(30167),
          'RunPlugin(%s?mode=<common>&sitemode=<toogleWatchlist>&asin=<%s>&remove=<%s>)' % (sys.argv[0], asin, cmmode)),
          (common.getString(30185) % common.getString(30167),
          'RunPlugin(%s?mode=<xbmclibrary>&sitemode=<EXPORT_SEASON>&asin=<%s>)' % (sys.argv[0], asin)),
          (common.getString(30183), 'Container.Update(%s?mode=<appfeed>&sitemode=<getSimilarities>&asin=<%s>)' % (sys.argv[0], asin)),
          (common.getString(30186), 'RunPlugin(%s?mode=<xbmclibrary>&sitemode=<UpdateLibrary>)' % sys.argv[0]),
          (common.getString(30155) % common.getString(30167), 'RunPlugin(%s?mode=<tv>&sitemode=<delfromTVdb>&asins=<%s>&table=<seasons>&title=<%s>)' % (
           sys.argv[0], urllib.quote_plus(infoLabels['Asins']), urllib.quote_plus(displayname)))]

    if onlyinfo:
        return infoLabels
    else:
        common.addDir(displayname, mode, submode, infoLabels['Asins'], poster, fanart, infoLabels, cm=cm)


def LIST_EPISODES_DB(url=False):
    if not url:
        seriestitle = common.args.url
    import tv as tvDB
    for asin in seriestitle.split(','):
        episodes = tvDB.loadTVEpisodesdb(asin)
        for episodedata in episodes:
            ADD_EPISODE_ITEM(episodedata)
    xbmcplugin.addSortMethod(pluginhandle, xbmcplugin.SORT_METHOD_LABEL)
    common.SetView('episodes', 'episodeview')


def ADD_EPISODE_ITEM(episodedata, onlyinfo=False, export=False):
    asin, seasonASIN, seriesASIN, seriestitle, season, episode, poster, mpaa, actors, genres, episodetitle, network, \
        stars, votes, fanart, plot, airdate, year, runtime, isHD, isprime, isAdult, audio = episodedata
    tvfanart, tvposter = getFanart(seriesASIN)
    fanart = tvfanart if showfanart else fanart
    displayname = "{} - {}".format(episode, episodetitle).replace('"', '')
    infoLabels = {'Title': displayname,
                  'TVShowTitle': seriestitle,
                  'Episode': episode,
                  'mediatype': 'episode',
                  'Season': season,
                  'Plot': plot,
                  'Premiered': airdate,
                  'Year': year,
                  'Duration': int(runtime) * 60 if runtime else None,
                  'MPAA': mpaa,
                  'Cast': actors.split(',') if actors else None,
                  'Rating': stars,
                  'Votes': votes,
                  'Genre': genres,
                  'Studio': network,
                  'AudioChannels': audio,
                  'isAdult': isAdult,
                  'Thumb': poster,
                  'Fanart': fanart,
                  'isHD': isHD,
                  'seriesASIN': seriesASIN,
                  'Poster': tvposter
                  }
    infoLabels = {k: v for k, v in infoLabels.items() if v}
    asin = asin.split(',')[0]

    if export:
        xbmclibrary.EXPORT_EPISODE(asin)
        return

    cm = [(common.getString(30185) % common.getString(30173),
           'RunPlugin(%s?mode=<xbmclibrary>&sitemode=<EXPORT_EPISODE>&asin=<%s>)' % (sys.argv[0], asin)),
          (common.getString(30183),
           'Container.Update(%s?mode=<appfeed>&sitemode=<getSimilarities>&asin=<%s>)' % (sys.argv[0], asin)),
          (common.getString(30186), 'RunPlugin(%s?mode=<xbmclibrary>&sitemode=<UpdateLibrary>)' % sys.argv[0])]

    if onlyinfo:
        return infoLabels
    else:
        common.addVideo(displayname, asin, poster, fanart, infoLabels=infoLabels, isAdult=isAdult, isHD=isHD, cm=cm)


def getFanart(asin, tbl='shows'):
    import tv
    fanart, poster = tv.lookupTVdb(asin, rvalue='fanart, poster', tbl=tbl)
    if not fanart or fanart == common.na:
        fanart = poster
    return fanart, poster
