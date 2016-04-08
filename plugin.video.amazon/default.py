#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
        AMAZON
"""
#main imports
from __future__ import unicode_literals
import resources.lib.common as common
sys = common.sys
addon = common.addon
getString = common.getString

def modes():
    if sys.argv[2]=='':
        common.Log('Version: %s' % common.__version__)
        common.Log('Unicode support: %s' % common.os.path.supports_unicode_filenames)
        
        cm_watchlist = [(getString(30185) % 'Watchlist', 'XBMC.RunPlugin(%s?mode=<appfeed>&sitemode=<ExportList>&url=<%s>)' % (sys.argv[0], common.wl))]
        cm_library   = [(getString(30185) % getString(30060), 'XBMC.RunPlugin(%s?mode=<appfeed>&sitemode=<ExportList>&url=<%s>)' % (sys.argv[0], common.lib)),
                        (getString(30116), 'XBMC.RunPlugin(%s?mode=<appfeed>&sitemode=<RefreshList>&url=<%s>)' % (sys.argv[0], common.lib))]
        common.addDir('Watchlist','appfeed','ListMenu', common.wl, cm=cm_watchlist)
        
        updatemovie = []
        updatemovie.append((getString(30103), 'XBMC.RunPlugin(%s?mode=<appfeed>&sitemode=<updateAll>)' % sys.argv[0]))
        updatemovie.append((getString(30102), 'XBMC.RunPlugin(%s?mode=<movies>&sitemode=<addMoviesdb>&url=<f>)' % sys.argv[0]))
        common.addDir(getString(30104),'listmovie','LIST_MOVIE_ROOT', cm=updatemovie)

        updatetv = []
        updatetv.append((getString(30103), 'XBMC.RunPlugin(%s?mode=<appfeed>&sitemode=<updateAll>)' % sys.argv[0]))
        updatetv.append((getString(30105), 'XBMC.RunPlugin(%s?mode=<tv>&sitemode=<addTVdb>&url=<f>)' % sys.argv[0]))
        common.addDir(getString(30107),'listtv','LIST_TV_ROOT', cm=updatetv)

        common.addDir(getString(30108),'appfeed','SEARCH_DB')
        common.addDir(getString(30060),'appfeed','ListMenu', common.lib, cm=cm_library)

        common.xbmcplugin.endOfDirectory(common.pluginhandle)
    else:
        exec 'import resources.lib.%s as sitemodule' % common.args.mode
        exec 'sitemodule.%s()' % common.args.sitemode
        
modes()
sys.modules.clear()
