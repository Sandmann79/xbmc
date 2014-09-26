#!/usr/bin/env python
# -*- coding: utf-8 -*-
from BeautifulSoup import BeautifulStoneSoup
from BeautifulSoup import BeautifulSoup
import xbmcplugin
import xbmc
import xbmcgui
import os.path
import sys
import urllib
import resources.lib.common as common
import re
import appfeed
import xbmclibrary
import xbmcaddon

xmlstring = xbmcaddon.Addon().getLocalizedString
pluginhandle = common.pluginhandle
confluence_views = [500,501,502,503,504,508]

################################ Library listing    
def LIBRARY_ROOT():
    common.addDir(xmlstring(30104),'library','LIBRARY_LIST_MOVIES','https://www.amazon.de/gp/video/library/movie?show=all&sort=alpha')
    common.addDir(xmlstring(30107),'library','LIBRARY_LIST_TV','https://www.amazon.de/gp/video/library/tv?show=all&sort=alpha')
    xbmcplugin.endOfDirectory(pluginhandle)

def WATCHLIST_ROOT():
    #cm = [(xmlstring(30151), 'XBMC.RunPlugin(%s?mode=<library>&sitemode=<WATCHLIST_LIST_MOVIES_EXPORT>&url=<>)' % sys.argv[0] ) ]
    common.addDir(xmlstring(30104),'library','WATCHLIST_LIST_MOVIES','')
    #cm = [(xmlstring(30151), 'XBMC.RunPlugin(%s?mode=<library>&sitemode=<WATCHLIST_LIST_TV_EXPORT>&url=<>)' % sys.argv[0] ) ]
    common.addDir(xmlstring(30107),'library','WATCHLIST_LIST_TV','')
    xbmcplugin.endOfDirectory(pluginhandle)

def WATCHLIST_LIST_MOVIES_EXPORT():
    WATCHLIST_LIST_MOVIES(export=True)

def WATCHLIST_LIST_MOVIES(export=False):
    if export:
        xbmclibrary.SetupLibrary()
    url = 'https://www.amazon.de/gp/video/watchlist/movie?show=all&sort=DATE_ADDED'
    data = common.getURL(url,useCookie=True)
    scripts = re.compile(r'<script.*?script>',re.DOTALL)
    data = scripts.sub('', data)
    style = re.compile(r'<style.*?style>',re.DOTALL)
    data = style.sub('', data)
    tree = BeautifulSoup(data, convertEntities=BeautifulSoup.HTML_ENTITIES)
    videos = tree.findAll('div',attrs={'class':'innerItem','id':True})
    totalItems = len(videos)
    for video in videos:
        asin = video['id']
        if export:
            xbmclibrary.EXPORT_MOVIE(asin)
        else:
            appfeed.ADD_MOVIE(asin,isPrime=True,inWatchlist=True)
    if not export:   
        xbmcplugin.setContent(int(sys.argv[1]), 'Movies')
        xbmcplugin.endOfDirectory(pluginhandle)
        viewenable=common.addon.getSetting("viewenable")
        if viewenable == 'true':
            view=int(common.addon.getSetting("movieview"))
            xbmc.executebuiltin("Container.SetViewMode("+str(confluence_views[view])+")")
    

def WATCHLIST_LIST_TV_EXPORT():
    WATCHLIST_LIST_TV(export=True)

def WATCHLIST_LIST_TV(export=False):
    if export:
        xbmclibrary.SetupLibrary()
    url = 'https://www.amazon.de/gp/video/watchlist/tv?show=all&sort=DATE_ADDED'
    data = common.getURL(url,useCookie=True)
    scripts = re.compile(r'<script.*?script>',re.DOTALL)
    data = scripts.sub('', data)
    style = re.compile(r'<style.*?style>',re.DOTALL)
    data = style.sub('', data)
    tree = BeautifulSoup(data, convertEntities=BeautifulSoup.HTML_ENTITIES)
    videos = tree.findAll('div',attrs={'class':'innerItem','id':True})
    totalItems = len(videos)
    ASINS = ''
    for video in videos:
        asin = video['id']
        if export:
            xbmclibrary.EXPORT_SEASON(asin)
        else:
            if common.addon.getSetting("watchlist_tv_view") == '0':
                appfeed.ADD_SEASON(asin,isPrime=True,inWatchlist=True,addSeries=True)
            elif common.addon.getSetting("watchlist_tv_view") == '1':
                asin1,asin2 = appfeed.ADD_SEASON_SERIES(asin,'library','WATCHLIST_LIST_SEASONS',isPrime=True,checklist=ASINS)
                if asin1:
                    ASINS += asin1
                if asin2:
                    ASINS += asin2
    if not export:
        xbmcplugin.setContent(int(sys.argv[1]), 'tvshows')
        xbmcplugin.endOfDirectory(pluginhandle)
        viewenable=common.addon.getSetting("viewenable")
        if viewenable == 'true':
            view=int(common.addon.getSetting("showview"))
            xbmc.executebuiltin("Container.SetViewMode("+str(confluence_views[view])+")")

def WATCHLIST_LIST_SEASONS():
    asin = common.args.url
    series = common.args.name
    
    url = 'https://www.amazon.de/gp/video/watchlist/tv?show=all&sort=DATE_ADDED'
    data = common.getURL(url,useCookie=True)
    scripts = re.compile(r'<script.*?script>',re.DOTALL)
    data = scripts.sub('', data)
    style = re.compile(r'<style.*?style>',re.DOTALL)
    data = style.sub('', data)
    tree = BeautifulSoup(data, convertEntities=BeautifulSoup.HTML_ENTITIES)
    videos = tree.findAll('div',attrs={'class':'innerItem','id':True})
    totalItems = len(videos)
    ASINS = ''
    for video in videos:
        asin = video['id']
        appfeed.ADD_SEASON(asin,isPrime=True,inWatchlist=True,seriesfilter=series)
    xbmcplugin.setContent(int(sys.argv[1]), 'tvshows')
    xbmcplugin.endOfDirectory(pluginhandle)
    viewenable=common.addon.getSetting("viewenable")
    if viewenable == 'true':
        view=int(common.addon.getSetting("seasonview"))
        xbmc.executebuiltin("Container.SetViewMode("+str(confluence_views[view])+")")


def LIBRARY_LIST_MOVIES():
    url = common.args.url
    data = common.getURL(url,useCookie=True)
    scripts = re.compile(r'<script.*?script>',re.DOTALL)
    data = scripts.sub('', data)
    style = re.compile(r'<style.*?style>',re.DOTALL)
    data = style.sub('', data)
    tree = BeautifulSoup(data, convertEntities=BeautifulSoup.HTML_ENTITIES)
    videos = tree.findAll('div',attrs={'class':'lib-item','asin':True})
    totalItems = len(videos)
    for video in videos:
        asin = video['asin']
        appfeed.ADD_MOVIE(asin,isPrime=False)
    xbmcplugin.setContent(int(sys.argv[1]), 'Movies')
    xbmcplugin.endOfDirectory(pluginhandle)
    viewenable=common.addon.getSetting("viewenable")
    if viewenable == 'true':
        view=int(common.addon.getSetting("movieview"))
        xbmc.executebuiltin("Container.SetViewMode("+str(confluence_views[view])+")")

def LIBRARY_LIST_TV():
    url = common.args.url
    data = common.getURL(url,useCookie=True)
    scripts = re.compile(r'<script.*?script>',re.DOTALL)
    data = scripts.sub('', data)
    style = re.compile(r'<style.*?style>',re.DOTALL)
    data = style.sub('', data)
    tree = BeautifulSoup(data, convertEntities=BeautifulSoup.HTML_ENTITIES)
    videos = tree.findAll('div',attrs={'class':'lib-item','asin':True})
    totalItems = len(videos)
    ASINS=''
    for video in videos:
        asin = video['asin']
        #appfeed.ADD_SEASON(asin,'library','LIBRARY_EPISODES',isPrime=False)
        if common.addon.getSetting("watchlist_tv_view") == '0':
            appfeed.ADD_SEASON(asin,'library','LIBRARY_EPISODES',isPrime=False,addSeries=True)
        elif common.addon.getSetting("watchlist_tv_view") == '1':
            asin1,asin2 = appfeed.ADD_SEASON_SERIES(asin,'library','LIBRARY_LIST_SEASONS',isPrime=True,checklist=ASINS)
            if asin1:
                ASINS += asin1
            if asin2:
                ASINS += asin2
    xbmcplugin.setContent(int(sys.argv[1]), 'tvshows')
    xbmcplugin.endOfDirectory(pluginhandle)
    viewenable=common.addon.getSetting("viewenable")
    if viewenable == 'true':
        view=int(common.addon.getSetting("showview"))
        xbmc.executebuiltin("Container.SetViewMode("+str(confluence_views[view])+")")

def LIBRARY_LIST_SEASONS():
    asin = common.args.url
    series = common.args.name
    
    url = 'https://www.amazon.de/gp/video/library/tv?show=all&sort=alpha'
    data = common.getURL(url,useCookie=True)
    scripts = re.compile(r'<script.*?script>',re.DOTALL)
    data = scripts.sub('', data)
    style = re.compile(r'<style.*?style>',re.DOTALL)
    data = style.sub('', data)
    tree = BeautifulSoup(data, convertEntities=BeautifulSoup.HTML_ENTITIES)
    videos = tree.findAll('div',attrs={'class':'lib-item','asin':True})
    totalItems = len(videos)
    for video in videos:
        asin = video['asin']
        appfeed.ADD_SEASON(asin,'library','LIBRARY_EPISODES',isPrime=True,inWatchlist=False,seriesfilter=series)
    xbmcplugin.setContent(int(sys.argv[1]), 'tvshows')
    xbmcplugin.endOfDirectory(pluginhandle)
    viewenable=common.addon.getSetting("viewenable")
    if viewenable == 'true':
        view=int(common.addon.getSetting("seasonview"))
        xbmc.executebuiltin("Container.SetViewMode("+str(confluence_views[view])+")")

def LIBRARY_EPISODES():
    LIST_EPISODES(owned=True)
    
def LIST_EPISODES(owned=False):
    episode_url = common.BASE_URL+'/gp/product/'+common.args.url
    data = common.getURL(episode_url,useCookie=owned)
    scripts = re.compile(r'<script.*?script>',re.DOTALL)
    data = scripts.sub('', data)
    style = re.compile(r'<style.*?style>',re.DOTALL)
    data = style.sub('', data)
    tree = BeautifulSoup(data, convertEntities=BeautifulSoup.HTML_ENTITIES)
    episodes = tree.find('div',attrs={'id':'avod-ep-list-rows'}).findAll('tr',attrs={'asin':True})
    del tree
    for episode in episodes:
        if owned:
            purchasecheckbox = episode.find('input',attrs={'type':'checkbox'})
            if purchasecheckbox:
                continue
        asin = episode['asin']
        appfeed.ADD_EPISODE(asin,isPrime=False)
    xbmcplugin.setContent(int(sys.argv[1]), 'Episodes') 
    xbmcplugin.endOfDirectory(pluginhandle,updateListing=False)
    viewenable=common.addon.getSetting("viewenable")
    if viewenable == 'true':
        view=int(common.addon.getSetting("episodeview"))
        xbmc.executebuiltin("Container.SetViewMode("+str(confluence_views[view])+")")
