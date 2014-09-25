#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
        AMAZON
"""
#main imports
import xbmcplugin
import xbmc
import xbmcgui
import xbmcaddon
import sys
import resources.lib.common as common
import urllib

pluginhandle = common.pluginhandle
xmlstring = xbmcaddon.Addon().getLocalizedString

#plugin constants
__plugin__ = "AMAZON"
__authors__ = "Sandmann79 + BlueCop + Romans I XVI"
__credits__ = ""
__version__ = "1.0.0"


print "\n\n\n\n\n\n\n====================AMAZON START====================\n\n\n\n\n\n"

def modes( ):
    if sys.argv[2]=='':
        #common.addDir(xmlstring(30100),'appfeed','APP_LEVEL2','2,2')
        #common.addDir(xmlstring(30101),'appfeed','APP_LEVEL2','3,2')

        updatemovie = []
        updatemovie.append( (xmlstring(30102),   'XBMC.RunPlugin(plugin://plugin.video.amazon/?mode="xbmclibrary"&sitemode="LIST_MOVIES")' ) )
        updatemovie.append((xmlstring(30103), 'XBMC.RunPlugin(plugin://plugin.video.amazon/?mode="movies"&sitemode="addMoviesdb")' ))
        common.addDir(xmlstring(30104),'listmovie','LIST_MOVIE_ROOT', cm=updatemovie)

        updatetv = []
        updatetv.append( (xmlstring(30105),   'XBMC.RunPlugin(plugin://plugin.video.amazon/?mode="xbmclibrary"&sitemode="LIST_TVSHOWS")' ) )
        updatetv.append( (xmlstring(30106), 'XBMC.RunPlugin(plugin://plugin.video.amazon/?mode="tv"&sitemode="addTVdb")' ) )
        #updatetv.append( ('Scan TVDB(DB)',   'XBMC.RunPlugin(plugin://plugin.video.amazon/?mode="tv"&sitemode="scanTVDBshows")' ) )]
        common.addDir(xmlstring(30107),'listtv','LIST_TV_ROOT', cm=updatetv)

        common.addDir(xmlstring(30108),'appfeed','SEARCH_PRIME','')
        #OLD SEARCH
        #common.addDir('Search Prime','searchprime','SEARCH_PRIME','http://www.amazon.com/s?ie=UTF8&field-is_prime_benefit=1&rh=n%3A2858778011%2Ck%3A')

        #TESTS
        #common.addDir('Categories Testing','appfeed','APP_ROOT')
        xbmcplugin.endOfDirectory(pluginhandle)
    else:
        exec 'import resources.lib.%s as sitemodule' % common.args.mode
        exec 'sitemodule.%s()' % common.args.sitemode

modes ( )
sys.modules.clear()
