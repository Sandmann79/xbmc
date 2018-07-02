#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals
"""AMAZON."""
# main imports
from resources.lib.common import *
init_common()

from service import updateRunning


def modes():
    if not sys.argv[2]:
        Log('Version: %s' % get_addon().getAddonInfo('version'))
        Log('Unicode filename support: %s' % os.path.supports_unicode_filenames)
        cm = {}

        updateall = (getString(30103), 'RunPlugin(%s?mode=appfeed&sitemode=updateAll)' % sys.argv[0])
        cm['wl'] = [(getString(30185) % 'Watchlist',
                     'RunPlugin(%s?mode=appfeed&sitemode=ExportList&url=%s)' % (sys.argv[0], wl)), updateall]
        cm['lib'] = [(getString(30185) % getString(30060), 'RunPlugin(%s?mode=appfeed&sitemode=ExportList&url=%s)' % (sys.argv[0], lib)),
                     (getString(30116), 'RunPlugin(%s?mode=appfeed&sitemode=RefreshList&url=%s)' % (sys.argv[0], lib)), updateall]

        cm['movie'] = [updateall, (getString(30102), 'RunPlugin(%s?mode=movies&sitemode=addMoviesdb&url=f)' % sys.argv[0])]
        cm['tv'] = [updateall, (getString(30105), 'RunPlugin(%s?mode=tv&sitemode=addTVdb&url=f)' % sys.argv[0])]
        cm['search'] = [updateall]

        if updateRunning():
            updaterun = json.dumps((getString(30135), 'RunPlugin(%s?mode=appfeed&sitemode=updateAll)' % sys.argv[0]))
            cm = json.loads(json.dumps(cm).replace(json.dumps(updateall), updaterun))

        if is_multiuser():
            cm['mu'] = [(getString(30174).split('.')[0], 'RunPlugin(%s?mode=common&sitemode=LogIn)' % sys.argv[0]),
                     (getString(30175).split('.')[0], 'RunPlugin(%s?mode=common&sitemode=removeUser)' % sys.argv[0]),
                     (getString(30176), 'RunPlugin(%s?mode=common&sitemode=renameUser)' % sys.argv[0])]
            addDir(getString(30178) + loadUser()['name'], 'common', 'switchUser', '', cm=cm['mu'])

        addDir('Watchlist', 'appfeed', 'ListMenu', wl, cm=cm['wl'])
        addDir(getString(30104), 'listmovie', 'LIST_MOVIE_ROOT', cm=cm['movie'])
        addDir(getString(30107), 'listtv', 'LIST_TV_ROOT', cm=cm['tv'])
        addDir(getString(30108), 'appfeed', 'SEARCH_DB', cm=cm['search'])
        addDir(getString(30060), 'appfeed', 'ListMenu', lib, cm=cm['lib'])

        if get_addon().getSetting('update_mm') == 'true':
            addDir(cm['search'][0][0], 'appfeed', 'updateAll')

        xbmcplugin.endOfDirectory(get_pluginhandle())
    else:
        exec 'import resources.lib.%s as sitemodule' % get_args().get('mode')
        exec 'sitemodule.%s()' % get_args().get('sitemode')


modes()
