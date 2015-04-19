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
os = common.os

print '\n\n\n\n\n\n\n====================AMAZON START====================\n\n\n\n\n\n'

def modes():
    if sys.argv[2]=='':
        common.Log('Unicode support: %s' % common.os.path.supports_unicode_filenames)
        cm_watchlist = [(common.getString(30185) % 'Watchlist', 'XBMC.RunPlugin(%s?mode=<appfeed>&sitemode=<ExportList>&url=<%s>)' % (sys.argv[0], common.wl) )]
        cm_library = [(common.getString(30185) % common.getString(30060), 'XBMC.RunPlugin(%s?mode=<appfeed>&sitemode=<ExportList>&url=<%s>)' % (sys.argv[0], common.lib) ),
                      (common.getString(30116), 'XBMC.RunPlugin(%s?mode=<appfeed>&sitemode=<RefreshList>&url=<%s>)' % (sys.argv[0], common.lib) )]
        common.addDir('Watchlist','appfeed','ListMenu', common.wl, cm=cm_watchlist)
        updatemovie = []
        updatemovie.append( (common.getString(30103), 'XBMC.RunPlugin(%s?mode=<appfeed>&sitemode=<updateAll>)' % sys.argv[0] ) )
        updatemovie.append( (common.getString(30102), 'XBMC.RunPlugin(%s?mode=<movies>&sitemode=<addMoviesdb>&url=<f>)' % sys.argv[0] ) )
        common.addDir(common.getString(30104),'listmovie','LIST_MOVIE_ROOT', cm=updatemovie)

        updatetv = []
        updatetv.append( (common.getString(30103), 'XBMC.RunPlugin(%s?mode=<appfeed>&sitemode=<updateAll>)' % sys.argv[0]  ) )
        updatetv.append( (common.getString(30105), 'XBMC.RunPlugin(%s?mode=<tv>&sitemode=<addTVdb>&url=<f>)' % sys.argv[0]  ) )
        common.addDir(common.getString(30107),'listtv','LIST_TV_ROOT', cm=updatetv)

        common.addDir(common.getString(30108),'appfeed','SEARCH_DB')
        common.addDir(common.getString(30060),'appfeed','ListMenu', common.lib, cm=cm_library)

        common.xbmcplugin.endOfDirectory(common.pluginhandle)
    else:
        exec 'import resources.lib.%s as sitemodule' % common.args.mode
        exec 'sitemodule.%s()' % common.args.sitemode
        
if addon.getSetting('save_login') == 'false':
    addon.setSetting('login_name', '')
    addon.setSetting('login_pass', '')
    addon.setSetting('no_cookie', '')
if os.path.isfile(common.COOKIEFILE) and addon.getSetting('no_cookie') == 'true':
    os.remove(common.COOKIEFILE)

modes()
sys.modules.clear()
