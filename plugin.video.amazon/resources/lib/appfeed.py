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
import demjson
import listtv
import listmovie
import xbmcaddon

pluginhandle = common.pluginhandle
confluence_views = [500,501,502,503,504,508]

#Modes
#===============================================================================
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
#===============================================================================

MAX = 20
common.gen_id()

deviceID = common.addon.getSetting("GenDeviceID")
#deviceTypeID = 'A2W5AJPLW5Q6YM'  #Android Type
#deviceTypeID = 'A13Q6A55DBZB7M' #WEB Type
#firmware = 'fmw:15-app:1.1.19' #Android
#firmware = 'fmw:10-app:1.1.23'
deviceTypeID = 'A3VN4E5F7BBC7S' #Roku
firmware = 'fmw:045.01E01164A-app:4.7'
#deviceTypeID = 'A63V4FRV3YUP9'
#firmware = '1'
format = 'json'

PARAMETERS = '?firmware='+firmware+'&deviceTypeID='+deviceTypeID+'&deviceID='+deviceID+'&format='+format

def BUILD_BASE_API(MODE,HOST=common.ATV_URL + '/cdp/'):
    return HOST+MODE+PARAMETERS

def getList(ContentType,start=0,isPrime=True,NumberOfResults=MAX,OrderBy='SalesRank',version=2,AsinList=False):
    if isPrime:
        BROWSE_PARAMS = '&OfferGroups=B0043YVHMY'
    BROWSE_PARAMS +='&NumberOfResults='+str(NumberOfResults)
    BROWSE_PARAMS +='&StartIndex='+str(start)
    BROWSE_PARAMS +='&ContentType='+ContentType
    BROWSE_PARAMS +='&OrderBy='+OrderBy
    BROWSE_PARAMS +='&IncludeAll=T'
    if ContentType == 'TVEpisode':
        BROWSE_PARAMS +='&Detailed=T'
        BROWSE_PARAMS +='&AID=T'
        BROWSE_PARAMS +='&tag=1'
        BROWSE_PARAMS +='&SeasonASIN='+AsinList
        BROWSE_PARAMS +='&IncludeBlackList=T'
    BROWSE_PARAMS +='&version='+str(version)    
    #&HighDef=F # T or F ??
    #&playbackInformationRequired=false
    #&OrderBy=SalesRank
    #&SuppressBlackedoutEST=T
    #&HideNum=T
    #&Detailed=T
    #&AID=1
    #&IncludeNonWeb=T
    url = BUILD_BASE_API('catalog/Browse')+BROWSE_PARAMS
    return demjson.decode(common.getATVURL(url))

def ASIN_LOOKUP(ASINLIST):
    results = len(ASINLIST.split(','))-1
    BROWSE_PARAMS = '&asinList='+ASINLIST+'&NumberOfResults='+str(results)+'&IncludeAll=T&playbackInformationRequired=true&version=2'
    url = BUILD_BASE_API('catalog/GetASINDetails')+BROWSE_PARAMS
    return demjson.decode(common.getATVURL(url))

def URL_LOOKUP(url):
    return demjson.decode(common.getATVURL(url+PARAMETERS.replace('?','&')))

def SEARCH_DB(searchString=False,results=MAX,index=0):
    if not searchString:
        keyboard = xbmc.Keyboard('')
        keyboard.doModal()
        q = keyboard.getText()
        if (keyboard.isConfirmed()):
            searchString=urllib.quote_plus(keyboard.getText())
            if searchString <> '':
                common.addText('          ----=== ' + common.getString(30104) + ' ===----')
                if not listmovie.LIST_MOVIES(search=True, alphafilter = '%' + searchString + '%'):
                    common.addText(common.getString(30180))
                common.addText('          ----=== ' + common.getString(30107) + ' ===----')
                if not listtv.LIST_TVSHOWS(search=True, alphafilter = '%' + searchString + '%'):
                    common.addText(common.getString(30180))
                xbmcplugin.setContent(pluginhandle, 'Movies')
                xbmcplugin.endOfDirectory(pluginhandle,updateListing=False)
                viewenable=common.addon.getSetting("viewenable")
                if viewenable == 'true':
                    view=int(common.addon.getSetting("showview"))
                    xbmc.executebuiltin("Container.SetViewMode("+str(confluence_views[view])+")")

def CATEGORY():
    import tv
    page = int(common.args.page)
    asins = common.SCRAP_ASINS(common.args.url, page)
    opt = common.args.opt
    showasins = []
    
    if page > 1:
        common.addDir("////      %s      \\\\\\\\" % common.getString(30112), common.args.mode, common.args.sitemode, url = common.args.url, page = page - 1, options = opt)
        
    for value in asins:
        if listmovie.LIST_MOVIES(search=True, asinfilter = value) == 0:
            seritem, seaitem = tv.lookupTVdb(value, rvalue='seriesasin,seasonasin', tbl='episodes', name='asin')
            if (seaitem) and (opt == ''):
                for seasondata in tv.lookupTVdb(seaitem, tbl='seasons', single=False):
                    listtv.ADD_SEASON_ITEM(seasondata, disptitle=True)
            if (seritem) and (opt == 'shows') and (seritem not in showasins):
                    showasins.append(seritem)
                    listtv.LIST_TVSHOWS(search=True, asinfilter = seritem)

    if len(asins) > 0:
        common.addDir("\\\\\\\\      %s      ////" % common.getString(30111), common.args.mode, common.args.sitemode, url = common.args.url, page = page + 1, options = opt)
    xbmcplugin.setContent(pluginhandle, 'Movies')
    xbmcplugin.endOfDirectory(pluginhandle,updateListing=False)
