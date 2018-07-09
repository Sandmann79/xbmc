#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
    Provides: Globals, Settings, sleep, jsonRPC
'''
from __future__ import unicode_literals
from os.path import join as OSPJoin
from locale import getdefaultlocale
from sys import argv
import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs
import json
from Singleton import Singleton
from resources.lib.l10n import *
from resources.lib.configs import *

# Usage:
#   g = Globals()
#   v = _g.attribute
#   v = _g.attribute.AttributeMemberFunction()

class Globals(Singleton):
    """ A singleton instance of globals accessible through dot notation """
    _globals = {
        'platform': 0
    }

    OS_WINDOWS = 1
    OS_LINUX = 2
    OS_OSX = 4
    OS_ANDROID = 8
    OS_LE = 16

    is_addon = 'inputstream.adaptive'
    na = 'not available'
    watchlist = 'watchlist'
    library = 'video-library'
    DBVersion = 1.4
    PayCol = 'FFE95E01'
    tmdb = b'b34490c056f0dd9e3ec9af2167a731f4' # b64decode('YjM0NDkwYzA1NmYwZGQ5ZTNlYzlhZjIxNjdhNzMxZjQ=')
    tvdb = b'1D62F2F90030C444' # b64decode('MUQ2MkYyRjkwMDMwQzQ0NA==')
    pluginid = argv[0]
    pluginhandle = int(argv[1])
    langID = {'movie': 30165, 'series': 30166, 'season': 30167, 'episode': 30173}

    ''' Allow the usage of dot notation for data inside the _globals dictionary, without explicit function call '''
    def __getattr__(self, name): return self._globals[name]
    #def __setattr__(self, name, value): self._globals[name] = value
    #def __delattr__(self, name): self._globals.pop(name, None)
    
    def __init__(self):
        def _genID(renew=False):
            guid = getConfig("GenDeviceID", configPath=self._globals['CONFIG_PATH']) if not renew else False
            if not guid or len(guid) != 56:
                guid = hmac.new(getConfig('UserAgent'), uuid.uuid4().bytes, hashlib.sha224).hexdigest()
                writeConfig("GenDeviceID", guid, self._globals['CONFIG_PATH'])
            return guid

        from PrimeVideo import PrimeVideo
        self._globals['addon'] = xbmcaddon.Addon()
        self._globals['pv'] = PrimeVideo(self, Settings())
        self._globals['dialog'] = xbmcgui.Dialog()
        #self._globals['dialogprogress'] = xbmcgui.DialogProgress()
        self._globals['hasExtRC'] = xbmc.getCondVisibility('System.HasAddon(script.chromium_remotecontrol)')

        self._globals['DATA_PATH'] = xbmc.translatePath(self.addon.getAddonInfo('profile')).decode('utf-8')
        self._globals['CONFIG_PATH'] = OSPJoin(self._globals['DATA_PATH'], 'config')
        self._globals['HOME_PATH'] = xbmc.translatePath('special://home').decode('utf-8')
        self._globals['PLUGIN_PATH'] = self._globals['addon'].getAddonInfo('path').decode('utf-8')

        self._globals['deviceID'] = _genID()

        self._globals['__plugin__'] = self._globals['addon'].getAddonInfo('name')
        self._globals['__authors__'] = self._globals['addon'].getAddonInfo('author')
        self._globals['__credits__'] = ""
        self._globals['__version__'] = self._globals['addon'].getAddonInfo('version')


        # OS Detection
        if xbmc.getCondVisibility('system.platform.windows'):
            self._globals['platform'] |= self.OS_WINDOWS
        if xbmc.getCondVisibility('system.platform.linux'):
            self._globals['platform'] |= self.OS_LINUX
        if xbmc.getCondVisibility('system.platform.osx'):
            self._globals['platform'] |= self.OS_OSX
        if xbmc.getCondVisibility('system.platform.android'):
            self._globals['platform'] |= self.OS_ANDROID
        if (xbmcvfs.exists('/etc/os-release')) and ('libreelec' in xbmcvfs.File('/etc/os-release').read()):
            self._globals['platform'] |= self.OS_LE

        # Save the language code for HTTP requests and set the locale for l10n
        loc = getdefaultlocale()[0]
        userAcceptLanguages = 'en-gb%s, en;q=0.5'
        self._globals['userAcceptLanguages'] = userAcceptLanguages % '' if not loc else '%s, %s' % (loc.lower().replace('_', '-'), userAcceptLanguages % ';q=0.75')

        self._globals['CONTEXTMENU_MULTIUSER'] = [
            (getString(30130, self._globals['addon']).split('…')[0], 'RunPlugin(%s?mode=LogIn)' % self.pluginid),
            (getString(30131, self._globals['addon']).split('…')[0], 'RunPlugin(%s?mode=removeUser)' % self.pluginid),
            (getString(30132, self._globals['addon']), 'RunPlugin(%s?mode=renameUser)' % self.pluginid)
        ]


    def SetMarketplace(self, mid, burl, atv, pv):
        self._globals['MarketID'] = mid
        self._globals['BaseUrl'] = burl
        self._globals['ATVUrl'] = atv
        self._globals['UsePrimeVideo'] = pv


class Settings(Singleton):
    def __getattr__(self, name):
        if not hasattr(self, '_g'):
            self._g = Globals()

        if name in ['MOVIE_PATH', 'TV_SHOWS_PATH']:
            export = self._g.DATA_PATH
            if self._g.addon.getSetting('enablelibraryfolder') == 'true':
                export = xbmc.translatePath(self._g.addon.getSetting('customlibraryfolder')).decode('utf-8')
            return OSPJoin(export, 'Movies' if 'MOVIE_PATH' == name else 'TV')
        elif 'Language' == name:
            # Language settings
            l = jsonRPC('Settings.GetSettingValue', param={'setting': 'locale.audiolanguage'})
            l = xbmc.convertLanguage(l['value'], xbmc.ISO_639_1)
            l = l if l else xbmc.getLanguage(xbmc.ISO_639_1, False)
            return l if l else 'en'
        elif 'playMethod' == name: return int(self._g.addon.getSetting("playmethod"))
        elif 'browser' == name: return int(self._g.addon.getSetting("browser"))
        elif 'MaxResults' == name: return int(self._g.addon.getSetting("items_perpage"))
        elif 'tvdb_art' == name: return self._g.addon.getSetting("tvdb_art")
        elif 'tmdb_art' == name: return self._g.addon.getSetting("tmdb_art")
        elif 'showfanart' == name: return self._g.addon.getSetting("useshowfanart") == 'true'
        elif 'dispShowOnly' == name: return self._g.addon.getSetting("disptvshow") == 'true'
        elif 'payCont' == name: return self._g.addon.getSetting('paycont') == 'true'
        elif 'verbLog' == name: return self._g.addon.getSetting('logging') == 'true'
        elif 'useIntRC' == name: return self._g.addon.getSetting("remotectrl") == 'true'
        elif 'RMC_vol' == name: return self._g.addon.getSetting("remote_vol") == 'true'
        elif 'ms_mov' == name: ms_mov = self._g.addon.getSetting('mediasource_movie'); return ms_mov if ms_mov else 'Amazon Movies'
        elif 'ms_tv' == name: ms_tv = self._g.addon.getSetting('mediasource_tv'); return ms_tv if ms_tv else 'Amazon TV'
        elif 'multiuser' == name: return self._g.addon.getSetting('multiuser') == 'true'
        elif 'DefaultFanart' == name: return OSPJoin(self._g.PLUGIN_PATH, 'fanart.jpg')
        elif 'NextIcon' == name: return OSPJoin(self._g.PLUGIN_PATH, 'resources', 'next.png')
        elif 'HomeIcon' == name: return OSPJoin(self._g.PLUGIN_PATH, 'resources', 'home.png')
        elif 'wl_order' == name: return ['DATE_ADDED_DESC', 'TITLE_DESC', 'TITLE_ASC'][int('0' + self._g.addon.getSetting("wl_order"))]
        elif 'verifySsl' == name: return self._g.addon.getSetting('ssl_verif') == 'false'
        elif 'OfferGroup' == name: return '' if self.payCont else '&OfferGroups=B0043YVHMY'


def jsonRPC(method, props='', param=None):
    rpc = {'jsonrpc': '2.0',
           'method': method,
           'params': {},
           'id': 1}

    if props:
        rpc['params']['properties'] = props.split(',')
    if param:
        rpc['params'].update(param)
        if 'playerid' in param.keys():
            res_pid = xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Player.GetActivePlayers","id": 1}')
            pid = [i['playerid'] for i in json.loads(res_pid)['result'] if i['type'] == 'video']
            pid = pid[0] if pid else 0
            rpc['params']['playerid'] = pid

    res = json.loads(xbmc.executeJSONRPC(json.dumps(rpc)))
    if 'error' in res.keys():
        Log(res['error'])
        return res['error']

    result = res['result']
    return result if type(result) == unicode else res['result'].get(props, res['result'])


def sleep(sec):
    if xbmc.Monitor().waitForAbort(sec):
        return
