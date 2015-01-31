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
info = xbmcaddon.Addon().getAddonInfo
xbmcaddon.Addon().setSetting('login_name', '')
xbmcaddon.Addon().setSetting('login_pass', '')

#plugin constants
__plugin__ = info('name')
__authors__ = info('author')
__credits__ = ""
__version__ = info('version')

print "\n\n\n\n\n\n\n====================AMAZON START====================\n\n\n\n\n\n"

def modes( ):
    if sys.argv[2]=='':
        common.addDir(common.getString(30110),'appfeed','CATEGORY','rh=n%3A3279204031&bbn=3279204031&sort=date-desc-rank')

        updatemovie = []
        #updatemovie.append( (common.getString(30103), 'XBMC.RunPlugin(%s?mode=<movies>&sitemode=<addMoviesdb>&url=<u>)'  % sys.argv[0] ) )
        updatemovie.append( (common.getString(30102), 'XBMC.RunPlugin(%s?mode=<movies>&sitemode=<addMoviesdb>&url=<f>)'  % sys.argv[0] ) )
        common.addDir(common.getString(30104),'listmovie','LIST_MOVIE_ROOT', cm=updatemovie)

        updatetv = []
        updatetv.append( (common.getString(30106), 'XBMC.RunPlugin(%s?mode=<tv>&sitemode=<addTVdb>&url=<u>)' % sys.argv[0]  ) )
        updatetv.append( (common.getString(30105), 'XBMC.RunPlugin(%s?mode=<tv>&sitemode=<addTVdb>&url=<f>)' % sys.argv[0]  ) )
        common.addDir(common.getString(30107),'listtv','LIST_TV_ROOT', cm=updatetv)

        common.addDir(common.getString(30108),'appfeed','SEARCH_DB','')

        xbmcplugin.endOfDirectory(pluginhandle)
    else:
        exec 'import resources.lib.%s as sitemodule' % common.args.mode
        exec 'sitemodule.%s()' % common.args.sitemode

modes()
sys.modules.clear()
