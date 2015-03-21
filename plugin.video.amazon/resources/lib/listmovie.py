#!/usr/bin/env python
# -*- coding: utf-8 -*-
import common
import xbmclibrary

pluginhandle = common.pluginhandle
xbmc = common.xbmc
xbmcplugin = common.xbmcplugin
xbmcaddon = common.xbmcaddon
urllib = common.urllib
sys = common.sys
xbmcgui = common.xbmcgui

################################ Movie listing
def LIST_MOVIE_ROOT():
    common.addDir(common.getString(30100),'listmovie','LIST_MOVIES_SORTED','popularity')
    common.addDir(common.getString(30110),'listmovie','LIST_MOVIES_SORTED','recent')
    common.addDir(common.getString(30143),'listmovie','LIST_MOVIES')
    common.addDir(common.getString(30144),'listmovie','LIST_MOVIE_TYPES','GENRE')
    common.addDir(common.getString(30145),'listmovie','LIST_MOVIE_TYPES','YEARS')
    common.addDir(common.getString(30146),'listmovie','LIST_MOVIE_TYPES','STUDIOS')
    common.addDir(common.getString(30158),'listmovie','LIST_MOVIE_TYPES','ACTORS')
    common.addDir(common.getString(30147),'listmovie','LIST_MOVIE_TYPES','MPAA')
    common.addDir(common.getString(30148),'listmovie','LIST_MOVIE_TYPES','DIRECTORS')
    xbmcplugin.endOfDirectory(pluginhandle)
    
def LIST_MOVIE_TYPES(type=False):
    import movies as moviesDB
    if not type:
        type = common.args.url
    if type=='GENRE':
        mode = 'LIST_MOVIES_GENRE_FILTERED'
        items = moviesDB.getMovieTypes('genres')
    elif type=='STUDIOS':
        mode =  'LIST_MOVIES_STUDIO_FILTERED'
        items = moviesDB.getMovieTypes('studio')
    elif type=='YEARS':
        mode = 'LIST_MOVIES_YEAR_FILTERED'
        items = moviesDB.getMovieTypes('year')
    elif type=='DIRECTORS':
        mode = 'LIST_MOVIES_DIRECTOR_FILTERED'
        items = moviesDB.getMovieTypes('director')
    elif type=='MPAA':
        mode = 'LIST_MOVIES_MPAA_FILTERED'
        items = moviesDB.getMovieTypes('mpaa')
    elif type=='ACTORS':        
        mode = 'LIST_MOVIES_ACTOR_FILTERED'
        items = moviesDB.getMovieTypes('actors')     
    for item in items:
        common.addDir(item,'listmovie',mode,item)
    xbmcplugin.addSortMethod(pluginhandle, xbmcplugin.SORT_METHOD_LABEL)          
    xbmcplugin.endOfDirectory(pluginhandle,updateListing=False)   

def LIST_MOVIES_GENRE_FILTERED():
    LIST_MOVIES(genrefilter=common.args.url)

def LIST_MOVIES_YEAR_FILTERED():
    LIST_MOVIES(yearfilter=common.args.url)

def LIST_MOVIES_MPAA_FILTERED():
    LIST_MOVIES(mpaafilter=common.args.url)
    
def LIST_MOVIES_STUDIO_FILTERED():
    LIST_MOVIES(studiofilter=common.args.url)

def LIST_MOVIES_DIRECTOR_FILTERED():
    LIST_MOVIES(directorfilter=common.args.url)

def LIST_MOVIES_ACTOR_FILTERED():
    LIST_MOVIES(actorfilter=common.args.url)

def LIST_MOVIES_SORTED():
    LIST_MOVIES(sortaz = False, sortcol = common.args.url)
    
def LIST_MOVIES(genrefilter=False,actorfilter=False,directorfilter=False,studiofilter=False,yearfilter=False,mpaafilter=False,alphafilter=False,asinfilter=False,sortcol=False,sortaz=True,search=False,cmmode=0, export=False):
    import movies as moviesDB
    movies = moviesDB.loadMoviedb(sortcol=sortcol,genrefilter=genrefilter,actorfilter=actorfilter,directorfilter=directorfilter,studiofilter=studiofilter,yearfilter=yearfilter,mpaafilter=mpaafilter,alphafilter=alphafilter,asinfilter=asinfilter)
    count = 0
    for moviedata in movies:
        count += 1
        ADD_MOVIE_ITEM(moviedata, cmmode=cmmode, export=export)
    if not search:
        if sortaz:
            xbmcplugin.addSortMethod(pluginhandle, xbmcplugin.SORT_METHOD_VIDEO_TITLE)
            xbmcplugin.addSortMethod(pluginhandle, xbmcplugin.SORT_METHOD_VIDEO_YEAR)
            xbmcplugin.addSortMethod(pluginhandle, xbmcplugin.SORT_METHOD_VIDEO_RUNTIME)
            xbmcplugin.addSortMethod(pluginhandle, xbmcplugin.SORT_METHOD_VIDEO_RATING)
            xbmcplugin.addSortMethod(pluginhandle, xbmcplugin.SORT_METHOD_DURATION)
            xbmcplugin.addSortMethod(pluginhandle, xbmcplugin.SORT_METHOD_STUDIO_IGNORE_THE)
        common.SetView('movies', 'movieview')
    return count
    
def ADD_MOVIE_ITEM(moviedata, onlyinfo=False,cmmode=0, export=False):
    asin,hd_asin,movietitle,trailer,poster,plot,director,writer,runtime,year,premiered,studio,mpaa,actors,genres,stars,votes,fanart,isprime,isHD,isAdult,popularity,recent,audio = moviedata
    if not fanart or fanart == 'na':
        if poster:
            fanart = poster.replace('.jpg','._BO354,0,0,0_CR177,354,708,500_.jpg')
    infoLabels={'Title':movietitle}
    if plot:
        infoLabels['Plot'] = plot
    if actors:
        infoLabels['Cast'] = actors.split(',')
    if director:
        infoLabels['Director'] = director
    if year:
        infoLabels['Year'] = year
    if premiered:
        infoLabels['Premiered'] = premiered
    if stars:
        infoLabels['Rating'] = stars
    if votes:
        infoLabels['Votes'] = votes  
    if genres:
        infoLabels['Genre'] = genres 
    if mpaa:
        infoLabels['mpaa'] = mpaa
    if studio:
        infoLabels['Studio'] = studio
    if runtime:
        infoLabels['Duration'] = runtime
    if audio:
        infoLabels['AudioChannels'] = audio
    if poster:
        infoLabels['Thumb'] = poster
    if fanart:
        infoLabels['Fanart'] = fanart
    infoLabels['isHD'] = isHD
    infoLabels['isAdult'] = isAdult
    asin = asin.split(',')[0]
    if export:
        xbmclibrary.EXPORT_MOVIE(asin)
        return
    cm = []
    if cmmode == 1:
        cm.append((common.getString(30181) % common.getString(30154), 'XBMC.RunPlugin(%s?mode=<common>&sitemode=<removeWatchlist>&asin=<%s>)' % (sys.argv[0], asin)))
    else:
        cm.append((common.getString(30180) % common.getString(30154), 'XBMC.RunPlugin(%s?mode=<common>&sitemode=<addWatchlist>&asin=<%s>)' % (sys.argv[0], asin)))
    cm.append((common.getString(30185) % common.getString(30154), 'XBMC.RunPlugin(%s?mode=<xbmclibrary>&sitemode=<EXPORT_MOVIE>&asin=<%s>)' % (sys.argv[0], asin)))
    cm.append((common.getString(30186), 'XBMC.RunPlugin(%s?mode=<xbmclibrary>&sitemode=<UpdateLibrary>)' % sys.argv[0]))
    if onlyinfo:
        return infoLabels
    else:
        common.addVideo(movietitle,asin,poster,fanart,infoLabels=infoLabels,cm=cm,trailer=trailer,isAdult=isAdult,isHD=isHD)
