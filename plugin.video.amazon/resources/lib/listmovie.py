#!/usr/bin/env python
# -*- coding: utf-8 -*-
import xbmcplugin
import xbmc
import xbmcgui
import os.path
import sys
import urllib
import string
import resources.lib.common as common
import xbmclibrary
import xbmcaddon

xmlstring = xbmcaddon.Addon().getLocalizedString
pluginhandle = common.pluginhandle

# 501-POSTER WRAP 503-MLIST3 504=MLIST2 508-FANARTPOSTER 
confluence_views = [500,501,502,503,504,508]

################################ Movie listing
def LIST_MOVIE_ROOT():
    cm = [(xmlstring(30140), 'XBMC.RunPlugin(plugin://plugin.video.amazon?mode="listmovie"&sitemode="LIST_MOVIES_FAVOR_FILTERED_EXPORT"&url="")' ) ]
    common.addDir(xmlstring(30141),'listmovie','LIST_MOVIES_FAVOR_FILTERED',cm=cm)
    cm = [(xmlstring(30142), 'XBMC.RunPlugin(plugin://plugin.video.amazon?mode="listmovie"&sitemode="LIST_MOVIES_EXPORT"&url="")' ) ]
    common.addDir(xmlstring(30143),'listmovie','LIST_MOVIES',cm=cm)
    #common.addDir('Alphabetical','listmovie','LIST_MOVIE_AZ')
    common.addDir(xmlstring(30144),'listmovie','LIST_MOVIE_TYPES','GENRE')
    common.addDir(xmlstring(30145),'listmovie','LIST_MOVIE_TYPES','YEARS')
    common.addDir(xmlstring(30146),'listmovie','LIST_MOVIE_TYPES','STUDIOS')
    common.addDir(xmlstring(30147),'listmovie','LIST_MOVIE_TYPES','MPAA')
    common.addDir(xmlstring(30148),'listmovie','LIST_MOVIE_TYPES','DIRECTORS')
    #common.addDir('Actors','listmovie','LIST_MOVIE_TYPES','ACTORS')
    cm = [(xmlstring(30149), 'XBMC.RunPlugin(plugin://plugin.video.amazon?mode="listmovie"&sitemode="LIST_MOVIES_WATCHED_FILTERED_EXPORT"&url="")' ) ]
    common.addDir(xmlstring(30150),'listmovie','LIST_MOVIES_WATCHED_FILTERED',cm=cm)
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
        export_mode=mode+'_EXPORT'
        cm = [(xmlstring(30151), 'XBMC.RunPlugin(plugin://plugin.video.amazon?mode="listmovie"&sitemode="%s"&url="%s")' % ( export_mode, urllib.quote_plus(item) ) ) ]
        common.addDir(item,'listmovie',mode,item,cm=cm)
    xbmcplugin.addSortMethod(pluginhandle, xbmcplugin.SORT_METHOD_LABEL)          
    xbmcplugin.endOfDirectory(pluginhandle,updateListing=False)   

def LIST_MOVIES_GENRE_FILTERED_EXPORT():
    LIST_MOVIES_GENRE_FILTERED(export=True) 

def LIST_MOVIES_GENRE_FILTERED(export=False):
    LIST_MOVIES(export=export,genrefilter=common.args.url)

def LIST_MOVIES_YEAR_FILTERED_EXPORT():
    LIST_MOVIES_YEAR_FILTERED(export=True) 

def LIST_MOVIES_YEAR_FILTERED(export=False):
    LIST_MOVIES(export=export,yearfilter=common.args.url)

def LIST_MOVIES_MPAA_FILTERED_EXPORT():
    LIST_MOVIES_MPAA_FILTERED(export=True) 

def LIST_MOVIES_MPAA_FILTERED(export=False):
    LIST_MOVIES(export=export,mpaafilter=common.args.url)
 
def LIST_MOVIES_STUDIO_FILTERED_EXPORT():
    LIST_MOVIES_STUDIO_FILTERED(export=True) 
    
def LIST_MOVIES_STUDIO_FILTERED(export=False):
    LIST_MOVIES(export=export,studiofilter=common.args.url)

def LIST_MOVIES_DIRECTOR_FILTERED_EXPORT():
    LIST_MOVIES_DIRECTOR_FILTERED(export=True)

def LIST_MOVIES_DIRECTOR_FILTERED(export=False):
    LIST_MOVIES(export=export,directorfilter=common.args.url)

def LIST_MOVIES_ACTOR_FILTERED_EXPORT():
    LIST_MOVIES_ACTOR_FILTERED(export=True)

def LIST_MOVIES_ACTOR_FILTERED(export=False):
    LIST_MOVIES(export=export,actorfilter=common.args.url)

def LIST_MOVIES_WATCHED_FILTERED_EXPORT():
    LIST_MOVIES_WATCHED_FILTERED(export=True)
    
def LIST_MOVIES_WATCHED_FILTERED(export=False):
    LIST_MOVIES(export=export,watchedfilter=True)

def LIST_MOVIES_FAVOR_FILTERED_EXPORT():
    LIST_MOVIES_FAVOR_FILTERED(export=True) 
  
def LIST_MOVIES_FAVOR_FILTERED(export=False):
    LIST_MOVIES(export=export,favorfilter=True)

def LIST_MOVIES_EXPORT():
    LIST_MOVIES(export=True)

def LIST_MOVIES(export=False,genrefilter=False,actorfilter=False,directorfilter=False,studiofilter=False,yearfilter=False,mpaafilter=False,watchedfilter=False,favorfilter=False,alphafilter=False):
    if export:
        xbmclibrary.SetupLibrary()
    import movies as moviesDB
    movies = moviesDB.loadMoviedb(genrefilter=genrefilter,actorfilter=actorfilter,directorfilter=directorfilter,studiofilter=studiofilter,yearfilter=yearfilter,mpaafilter=mpaafilter,watchedfilter=watchedfilter,favorfilter=favorfilter,alphafilter=alphafilter)
    for moviedata in movies:
        if export:
            xbmclibrary.EXPORT_MOVIE(moviedata[0])
        else:
            ADD_MOVIE_ITEM(moviedata)
    if not export:
        xbmcplugin.setContent(pluginhandle, 'Movies')
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
    
def ADD_MOVIE_ITEM(moviedata,override_url=False,inWatchlist=False):
    asin,hd_asin,movietitle,url,poster,plot,director,writer,runtime,year,premiered,studio,mpaa,actors,genres,stars,votes,TMDBbanner,TMDBposter,TMDBfanart,isprime,isHD,watched,favor,TMDB_ID = moviedata
    if override_url:
        url=override_url
    if poster == None or poster == 'None':
        fanart = ''
        poster =''
    else:
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
    cm = []
    #if inWatchlist:
    #    cm.append( ('Remove from Watchlist', 'XBMC.RunPlugin(%s?mode="common"&sitemode="removeMovieWatchlist"&asin="%s")' % ( sys.argv[0], urllib.quote_plus(asin) ) ) )
    #else:
    #    cm.append( ('Add to Watchlist', 'XBMC.RunPlugin(%s?mode="common"&sitemode="addMovieWatchlist"&asin="%s")' % ( sys.argv[0], urllib.quote_plus(asin) ) ) )
    if favor: cm.append( (xmlstring(30152), 'XBMC.RunPlugin(%s?mode="movies"&sitemode="unfavorMoviedb"&url="%s")' % ( sys.argv[0], urllib.quote_plus(asin) ) ) )
    else: cm.append( (xmlstring(30153), 'XBMC.RunPlugin(%s?mode="movies"&sitemode="favorMoviedb"&url="%s")' % ( sys.argv[0], urllib.quote_plus(asin) ) ) )
    cm.append( (xmlstring(30151), 'XBMC.RunPlugin(plugin://plugin.video.amazon?mode="xbmclibrary"&sitemode="EXPORT_MOVIE"&asin="%s")' % ( urllib.quote_plus(asin) ) ) )
    if watched:
        infoLabels['overlay']=7
        cm.append( (xmlstring(30154), 'XBMC.RunPlugin(%s?mode="movies"&sitemode="unwatchMoviedb"&url="%s")' % ( sys.argv[0], urllib.quote_plus(asin) ) ) )
    else: cm.append( (xmlstring(30155), 'XBMC.RunPlugin(%s?mode="movies"&sitemode="watchMoviedb"&url="%s")' % ( sys.argv[0], urllib.quote_plus(asin) ) ) )
    if common.addon.getSetting("editenable") == 'true':
        cm.append( (xmlstring(30156), 'XBMC.RunPlugin(%s?mode="movies"&sitemode="deleteMoviedb"&url="%s")' % ( sys.argv[0], urllib.quote_plus(asin) ) ) )
    common.addVideo(movietitle,url,poster,fanart,infoLabels=infoLabels,cm=cm)
        

