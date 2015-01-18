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

xmlstring = xbmcaddon.Addon().getLocalizedString
pluginhandle = common.pluginhandle

# 501-POSTER WRAP 503-MLIST3 504=MLIST2 508-FANARTPOSTER 
confluence_views = [500,501,502,503,504,508]

################################ Movie listing
def LIST_MOVIE_ROOT():
    #common.addDir(xmlstring(30157),'listmovie','LIST_MOVIES','no')
    common.addDir(xmlstring(30143),'listmovie','LIST_MOVIES')
    common.addDir(xmlstring(30144),'listmovie','LIST_MOVIE_TYPES','GENRE')
    common.addDir(xmlstring(30145),'listmovie','LIST_MOVIE_TYPES','YEARS')
    common.addDir(xmlstring(30146),'listmovie','LIST_MOVIE_TYPES','STUDIOS')
    common.addDir(xmlstring(30158),'listmovie','LIST_MOVIE_TYPES','ACTORS')
    common.addDir(xmlstring(30147),'listmovie','LIST_MOVIE_TYPES','MPAA')
    common.addDir(xmlstring(30148),'listmovie','LIST_MOVIE_TYPES','DIRECTORS')
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

def LIST_MOVIES(genrefilter=False,actorfilter=False,directorfilter=False,studiofilter=False,yearfilter=False,mpaafilter=False,alphafilter=False,sortaz=True,search=False):
    import movies as moviesDB
    if common.args.url == 'no': sortaz = False
    movies = moviesDB.loadMoviedb(genrefilter=genrefilter,actorfilter=actorfilter,directorfilter=directorfilter,studiofilter=studiofilter,yearfilter=yearfilter,mpaafilter=mpaafilter,alphafilter=alphafilter)
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
    
def ADD_MOVIE_ITEM(moviedata,override_url=False,inWatchlist=False):
    asin,hd_asin,movietitle,trailer,poster,plot,director,writer,runtime,year,premiered,studio,mpaa,actors,genres,stars,votes,TMDBbanner,TMDBposter,TMDBfanart,isprime,isHD,isAdult,watched,audio,TMDB_ID = moviedata
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
    if audio:
        infoLabels['AudioChannels'] = audio
    cm = []
#    if favor: cm.append( (xmlstring(30152), 'XBMC.RunPlugin(%s?mode=<movies>&sitemode=<unfavorMoviedb>&url=<%s>)' % ( sys.argv[0], urllib.quote_plus(asin) ) ) )
#    else: cm.append( (xmlstring(30153), 'XBMC.RunPlugin(%s?mode=<movies>&sitemode=<favorMoviedb>&url=<%s>)' % ( sys.argv[0], urllib.quote_plus(asin) ) ) )
#    if watched:
#        infoLabels['playcount']=1
#        infoLabels['overlay']=5
#        cm.append( (xmlstring(30154), 'XBMC.RunPlugin(%s?mode=<movies>&sitemode=<unwatchMoviedb>&url=<%s>)' % ( sys.argv[0], urllib.quote_plus(asin) ) ) )
#    else:
#        infoLabels['playcount']=0
#        infoLabels['overlay']=4
#        cm.append( (xmlstring(30155), 'XBMC.RunPlugin(%s?mode=<movies>&sitemode=<watchMoviedb>&url=<%s>)' % ( sys.argv[0], urllib.quote_plus(asin) ) ) )
    if common.addon.getSetting("editenable") == 'true':
        cm.append( (xmlstring(30156), 'XBMC.RunPlugin(%s?mode=<movies>&sitemode=<deleteMoviedb>&url=<%s>)' % ( sys.argv[0], urllib.quote_plus(asin) ) ) )
    common.addVideo(movietitle,asin,poster,fanart,infoLabels=infoLabels,cm=cm,trailer=trailer,isAdult=isAdult,isHD=isHD)    
