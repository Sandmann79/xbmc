#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import os.path

from .network import *
from .users import *
from .itemlisting import *
from .logging import *
from .configs import *
from .common import Globals, Settings
from .playback import PlayVideo
from .ages import AgeRestrictions


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

    import urlparse
    args = dict(urlparse.parse_qsl(urlparse.urlparse(sys.argv[2]).query))

    Log(args, Log.DEBUG)
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
                             loadUser('atvurl', cachedUsers=users), loadUser('pv', cachedUsers=users))
    elif mode != 'LogIn':
        g.dialog.notification(getString(30200), getString(30216))
        xbmc.executebuiltin('g.addon.OpenSettings(%s)' % g.addon.getAddonInfo('id'))
        return

    if None is mode:
        Log('Version: %s' % g.__version__)
        Log('Unicode filename support: %s' % os.path.supports_unicode_filenames)
        Log('Locale: %s / Language: %s' % (g.userAcceptLanguages.split(',')[0], s.Language))
        if False is not g.UsePrimeVideo:
            g.pv.BrowseRoot()
        else:
            g.amz.BrowseRoot()
    elif mode == 'listCategories':
        g.amz.listCategories(args.get('url', ''), args.get('opt', ''))
    elif mode == 'listContent':
        g.amz.listContent(args.get('cat'), args.get('url', '').decode('utf-8'), int(args.get('page', '1')), args.get('opt', ''))
    elif mode == 'PlayVideo':
        g.amz.PlayVideo(args.get('name', ''), args.get('asin'), args.get('adult', '0'), int(args.get('trailer', '0')), int(args.get('selbitrate', '0')))
    elif mode == 'getList':
        g.amz.getList(args.get('url', ''), int(args.get('export', '0')), [args.get('opt')])
    elif mode == 'getListMenu':
        g.amz.getListMenu(args.get('url', ''), int(args.get('export', '0')))
    elif mode == 'WatchList':
        g.amz.WatchList(args.get('url', ''), int(args.get('opt', '0')))
    elif mode == 'openSettings':
        aid = args.get('url')
        aid = g.is_addon if aid == 'is' else aid
        import xbmcaddon
        xbmcaddon.Addon(aid).openSettings()
    elif mode == 'ageSettings':
        AgeRestrictions().Settings()
    elif mode == 'PrimeVideo_Browse':
        g.pv.Browse(None if 'path' not in args else args['path'])
    elif mode == 'PrimeVideo_Search':
        g.pv.Search()
    elif None is not re.match(r'^[a-zA-Z]+$', mode):
        cmd = mode + '()'
        # if mode in g.amz:
        #     cmd = 'g.amz.' + cmd
        exec cmd
