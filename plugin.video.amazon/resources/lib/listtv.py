#!/usr/bin/env python
# -*- coding: utf-8 -*-
import xbmcplugin
import xbmc
import xbmcgui
import os.path
import sys
import urllib
import resources.lib.common as common
import xbmclibrary
import xbmcaddon

xmlstring = xbmcaddon.Addon().getLocalizedString
pluginhandle = common.pluginhandle

# 501-POSTER WRAP 503-MLIST3 504=MLIST2 508-FANARTPOSTER 
confluence_views = [500,501,502,503,504,508]

###################### Television

def LIST_TV_ROOT():
    common.addDir(xmlstring(30141),'listtv','LIST_TVSHOWS_FAVOR_FILTERED')
    common.addDir(xmlstring(30172),'listtv','LIST_TVSHOWS','no')
    common.addDir(xmlstring(30160),'listtv','LIST_TVSHOWS')
    common.addDir(xmlstring(30144),'listtv','LIST_TVSHOWS_TYPES','GENRE' )
    common.addDir(xmlstring(30145),'listtv','LIST_TVSHOWS_TYPES','YEARS' )
    common.addDir(xmlstring(30161),'listtv','LIST_TVSHOWS_TYPES','NETWORKS')
    common.addDir(xmlstring(30162),'listtv','LIST_TVSHOWS_TYPES','MPAA' )
    #common.addDir('Creators','listtv','LIST_TVSHOWS_TYPES','CREATORS')
    xbmcplugin.endOfDirectory(pluginhandle)
    
def LIST_TVSHOWS_TYPES(type=False):
    import tv as tvDB
    if not type:
        type = common.args.url
    if type=='GENRE':
        mode = 'LIST_TVSHOWS_GENRE_FILTERED'
        items = tvDB.getShowTypes('genres')
    elif type=='NETWORKS':
        mode =  'LIST_TVSHOWS_NETWORKS_FILTERED'
        items = tvDB.getShowTypes('network')  
    elif type=='YEARS':
        mode = 'LIST_TVSHOWS_YEARS_FILTERED'
        items = tvDB.getShowTypes('year')
    elif type=='MPAA':
        mode = 'LIST_TVSHOWS_MPAA_FILTERED'
        items = tvDB.getShowTypes('mpaa')
    elif type=='CREATORS':
        mode = 'LIST_TVSHOWS_CREATORS_FILTERED'
        items = tvDB.getShowTypes('creator')
    for item in items:
        export_mode=mode+'_EXPORT'
        common.addDir(item,'listtv',mode,item)
    xbmcplugin.addSortMethod(pluginhandle, xbmcplugin.SORT_METHOD_LABEL)          
    xbmcplugin.endOfDirectory(pluginhandle,updateListing=False)   

def LIST_TVSHOWS_GENRE_FILTERED_EXPORT():
    LIST_TVSHOWS_GENRE_FILTERED(export=True)

def LIST_TVSHOWS_GENRE_FILTERED(export=False):
    LIST_TVSHOWS(export=export,genrefilter=common.args.url)

def LIST_TVSHOWS_NETWORKS_FILTERED_EXPORT():
    LIST_TVSHOWS_NETWORKS_FILTERED(export=True)

def LIST_TVSHOWS_NETWORKS_FILTERED(export=False):
    LIST_TVSHOWS(export=export,networkfilter=common.args.url)

def LIST_TVSHOWS_YEARS_FILTERED_EXPORT():
    LIST_TVSHOWS_YEARS_FILTERED(export=True)
    
def LIST_TVSHOWS_YEARS_FILTERED(export=False):
    LIST_TVSHOWS(export=export,yearfilter=common.args.url)

def LIST_TVSHOWS_MPAA_FILTERED_EXPORT():
    LIST_TVSHOWS_MPAA_FILTERED(export=True)

def LIST_TVSHOWS_MPAA_FILTERED(export=False):
    LIST_TVSHOWS(export=export,mpaafilter=common.args.url)

def LIST_TVSHOWS_CREATORS_FILTERED_EXPORT():
    LIST_TVSHOWS_CREATORS_FILTERED(export=True)

def LIST_TVSHOWS_CREATORS_FILTERED(export=False):
    LIST_TVSHOWS(export=export,creatorfilter=common.args.url)

def LIST_TVSHOWS_FAVOR_FILTERED_EXPORT():
    LIST_TVSHOWS_FAVOR_FILTERED(export=True)
  
def LIST_TVSHOWS_FAVOR_FILTERED(export=False):
    LIST_TVSHOWS(export=export,favorfilter=True)

def LIST_HDTVSHOWS_EXPORT():
    LIST_HDTVSHOWS(export=True)
        
def LIST_HDTVSHOWS(export=False):
    LIST_TVSHOWS(export=export,HDonly=True)

def LIST_TVSHOWS_EXPORT():
    LIST_TVSHOWS(export=True)
    
def LIST_TVSHOWS(export=False,HDonly=False,mpaafilter=False,genrefilter=False,creatorfilter=False,networkfilter=False,yearfilter=False,favorfilter=False,alphafilter=False,sortaz=True):
    import tv as tvDB
    if common.args.url == 'no': sortaz = False
    shows = tvDB.loadTVShowdb(HDonly=HDonly,mpaafilter=mpaafilter,genrefilter=genrefilter,creatorfilter=creatorfilter,networkfilter=networkfilter,yearfilter=yearfilter,favorfilter=favorfilter,alphafilter=alphafilter)
    count = 0
    for showdata in shows:
        count += 1
        ADD_SHOW_ITEM(showdata,HDonly=HDonly)
    if not export:
        xbmcplugin.setContent(pluginhandle, 'tvshows')
        if sortaz:
            xbmcplugin.addSortMethod(pluginhandle, xbmcplugin.SORT_METHOD_LABEL)
            xbmcplugin.addSortMethod(pluginhandle, xbmcplugin.SORT_METHOD_VIDEO_YEAR)
            xbmcplugin.addSortMethod(pluginhandle, xbmcplugin.SORT_METHOD_VIDEO_RATING)
            xbmcplugin.addSortMethod(pluginhandle, xbmcplugin.SORT_METHOD_STUDIO_IGNORE_THE)
        xbmcplugin.endOfDirectory(pluginhandle,updateListing=False)
        viewenable=common.addon.getSetting("viewenable")
        if viewenable == 'true':
            view=int(common.addon.getSetting("showview"))
            xbmc.executebuiltin("Container.SetViewMode("+str(confluence_views[view])+")")
    return count

def ADD_SHOW_ITEM(showdata,mode='listtv',submode='LIST_TV_SEASONS',HDonly=False):
    artOptions = ['Poster','Banner','Amazon']
    tvart=int(common.addon.getSetting("tvart"))
    option = artOptions[tvart]
    asin,asin2,feed,seriestitle,poster,plot,network,mpaa,genres,actors,premiered,year,stars,votes,seasontotal,episodetotal,watched,unwatched,isHD,isprime,favor,TVDBbanner,TVDBposter,TVDBfanart,TVDBseriesid = showdata
    infoLabels={'Title': seriestitle,'TVShowTitle':seriestitle}
    if plot:
        infoLabels['Plot'] = plot
    if mpaa:
        infoLabels['MPAA'] = mpaa
    if actors:
        infoLabels['Cast'] = actors.split(',')
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
    if episodetotal:
        infoLabels['Episode'] = episodetotal
    if network:
        infoLabels['Studio'] = network
    item_url = asin
    if mode == 'listtv':
        submode = 'LIST_TV_SEASONS'
    if poster is None:
        poster=''
    if TVDBposter and option == 'Poster':
        poster = TVDBposter
    elif TVDBbanner and option == 'Banner':
        poster = TVDBbanner
    if TVDBfanart:
        fanart = TVDBfanart
    else:
        fanart = poster
    cm = []
    if favor: cm.append( (xmlstring(30152), 'XBMC.RunPlugin(%s?mode=<tv>&sitemode=<unfavorShowdb>&title=<%s>)' % ( sys.argv[0], urllib.quote_plus(seriestitle) ) ) )
    else: cm.append( (xmlstring(30153), 'XBMC.RunPlugin(%s?mode=<tv>&sitemode=<favorShowdb>&title=<%s>)' % ( sys.argv[0], urllib.quote_plus(seriestitle) ) ) )
    #cm.append( (xmlstring(30151), 'XBMC.RunPlugin(%s?mode=<xbmclibrary>&sitemode=<EXPORT_SHOW>&asin=<%s>)' % ( sys.argv[0], urllib.quote_plus(asin) ) ) )
    if common.addon.getSetting("editenable") == 'true':
        cm.append( (xmlstring(30163), 'XBMC.RunPlugin(%s?mode=<tv>&sitemode=<renameShowdb>&title=<%s>&asin=<%s>)' % ( sys.argv[0], urllib.quote_plus(seriestitle),asin ) ) )
        if TVDBseriesid:
            cm.append( (xmlstring(30164), 'XBMC.RunPlugin(%s?mode=<tv>&sitemode=<refreshTVDBshow>&title=<%s>)' % ( sys.argv[0], urllib.quote_plus(seriestitle) ) ) )
        cm.append( (xmlstring(30165), 'XBMC.RunPlugin(%s?mode=<tv>&sitemode=<scanTVDBshow>&title=<%s>)' % ( sys.argv[0], urllib.quote_plus(seriestitle) ) ) )
        cm.append( (xmlstring(30166), 'XBMC.RunPlugin(%s?mode=<tv>&sitemode=<deleteShowdb>&title=<%s>)' % ( sys.argv[0], urllib.quote_plus(seriestitle) ) ) )
    common.addDir(seriestitle,mode,submode,item_url,poster,fanart,infoLabels,cm=cm)

def LIST_HDTV_SEASONS():
    LIST_TV_SEASONS(HDonly=True)
   
def LIST_TV_SEASONS(HDonly=False,export=False):
    seriestitle = common.args.url
    import tv as tvDB
    for asin in seriestitle.split(','):
        seasons = tvDB.loadTVSeasonsdb(seriestitle=asin,HDonly=HDonly).fetchall()
        for seasondata in seasons:
            ADD_SEASON_ITEM(seasondata)
    xbmcplugin.addSortMethod(pluginhandle, xbmcplugin.SORT_METHOD_LABEL)
    xbmcplugin.setContent(pluginhandle, 'tvshows')
    xbmcplugin.endOfDirectory(pluginhandle,updateListing=False)
    viewenable=common.addon.getSetting("viewenable")
    if viewenable == 'true':
        view=int(common.addon.getSetting("seasonview"))
        xbmc.executebuiltin("Container.SetViewMode("+str(confluence_views[view])+")")

def ADD_SEASON_ITEM(seasondata,mode='listtv',submode='LIST_EPISODES_DB',seriesTitle=False,inWatchlist=False):
   #asin,episodeFeed,poster,season,seriestitle,plot,actors,studio,mpaa,genres,premiered,year,stars,votes,episodetotal,watched,unwatched,isHD,isprime
    asin,seriesASIN,episodeFeed,poster,season,seriestitle,plot,actors,network,mpaa,genres,premiered,year,stars,votes,episodetotal,watched,unwatched,isHD,isprime = seasondata
    infoLabels={'Title': seriestitle,'TVShowTitle':seriestitle}
    if plot:
        infoLabels['Plot'] = plot
    if mpaa:
        infoLabels['MPAA'] = mpaa
    if actors:
        infoLabels['Cast'] = actors.split(',')
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
    if episodetotal:
        infoLabels['Episode'] = episodetotal
    if season:
        infoLabels['Season'] = season
    if network:
        infoLabels['Studio'] = network
    url = asin
    if seriesTitle:
        displayname=seriestitle+' '
    else:
        displayname=''
    if season <> 0 and len(str(season)) < 3: displayname += xmlstring(30167) + str(season)
    elif len(str(season)) > 2: displayname += xmlstring(30168) + str(season)
    else: displayname += xmlstring(30169)
    cm = []
    fanart = poster
    common.addDir(displayname,mode,submode,url,poster,fanart,infoLabels,cm=cm)


def LIST_HDEPISODES_DB(url=False):
    LIST_EPISODES_DB(HDonly=True,url=url)

def LIST_EPISODES_DB(HDonly=False,owned=False,url=False,export=False):
    if not url:
        url = common.args.url
    split = url.split('<split>')
    seriestitle = split[0]
    try:
        season = int(split[1])
    except:
        season = 0
    import tv as tvDB
    for asin in seriestitle.split(','):
        episodes = tvDB.loadTVEpisodesdb(asin)
        for episodedata in episodes:
            ADD_EPISODE_ITEM(episodedata)
    xbmcplugin.addSortMethod(pluginhandle, xbmcplugin.SORT_METHOD_LABEL)
    xbmcplugin.setContent(pluginhandle, 'Episodes')
    xbmcplugin.endOfDirectory(pluginhandle,updateListing=False)
    viewenable=common.addon.getSetting("viewenable")
    if viewenable == 'true':
        view=int(common.addon.getSetting("episodeview"))
        xbmc.executebuiltin("Container.SetViewMode("+str(confluence_views[view])+")")
        
def ADD_EPISODE_ITEM(episodedata,seriesTitle=False):
   #asin,seriestitle,season,episode,poster,mpaa,actors,genres,episodetitle,studio,stars,votes,url,plot,airdate,year,runtime,isHD,isprime,watched
    asin,seasonASIN,seriesASIN,seriestitle,season,episode,poster,mpaa,actors,genres,episodetitle,network,stars,votes,url,plot,airdate,year,runtime,isHD,isprime,isAdult,watched = episodedata
    infoLabels={'Title': episodetitle,'TVShowTitle':seriestitle,
                'Episode': episode,'Season':season}
    if plot:
        infoLabels['Plot'] = plot
    if airdate:
        infoLabels['Premiered'] = airdate 
    if year:
        infoLabels['Year'] = year
    if runtime:
        infoLabels['Duration'] = runtime
    if mpaa:
        infoLabels['MPAA'] = mpaa
    if actors:
        infoLabels['Cast'] = actors.split(',')
    if stars:
        infoLabels['Rating'] = stars           
    if votes:
        infoLabels['Votes'] = votes  
    if genres:
        infoLabels['Genre'] = genres 
    if network:
        infoLabels['Studio'] = network
    if seriesTitle:
        displayname=seriestitle+' - '
    else:
        displayname=''
    displayname +=  str(episode)+' - '+episodetitle 
    displayname = displayname.replace('"','')
    try:
        if common.args.thumb and poster == None: poster = common.args.thumb
        if common.args.fanart and common.args.fanart <>'': fanart = common.args.fanart
        else: fanart=poster
    except: fanart=poster

    cm = []
    if watched:
        infoLabels['overlay']=7
        cm.append( (xmlstring(30154), 'XBMC.RunPlugin(%s?mode=<tv>&sitemode=<unwatchEpisodedb>&url=<%s>)' % ( sys.argv[0], urllib.quote_plus(asin) ) ) )
    else: cm.append( (xmlstring(30155), 'XBMC.RunPlugin(%s?mode=<tv>&sitemode=<watchEpisodedb>&url=<%s>)' % ( sys.argv[0], urllib.quote_plus(asin) ) ) )
    #cm.append( (xmlstring(30151), 'XBMC.RunPlugin(%s?mode=<xbmclibrary>&sitemode=<EXPORT_EPISODE>&asin=<%s>)' % ( sys.argv[0], urllib.quote_plus(asin) ) ) )
    common.addVideo(displayname,url,poster,fanart,infoLabels=infoLabels,cm=cm,isAdult=isAdult)
