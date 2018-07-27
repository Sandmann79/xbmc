#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from .common import *
import xbmclibrary
import movies as moviesDB


def LIST_MOVIE_ROOT():
    addDir(getString(30100), 'listmovie', 'LIST_MOVIES_SORTED', 'popularity')
    addDir(getString(30110), 'listmovie', 'LIST_MOVIES_SORTED', 'recent')
    addDir(getString(30149), 'listmovie', 'LIST_MOVIES_CATS')
    addDir(getString(30143), 'listmovie', 'LIST_MOVIES')
    addDir(getString(30144), 'listmovie', 'LIST_MOVIE_TYPES', 'genres')
    addDir(getString(30145), 'listmovie', 'LIST_MOVIE_TYPES', 'year')
    addDir(getString(30146), 'listmovie', 'LIST_MOVIE_TYPES', 'studio')
    addDir(getString(30158), 'listmovie', 'LIST_MOVIE_TYPES', 'actors')
    addDir(getString(30147), 'listmovie', 'LIST_MOVIE_TYPES', 'mpaa')
    addDir(getString(30148), 'listmovie', 'LIST_MOVIE_TYPES', 'director')
    xbmcplugin.endOfDirectory(var.pluginhandle)


def LIST_MOVIES_CATS():
    catid = var.args.get('url')
    if catid:
        asins = moviesDB.lookupMoviedb(catid, rvalue='asins', name='title', table='categories')
        for asin in asins.split(','):
            LIST_MOVIES('asin', asin, search=True)
        SetView('movies', 'movieview')
    else:
        for title in moviesDB.lookupMoviedb('', name='asins', table='categories', single=False):
            if title:
                addDir(title[0], 'listmovie', 'LIST_MOVIES_CATS', title[0])

        xbmcplugin.endOfDirectory(var.pluginhandle, updateListing=False)


def LIST_MOVIE_TYPES(movtype=None):
    if not movtype:
        movtype = var.args.get('url')
    if movtype:
        for item in moviesDB.getMovieTypes(movtype):
            addDir(item, 'listmovie', 'LIST_MOVIES_FILTERED', movtype)
        xbmcplugin.addSortMethod(var.pluginhandle, xbmcplugin.SORT_METHOD_LABEL)
        xbmcplugin.endOfDirectory(var.pluginhandle, updateListing=False)


def LIST_MOVIES_FILTERED():
    LIST_MOVIES(var.args.get('url'), var.args.get('name'))


def LIST_MOVIES_SORTED():
    LIST_MOVIES(sortaz=False, sortcol=var.args.get('url'))


def LIST_MOVIES(filterobj='', value=None, sortcol=False, sortaz=True, search=False, cmmode=0, export=False):
    if 'year' in filterobj:
        value = value.replace('0 -', '')

    movies = moviesDB.loadMoviedb(filterobj, value, sortcol)
    count = 0
    for moviedata in movies:
        count += 1
        ADD_MOVIE_ITEM(moviedata, cmmode=cmmode, export=export)
    if not search:
        if sortaz:
            if 'year' not in filterobj:
                xbmcplugin.addSortMethod(var.pluginhandle, xbmcplugin.SORT_METHOD_VIDEO_TITLE)

            xbmcplugin.addSortMethod(var.pluginhandle, xbmcplugin.SORT_METHOD_VIDEO_YEAR)
            xbmcplugin.addSortMethod(var.pluginhandle, xbmcplugin.SORT_METHOD_VIDEO_RUNTIME)
            xbmcplugin.addSortMethod(var.pluginhandle, xbmcplugin.SORT_METHOD_VIDEO_RATING)
            xbmcplugin.addSortMethod(var.pluginhandle, xbmcplugin.SORT_METHOD_DURATION)
            xbmcplugin.addSortMethod(var.pluginhandle, xbmcplugin.SORT_METHOD_STUDIO_IGNORE_THE)
        SetView('movies', 'movieview')
    return count


def ADD_MOVIE_ITEM(moviedata, onlyinfo=False, cmmode=0, export=False):
    asin, movietitle, trailer, poster, plot, director, writer, runtime, year, premiered, studio, mpaa, actors,\
     genres, stars, votes, fanart, isprime, isHD, isAdult, popularity, recent, audio = moviedata
    infoLabels = {'Title': movietitle,
                  'Plot': plot,
                  'mediatype': 'movie',
                  'Cast': actors.split(',') if actors else [],
                  'Director': director,
                  'Year': year,
                  'Premiered': premiered,
                  'Rating': stars,
                  'Votes': votes,
                  'Genre': genres,
                  'MPAA': mpaa if mpaa else getString(30171),
                  'Studio': studio,
                  'Duration': runtime,
                  'AudioChannels': audio,
                  'Thumb': poster,
                  'Fanart': fanart,
                  'isHD': isHD,
                  'isAdult': isAdult}
    asin = asin.split(',')[0]
    if export:
        xbmclibrary.EXPORT_MOVIE(asin)
        return
    cm = [(getString(30180 + cmmode) % getString(30154),
          'RunPlugin(%s?mode=common&sitemode=toogleWatchlist&asin=%s&remove=%s)' % (sys.argv[0], asin, cmmode)),
          (getString(30185) % getString(30154),
          'RunPlugin(%s?mode=xbmclibrary&sitemode=EXPORT_MOVIE&asin=%s)' % (sys.argv[0], asin)),
          (getString(30183), 'Container.Update(%s?mode=appfeed&sitemode=getSimilarities&asin=%s)' % (sys.argv[0], asin)),
          (getString(30186), 'RunPlugin(%s?mode=xbmclibrary&sitemode=UpdateLibrary)' % sys.argv[0])]
    if onlyinfo:
        return infoLabels
    else:
        addVideo(movietitle, asin, poster, fanart, infoLabels=infoLabels, cm=cm, trailer=trailer, isAdult=isAdult, isHD=isHD)
