#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import os.path
import sys

from .network import *
from .users import *
from .logging import *
from .configs import *
from .common import Globals, Settings
from kodi_six.utils import py2_decode


def EntryPoint():
    """ Main entry point of the Amazon VOD addon """

    # Initialise globals and settings before doing anything else
    g = Globals()
    s = Settings()

    if not xbmcvfs.exists(os.path.join(g.DATA_PATH, 'settings.xml')):
        g.addon.openSettings()

    from socket import setdefaulttimeout
    setdefaulttimeout(30)

    # import requests, warnings
    # warnings.simplefilter('error', requests.packages.urllib3.exceptions.SNIMissingWarning)
    # warnings.simplefilter('error', requests.packages.urllib3.exceptions.InsecurePlatformWarning)

    try:
        from urllib.parse import urlparse, parse_qsl
    except ImportError:
        from urlparse import urlparse, parse_qsl
    args = dict(parse_qsl(urlparse(sys.argv[2]).query))
    path = urlparse(sys.argv[0]).path

    Log('Requested {}'.format(path if 1 < len(path) else args), Log.DEBUG)
    mode = args.get('mode', None)

    if not getConfig('UserAgent'):
        getUA()

    users = loadUsers()
    if users:
        if not loadUser('mid', cachedUsers=users):
            switchUser(0)

        # Set marketplace, base and atv urls, prime video usage and
        # initialise either AmazonTLD or PrimeVideo
        g.InitialiseProvider(loadUser('mid', cachedUsers=users), loadUser('baseurl', cachedUsers=users),
                             loadUser('atvurl', cachedUsers=users), loadUser('pv', cachedUsers=users), loadUser('deviceid', cachedUsers=users))
    elif mode != 'LogIn':
        g.dialog.notification(getString(30200), getString(30216))
        xbmc.executebuiltin('Addon.OpenSettings(%s)' % g.addon.getAddonInfo('id'))
        return

    if path.startswith('/pv/'):
        path = py2_decode(path[4:])
        verb, path = path.split('/', 1)
        g.pv.Route(verb, path)
    elif None is mode:
        Log('Version: %s' % g.__version__)
        Log('Unicode filename support: %s' % os.path.supports_unicode_filenames)
        Log('Locale: %s / Language: %s' % (g.userAcceptLanguages.split(',')[0], s.Language))
        g.pv.BrowseRoot()
    elif mode == 'PlayVideo':
        from .playback import PlayVideo
        PlayVideo(args.get('name', ''), args.get('asin'), args.get('adult', '0'), int(args.get('trailer', '0')), int(args.get('selbitrate', '0')))
    elif mode == 'openSettings':
        aid = args.get('url')
        aid = g.is_addon if aid == 'is' else aid
        import xbmcaddon
        xbmcaddon.Addon(aid).openSettings()
    elif mode == 'exportWatchlist':
        if hasattr(g.pv, 'getListMenu'):
            g.pv.getListMenu('watchlist', export=2)
        else:
            g.pv.Browse('root/Watchlist/watchlist', export=5)
    elif mode in ['LogIn', 'remLoginData', 'removeUser', 'renameUser', 'switchUser']:
        exec('{}()'.format(mode))
    else:
        g.pv.Route(mode, args)
