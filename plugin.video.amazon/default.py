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
__version__ = "1.0.2"


print "\n\n\n\n\n\n\n====================AMAZON START====================\n\n\n\n\n\n"

def modes( ):
    if sys.argv[2]=='':
        #common.addDir(xmlstring(30100),'appfeed','APP_LEVEL2','2,2')
        #common.addDir(xmlstring(30101),'appfeed','APP_LEVEL2','3,2')

        updatemovie = []
        #updatemovie.append( (xmlstring(30102),   'XBMC.RunPlugin(%s?mode=<xbmclibrary>&sitemode=<LIST_MOVIES>)' % sys.argv[0]  ) )
        updatemovie.append( (xmlstring(30103), 'XBMC.RunPlugin(%s?mode=<movies>&sitemode=<addMoviesdb>)'  % sys.argv[0] ) )
        common.addDir(xmlstring(30104),'listmovie','LIST_MOVIE_ROOT', cm=updatemovie)

        updatetv = []
        #updatetv.append( (xmlstring(30105),   'XBMC.RunPlugin(%s?mode=<xbmclibrary>&sitemode=<LIST_TVSHOWS>)' % sys.argv[0]  ) )
        updatetv.append( (xmlstring(30106), 'XBMC.RunPlugin(%s?mode=<tv>&sitemode=<addTVdb>)' % sys.argv[0]  ) )
        #updatetv.append( ('Scan TVDB(DB)',   'XBMC.RunPlugin(%s?mode="tv"&sitemode="scanTVDBshows")' % sys.argv[0] ) )]
        common.addDir(xmlstring(30107),'listtv','LIST_TV_ROOT', cm=updatetv)

        common.addDir(xmlstring(30108),'appfeed','SEARCH_PRIME','')

        xbmcplugin.endOfDirectory(pluginhandle)
    else:
        exec 'import resources.lib.%s as sitemodule' % common.args.mode
        exec 'sitemodule.%s()' % common.args.sitemode

modes ( )
sys.modules.clear()
