#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from common import *
import xbmclibrary
import tv

showfanart = addon.getSetting("useshowfanart") == 'true'


def LIST_TV_ROOT():
    addDir(getString(30100), 'listtv', 'LIST_TVSHOWS_SORTED', 'popularity')
    addDir(getString(30110), 'listtv', 'LIST_TVSEASON_SORTED', 'recent')
    addDir(getString(30149), 'listtv', 'LIST_TVSHOWS_CATS')
    addDir(getString(30160), 'listtv', 'LIST_TVSHOWS')
    addDir(getString(30144), 'listtv', 'LIST_TVSHOWS_TYPES', 'genres')
    addDir(getString(30158), 'listtv', 'LIST_TVSHOWS_TYPES', 'actors')
    addDir(getString(30145), 'listtv', 'LIST_TVSHOWS_TYPES', 'year')
    addDir(getString(30161), 'listtv', 'LIST_TVSHOWS_TYPES', 'network')
    addDir(getString(30162), 'listtv', 'LIST_TVSHOWS_TYPES', 'mpaa')
    xbmcplugin.endOfDirectory(pluginhandle)


def LIST_TVSHOWS_CATS():
    catid = args.get('url')
    if catid:
        asins = tv.lookupTVdb(catid, rvalue='asins', name='title', tbl='categories')
        epidb = tv.lookupTVdb('', name='asin', rvalue='asin, seasonasin', tbl='episodes', single=False)
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

            for seasondata in tv.loadTVSeasonsdb(seasonasin=seasonasin).fetchall():
                ADD_SEASON_ITEM(seasondata, disptitle=True)
        SetView('seasons', 'seasonview')
        del epidb
    else:
        for title in tv.lookupTVdb('', name='asins', tbl='categories', single=False):
            if title:
                addDir(title[0], 'listtv', 'LIST_TVSHOWS_CATS', title[0])

        xbmcplugin.endOfDirectory(pluginhandle, updateListing=False)


def LIST_TVSHOWS_TYPES(tvtype=None):
    if not tvtype:
        tvtype = args.get('url')
    if tvtype:
        for item in tv.getShowTypes(tvtype):
            addDir(item, 'listtv', 'LIST_TVSHOWS_FILTERED', tvtype)
        xbmcplugin.addSortMethod(pluginhandle, xbmcplugin.SORT_METHOD_LABEL)
        xbmcplugin.endOfDirectory(pluginhandle, updateListing=False)


def LIST_TVSHOWS_FILTERED():
    LIST_TVSHOWS(args.get('url'), args.get('name'))


def LIST_TVSHOWS_SORTED():
    LIST_TVSHOWS(sortaz=False, sortcol=args.get('url'))


def LIST_TVSHOWS(filterobj='', value=None, sortcol=False, sortaz=True, search=False, cmmode=0, export=False):
    if 'year' in filterobj:
        value = value.replace('0 -', '')

    shows = tv.loadTVShowdb(filterobj, value, sortcol)
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
        SetView('tvshows', 'showview')
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
                  'Cast': actors.split(',') if actors else [],
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
    asin = asin.split(',')[0]

    if export:
        xbmclibrary.EXPORT_SHOW(asin)
        return

    cm = [(getString(30180 + cmmode) % getString(30166),
           'RunPlugin(%s?mode=common&sitemode=toogleWatchlist&asin=%s&remove=%s)' % (sys.argv[0], asin, cmmode)),
          (getString(30185) % getString(30166),
          'RunPlugin(%s?mode=xbmclibrary&sitemode=EXPORT_SHOW&asin=%s)' % (sys.argv[0], asin)),
          (getString(30183), 'Container.Update(%s?mode=appfeed&sitemode=getSimilarities&asin=%s)' % (sys.argv[0], asin)),
          (getString(30186), 'RunPlugin(%s?mode=xbmclibrary&sitemode=UpdateLibrary)' % sys.argv[0]),
          (getString(30155) % getString(30166), 'RunPlugin(%s?mode=tv&sitemode=delfromTVdb&asins=%s&table=shows&title=%s)' % (
           sys.argv[0], urllib.quote_plus(infoLabels['Asins']), urllib.quote_plus(seriestitle.encode('utf-8'))))]

    if onlyinfo:
        return infoLabels
    else:
        addDir(seriestitle, mode, submode, infoLabels['Asins'], poster, fanart, infoLabels, cm=cm)


def LIST_TV_SEASONS():
    seriesasin = args.get('url')
    for asin in seriesasin.split(','):
        seasons = tv.loadTVSeasonsdb(seriesasin=asin).fetchall()
        for seasondata in seasons:
            ADD_SEASON_ITEM(seasondata)
    xbmcplugin.addSortMethod(pluginhandle, xbmcplugin.SORT_METHOD_LABEL)
    SetView('seasons', 'seasonview')


def LIST_TVSEASON_SORTED(seasons=False, cmmode=0):
    if not seasons:
        seasons = tv.loadTVSeasonsdb(sortcol=args.get('url')).fetchall()
    for seasondata in seasons:
        ADD_SEASON_ITEM(seasondata, disptitle=True, cmmode=cmmode)
    SetView('seasons', 'seasonview')


def ADD_SEASON_ITEM(seasondata, mode='listtv', submode='LIST_EPISODES_DB', disptitle=False, cmmode=0, onlyinfo=False, export=False):
    asin, seriesASIN, season, seriestitle, plot, actors, network, mpaa, genres, premiered, year, stars, votes, \
        episodetotal, audio, empty, empty, isHD, isprime, empty, poster, banner, fanart, forceupd = seasondata
    tvfanart, tvposter = getFanart(seriesASIN)
    fanart = tvfanart if showfanart else fanart
    infoLabels = {'Title': seriestitle,
                  'TVShowTitle': seriestitle,
                  'Plot': plot,
                  'mediatype': 'season',
                  'MPAA': mpaa,
                  'Cast': actors.split(',') if actors else [],
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

    asin = asin.split(',')[0]
    displayname = seriestitle + ' - ' if disptitle else ''

    if season != 0 and season < 99:
        displayname += getString(30167) + ' ' + str(season)
    elif season > 1900:
        displayname += getString(30168) + str(season)
    elif season > 99:
        displayname += getString(30167) + ' ' + str(season).replace('0', '.')
    else:
        displayname += getString(30169)

    if export:
        xbmclibrary.EXPORT_SEASON(asin)
        return

    cm = [(getString(30180 + cmmode) % getString(30167),
          'RunPlugin(%s?mode=common&sitemode=toogleWatchlist&asin=%s&remove=%s)' % (sys.argv[0], asin, cmmode)),
          (getString(30185) % getString(30167),
          'RunPlugin(%s?mode=xbmclibrary&sitemode=EXPORT_SEASON&asin=%s)' % (sys.argv[0], asin)),
          (getString(30183), 'Container.Update(%s?mode=appfeed&sitemode=getSimilarities&asin=%s)' % (sys.argv[0], asin)),
          (getString(30186), 'RunPlugin(%s?mode=xbmclibrary&sitemode=UpdateLibrary)' % sys.argv[0]),
          (getString(30155) % getString(30167), 'RunPlugin(%s?mode=tv&sitemode=delfromTVdb&asins=%s&table=seasons&title=%s)' % (
           sys.argv[0], urllib.quote_plus(infoLabels['Asins']), urllib.quote_plus(displayname.encode('utf-8'))))]

    if onlyinfo:
        return infoLabels
    else:
        addDir(displayname, mode, submode, infoLabels['Asins'], poster, fanart, infoLabels, cm=cm)


def LIST_EPISODES_DB():
    seriestitle = args.get('url')
    for asin in seriestitle.split(','):
        episodes = tv.loadTVEpisodesdb(asin)
        for episodedata in episodes:
            ADD_EPISODE_ITEM(episodedata)
    xbmcplugin.addSortMethod(pluginhandle, xbmcplugin.SORT_METHOD_LABEL)
    SetView('episodes', 'episodeview')


def ADD_EPISODE_ITEM(episodedata, onlyinfo=False, export=False):
    asin, seasonASIN, seriesASIN, seriestitle, season, episode, poster, mpaa, actors, genres, episodetitle, network, \
        stars, votes, fanart, plot, airdate, year, runtime, isHD, isprime, isAdult, audio = episodedata
    tvfanart, tvposter = getFanart(seriesASIN)
    fanart = tvfanart if showfanart else fanart
    displayname = '%s - %s' % (episode, episodetitle)
    if episode == 0 and ':' in episodetitle:
        displayname = '- ' + episodetitle.split(':')[1].strip() + ' -'

    infoLabels = {'Title': displayname,
                  'TVShowTitle': seriestitle,
                  'Episode': episode,
                  'mediatype': 'episode',
                  'Season': season,
                  'Plot': plot,
                  'Premiered': airdate,
                  'Year': year,
                  'Duration': runtime,
                  'MPAA': mpaa if mpaa else getString(30171),
                  'Cast': actors.split(',') if actors else [],
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
                  'Poster': tvposter,
                  'EpisodeName': episodetitle
                  }
    asin = asin.split(',')[0]

    if export:
        xbmclibrary.EXPORT_EPISODE(asin)
        return

    cm = [(getString(30185) % getString(30173),
           'RunPlugin(%s?mode=xbmclibrary&sitemode=EXPORT_EPISODE&asin=%s)' % (sys.argv[0], asin)),
          (getString(30183),
           'Container.Update(%s?mode=appfeed&sitemode=getSimilarities&asin=%s)' % (sys.argv[0], asin)),
          (getString(30186), 'RunPlugin(%s?mode=xbmclibrary&sitemode=UpdateLibrary)' % sys.argv[0])]

    if onlyinfo:
        return infoLabels
    else:
        addVideo(displayname, asin, poster, fanart, infoLabels=infoLabels, isAdult=isAdult, isHD=isHD, cm=cm)


def getFanart(asin, tbl='shows'):
    fanart, poster = tv.lookupTVdb(asin, rvalue='fanart, poster', tbl=tbl)
    if not fanart or fanart == na:
        fanart = poster
    return fanart, poster
