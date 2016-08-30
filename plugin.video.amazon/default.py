#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""AMAZON."""
# main imports
# from __future__ import unicode_literals
from resources.lib.common import *


def modes():
    if not sys.argv[2]:
        Log('Version: %s' % addon.getAddonInfo('version'))
        Log('Unicode support: %s' % os.path.supports_unicode_filenames)

        cm_watchlist = [(getString(30185) % 'Watchlist',
                         'RunPlugin(%s?mode=appfeed&sitemode=ExportList&url=%s)' % (sys.argv[0], wl))]
        cm_library = [(getString(30185) % getString(30060), 'RunPlugin(%s?mode=appfeed&sitemode=ExportList&url=%s)' % (sys.argv[0], lib)),
                      (getString(30116), 'RunPlugin(%s?mode=appfeed&sitemode=RefreshList&url=%s)' % (sys.argv[0], lib))]

        updatemovie = [(getString(30103), 'RunPlugin(%s?mode=appfeed&sitemode=updateAll)' % sys.argv[0]),
                       (getString(30102), 'RunPlugin(%s?mode=movies&sitemode=addMoviesdb&url=f)' % sys.argv[0])]
        updatetv = [(getString(30103), 'RunPlugin(%s?mode=appfeed&sitemode=updateAll)' % sys.argv[0]),
                    (getString(30105), 'RunPlugin(%s?mode=tv&sitemode=addTVdb&url=f)' % sys.argv[0])]

        if updateRunning():
            updatemovie = updatetv = [(getString(30135), 'RunPlugin(%s?mode=appfeed&sitemode=updateAll)' % sys.argv[0])]

        addDir('Watchlist', 'appfeed', 'ListMenu', wl, cm=cm_watchlist)
        addDir(getString(30104), 'listmovie', 'LIST_MOVIE_ROOT', cm=updatemovie)
        addDir(getString(30107), 'listtv', 'LIST_TV_ROOT', cm=updatetv)
        addDir(getString(30108), 'appfeed', 'SEARCH_DB')
        addDir(getString(30060), 'appfeed', 'ListMenu', lib, cm=cm_library)

        xbmcplugin.endOfDirectory(pluginhandle)
    else:
        exec 'import resources.lib.%s as sitemodule' % args.get('mode')
        exec 'sitemodule.%s()' % args.get('sitemode')


modes()
