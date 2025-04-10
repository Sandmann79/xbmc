#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
    Provides: Globals, Settings, sleep, jsonRPC
'''
from __future__ import unicode_literals

import base64
import json
from locale import getdefaultlocale
from sys import argv
from os.path import join as OSPJoin

from kodi_six import xbmc, xbmcgui, xbmcvfs
from kodi_six.utils import py2_decode
from xbmcaddon import Addon

from .singleton import Singleton
from .l10n import getString
from .configs import getConfig, writeConfig

try:
    from xbmcvfs import translatePath
except ImportError:
    from xbmc import translatePath


# Usage:
#   gs = Globals()/Settings()
#   v = gs.attribute
#   v = gs.attribute.AttributeMemberFunction()


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
    library = 'library'
    DBVersion = 1.4
    PayCol = 'FFE95E01'
    PrimeCol = 'FF00A8E0'
    tmdb = base64.b64decode('YjM0NDkwYzA1NmYwZGQ5ZTNlYzlhZjIxNjdhNzMxZjQ=').decode()
    tvdb = base64.b64decode('ZWRhZTYwZGMtMWI0NC00YmFjLThkYjctNjVjMGFhZjUyNThi').decode()
    langID = {'movie': 30165, 'series': 30166, 'season': 30167, 'episode': 30173, 'tvshow': 30166, 'video': 30173, 'event': 30174, 'live': 30174}
    KodiVersion = int(xbmc.getInfoLabel('System.BuildVersion').split('.')[0])
    dtid_android = 'A43PXU4ZN2AL1'
    dtid_web = 'AOAGZA014O5RE'
    headers_android = {'Accept-Charset': 'utf-8', 'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 11; SHIELD Android TV RQ1A.210105.003)',
                       'X-Requested-With': 'com.amazon.avod.thirdpartyclient', 'x-gasc-enabled': 'true'}

    """ Allow the usage of dot notation for data inside the _globals dictionary, without explicit function call """

    def __init__(self):
        try:
            from urllib.parse import urlparse
        except ImportError:
            from urlparse import urlparse

        # argv[0] can contain the entire path, so we limit ourselves to the base url
        pid = urlparse(argv[0])
        self._globals['pluginid'] = '{}://{}/'.format(pid.scheme, pid.netloc)
        self._globals['pluginhandle'] = int(argv[1]) if (1 < len(argv)) and argv[0] else -1

        self._globals['monitor'] = xbmc.Monitor()
        self._globals['addon'] = Addon()
        self._globals['dialog'] = xbmcgui.Dialog()
        # self._globals['dialogprogress'] = xbmcgui.DialogProgress()
        self._globals['hasExtRC'] = xbmc.getCondVisibility('System.HasAddon(script.chromium_remotecontrol)')

        self._globals['DATA_PATH'] = py2_decode(translatePath(self._globals['addon'].getAddonInfo('profile')))
        self._globals['CONFIG_PATH'] = OSPJoin(self._globals['DATA_PATH'], 'config')
        self._globals['LOG_PATH'] = OSPJoin(self._globals['DATA_PATH'], 'log')
        self._globals['HOME_PATH'] = py2_decode(translatePath('special://home'))
        self._globals['PLUGIN_PATH'] = py2_decode(self._globals['addon'].getAddonInfo('path'))

        self._globals['DefaultFanart'] = OSPJoin(self._globals['PLUGIN_PATH'], 'fanart.png')
        self._globals['ThumbIcon'] = OSPJoin(self._globals['PLUGIN_PATH'], 'icon.png')
        self._globals['NextIcon'] = OSPJoin(self._globals['PLUGIN_PATH'], 'resources', 'art', 'next.png')
        self._globals['HomeIcon'] = OSPJoin(self._globals['PLUGIN_PATH'], 'resources', 'art', 'home.png')
        self._globals['PrimeVideoEntitlement'] = OSPJoin(self._globals['PLUGIN_PATH'], 'resources', 'art', 'prime.png')

        # With main PATHs configured, we initialise the get/write path attributes
        # and generate/retrieve the device ID
        getConfig.configPath = self._globals['CONFIG_PATH']
        writeConfig.configPath = self._globals['CONFIG_PATH']

        if not xbmcvfs.exists(self._globals['LOG_PATH']):
            xbmcvfs.mkdirs(self._globals['LOG_PATH'])

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
        userAcceptLanguages = 'en-gb{}, en;q=0.5'
        self._globals['userAcceptLanguages'] = userAcceptLanguages.format('') if not loc else '{}, {}'.format(loc.lower().replace('_', '-'),
                                                                                                              userAcceptLanguages.format(';q=0.75'))
        self._globals['mfa_keywords'] = ['auth-mfa-form', 'ap_dcq_form', 'ap_captcha_img_label', 'claimspicker', 'fwcim-form', 'auth-captcha-image-container',
                                         'validateCaptcha', 'pollingForm', 'auth-select-device-form', 'verifyOtp']

        self._globals['CONTEXTMENU_MULTIUSER'] = [
            (getString(30130, self._globals['addon']).split('…')[0], 'RunPlugin({}?mode=LogIn)'.format(self.pluginid)),
            (getString(30131, self._globals['addon']).split('…')[0], 'RunPlugin({}?mode=removeUser)'.format(self.pluginid)),
            (getString(30132, self._globals['addon']), 'RunPlugin({}?mode=renameUser)'.format(self.pluginid))
        ]

    def __getattr__(self, name):
        return self._globals[name]

    def InitialiseProvider(self, mid, burl, atv, pv, did):
        self._globals['MarketID'] = mid
        self._globals['BaseUrl'] = burl
        self._globals['ATVUrl'] = atv
        self._globals['UsePrimeVideo'] = pv
        self._globals['deviceID'] = did
        ds = int('0' + self._globals['addon'].getSetting('data_source'))

        if ds == 0:
            from .web_api import PrimeVideo
        elif ds == 1:
            from .android_api import PrimeVideo
        elif ds == 2:
            from .atv_api import PrimeVideo
        if 'pv' not in self._globals:
            self._globals['pv'] = PrimeVideo(self, Settings())


class Settings(Singleton):
    """ A singleton instance of various settings that could be needed to reload during runtime """
    _g = Globals()
    _gs = _g.addon.getSetting
    _integer = 'int("0" + self._gs("%s"))'
    _bool_true = 'self._gs("%s") == "true"'
    _bool_false = 'self._gs("%s") == "false"'
    _ret_types = {_integer: ['playmethod', 'browser', 'items_perpage', 'tvdb_art', 'tmdb_art', 'region', 'skip_scene', 'data_source', 'send_vp'],
                  _bool_true:
                      ['useshowfanart', 'disptvshow', 'paycont', 'logging', 'json_dump', 'json_dump_collisions', 'sub_stretch', 'log_http', 'remotectrl',
                       'remote_vol', 'multiuser', 'wl_export', 'audio_description', 'pv_episode_thumbnails', 'tld_episode_thumbnails', 'use_h265', 'enable_atmos',
                       'profiles', 'show_pass', 'enable_uhd', 'show_recents', 'preload_seasons', 'preload_all_seasons', 'wvl1_device', 'search_history',
                       'hide_trailers', 'export_not_aired'],
                  _bool_false: ['json_dump_raw', 'ssl_verif', 'proxy_mpdalter']}

    def __getattr__(self, name):
        if name in ['MOVIE_PATH', 'TV_SHOWS_PATH']:
            export = self._g.DATA_PATH
            if self._gs('enablelibraryfolder') == 'true':
                export = py2_decode(translatePath(self._gs('customlibraryfolder')))
            export = OSPJoin(export, 'Movies' if 'MOVIE_PATH' == name else 'TV')
            return export + '\\' if '\\' in export else export + '/'
        elif 'Language' == name:
            # Language settings
            l = jsonRPC('Settings.GetSettingValue', param={'setting': 'locale.audiolanguage'})
            l = xbmc.convertLanguage(l['value'], xbmc.ISO_639_1)
            l = l if l else xbmc.getLanguage(xbmc.ISO_639_1, False)
            return l if l else 'en'
        elif 'ms_mov' == name:
            ms_mov = self._gs('mediasource_movie')
            return ms_mov if ms_mov else 'Amazon Movies'
        elif 'ms_tv' == name:
            ms_tv = self._gs('mediasource_tv')
            return ms_tv if ms_tv else 'Amazon TV'
        elif 'wl_order' == name:
            return ['DATE_ADDED_DESC', 'TITLE_DESC', 'TITLE_ASC'][int('0' + self._gs('wl_order'))]
        elif 'OfferGroup' == name:
            return '' if self.paycont else '&OfferGroups=B0043YVHMY'
        elif 'subtitleStretchFactor' == name:
            return [24 / 23.976, 23.976 / 24, 25 / 23.976, 23.976 / 25, 25.0 / 24.0, 24.0 / 25.0][int(self._gs('sub_stretch_factor'))]
        elif 'pagination' == name:
            return {'all': self._gs('paginate_everything') == 'true',
                    'watchlist': self._gs('paginate_watchlist') == 'true',
                    'collections': self._gs('paginate_collections') == 'true',
                    'search': self._gs('paginate_search') == 'true'}
        elif 'catalogCacheExpiry' == name:
            return [3600, 21600, 43200, 86400, 259200, 604800, 1296000, 2592000][int(self._gs('catalog_cache_expiry'))]
        elif 'proxyaddress' == name:
            return getConfig('proxyaddress')
        elif 'wvl1_device' == name and getConfig('autoWV', 0) == 0:
            return detectWidevine()

        value = None
        for cmd in self._ret_types:
            if self._ret_types[cmd].count(name) > 0:
                value = eval(cmd % name)

        value = self._gs(name) if value is None else value
        return value

    def __setattr__(self, name, value):
        if not name.startswith('_'):
            self._g.addon.setSetting(name, value)


def jsonRPC(method, props='', param=None):
    """ Wrapper for Kodi's executeJSONRPC API """
    from .logging import Log
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
    return res['result'].get(props, res['result']) if type(result) == dict else result


def sleep(sec):
    from .logging import Log
    if Globals().monitor.waitForAbort(sec):
        import sys
        Log('Abort requested – exiting addon')
        sys.exit()


def key_exists(dictionary, *keys):
    """ Check if a nested list of keys exists """
    _p = dictionary
    for key in keys:
        try:
            _p = _p[key]
        except:
            return False
    return True


def return_item(dictionary, *keys):
    """ Returns an item nested in the dictionary, or the dictionary itself """
    _p = dictionary
    for key in keys:
        try:
            _p = _p[key]
        except:
            return dictionary
    return _p


def return_value(dictionary, *keys):
    """ Returns an value nested in the dictionary, or the dictionary itself """
    _p = dictionary
    for key in keys:
        try:
            _p = _p[key]
        except:
            return _p
    return _p


def findKey(key, obj):
    if not isinstance(obj, dict):
        return {}
    if key in obj.keys():
        return obj[key]
    for v in obj.values():
        if isinstance(v, dict):
            res = findKey(key, v)
            if res: return res
        elif isinstance(v, list):
            for d in v:
                if isinstance(d, dict):
                    res = findKey(key, d)
                    if res:
                        return res
    return {}


def get_key(def_value, obj, *keys):
    """ Returns a value nested in the dictionary, or the def_value if the key is None or not existent """
    for key in keys:
        if (key not in obj) or (key in obj and obj[key] is None):
            return def_value
        obj = obj[key]
    return obj


def decode_token(token):
    if token.startswith('v0_'):
        token = token[3:]
    if token.startswith('ey'):
        return base64.b64decode(token)

    padding_needed = (4 - len(token) % 4) % 4
    token_padded = token + ("=" * padding_needed)

    try:
        decoded_bytes = base64.urlsafe_b64decode(token_padded)
        decoded_text = decoded_bytes.decode('utf-8', errors='replace')
        readable = ''.join(c if 32 <= ord(c) <= 126 else '.' for c in decoded_text)
        return readable
    except:
        return ''


def get_user_lang(cj=None, iso6392=False):
    from .users import loadUser
    from .l10n import datetimeParser as dtp
    _s = Settings()
    if cj is None:
        cj = MechanizeLogin()
    l = loadUser('lang') if _s.data_source == 1 else cj.get('lc-main-av')
    return dtp.get(l, dtp['en_US'])['iso6392'] if iso6392 else l


def MechanizeLogin(preferToken=False):
    _s = Settings()
    if preferToken:
        from .login import getToken
        token = getToken()
        if token:
            return token

    # if Token not requested or not avaiable use cookie
    from .users import loadUser
    import requests
    cj = requests.cookies.RequestsCookieJar()
    cookie = loadUser('cookie')
    if cookie and (_s.data_source == 0 or not preferToken):
        try:
            cj.update(cookie)
            return cj
        except:
            pass

    if _s.data_source == 1 and preferToken and cookie:
        _g = Globals()
        _g.dialog.ok(_g.__plugin__, getString(30272))

    from .login import LogIn
    res = LogIn(preferToken)
    if res is False:
        exit()
    return res


def parseHTML(br):
    from .logging import Log
    Log(br.get_url(), Log.DEBUG)
    soup = br.get_current_page()
    response = soup.__unicode__()
    return response, soup


def detectWidevine():
    try:
        import xbmcdrm
        from .logging import Log
        crypto_session = xbmcdrm.CryptoSession('edef8ba9-79d6-4ace-a3c8-27dcd51d21ed', 'AES/CBC/NoPadding', 'HmacSHA256')
        sec_level = crypto_session.GetPropertyString('securityLevel')
        Log('Detected Widevine security level: {}'.format(sec_level, Log.DEBUG))
        res = sec_level.upper() == 'L1'
    except:
        res = False
    Settings().wvl1_device = str(res).lower()
    writeConfig('autoWV', '1')
    return res
