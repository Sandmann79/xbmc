#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
        AMAZON
"""
#main imports
import xbmcplugin
import xbmcaddon
import sys
import resources.lib.common as common
import resources.lib.appfeed as appfeed

print "\n\n\n\n\n\n\n====================AMAZON START====================\n\n\n\n\n\n"

def modes():
    if sys.argv[2]=='':
        common.addDir('Watchlist','appfeed','WatchList','')
        updatemovie = []
        updatemovie.append( (common.getString(30103), 'XBMC.RunPlugin(%s?mode=<appfeed>&sitemode=<updateAll>)'  % sys.argv[0] ) )
        updatemovie.append( (common.getString(30102), 'XBMC.RunPlugin(%s?mode=<movies>&sitemode=<addMoviesdb>&url=<f>)'  % sys.argv[0] ) )
        common.addDir(common.getString(30104),'listmovie','LIST_MOVIE_ROOT', cm=updatemovie)

        updatetv = []
        updatetv.append( (common.getString(30103), 'XBMC.RunPlugin(%s?mode=<appfeed>&sitemode=<updateAll>)' % sys.argv[0]  ) )
        updatetv.append( (common.getString(30105), 'XBMC.RunPlugin(%s?mode=<tv>&sitemode=<addTVdb>&url=<f>)' % sys.argv[0]  ) )
        common.addDir(common.getString(30107),'listtv','LIST_TV_ROOT', cm=updatetv)

        common.addDir(common.getString(30108),'appfeed','SEARCH_DB','')

        xbmcplugin.endOfDirectory(common.pluginhandle)
    else:
        exec 'import resources.lib.%s as sitemodule' % common.args.mode
        exec 'sitemodule.%s()' % common.args.sitemode

addon = xbmcaddon.Addon()
if addon.getSetting('save_login') == 'false':
    addon.setSetting('login_name', '')
    addon.setSetting('login_pass', '')
    
modes()
sys.modules.clear()
