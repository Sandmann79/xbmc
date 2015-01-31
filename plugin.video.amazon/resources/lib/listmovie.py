#!/usr/bin/env python
# -*- coding: utf-8 -*-
import xbmcplugin
import xbmc
import xbmcgui
import os.path
import sys
import urllib
import resources.lib.common as common
import xbmcaddon

pluginhandle = common.pluginhandle

# 501-POSTER WRAP 503-MLIST3 504=MLIST2 508-FANARTPOSTER 
confluence_views = [500,501,502,503,504,508]

################################ Movie listing
def LIST_MOVIE_ROOT():
    common.addDir(common.getString(30100),'appfeed','CATEGORY','rh=n%3A3010075031%2Cn%3A3356018031&sort=popularity-rank')
    common.addDir(common.getString(30143),'listmovie','LIST_MOVIES')
    common.addDir(common.getString(30144),'listmovie','LIST_MOVIE_TYPES','GENRE')
    common.addDir(common.getString(30145),'listmovie','LIST_MOVIE_TYPES','YEARS')
    common.addDir(common.getString(30146),'listmovie','LIST_MOVIE_TYPES','STUDIOS')
    common.addDir(common.getString(30158),'listmovie','LIST_MOVIE_TYPES','ACTORS')
    common.addDir(common.getString(30147),'listmovie','LIST_MOVIE_TYPES','MPAA')
    common.addDir(common.getString(30148),'listmovie','LIST_MOVIE_TYPES','DIRECTORS')
    xbmcplugin.endOfDirectory(pluginhandle)
    
def LIST_MOVIE_AZ():
    common.addDir('#','listmovie','LIST_MOVIES_AZ_FILTERED','')
    alphabet=set(string.ascii_uppercase)
    for letter in alphabet:
        common.addDir(letter,'listmovie','LIST_MOVIES_AZ_FILTERED',letter)
    xbmcplugin.addSortMethod(pluginhandle, xbmcplugin.SORT_METHOD_LABEL)
    xbmcplugin.endOfDirectory(pluginhandle)

def LIST_MOVIES_AZ_FILTERED():
    LIST_MOVIES(alphafilter=common.args.url)

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

def LIST_MOVIES(genrefilter=False,actorfilter=False,directorfilter=False,studiofilter=False,yearfilter=False,mpaafilter=False,alphafilter=False,asinfilter=False,sortaz=True,search=False):
    import movies as moviesDB
    if common.args.url == 'no': sortaz = False
    movies = moviesDB.loadMoviedb(genrefilter=genrefilter,actorfilter=actorfilter,directorfilter=directorfilter,studiofilter=studiofilter,yearfilter=yearfilter,mpaafilter=mpaafilter,alphafilter=alphafilter,asinfilter=asinfilter)
    count = 0
    for moviedata in movies:
        count += 1
        ADD_MOVIE_ITEM(moviedata)
    if not search:
        xbmcplugin.setContent(pluginhandle, 'Movies')
        if sortaz:
            xbmcplugin.addSortMethod(pluginhandle, xbmcplugin.SORT_METHOD_VIDEO_TITLE)
            xbmcplugin.addSortMethod(pluginhandle, xbmcplugin.SORT_METHOD_VIDEO_YEAR)
            xbmcplugin.addSortMethod(pluginhandle, xbmcplugin.SORT_METHOD_VIDEO_RUNTIME)
            xbmcplugin.addSortMethod(pluginhandle, xbmcplugin.SORT_METHOD_VIDEO_RATING)
            xbmcplugin.addSortMethod(pluginhandle, xbmcplugin.SORT_METHOD_DURATION)
            xbmcplugin.addSortMethod(pluginhandle, xbmcplugin.SORT_METHOD_STUDIO_IGNORE_THE)
        viewenable=common.addon.getSetting("viewenable")
        if viewenable == 'true':
            view=int(common.addon.getSetting("movieview"))
            xbmc.executebuiltin("Container.SetViewMode("+str(confluence_views[view])+")")
        xbmcplugin.endOfDirectory(pluginhandle,updateListing=False)
    return count
    
def ADD_MOVIE_ITEM(moviedata, onlyinfo=False,inWatchlist=False):
    asin,hd_asin,movietitle,trailer,poster,plot,director,writer,runtime,year,premiered,studio,mpaa,actors,genres,stars,votes,TMDBbanner,TMDBposter,fanart,isprime,isHD,isAdult,watched,audio,TMDB_ID = moviedata
    if not fanart:
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
    cm = []
    if onlyinfo:
        return infoLabels
    else:
        common.addVideo(movietitle,asin.split(',')[0],poster,fanart,infoLabels=infoLabels,cm=cm,trailer=trailer,isAdult=isAdult,isHD=isHD)
