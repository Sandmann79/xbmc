#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals
"""AMAZON."""
# main imports
from resources.lib.common import *
from service import updateRunning
var.__init__()


def modes():
    if not sys.argv[2]:
        Log('Version: {}'.format(var.addon.getAddonInfo('version')))
        Log('Unicode filename support: {}'.format(os.path.supports_unicode_filenames))
        cm = {}

        updateall = (getString(30103), 'RunPlugin({}?mode=appfeed&sitemode=updateAll)'.format(sys.argv[0]))
        cm['wl'] = [(getString(30185).format('Watchlist'),
                     'RunPlugin({}?mode=appfeed&sitemode=ExportList&url={})'.format(sys.argv[0], wl)), updateall]
        cm['lib'] = [(getString(30185).format(getString(30060)), 'RunPlugin({}?mode=appfeed&sitemode=ExportList&url={})'.format(sys.argv[0], lib)),
                     (getString(30116), 'RunPlugin({}?mode=appfeed&sitemode=RefreshList&url={})'.format(sys.argv[0], lib)), updateall]

        cm['movie'] = [updateall, (getString(30102), 'RunPlugin({}?mode=movies&sitemode=addMoviesdb&url=f)'.format(sys.argv[0]))]
        cm['tv'] = [updateall, (getString(30105), 'RunPlugin({}?mode=tv&sitemode=addTVdb&url=f)'.format(sys.argv[0]))]
        cm['search'] = [updateall]

        if updateRunning():
            updaterun = json.dumps((getString(30135), 'RunPlugin({}?mode=appfeed&sitemode=updateAll)'.format(sys.argv[0])))
            cm = json.loads(json.dumps(cm).replace(json.dumps(updateall), updaterun))

        if var.multiuser:
            cm['mu'] = [(getString(30174).split('.')[0], 'RunPlugin({}?mode=common&sitemode=LogIn)'.format(sys.argv[0])),
                     (getString(30175).split('.')[0], 'RunPlugin({}?mode=common&sitemode=removeUser)'.format(sys.argv[0])),
                     (getString(30176), 'RunPlugin({}?mode=common&sitemode=renameUser)'.format(sys.argv[0]))]
            addDir(getString(30178) + loadUser()['name'], 'common', 'switchUser', '', cm=cm['mu'])

        addDir('Watchlist', 'appfeed', 'ListMenu', wl, cm=cm['wl'])
        addDir(getString(30104), 'listmovie', 'LIST_MOVIE_ROOT', cm=cm['movie'])
        addDir(getString(30107), 'listtv', 'LIST_TV_ROOT', cm=cm['tv'])
        addDir(getString(30108), 'appfeed', 'SEARCH_DB', cm=cm['search'])
        addDir(getString(30060), 'appfeed', 'ListMenu', lib, cm=cm['lib'])

        if var.addon.getSetting('update_mm') == 'true':
            addDir(cm['search'][0][0], 'appfeed', 'updateAll')

        xbmcplugin.endOfDirectory(var.pluginhandle)
    else:
        exec('import resources.lib.{} as sitemodule'.format(var.args.get('mode')))
        exec('sitemodule.{}()'.format(var.args.get('sitemode')))


modes()
