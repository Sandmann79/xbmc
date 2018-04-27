#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from base64 import b64encode, b64decode
from collections import OrderedDict
from BeautifulSoup import BeautifulSoup, BeautifulStoneSoup, Tag
from datetime import date
from platform import node
from random import randint
from sqlite3 import dbapi2 as sqlite
import hashlib
import hmac
import json
import locale
import os
import pickle
import re
import requests
import shlex
import socket
import subprocess
import time
import threading
import urllib
import urlparse
import uuid
import warnings

from pyDes import *
import mechanize

from inputstreamhelper import Helper
import pyxbmct
import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs

addon = xbmcaddon.Addon()
Dialog = xbmcgui.Dialog()
pDialog = xbmcgui.DialogProgress()
pluginhandle = int(sys.argv[1])
__plugin__ = addon.getAddonInfo('name')
__authors__ = addon.getAddonInfo('author')
__credits__ = ""
__version__ = addon.getAddonInfo('version')
platform = 0
osWindows = 1
osLinux = 2
osOSX = 3
osAndroid = 4
if xbmc.getCondVisibility('system.platform.windows'):
    platform = osWindows
if xbmc.getCondVisibility('system.platform.linux'):
    platform = osLinux
if xbmc.getCondVisibility('system.platform.osx'):
    platform = osOSX
if xbmc.getCondVisibility('system.platform.android'):
    platform = osAndroid
hasExtRC = xbmc.getCondVisibility('System.HasAddon(script.chromium_remotecontrol)')
DataPath = xbmc.translatePath(addon.getAddonInfo('profile')).decode('utf-8')
HomePath = xbmc.translatePath('special://home').decode('utf-8')
PluginPath = addon.getAddonInfo('path').decode('utf-8')
ConfigPath = os.path.join(DataPath, 'config')
if not xbmcvfs.exists(os.path.join(DataPath, 'settings.xml')):
    addon.openSettings()
playMethod = int(addon.getSetting("playmethod"))
browser = int(addon.getSetting("browser"))
MaxResults = int(addon.getSetting("items_perpage"))
tvdb_art = addon.getSetting("tvdb_art")
tmdb_art = addon.getSetting("tmdb_art")
showfanart = addon.getSetting("useshowfanart") == 'true'
dispShowOnly = addon.getSetting("disptvshow") == 'true'
payCont = addon.getSetting('paycont') == 'true'
verbLog = addon.getSetting('logging') == 'true'
useIntRC = addon.getSetting("remotectrl") == 'true'
RMC_vol = addon.getSetting("remote_vol") == 'true'
ms_mov = addon.getSetting('mediasource_movie')
ms_tv = addon.getSetting('mediasource_tv')
multiuser = addon.getSetting('multiuser') == 'true'
tmdb = b64decode('YjM0NDkwYzA1NmYwZGQ5ZTNlYzlhZjIxNjdhNzMxZjQ=')
tvdb = b64decode('MUQ2MkYyRjkwMDMwQzQ0NA==')
DefaultFanart = os.path.join(PluginPath, 'fanart.jpg')
NextIcon = os.path.join(PluginPath, 'resources', 'next.png')
HomeIcon = os.path.join(PluginPath, 'resources', 'home.png')
wl_order = ['DATE_ADDED_DESC', 'TITLE_DESC', 'TITLE_ASC'][int('0' + addon.getSetting("wl_order"))]
verifySsl = addon.getSetting('ssl_verif') == 'false'
sessions = {}  # Keep-Alive sessions
is_addon = 'inputstream.adaptive'
na = 'not available'
watchlist = 'watchlist'
library = 'video-library'
DBVersion = 1.4
PayCol = 'FFE95E01'
AgesCfg = {'A1PA6795UKMFR9': ['FSK', ('FSK 0', 'FSK 0'), ('FSK 6', 'FSK 6'), ('FSK 12', 'FSK 12'), ('FSK 16', 'FSK 16'), ('FSK 18', 'FSK 18')],
           'A1F83G8C2ARO7P': ['', ('Universal', 'U'), ('Parental Guidance', 'PG'), ('12 and older', '12,12A'), ('15 and older', '15'), ('18 and older', '18')],
           'ATVPDKIKX0DER': ['', ('General Audiences', 'G,TV-G,TV-Y'), ('Family', 'PG,NR,TV-Y7,TV-Y7-FV,TV-PG'), ('Teen', 'PG-13,TV-14'),
                              ('Mature', 'R,NC-17,TV-MA,Unrated,Not rated')],
           'A1VC38T7YXB528': ['', ('全ての観客', 'g'), ('親の指導・助言', 'pg12'), ('R-15指定', 'r15+'), ('成人映画', 'r18+,nr')]}

dateParserData = {
    'de_DE': {'deconstruct': r'^([0-9]+)\.\s+([^\s]+)\s+([0-9]+)', 'reassemble': '{2}-{1:0>2}-{0:0>2}', 'month': 1,
              'months': {'Januar': 1, 'Februar': 2, 'März': 3, 'April': 4, 'Mai': 5, 'Juni': 6, 'Juli': 7, 'August': 8, 'September': 9, 'Oktober': 10,
                         'November': 11, 'Dezember': 12}},
    'en_US': {'deconstruct': r'^([^\s]+)\s+([0-9]+),\s+([0-9]+)', 'reassemble': '{2}-{0:0>2}-{1:0>2}', 'month': 0,
              'months': {'January': 1, 'February': 2, 'March': 3, 'April': 4, 'May': 5, 'June': 6, 'July': 7, 'August': 8, 'September': 9, 'October': 10,
                         'November': 11, 'December': 12}},
    'es_ES': {'deconstruct': r'^([0-9]+)\s+de\s+([^\s]+),\s+de\s+([0-9]+)', 'reassemble': '{2}-{1:0>2}-{0:0>2}', 'month': 1,
              'months': {'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6, 'julio': 7, 'agosto': 8, 'septiembre': 9, 'octubre': 10,
                         'noviembre': 11, 'diciembre': 12}},
    'fr_FR': {'deconstruct': r'^([0-9]+)\s+([^\s]+)\s+([0-9]+)', 'reassemble': '{2}-{1:0>2}-{0:0>2}', 'month': 1,
              'months': {'janvier': 1, 'février': 2, 'mars': 3, 'avril': 4, 'mai': 5, 'juin': 6, 'juillet': 7, 'aout': 8, 'septembre': 9, 'octobre': 10,
                         'novembre': 11, 'décembre': 12}},
    'it_IT': {'deconstruct': r'^([0-9]+)\s+([^\s]+)\s+([0-9]+)', 'reassemble': '{2}-{1:0>2}-{0:0>2}', 'month': 1,
              'months': {'gennaio': 1, 'febbraio': 2, 'marzo': 3, 'aprile': 4, 'maggio': 5, 'giugno': 6, 'luglio': 7, 'agosto': 8, 'settembre': 9,
                         'ottobre': 10, 'novembre': 11, 'dicembre': 12}},
    'pt_BR': {'deconstruct': r'^([0-9]+)\s+de\s+([^\s]+),\s+de\s+([0-9]+)', 'reassemble': '{2}-{1:0>2}-{0:0>2}', 'month': 1,
              'months': {'janeiro': 1, 'fevereiro': 2, 'março': 3, 'abril': 4, 'maio': 5, 'junho': 6, 'julho': 7, 'agosto': 8, 'setembro': 9, 'outubro': 10,
                         'novembro': 11, 'dezembro': 12}},
}

# Save the language code for HTTP requests and set the locale for l10n
loc = locale.getdefaultlocale()[0]
userAcceptLanguages = 'en-gb%s, en;q=0.5'
userAcceptLanguages = '%s, %s' % (loc.lower().replace('_', '-'), userAcceptLanguages % ';q=0.75') if loc else userAcceptLanguages % ''

# ids: A28RQHJKHM2A2W - ps3 / AFOQV1TK6EU6O - ps4 / A1IJNVP3L4AY8B - samsung / A2E0SNTXJVT7WK - firetv1 /
#      ADVBD696BHNV5 - montoya / A3VN4E5F7BBC7S - roku / A1MPSLFC7L5AFK - kindle / A2M4YX06LWP8WI - firetv2 /
# PrimeVideo web device IDs:
#      A63V4FRV3YUP9 / SILVERLIGHT_PC, A2G17C9GWLWFKO / SILVERLIGHT_MAC, AOAGZA014O5RE / HTML5
# TypeIDs = {'GetCategoryList': 'firmware=fmw:15-app:1.1.23&deviceTypeID=A1MPSLFC7L5AFK',
#            'GetSimilarities': 'firmware=fmw:15-app:1.1.23&deviceTypeID=A1MPSLFC7L5AFK',
#                        'All': 'firmware=fmw:22-app:3.0.211.123001&deviceTypeID=A43PXU4ZN2AL1'}
#                        'All': 'firmware=fmw:045.01E01164A-app:4.7&deviceTypeID=A3VN4E5F7BBC7S'}
# TypeIDs = {'All': 'firmware=fmw:17-app:2.0.45.1210&deviceTypeID=A2RJLFEH0UEKI9'}

TypeIDs = {'All': 'firmware=fmw:17-app:2.0.45.1210&deviceTypeID=A2M4YX06LWP8WI',
           'GetCategoryList_ftv': 'firmware=fmw:17-app:2.0.45.1210&deviceTypeID=ADVBD696BHNV5'}

langID = {'movie': 30165, 'series': 30166, 'season': 30167, 'episode': 30173}
OfferGroup = '' if payCont else '&OfferGroups=B0043YVHMY'
socket.setdefaulttimeout(30)

EXPORT_PATH = DataPath
if addon.getSetting('enablelibraryfolder') == 'true':
    EXPORT_PATH = xbmc.translatePath(addon.getSetting('customlibraryfolder')).decode('utf-8')
MOVIE_PATH = os.path.join(EXPORT_PATH, 'Movies')
TV_SHOWS_PATH = os.path.join(EXPORT_PATH, 'TV')
ms_mov = ms_mov if ms_mov else 'Amazon Movies'
ms_tv = ms_tv if ms_tv else 'Amazon TV'

warnings.simplefilter('error', requests.packages.urllib3.exceptions.SNIMissingWarning)
warnings.simplefilter('error', requests.packages.urllib3.exceptions.InsecurePlatformWarning)


def setContentAndView(content, updateListing=False):
    if content == 'movie':
        ctype = 'movies'
        cview = 'movieview'
    elif content == 'series':
        ctype = 'tvshows'
        cview = 'showview'
    elif content == 'season':
        ctype = 'seasons'
        cview = 'seasonview'
    elif content == 'episode':
        ctype = 'episodes'
        cview = 'episodeview'
    elif content == 'videos':
        ctype = 'videos'
        cview = None
    elif content == 'files':
        ctype = 'files'
        cview = None
    else:
        ctype = None
        cview = None

    if None is not ctype:
        xbmcplugin.setContent(pluginhandle, ctype)
    if (None is not cview) and ('true' == addon.getSetting("viewenable")):
        views = [50, 51, 52, 53, 54, 55, 500, 501, 502, -1]
        viewid = views[int(addon.getSetting(cview))]
        if viewid == -1:
            viewid = int(addon.getSetting(cview.replace('view', 'id')))
        xbmc.executebuiltin('Container.SetViewMode(%s)' % viewid)
    xbmcplugin.endOfDirectory(pluginhandle, updateListing=updateListing)


def getURL(url, useCookie=False, silent=False, headers=None, rjson=True, attempt=1, check=False):
    # Try to extract the host from the URL
    host = re.search('://([^/]+)/', url)

    # Create sessions for keep-alives and connection pooling
    if None is not host:
        host = host.group(1)
        if host in sessions:
            session = sessions[host]
        else:
            session = requests.Session()
            sessions[host] = session
    else:
        session = requests.Session()

    cj = requests.cookies.RequestsCookieJar()
    retval = [] if rjson else ''
    if useCookie:
        cj = MechanizeLogin() if isinstance(useCookie, bool) else useCookie
        if isinstance(cj, bool):
            return retval
    if (not silent) or verbLog:
        dispurl = url
        dispurl = re.sub('(?i)%s|%s|&token=\w+|&customerId=\w+' % (tvdb, tmdb), '', url).strip()
        Log('%sURL: %s' % ('check' if check else 'get', dispurl))

    headers = {} if not headers else headers
    if 'User-Agent' not in headers:
        headers['User-Agent'] = getConfig('UserAgent')
    if 'Host' not in headers:
        headers['Host'] = host
    if 'Accept-Language' not in headers:
        headers['Accept-Language'] = userAcceptLanguages

    try:
        r = session.get(url, headers=headers, cookies=cj, verify=verifySsl)
        response = r.text if not check else 'OK'
        if r.status_code >= 400:
            Log('Error %s' % r.status_code)
            raise requests.exceptions.HTTPError('429')
    except (requests.exceptions.Timeout,
            requests.exceptions.ConnectionError,
            requests.exceptions.SSLError,
            requests.exceptions.HTTPError,
            requests.packages.urllib3.exceptions.SNIMissingWarning,
            requests.packages.urllib3.exceptions.InsecurePlatformWarning), e:
        eType = e.__class__.__name__
        Log('Error reason: %s (%s)' % (e, eType), xbmc.LOGERROR)
        if 'SNIMissingWarning' in eType:
            Log('Using a Python/OpenSSL version which doesn\'t support SNI for TLS connections.', xbmc.LOGERROR)
            Dialog.ok('No SNI for TLS', 'Your current Python/OpenSSL environment does not support SNI over TLS connections.',
                      'You can find a Linux guide on how to update Python and its modules for Kodi here: https://goo.gl/CKtygz',
                      'Additionally, follow this guide to update the required modules: https://goo.gl/ksbbU2')
            exit()
        if 'InsecurePlatformWarning' in eType:
            Log('Using an outdated SSL module.', xbmc.LOGERROR)
            Dialog.ok('SSL module outdated', 'The SSL module for Python is outdated.',
                      'You can find a Linux guide on how to update Python and its modules for Kodi here: https://goo.gl/CKtygz',
                      'Additionally, follow this guide to update the required modules: https://goo.gl/ksbbU2')
            exit()
        if (('429' in e) or ('Timeout' in eType)) and (3 > attempt):
            attempt += 1 if not check else 10
            logout = 'Attempt #%s' % attempt
            if '429' in e:
                logout += '. Too many requests - Pause 10 sec'
                sleep(10)
            Log(logout)
            return getURL(url, useCookie, silent, headers, rjson, attempt)
        return retval
    return json.loads(response) if rjson else response


def getATVData(pg_mode, query='', version=2, useCookie=False, site_id=None):
    if '?' in query:
        query = query.split('?')[1]
    if query:
        query = '&IncludeAll=T&AID=1&' + query.replace('HideNum=T', 'HideNum=F')
    deviceTypeID = TypeIDs[pg_mode] if pg_mode in TypeIDs else TypeIDs['All']
    pg_mode = pg_mode.split('_')[0]
    if '/' not in pg_mode:
        pg_mode = 'catalog/' + pg_mode
    parameter = '%s&deviceID=%s&format=json&version=%s&formatVersion=3&marketplaceId=%s' % (
        deviceTypeID, deviceID, version, MarketID)
    if site_id:
        parameter += '&id=' + site_id
    jsondata = getURL('%s/cdp/%s?%s%s' % (ATVUrl, pg_mode, parameter, query), useCookie=useCookie)
    if not jsondata:
        return False

    if jsondata['message']['statusCode'] != "SUCCESS":
        Log('Error Code: ' + jsondata['message']['body']['code'], xbmc.LOGERROR)
        return None
    return jsondata['message']['body']


def addDir(name, mode='', url='', infoLabels=None, opt='', catalog='Browse', cm=None, page=1, export=False, thumb=DefaultFanart):
    u = {'mode': mode, 'url': url.encode('utf-8'), 'page': page, 'opt': opt, 'cat': catalog}
    url = '%s?%s' % (sys.argv[0], urllib.urlencode(u))

    if not mode:
        url = sys.argv[0]

    if export:
        Export(infoLabels, url)
        return
    if infoLabels:
        thumb = infoLabels['Thumb']
        fanart = infoLabels['Fanart']
    else:
        fanart = DefaultFanart

    item = xbmcgui.ListItem(name, iconImage=thumb, thumbnailImage=thumb)
    item.setProperty('IsPlayable', 'false')
    item.setArt({'fanart': fanart, 'poster': thumb})

    if infoLabels:
        item.setInfo(type='Video', infoLabels=getInfolabels(infoLabels))
        if 'TotalSeasons' in infoLabels:
            item.setProperty('TotalSeasons', str(infoLabels['TotalSeasons']))
        if 'Poster' in infoLabels.keys():
            item.setArt({'tvshow.poster': infoLabels['Poster']})

    if cm:
        item.addContextMenuItems(cm)
    xbmcplugin.addDirectoryItem(pluginhandle, url, item, isFolder=True)


def addVideo(name, asin, infoLabels, cm=[], export=False):
    u = {'asin': asin, 'mode': 'PlayVideo', 'name': name.encode('utf-8'), 'adult': infoLabels['isAdult']}
    url = '%s?%s' % (sys.argv[0], urllib.urlencode(u))

    item = xbmcgui.ListItem(name, thumbnailImage=infoLabels['Thumb'])
    item.setArt({'fanart': infoLabels['Fanart'], 'poster': infoLabels['Thumb']})
    item.addStreamInfo('audio', {'codec': 'ac3', 'channels': int(infoLabels['AudioChannels'])})
    item.setProperty('IsPlayable', str(playMethod == 3).lower())

    if 'Poster' in infoLabels.keys():
        item.setArt({'tvshow.poster': infoLabels['Poster']})

    if infoLabels['isHD']:
        item.addStreamInfo('video', {'width': 1920, 'height': 1080})
    else:
        item.addStreamInfo('video', {'width': 720, 'height': 480})

    if infoLabels['TrailerAvailable']:
        infoLabels['Trailer'] = url + '&trailer=1&selbitrate=0'

    url += '&trailer=2' if "live" in infoLabels['contentType'] else '&trailer=0'

    if export:
        url += '&selbitrate=0'
        Export(infoLabels, url)
    else:
        cm.insert(0, (getString(30101), 'Action(ToggleWatched)'))
        cm.insert(1, (getString(30102), 'RunPlugin(%s)' % (url + '&selbitrate=1')))
        url += '&selbitrate=0'
        item.setInfo(type='Video', infoLabels=getInfolabels(infoLabels))
        item.addContextMenuItems(cm)
        xbmcplugin.addDirectoryItem(pluginhandle, url, item, isFolder=False)


def ContextMenu_MultiUser():
    return [(getString(30130).split('…')[0], 'RunPlugin(%s?mode=LogIn)' % sys.argv[0]),
            (getString(30131).split('…')[0], 'RunPlugin(%s?mode=removeUser)' % sys.argv[0]),
            (getString(30132), 'RunPlugin(%s?mode=renameUser)' % sys.argv[0])]


def MainMenu():
    Log('Version: %s' % __version__)
    Log('Unicode filename support: %s' % os.path.supports_unicode_filenames)
    Log('Locale: %s / Language: %s' % (userAcceptLanguages.split(',')[0], Language))
    if False is not UsePrimeVideo:
        if 0 == len(pvCatalog):
            ''' Build the root catalog '''
            if not PrimeVideo_BuildRoot():
                return
        PrimeVideo_Browse('root')
    else:
        loadCategories()

        cm_wl = [(getString(30185) % 'Watchlist', 'RunPlugin(%s?mode=getListMenu&url=%s&export=1)' % (sys.argv[0], watchlist))]
        cm_lb = [(getString(30185) % getString(30100),
                  'RunPlugin(%s?mode=getListMenu&url=%s&export=1)' % (sys.argv[0], library))]

        if multiuser:
            addDir(getString(30134).format(loadUser('name')), 'switchUser', '', cm=ContextMenu_MultiUser())
        addDir('Watchlist', 'getListMenu', watchlist, cm=cm_wl)
        getRootNode()
        addDir(getString(30108), 'Search', '')
        addDir(getString(30100), 'getListMenu', library, cm=cm_lb)
        xbmcplugin.endOfDirectory(pluginhandle, updateListing=False)


def BeautifyText(title):
    """ Correct stylistic errors in Amazon's titles """
    for t in [(r'\s+-\s*', ' – '), # Convert dash from small to medium where needed
              (r'\s*-\s+', ' – '), # Convert dash from small to medium where needed
              (r'^\s+', ''), # Remove leading spaces
              (r'\s+$', ''), # Remove trailing spaces
              (r' {2,}', ' '), # Remove double spacing
              (r'\.\.\.', '…')]: # Replace triple dots with ellipsis
        title = re.sub(t[0], t[1], title)
    return title


def PrimeVideo_BuildRoot():
    """ Parse the top menu on primevideo.com and build the root catalog """
    pvCatalog['root'] = OrderedDict()
    home = getURL(BaseUrl, silent=True, useCookie=True, rjson=False)
    if None is home:
        Dialog.notification('Connection error', 'Unable to fetch the primevideo.com homepage', xbmcgui.NOTIFICATION_ERROR)
        Log('Unable to fetch the primevideo.com homepage', xbmc.LOGERROR)
        return False
    watchlist = re.search(r'<a[^>]* href="(/watchlist/)[^"]*"[^>]*>(.*?)</a>', home)
    if None is not watchlist:
        pvCatalog['root']['Watchlist'] = { 'title': watchlist.group(2), 'lazyLoadURL': BaseUrl + watchlist.group(1) }
    home = re.search('<div id="av-nav-main-menu".*?<ul role="navigation"[^>]*>\s*(.*?)\s*</ul>', home)
    if None is home:
        Dialog.notification('PrimeVideo error', 'Unable to find the main primevideo.com navigation section', xbmcgui.NOTIFICATION_ERROR)
        Log('Unable to find the main primevideo.com navigation section', xbmc.LOGERROR)
        return False
    for item in re.findall('<li[^>]*>\s*(.*?)\s*</li>', home.group(1)):
        item = re.search('<a href="([^"]+)"[^>]*>\s*(.*?)\s*</a>', item)
        if None is not re.match('/storefront/home/', item.group(1)):
            continue
        # Remove react comments
        title = re.sub('^<!--\s*[^>]+\s*-->', '', re.sub('<!--\s*[^>]+\s*-->$', '', item.group(2)))
        pvCatalog['root'][title] = {'title': title, 'lazyLoadURL': BaseUrl + item.group(1) + '?_encoding=UTF8&format=json'}
    if 0 == len(pvCatalog['root']):
        Dialog.notification('PrimeVideo error', 'Unable to build the root catalog from primevideo.com', xbmcgui.NOTIFICATION_ERROR)
        Log('Unable to build the root catalog from primevideo.com', xbmc.LOGERROR)
        return False
    ''' Add functionalities to the root catalog '''
    pvCatalog['root']['Search'] = {'title': getString(30108), 'verb': 'PrimeVideo_Search'}

    # Set the expiration in 11 hours
    pvCatalog['expiration'] = 39600 + int(time.time())

    # Flush
    with open(PrimeVideoCache, 'w+') as fp:
        pickle.dump(pvCatalog, fp)

    return True


def PrimeVideo_Search():
    """ Provide search functionality for PrimeVideo """
    searchString = Dialog.input(getString(24121)).strip(' \t\n\r')
    if 0 == len(searchString):
        xbmcplugin.endOfDirectory(pluginhandle, succeeded=False)
        return
    Log('Searching "{0}"…'.format(searchString), xbmc.LOGINFO)
    pvCatalog['search'] = OrderedDict([('lazyLoadURL', 'https://www.primevideo.com/search/ref=atv_nb_sr?ie=UTF8&phrase={0}'.format(searchString))])
    PrimeVideo_Browse('search', xbmcplugin.SORT_METHOD_NONE)


def PrimeVideo_Browse(path, forceSort=None):
    """ Display and navigate the menu for PrimeVideo users """

    path = path.decode('utf-8')

    # Add multiuser menu if needed
    if (multiuser) and ('root' == path) and (1 < len(loadUsers())):
        li = xbmcgui.ListItem(getString(30134).format(loadUser('name')))
        li.addContextMenuItems(ContextMenu_MultiUser())
        xbmcplugin.addDirectoryItem(pluginhandle, '{0}?mode=PrimeVideo_Browse&path=root-//-SwitchUser'.format(sys.argv[0]), li, isFolder=False)
    if 'root-//-SwitchUser' == path:
        if switchUser():
            PrimeVideo_BuildRoot()
        return

    node = pvCatalog
    nodeName = None
    for n in path.split('-//-'):
        nodeName = n
        node = node[n]

    if (nodeName in pvVideoData) and ('metadata' in pvVideoData[nodeName]) and ('video' in pvVideoData[nodeName]['metadata']):
        """ Start the playback if on a video leaf """
        PlayVideo(pvVideoData[nodeName]['metadata']['video'], pvVideoData[nodeName]['metadata']['asin'], '', 0)
        return

    if (None is not node) and ('lazyLoadURL' in node):
        PrimeVideo_LazyLoad(node, nodeName)

    if None is node:
        Dialog.notification('General error', 'Something went terribly wrong…', xbmcgui.NOTIFICATION_ERROR)
        return

    folderType = 0 if 'root' == path else 1
    for key in node:
        if key in ['metadata', 'ref', 'title', 'verb', 'children']:
            continue
        url = '{0}?mode='.format(sys.argv[0])
        entry = node[key] if key not in pvVideoData else pvVideoData[key]
        if 'verb' not in entry:
            url += 'PrimeVideo_Browse&path={0}-//-{1}'.format(urllib.quote_plus(path.encode('utf-8')), urllib.quote_plus(key.encode('utf-8')))
            # Squash season number folder when only one season is available
            if ('metadata' not in entry) and ('children' in entry) and (1 == len(entry['children'])):
                url += '-//-{0}'.format(urllib.quote_plus(entry['children'][0].encode('utf-8')))
        else:
            url += entry['verb']
        title = entry['title'] if 'title' in entry else nodeName
        item = xbmcgui.ListItem(title)
        folder = True
        # In case of series find the oldest series and apply its art, also update metadata in case of squashed series
        if ('metadata' not in entry) and ('children' in entry) and (0 < len(entry['children'])):
            if 1 == len(entry['children']):
                entry['metadata'] = { 'artmeta': pvVideoData[entry['children'][0]]['metadata']['artmeta'], 'videometa': pvVideoData[entry['children'][0]]['metadata']['videometa'] }
            else:
                sn = 90001
                snid = None
                for child in entry['children']:
                    if ('season' in pvVideoData[child]['metadata']['videometa']) and (sn > pvVideoData[child]['metadata']['videometa']['season']):
                        sn = pvVideoData[child]['metadata']['videometa']['season']
                        snid = child
                if None is not snid:
                    entry['metadata'] = { 'artmeta': pvVideoData[snid]['metadata']['artmeta'], 'videometa': { 'mediatype': 'tvshow' } }
        if 'metadata' in entry:
            m = entry['metadata']
            if 'artmeta' in m: item.setArt(m['artmeta'])
            if 'videometa' in m:
                # https://codedocs.xyz/xbmc/xbmc/group__python__xbmcgui__listitem.html#ga0b71166869bda87ad744942888fb5f14
                item.setInfo('video', m['videometa'])
                if 'episode' in m['videometa']:
                    folderType = 4  # Episode
                elif 'season' in m['videometa']:
                    if 'tvshow' == m['videometa']['mediatype']:
                        folderType = 2  # Series list
                    else:
                        folderType = 3  # Season
                elif 2 > folderType:  # If it's not been declared series, season or episode yet…
                    folderType = 5  # … it's a Movie
            if 'video' in m:
                folder = False
                item.setProperty('IsPlayable', 'true')
                item.setInfo('video', {'title': title})
                if 'runtime' in m:
                    item.setInfo('video', {'duration': m['runtime']})
                    item.addStreamInfo('video', {'duration': m['runtime']})
        xbmcplugin.addDirectoryItem(pluginhandle, url, item, isFolder=folder)
        del item

    # Set sort method and view
    # https://codedocs.xyz/xbmc/xbmc/group__python__xbmcplugin.html#ga85b3bff796fd644fb28f87b136025f40
    xbmcplugin.addSortMethod(pluginhandle, [
        xbmcplugin.SORT_METHOD_NONE,
        xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE,
        xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE,
        xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE,
        xbmcplugin.SORT_METHOD_EPISODE,
        xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE,
    ][folderType if None is forceSort else forceSort])

    if 'false' == addon.getSetting("viewenable"):
        # Only vfs and videos to keep Kodi's watched functionalities
        folderType = 0 if 2 > folderType else 1
    else:
        # Actual views, set the main categories as vfs
        folderType = 0 if 2 > folderType else 2

    setContentAndView([None, 'videos', 'series', 'season', 'episode', 'movie'][folderType])


def PrimeVideo_LazyLoad(obj, objName):
    def Unescape(text):
        """ Unescape various html/xml entities, courtesy of Fredrik Lundh """

        def fixup(m):
            import htmlentitydefs
            text = m.group(0)
            if text[:2] == "&#":
                # character reference
                try:
                    if text[:3] == "&#x":
                        return unichr(int(text[3:-1], 16))
                    else:
                        return unichr(int(text[2:-1]))
                except ValueError:
                    pass
            else:
                # named entity
                try:
                    text = unichr(htmlentitydefs.name2codepoint[text[1:-1]])
                except KeyError:
                    pass
            return text  # leave as is

        # Since we're using this for titles and synopses, and clean up general mess
        ret = re.sub("&#?\w+;", fixup, text)
        if ('"' == ret[0:1]) and ('"' == ret[-1:]):
            ret = ret[1:-1]
        
        # Try to correct text when Amazon returns latin-1 encoded utf-8 characters
        # (with the help of https://ftfy.now.sh/)
        try:
            ret = ret.encode('latin-1').decode('utf-8')
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass

        return BeautifyText(ret)

    def MaxSize(imgUrl):
        """ Strip the dynamic resize triggers from the URL """
        return re.sub(r'_(SX[0-9]+|UR[0-9]+,[0-9]+)', '', imgUrl)

    def ExtractURN(url):
        """ Extract the unique resource name identifier """
        ret = re.search(r'(/gp/video)?/detail/([^/]+)/', url)
        if None is not ret:
            ret = ret.group(2)
        return ret

    def DelocalizeDate(lang, datestr):
        """ Convert language based timestamps into YYYY-MM-DD """
        if lang not in dateParserData:
            Log('Unable decode date "{0}": language "{1}" not supported'.format(datestr, lang), xbmc.LOGWARNING)
            return datestr
        p = re.search(dateParserData[lang]['deconstruct'], datestr)
        if None is p:
            # Sometimes Amazon returns english everything, let's try to figure out if this is the case
            p = re.search(dateParserData['en_US']['deconstruct'], datestr)
            if None is p:
                Log('Unable to parse date "{0}" with language "{1}": format changed?'.format(datestr, lang), xbmc.LOGWARNING)
                return datestr
        p = list(p.groups())
        p[dateParserData[lang]['month']] = dateParserData[lang]['months'][p[dateParserData[lang]['month']]]
        return dateParserData[lang]['reassemble'].format(p[0], p[1], p[2])

    def NotifyUser(msg):
        """ Pop up messages while scraping to inform users of progress """
        if not hasattr(NotifyUser, 'lastNotification'):
            NotifyUser.lastNotification = 0
        if NotifyUser.lastNotification < time.time():
            ''' Only update once every other second, to avoid endless message queue '''
            NotifyUser.lastNotification = 1 + time.time()
            Dialog.notification(__plugin__, msg, time=1000, sound=False)

    # Set up the fetch order to find the best quality image possible
    imageSizes = r'(large-screen-double|desktop-double|tablet-landscape-double|phone-landscape-double|phablet-double|phone-double|large-screen|desktop|tablet-landscape|tablet|phone-landscape|phablet|phone)'

    if 'lazyLoadURL' not in obj:
        return
    requestURLs = [obj['lazyLoadURL']]

    amzLang = None
    if None is not requestURLs[0]:
        # Fine the locale amazon's using
        cj = MechanizeLogin()
        if cj:
            amzLang = cj.get('lc-main-av', domain='.primevideo.com', path='/')

    bUpdatedVideoData = False  # Whether or not the pvData has been updated

    while 0 < len(requestURLs):
        # We linearize and avoid recursion through requestURLs differentiation
        # - String: request url, the obj parameter is the root object
        # - Tuple(URL, object, [urn]): request url, object reference and its urn
        if not isinstance(requestURLs[0], tuple):
            requestURL = requestURLs[0]
            o = obj
            refUrn = objName
        else:
            requestURL = requestURLs[0][0]
            o = requestURLs[0][1]
            refUrn = requestURLs[0][2]
        del requestURLs[0]
        couldNotParse = False
        try:
            cnt = getURL(requestURL, silent=True, useCookie=True, rjson=False)
            if 'lazyLoadURL' in o:
                o['ref'] = o['lazyLoadURL']
                del o['lazyLoadURL']
        except:
            couldNotParse = True
        if couldNotParse or (0 == len(cnt)):
            Dialog.notification(getString(30251), requestURL, xbmcgui.NOTIFICATION_ERROR)
            Log('Unable to fetch the url: {0}'.format(requestURL), xbmc.LOGERROR)
            break

        for t in [('\\\\n', '\n'), ('\\n', '\n'), ('\\\\"', '"'), (r'^\s+', '')]:
            cnt = re.sub(t[0], t[1], cnt, flags=re.DOTALL)
        if None is not re.search('<html[^>]*>', cnt):
            ''' If there's an HTML tag it's no JSON-AmazonUI-Streaming object '''
            if None is not re.search(r'<div[^>]* id="Watchlist"[^>]*>', cnt, flags=re.DOTALL):
                ''' Watchlist '''
                if not hasattr(PrimeVideo_LazyLoad, 'WatchlistPages'):
                    PrimeVideo_LazyLoad.WatchlistPages = {}
                if ('Watchlist' == objName):
                    for entry in re.findall(r'<a href="([^"]+/)[^"/]+" class="DigitalVideoUI_TabHeading__tab([^"]*DigitalVideoUI_TabHeading__active)?">(.*?)</a>', cnt, flags=re.DOTALL):
                        obj[Unescape(entry[2])] = { 'title': Unescape(entry[2]), 'lazyLoadURL': BaseUrl + entry[0] + '?sort=DATE_ADDED_DESC' }
                    continue
                for entry in re.findall(r'<div[^>]* class="[^"]*DigitalVideoWebNodeLists_Item__item[^"]*"[^>]*>\s*<a href="(/detail/([^/]+)/)[^"]*"[^>]*>*.*?"[^"]*DigitalVideoWebNodeLists_Item__coreTitle[^"]*"[^>]*>\s*(.*?)\s*</', cnt):
                    obj[entry[1]] = { 'title': Unescape(entry[2]), 'lazyLoadURL': BaseUrl + entry[0] }
                pagination = re.search(r'<ol[^>]* class="[^"]*DigitalVideoUI_Pagination__pagination[^"]*"[^>]*>(.*?)</ol>', cnt)
                if None is not pagination:
                    # We save a semi-static list of scraped pages, to avoid circular loops
                    if (refUrn not in PrimeVideo_LazyLoad.WatchlistPages):
                        PrimeVideo_LazyLoad.WatchlistPages[refUrn] = []
                    currentPage = re.search(r'<a[^>]* href="#"[^>]*>\s*<span>\s*([0-9]+)\s*</span>', pagination.group(0), flags=re.DOTALL).group(1)
                    if currentPage not in PrimeVideo_LazyLoad.WatchlistPages[refUrn]:
                        PrimeVideo_LazyLoad.WatchlistPages[refUrn].append(currentPage)
                    for entry in re.findall(r'<li[^>]*>\s*<a href="(/[^"]+)"[^>]*>\s*<span>\s*([0-9]+)\s*', pagination.group(0)):
                        if entry[1] not in PrimeVideo_LazyLoad.WatchlistPages[refUrn]:
                            requestURLs.append((BaseUrl + entry[0], o, refUrn))
            elif None is re.search(r'"[^"]*av-result-cards[^"]*"', cnt, flags=re.DOTALL):
                ''' Movie/series page '''
                # Find the biggest fanart available
                bgimg = re.search(r'<div class="av-hero-background-size av-bgimg av-bgimg-' + imageSizes + r'">.*?url\(([^)]+)\)', cnt, flags=re.DOTALL)
                if None is not bgimg:
                    bgimg = MaxSize(bgimg.group(2))

                # Extract the global data
                rx = [
                    r'<span data-automation-id="imdb-release-year-badge"[^>]*>\s*([0-9]+)\s*</span>',  # Year
                    r'<span data-automation-id="imdb-rating-badge"[^>]*>\s*([0-9]+)[,.]([0-9]+)\s*</span>',  # IMDb rating
                    r'<span data-automation-id="maturity-rating-badge"[^>]*>\s*(.*?)\s*</span>',  # Age rating
                    r'<dt data-automation-id="meta-info-starring"[^>]*>[^<]*</dt>\s*<dd[^>]*>\s*(.*?)\s*</dd>',  # Starring
                    r'<dt data-automation-id="meta-info-genres"[^>]*>[^<]*</dt>\s*<dd[^>]*>\s*(.*?)\s*</dd>',  # Genre
                    r'<dt data-automation-id="meta-info-director"[^>]*>[^<]*</dt>\s*<dd[^>]*>\s*(.*?)\s*</dd>',  # Director
                    r'<div data-automation-id="synopsis"[^>]*>[^<]*<p>\s*(.*?)\s*</p>',  # Synopsis
                ]
                results = re.search(r'<section\s+[^>]*class="[^"]*av-detail-section[^"]*"[^>]*>\s*(.*?)\s*</section>', cnt, flags=re.DOTALL).group(1)
                gres = []
                for i in range(0, len(rx)):
                    gres.append(re.search(rx[i], results, flags=re.DOTALL))
                    if None is not gres[i]:
                        gres[i] = gres[i].groups()
                        if 1 == len(gres[i]):
                            gres[i] = Unescape(gres[i][0])
                        if (2 < i) and (6 != i):
                            gres[i] = re.sub(r'\s*</?a[^>]*>\s*', '', gres[i])
                            gres[i] = re.split(r'\s*[,;]\s*', gres[i])
                            # Cast is always to be sent as a list, single string is only required/preferred for Genre and Director
                            if (3 < i) and (1 == len(gres[i])):
                                gres[i] = gres[i][0]

                results = re.search(r'<ol\s+[^>]*class="[^"]*av-episode-list[^"]*"[^>]*>\s*(.*?)\s*</ol>', cnt, flags=re.DOTALL)
                if None is results:
                    ''' Standalone movie '''
                    if 'video' not in pvVideoData[refUrn]['metadata']:
                        asin = re.search(r'"asin":"([^"]*)"', cnt, flags=re.DOTALL)
                        if None is not asin:
                            bUpdatedVideoData = True

                            meta = pvVideoData[refUrn]['metadata']
                            if None is not bgimg:
                                meta['artmeta']['fanart'] = bgimg
                            NotifyUser(getString(30253).format(pvVideoData[refUrn]['title']))
                            meta['asin'] = asin.group(1)
                            meta['video'] = ExtractURN(requestURL)

                            # Insert movie information
                            if None is not gres[0]: meta['videometa']['year'] = gres[0]
                            if None is not gres[1]: meta['videometa']['rating'] = int(gres[1][0]) + (int(gres[1][1]) / 10.0)
                            if None is not gres[2]: meta['videometa']['mpaa'] = gres[2]
                            if None is not gres[3]: meta['videometa']['cast'] = gres[3]
                            if None is not gres[4]: meta['videometa']['genre'] = gres[4]
                            if None is not gres[5]: meta['videometa']['director'] = gres[5]
                            if None is not gres[6]: meta['videometa']['plot'] = gres[6]

                            # Extract the runtime
                            success, gpr = getUrldata('catalog/GetPlaybackResources', meta['asin'], useCookie=True, extra=True,
                                                    opt='&titleDecorationScheme=primary-content', dRes='CatalogMetadata')
                            if not success:
                                gpr = None
                            else:
                                if 'runtimeSeconds' in gpr['catalogMetadata']['catalog']:
                                    meta['runtime'] = gpr['catalogMetadata']['catalog']['runtimeSeconds']
                else:
                    ''' Episode list '''
                    for entry in re.findall(r'<li[^>]*>\s*(.*?)\s*</li>', results.group(1), flags=re.DOTALL):
                        rx = [
                            r'<a data-automation-id="ep-playback-[0-9]+"[^>]*data-ref="([^"]*)"[^>]*data-title-id="([^"]*)"[^>]*href="([^"]*)"',
                            r'<div class="av-bgimg av-bgimg-' + imageSizes + r'">.*?url\(([^)]+)\)',  # Image
                            r'<span class="av-play-title-text">\s*(.*?)\s*</span>',  # Title
                            r'<span data-automation-id="ep-air-date-badge-[0-9]+"[^>]*>\s*(.*?)\s*</span>',  # Original air date
                            r'<span data-automation-id="ep-amr-badge-[0-9]+"[^>]*>\s*(.*?)\s*</span>',  # Age rating
                            r'<p data-automation-id="ep-synopsis-[0-9]+"[^>]*>\s*(.*?)\s*</p>',  # Synopsis
                            r'id="ep-playback-([0-9]+)"',  # Episode number
                            r'\s+data-title-id="\s*([^"]+?)\s*"',  # Episode's asin
                        ]
                        res = []
                        for i in range(0, len(rx)):
                            res.append(re.search(rx[i], entry))
                            if None is not res[i]:
                                res[i] = res[i].groups()
                                # If holding a single result, don't provide a list
                                if 1 == len(res[i]):
                                    res[i] = Unescape(res[i][0])
                                # We just need the image, not the type                            
                                if 1 == i:
                                    res[i] = res[i][1]
                        if (None is res[0]) or (None is res[2]):
                            ''' Some episodes might be not playable until a later date or just N/A, although listed '''
                            continue
                        meta = {'artmeta': {'thumb': MaxSize(res[1]), 'poster': MaxSize(res[1]), 'fanart': bgimg, }, 'videometa': {'mediatype': 'episode'},
                                'id': res[0][0], 'asin': res[0][1], 'videoURL': res[0][2]}
                        if None is not re.match(r'/[^/]', meta['videoURL']):
                            meta['videoURL'] = BaseUrl + meta['videoURL']
                        meta['video'] = ExtractURN(meta['videoURL'])
                        eid = meta['video']
                        #if None is not res[7]:
                        #    eid = res[7]

                        if (eid not in pvVideoData) or ('videometa' not in pvVideoData[eid]) or (0 == len(pvVideoData[eid]['videometa'])):
                            # Extract the runtime
                            success, gpr = getUrldata('catalog/GetPlaybackResources', res[7], useCookie=True, extra=True,
                                                    opt='&titleDecorationScheme=primary-content', dRes='CatalogMetadata')
                            if not success:
                                gpr = None
                            else:
                                if 'runtimeSeconds' in gpr['catalogMetadata']['catalog']:
                                    meta['runtime'] = gpr['catalogMetadata']['catalog']['runtimeSeconds']

                            # Sometimes the chicken comes before the egg
                            #if refUrn not in pvVideoData:
                            #    pvVideoData[refUrn] = { 'metadata': { 'videometa': {} }, 'children': [] }

                            # Insert series information
                            if None is not gres[0]: meta['videometa']['year'] = gres[0]
                            if None is not gres[1]: meta['videometa']['rating'] = int(gres[1][0]) + (int(gres[1][1]) / 10.0)
                            if None is not gres[2]: meta['videometa']['mpaa'] = gres[2]
                            if None is not gres[3]:
                                meta['videometa']['cast'] = gres[3]
                                pvVideoData[refUrn]['metadata']['videometa']['cast'] = gres[3]
                            if None is not gres[4]:
                                meta['videometa']['genre'] = gres[4]
                                pvVideoData[refUrn]['metadata']['videometa']['genre'] = gres[4]
                            if None is not gres[5]:
                                meta['videometa']['director'] = gres[5]
                                pvVideoData[refUrn]['metadata']['videometa']['director'] = gres[5]

                            # Insert episode specific information
                            if None is not res[3]: meta['videometa']['premiered'] = DelocalizeDate(amzLang, res[3])
                            if None is not res[4]: meta['videometa']['mpaa'] = res[4]
                            if None is not res[5]: meta['videometa']['plot'] = res[5]
                            if None is not res[6]:
                                if 'season' in pvVideoData[refUrn]['metadata']['videometa']:
                                    meta['videometa']['season'] = pvVideoData[refUrn]['metadata']['videometa']['season']
                                else:
                                    ''' We're coming from a widow carousel '''
                                    pvVideoData[refUrn]['metadata']['videometa']['mediatype'] = 'tvshow'
                                    # Try with page season selector
                                    ssn = re.search(r'<a class="av-droplist--selected"[^>]*>[^0-9]*([0-9]+)[^0-9]*</a>', cnt)
                                    if None is ssn:
                                        # Try with single season
                                        ssn = re.search(r'<span class="av-season-single av-badge-text">[^0-9]*([0-9]+)[^0-9]*</span>', cnt)
                                    if None is not ssn:
                                        ssn = ssn.group(1)
                                        meta['videometa']['season'] = ssn
                                        pvVideoData[refUrn]['metadata']['videometa']['season'] = ssn
                                meta['videometa']['episode'] = int(res[6])

                            # Episode title cleanup
                            title = res[2]
                            if None is not re.match(r'[0-9]+[.]\s*', title):
                                ''' Strip the episode number '''
                                title = re.sub(r'^[0-9]+.\s*', '', title)
                            else:
                                ''' Probably an extra trailer or something, remove episode information '''
                                del meta['videometa']['season']
                                del meta['videometa']['episode']

                            bUpdatedVideoData = True
                            pvVideoData[eid] = { 'metadata': meta, 'title': title, 'parent': refUrn }
                            NotifyUser(getString(30253).format(title))
                        if eid not in o:
                            o[eid] = {}
                        if (refUrn in pvVideoData) and ('children' in pvVideoData[refUrn]) and (eid not in pvVideoData[refUrn]['children']):
                            pvVideoData[refUrn]['children'].append(eid)

            else:
                ''' Movie and series list '''
                results = re.search(r'<ol\s+[^>]*class="[^"]*av-result-cards[^"]*"[^>]*>\s*(.*?)\s*</ol>', cnt, flags=re.DOTALL)
                for entry in re.findall(r'<li[^>]*>\s*(.*?)\s*</li>', results.group(1), flags=re.DOTALL):
                    rx = [
                        r'<img\s+[^>]*src="([^"]*)".*?<h2[^>]*>\s*<a\s+[^>]*href="([^"]+)"[^>]*>\s*(.*?)\s*</a>\s*</h2>',  # Image, link and title
                        r'<span\s+[^>]*class="[^"]*av-result-card-rating[^"]*"[^>]*>\s*([0-9]+)[,.]([0-9]+)\s*</span>',  # IMDb rating
                        r'<p\s+[^>]*class="[^"]*av-result-card-synopsis[^"]*"[^>]*>\s*(.*?)\s*</p>',  # Synopsis
                        r'<span\s+[^>]*class="[^"]*av-result-card-season[^"]*"[^>]*>\s*(.*?)\s*</span>',  # Season
                        r'<span\s+[^>]*class="[^"]*av-result-card-year[^"]*"[^>]*>\s*(.*?)\s*</span>',  # Year
                        r'<span\s+[^>]*class="[^"]*av-result-card-certification[^"]*"[^>]*>\s*(.*?)\s*</span>',  # Age rating
                        r'\s+data-asin="\s*([^"]+?)\s*"',  # Movie/episode's URN
                    ]
                    res = []
                    for i in range(0, len(rx)):
                        res.append(re.search(rx[i], entry))
                        if None is not res[i]:
                            res[i] = res[i].groups()
                            if 1 == len(res[i]):
                                res[i] = Unescape(res[i][0])
                            else:
                                res[i] = list(res[i])
                    title = Unescape(res[0][2])
                    NotifyUser(getString(30253).format(title))
                    if None is not re.match(r'/[^/]', res[0][1]):
                        res[0][1] = BaseUrl + res[0][1]
                    meta = {'artmeta': {'thumb': MaxSize(res[0][0]), 'poster': MaxSize(res[0][0])}, 'videometa': {}}
                    if None is not res[1]: meta['videometa']['rating'] = int(res[1][0]) + (int(res[1][1]) / 10.0)
                    if None is not res[2]: meta['videometa']['plot'] = res[2]
                    meta['videometa']['mediatype'] = 'movie' if None is res[3] else 'season'
                    if None is not res[4]: meta['videometa']['year'] = int(res[4])
                    if None is not res[5]: meta['videometa']['mpaa'] = res[5]

                    if None is res[3]:
                        ''' Movie '''
                        # Queue the movie page instead of parsing partial information here
                        urn = ExtractURN(res[0][1])
                        if urn not in o:
                            o[urn] = {}
                        if (urn not in pvVideoData) or ('metadata' not in pvVideoData[urn]) or ('video' not in pvVideoData[urn]['metadata']):
                            bUpdatedVideoData = True
                            pvVideoData[urn] = {'metadata': meta, 'title': title}
                            requestURLs.append((res[0][1], o[urn], urn))
                    else:
                        ''' Series '''
                        id = title
                        sid = ExtractURN(res[0][1])

                        if sid not in pvVideoData:
                            pvVideoData[sid] = { 'children': [] }

                        # Extract video metadata
                        if 'parent' in pvVideoData[sid]:
                            id = pvVideoData[sid]['parent']
                        elif (id is title) and (None is not res[6]):
                            success, gpr = getUrldata('catalog/GetPlaybackResources', res[6], useCookie=True, extra=True,
                                                      opt='&titleDecorationScheme=primary-content', dRes='CatalogMetadata')
                            if not success:
                                Log('Unable to get the video metadata for {0} ({1})'.format(title, res[0][1]), xbmc.LOGWARNING)
                            else:
                                # Find the show Asin URN, if possible
                                for d in gpr['catalogMetadata']['family']['tvAncestors']:
                                    if 'SHOW' == d['catalog']['type']:
                                        id = d['catalog']['id']
                                        pvVideoData[sid]['parent'] = id
                                        break
                        if id not in o:
                            o[id] = { 'title': title }
                        if (sid in pvVideoData) and ('children' in pvVideoData[sid]) and (0 < len(pvVideoData[sid]['children'])):
                            o[id][sid] = { k: {} for k in pvVideoData[sid]['children'] }
                        else:
                            # Save tree information if id is a URN and not a title name
                            if (id is not title):
                                if id not in pvVideoData:
                                    pvVideoData[id] = { 'children': [] }
                                if sid not in pvVideoData[id]['children']:
                                    pvVideoData[id]['children'].append(sid)
                                if 'title' not in pvVideoData[id]:
                                    pvVideoData[id]['title'] = title
                            sn = res[3]
                            n = int(re.sub(r'^[^0-9]*([0-9]+)[^0-9]*$', r'\1', sn))
                            meta['videometa']['season'] = n
                            o[id][sid] = { 'lazyLoadURL': res[0][1] }
                            bUpdatedVideoData = True
                            pvVideoData[sid]['title'] = sn
                            pvVideoData[sid]['metadata'] = meta

                # Next page
                pagination = re.search(
                    r'<ol\s+[^>]*id="[^"]*av-pagination[^"]*"[^>]*>.*?<li\s+[^>]*class="[^"]*av-pagination-current-page[^"]*"[^>]*>.*?</li>\s*<li\s+[^>]*class="av-pagination[^>]*>\s*(.*?)\s*</li>\s*</ol>',
                    cnt, flags=re.DOTALL)
                if None is not pagination:
                    nru = Unescape(re.search(r'href="([^"]+)"', pagination.group(1), flags=re.DOTALL).group(1))
                    if None is not re.match(r'/[^/]', nru):
                        nru = BaseUrl + nru
                    requestURLs.append(nru)
        else:
            ''' Categories list '''
            for section in re.split(r'&&&\s+', cnt):
                if 0 == len(section):
                    continue
                section = re.split(r'","', section[2:-2])
                if 'dvappend' == section[0]:
                    title = Unescape(re.sub(r'^.*<h2[^>]*>\s*<span[^>]*>\s*(.*?)\s*</span>.*$', r'\1', section[2], flags=re.DOTALL))
                    NotifyUser(getString(30253).format(title))
                    o[title] = {'title': title}
                    if None is not re.search('<h2[^>]*>.*?<a\s+[^>]*\s+href="[^"]+"[^>]*>.*?</h2>', section[2], flags=re.DOTALL):
                        o[title]['lazyLoadURL'] = Unescape(
                            re.sub('\\n', '', re.sub(r'^.*?<h2[^>]*>.*?<a\s+[^>]*\s+href="([^"]+)"[^>]*>.*?</h2>.*?$', r'\1', section[2], flags=re.DOTALL)))
                    else:
                        ''' The carousel has no explore link, we need to parse what we can from the carousel itself '''
                        for entry in re.findall(r'<li[^>]*>\s*(.*?)\s*</li>', section[2], flags=re.DOTALL):
                            parts = re.search(
                                r'<a\s+[^>]*href="([^"]*)"[^>]*>\s*.*?(src|data-a-image-source)="([^"]*)"[^>]*>.*?class="dv-core-title"[^>]*>\s*(.*?)\s*</span>',
                                entry, flags=re.DOTALL)
                            if None is not re.search(r'/search/', parts.group(1)):
                                ''' Category '''
                                o[title][parts.group(4)] = {'metadata': {'artmeta': {'thumb': MaxSize(parts.group(3)), 'poster': MaxSize(parts.group(3))}},
                                                            'lazyLoadURL': parts.group(1), 'title': parts.group(4)}
                            else:
                                ''' Movie/Series list '''
                                urn = ExtractURN(parts.group(1))
                                o[title][urn] = {}
                                if urn not in pvVideoData:
                                    bUpdatedVideoData = True
                                    pvVideoData[urn] = {
                                    'metadata': {'artmeta': {'thumb': MaxSize(parts.group(3)), 'poster': MaxSize(parts.group(3))}, 'videometa': {}},
                                    'title': Unescape(parts.group(4))}
                                    requestURLs.append((parts.group(1), o[title][urn], urn))
                pagination = re.search(r'data-ajax-pagination="{&quot;href&quot;:&quot;([^}]+)&quot;}"', section[2], flags=re.DOTALL)
                if ('dvupdate' == section[0]) and (None is not pagination):
                    requestURLs.append(re.sub(r'(&quot;,&quot;|&amp;)', '&', re.sub('&quot;:&quot;', '=', pagination.group(1) + '&format=json')))
        if 0 < len(requestURLs):
            NotifyUser(getString(30252))

    # Flush catalog and data
    with open(PrimeVideoCache, 'w+') as fp:
        pickle.dump(pvCatalog, fp)
    if bUpdatedVideoData:
        with open(PrimeVideoData, 'w+') as fp:
            pickle.dump(pvVideoData, fp)


def Search():
    searchString = Dialog.input(getString(24121))
    if searchString:
        url = 'searchString=%s%s' % (urllib.quote_plus(searchString), OfferGroup)
        listContent('Search', url, 1, 'search')


def loadCategories(force=False):
    if xbmcvfs.exists(menuFile) and not force:
        ftime = updateTime(False)
        ctime = time.time()
        if ctime - ftime < 8 * 3600:
            return

    Log('Parse Menufile', xbmc.LOGDEBUG)
    parseStart = time.time()
    data = getURL('https://raw.githubusercontent.com/Sandmann79/xbmc/master/plugin.video.amazon-test/resources/menu/%s.json' % MarketID)
    if not data:
        jsonfile = os.path.join(PluginPath, 'resources', 'menu', MarketID + '.json')
        jsonfile = jsonfile.replace(MarketID, 'ATVPDKIKX0DER') if not xbmcvfs.exists(jsonfile) else jsonfile
        data = json.load(open(jsonfile))
    createDB(True)
    parseNodes(data)
    updateTime()
    menuDb.commit()
    Log('Parse MenuTime: %s' % (time.time() - parseStart), xbmc.LOGDEBUG)


def updateTime(savetime=True):
    c = menuDb.cursor()
    if savetime:
        wMenuDB(['last_update', '', '', str(time.time()), str(DBVersion), ''])
    else:
        try:
            result = c.execute('select content, id from menu where node = ("last_update")').fetchone()
        except:
            result = 0
        c.close()
        if result:
            if DBVersion > float(result[1]):
                return 0
            return float(result[0])
        return 0
    c.close()


def getRootNode():
    c = menuDb.cursor()
    st = 'all' if payCont else 'prime'
    for title, nodeid, id in c.execute('select title, content, id from menu where node = (0)').fetchall():
        result = c.execute('select content from menu where node = (?) and id = (?)', (nodeid, st)).fetchone()
        nodeid = result[0] if result else nodeid
        addDir(title, 'listCategories', str(nodeid), opt=id)
    c.close()
    return


def parseNodes(data, node_id=''):
    if type(data) != list:
        data = [data]

    for count, entry in enumerate(data):
        category = None
        if 'categories' in entry.keys():
            parseNodes(entry['categories'], '%s%s' % (node_id, count))
            content = '%s%s' % (node_id, count)
            category = 'node'
        else:
            for e in ['query', 'play']:
                if e in entry.keys():
                    content = entry[e]
                    category = e
        if category:
            wMenuDB([node_id, entry.get('title', ''), category, content, entry.get('id', ''), json.dumps(entry.get('infolabel', ''))])


def wMenuDB(menudata):
    c = menuDb.cursor()
    c.execute('insert or ignore into menu values (?,?,?,?,?,?)', menudata)
    c.close()


def getNode(node):
    c = menuDb.cursor()
    result = c.execute('select distinct * from menu where node = (?)', (node,)).fetchall()
    c.close()
    return result


def listCategories(node, root=None):
    loadCategories()
    cat = getNode(node)
    all_vid = {'movies': [30143, 'movie'], 'tv_shows': [30160, 'tvseason,tvepisodes&RollUpToSeries=T']}

    if root in all_vid.keys():
        url = 'OrderBy=Title%s&contentType=%s' % (OfferGroup, all_vid[root][1])
        addDir(getString(all_vid[root][0]), 'listContent', url)

    for node, title, category, content, menu_id, infolabel in cat:
        infolabel = json.loads(infolabel)
        mode = None
        info = None
        opt = ''
        if infolabel:
            info = getAsins({'formats': []}, True)
            info.update(infolabel)

        if category == 'node':
            mode = 'listCategories'
            url = content
        elif category == 'query':
            mode = 'listContent'
            opt = 'listcat'
            url = re.sub('\n|\\n', '', content)
        elif category == 'play':
            addVideo(info['Title'], info['Asins'], info)
        if mode:
            addDir(title, mode, url, info, opt)
    xbmcplugin.endOfDirectory(pluginhandle)


def listContent(catalog, url, page, parent, export=False):
    oldurl = url
    ResPage = 240 if export else MaxResults
    url = '%s&NumberOfResults=%s&StartIndex=%s&Detailed=T' % (url, ResPage, (page - 1) * ResPage)
    titles = getATVData(catalog, url)

    if page != 1 and not export:
        addDir(' --= %s =--' % getString(30112), thumb=HomeIcon)

    if not titles or not len(titles['titles']):
        if 'search' in parent:
            Dialog.ok(__plugin__, getString(30202))
        else:
            xbmcplugin.endOfDirectory(pluginhandle)
        return
    endIndex = titles['endIndex']
    numItems = len(titles['titles'])
    if 'approximateSize' not in titles.keys():
        endIndex = 1 if numItems >= MaxResults else 0
    else:
        if endIndex == 0:
            if (page * ResPage) <= titles['approximateSize']:
                endIndex = 1

    for item in titles['titles']:
        if 'title' not in item:
            continue
        contentType, infoLabels = getInfos(item, export)
        name = infoLabels['DisplayTitle']
        asin = item['titleId']
        wlmode = 1 if watchlist in parent else 0
        simiUrl = urllib.quote_plus('ASIN=' + asin + OfferGroup)
        cm = [(getString(30183),
               'Container.Update(%s?mode=listContent&cat=GetSimilarities&url=%s&page=1&opt=gs)' % (sys.argv[0], simiUrl)),
              (getString(wlmode + 30180) % getString(langID[contentType]),
               'RunPlugin(%s?mode=WatchList&url=%s&opt=%s)' % (sys.argv[0], asin, wlmode)),
              (getString(30185) % getString(langID[contentType]),
               'RunPlugin(%s?mode=getListMenu&url=%s&export=1)' % (sys.argv[0], asin)),
              (getString(30186), 'UpdateLibrary(video)')]

        if contentType == 'movie' or contentType == 'episode':
            addVideo(name, asin, infoLabels, cm, export)
        else:
            mode = 'listContent'
            url = item['childTitles'][0]['feedUrl']
            if watchlist in parent:
                url += OfferGroup
            if contentType == 'season':
                name = formatSeason(infoLabels, parent)
                if library not in parent and parent != '':
                    curl = 'SeriesASIN=%s&ContentType=TVEpisode,TVSeason&RollUpToSeason=T&IncludeBlackList=T%s' % (
                        infoLabels['SeriesAsin'], OfferGroup)
                    cm.insert(0, (getString(30182), 'Container.Update(%s?mode=listContent&cat=Browse&url=%s&page=1)' % (
                        sys.argv[0], urllib.quote_plus(curl))))

            if export:
                url = re.sub(r'(?i)contenttype=\w+', 'ContentType=TVEpisode', url)
                url = re.sub(r'(?i)&rollupto\w+=\w+', '', url)
                listContent('Browse', url, 1, '', export)
            else:
                addDir(name, mode, url, infoLabels, cm=cm, export=export)

    if endIndex > 0:
        if export:
            listContent(catalog, oldurl, page + 1, parent, export)
        else:
            addDir(' --= %s =--' % (getString(30111) % int(page + 1)), 'listContent', oldurl, page=page + 1,
                   catalog=catalog, opt=parent, thumb=NextIcon)
    if not export:
        db.commit()
        xbmc.executebuiltin('RunPlugin(%s?mode=checkMissing)' % sys.argv[0])
        if 'search' in parent:
            setContentAndView('season')
        else:
            setContentAndView(contentType)


def cleanTitle(title):
    if title.isupper():
        title = title.title().replace('[Ov]', '[OV]').replace('Bc', 'BC')
    title = title.replace('\u2013', '-').replace('\u00A0', ' ').replace('[dt./OV]', '').replace('_DUPLICATE_', '')
    return title.strip()


def Export(infoLabels, url):
    isEpisode = infoLabels['contentType'] != 'movie'
    language = xbmc.convertLanguage(Language, xbmc.ISO_639_2)
    ExportPath = MOVIE_PATH
    nfoType = 'movie'
    title = infoLabels['Title']

    if isEpisode:
        ExportPath = TV_SHOWS_PATH
        title = infoLabels['TVShowTitle']

    tl = title.lower()
    if '[omu]' in tl or '[ov]' in tl or ' omu' in tl:
        language = ''
    filename = re.sub(r'(?i)\[.*| omu| ov', '', title).strip()
    ExportPath = os.path.join(ExportPath, cleanName(filename))

    if isEpisode:
        infoLabels['TVShowTitle'] = filename
        nfoType = 'episodedetails'
        filename = '%s - S%02dE%02d - %s' % (infoLabels['TVShowTitle'], infoLabels['Season'],
                                             infoLabels['Episode'], infoLabels['Title'])

    if addon.getSetting('cr_nfo') == 'true':
        CreateInfoFile(filename, ExportPath, nfoType, infoLabels, language)

    SaveFile(filename + '.strm', url, ExportPath)
    Log('Export: ' + filename)


def WatchList(asin, remove):
    action = 'remove' if remove else 'add'
    cookie = MechanizeLogin()

    if not cookie:
        return

    token = getToken(asin, cookie)
    url = BaseUrl + '/gp/video/watchlist/ajax/addRemove.html?&ASIN=%s&dataType=json&csrfToken=%s&action=%s' % (asin, token, action)
    data = getURL(url, useCookie=cookie)

    if data['success'] == 1:
        Log(asin + ' ' + data['status'])
        if remove:
            cPath = xbmc.getInfoLabel('Container.FolderPath').replace(asin, '').replace('opt=' + watchlist,
                                                                                        'opt=rem_%s' % watchlist)
            xbmc.executebuiltin('Container.Update("%s", replace)' % cPath)
    else:
        Log(data['status'] + ': ' + data['reason'])


def getToken(asin, cookie):
    url = BaseUrl + '/dp/video/' + asin
    data = getURL(url, useCookie=cookie, rjson=False)
    if data:
        tree = BeautifulSoup(data, convertEntities=BeautifulSoup.HTML_ENTITIES)
        form = tree.find('form', attrs={'class': 'dv-watchlist-toggle'})
        token = form.find('input', attrs={'name': 'csrfToken'})['value']
        return urllib.quote_plus(token)
    return ''


def getArtWork(infoLabels, contentType):
    if contentType == 'movie' and tmdb_art == '0':
        return infoLabels
    if contentType != 'movie' and tvdb_art == '0':
        return infoLabels

    c = db.cursor()
    asins = infoLabels['Asins']
    infoLabels['Banner'] = None
    season = -1 if contentType == 'series' else -2

    if contentType == 'season' or contentType == 'episode':
        asins = infoLabels['SeriesAsin']
    if 'Season' in infoLabels.keys():
        season = int(infoLabels['Season'])

    extra = ' and season = %s' % season if season > -2 else ''

    for asin in asins.split(','):
        result = c.execute('select poster,fanart,banner from art where asin like (?)' + extra,
                           ('%' + asin + '%',)).fetchone()
        if result:
            if result[0] and contentType != 'episode' and result[0] != na:
                infoLabels['Thumb'] = result[0]
            if result[0] and contentType != 'movie' and result[0] != na:
                infoLabels['Poster'] = result[0]
            if result[1] and result[1] != na:
                infoLabels['Fanart'] = result[1]
            if result[2] and result[2] != na:
                infoLabels['Banner'] = result[2]
            if season > -1:
                result = c.execute('select poster, fanart from art where asin like (?) and season = -1',
                                   ('%' + asin + '%',)).fetchone()
                if result:
                    if result[0] and result[0] != na and contentType == 'episode':
                        infoLabels['Poster'] = result[0]
                    if result[1] and result[1] != na and showfanart:
                        infoLabels['Fanart'] = result[1]
            return infoLabels
        elif season > -1 and showfanart:
            result = c.execute('select poster,fanart from art where asin like (?) and season = -1',
                               ('%' + asin + '%',)).fetchone()
            if result:
                if result[0] and result[0] != na and contentType == 'episode':
                    infoLabels['Poster'] = result[0]
                if result[1] and result[1] != na:
                    infoLabels['Fanart'] = result[1]
                return infoLabels

    if contentType != 'episode':
        title = infoLabels['Title']
        if contentType == 'season':
            title = infoLabels['TVShowTitle']
        c.execute('insert or ignore into miss values (?,?,?,?)', (asins, title, infoLabels['Year'], contentType))
    c.close()
    return infoLabels


def checkMissing():
    Log('Starting Fanart Update')
    c = db.cursor()
    for data in c.execute('select distinct * from miss').fetchall():
        loadArtWork(*data)
    c.execute('drop table if exists miss')
    c.close()
    db.commit()
    createDB()
    Log('Finished Fanart Update')


def loadArtWork(asins, title, year, contentType):
    seasons = None
    season_number = None
    poster = None
    fanart = None
    title = title.lower().replace('?', '').replace('omu', '').split('(')[0].split('[')[0].strip()

    if not title:
        return

    if contentType == 'movie':
        fanart = getTMDBImages(title, year=year)
    if contentType == 'season' or contentType == 'series':
        seasons, poster, fanart = getTVDBImages(title)
        if not fanart:
            fanart = getTMDBImages(title, content='tv')
        season_number = -1
        content = getATVData('GetASINDetails', 'ASINList=' + asins)['titles']
        if content:
            asins = getAsins(content[0], False)
            del content

    cur = db.cursor()
    if fanart:
        cur.execute('insert or ignore into art values (?,?,?,?,?,?)', (asins, season_number, poster, None, fanart, date.today()))
    if seasons:
        for season, url in seasons.items():
            cur.execute('insert or ignore into art values (?,?,?,?,?,?)', (asins, season, url, None, None, date.today()))
    db.commit()
    cur.close()


def getTVDBImages(title, tvdb_id=None):
    Log('searching fanart for %s at thetvdb.com' % title.upper())
    posterurl = fanarturl = None
    splitter = [' - ', ': ', ', ']
    langcodes = [Language.split('_')[0]]
    langcodes += ['en'] if 'en' not in langcodes else []
    TVDB_URL = 'http://www.thetvdb.com/banners/'

    while not tvdb_id and title:
        tv = urllib.quote_plus(title.encode('utf-8'))
        result = getURL('http://www.thetvdb.com/api/GetSeries.php?seriesname=%s&language=%s' % (tv, Language),
                        silent=True, rjson=False)
        if not result:
            continue
        soup = BeautifulSoup(result)
        tvdb_id = soup.find('seriesid')
        if tvdb_id:
            tvdb_id = tvdb_id.string
        else:
            oldtitle = title
            for splitchar in splitter:
                if title.count(splitchar):
                    title = title.split(splitchar)[0]
                    break
            if title == oldtitle:
                break
    if not tvdb_id:
        return None, None, None

    seasons = {}
    result = getURL('http://www.thetvdb.com/api/%s/series/%s/banners.xml' % (tvdb, tvdb_id), silent=True, rjson=False)
    if result:
        soup = BeautifulSoup(result)
        for lang in langcodes:
            for datalang in soup.findAll('language'):
                if datalang.string == lang:
                    data = datalang.parent
                    if data.bannertype.string == 'fanart' and not fanarturl:
                        fanarturl = TVDB_URL + data.bannerpath.string
                    if data.bannertype.string == 'poster' and not posterurl:
                        posterurl = TVDB_URL + data.bannerpath.string
                    if data.bannertype.string == data.bannertype2.string == 'season':
                        snr = data.season.string
                        if snr not in seasons.keys():
                            seasons[snr] = TVDB_URL + data.bannerpath.string

    return seasons, posterurl, fanarturl


def getTMDBImages(title, content='movie', year=None):
    Log('searching fanart for %s at tmdb.com' % title.upper())
    fanart = tmdb_id = None
    splitter = [' - ', ': ', ', ']
    TMDB_URL = 'http://image.tmdb.org/t/p/original'
    yearorg = year

    while not tmdb_id and title:
        str_year = '&year=' + str(year) if year else ''
        movie = urllib.quote_plus(title.encode('utf-8'))
        data = getURL('http://api.themoviedb.org/3/search/%s?api_key=%s&language=%s&query=%s%s' % (
            content, tmdb, Language, movie, str_year), silent=True)
        if not data:
            continue

        if data.get('total_results', 0) > 0:
            result = data['results'][0]
            if result.get('backdrop_path'):
                fanart = TMDB_URL + result['backdrop_path']
            tmdb_id = result.get('id')
        elif year:
            year = 0
        else:
            year = yearorg
            oldtitle = title
            for splitchar in splitter:
                if title.count(splitchar):
                    title = title.split(splitchar)[0]
                    break
            if title == oldtitle:
                break

    if content == 'movie' and tmdb_id and not fanart:
        fanart = na
    return fanart


def formatSeason(infoLabels, parent):
    name = ''
    season = infoLabels['Season']
    if parent:
        return infoLabels['DisplayTitle']
        # name = infoLabels['TVShowTitle'] + ' - '
    if season != 0 and season < 100:
        name += getString(30167) + ' ' + str(season)
    elif season > 1900:
        name += getString(30168) + str(season)
    elif season > 99:
        name += getString(30167) + ' ' + str(season).replace('0', '.')
    else:
        name += getString(30169)
    if not infoLabels['isPrime']:
        name = '[COLOR %s]%s[/COLOR]' % (PayCol, name)
    return name


def getListMenu(listing, export):
    if export:
        getList(listing, export, ['movie', 'tv'])
    else:
        addDir(getString(30104), 'getList', listing, export, opt='movie')
        addDir(getString(30107), 'getList', listing, export, opt='tv')
        xbmcplugin.endOfDirectory(pluginhandle, updateListing=False)


def getList(listing, export, cont):
    if listing == watchlist or listing == library:
        cj = MechanizeLogin()
        if not cj:
            return
        asins = ''
        for content in cont:
            asins += scrapAsins('/gp/video/%s/%s/?ie=UTF8&sort=%s' % (listing, content, wl_order), cj) + ','
    else:
        asins = listing

    if export:
        SetupLibrary()

    url = 'ASINList=' + asins
    extraArgs = '&RollUpToSeries=T' if dispShowOnly and 'movie' not in cont and not export else ''
    listContent('GetASINDetails', url + extraArgs, 1, listing, export)


def Log(msg, level=xbmc.LOGNOTICE):
    if level == xbmc.LOGDEBUG and verbLog:
        level = xbmc.LOGNOTICE
    msg = '[%s] %s' % (__plugin__, msg)
    xbmc.log(msg.encode('utf-8'), level)


def WriteLog(data, fn=''):
    if not verbLog:
        return

    fn = '-' + fn if fn else ''
    fn = 'avod%s.log' % fn
    path = os.path.join(HomePath, fn)
    if isinstance(data, unicode):
        data = data.encode('utf-8')
    logfile = xbmcvfs.File(path, 'w')
    logfile.write(data.__str__())
    logfile.close()


def getString(string_id):
    src = xbmc if string_id < 30000 else addon
    locString = src.getLocalizedString(string_id)
    return locString


def getAsins(content, crIL=True):
    if crIL:
        infoLabels = {'Plot': None, 'MPAA': None, 'Cast': [], 'Year': None, 'Premiered': None, 'Rating': None,
                      'Votes': None, 'isAdult': 0, 'Director': None,
                      'Genre': None, 'Studio': None, 'Thumb': None, 'Fanart': None, 'isHD': False, 'isPrime': False,
                      'AudioChannels': 1, 'TrailerAvailable': False}
    asins = content.get('titleId', '')

    for offerformat in content['formats']:
        for offer in offerformat['offers']:
            if offerformat['videoFormatType'] == 'HD' and offerformat['hasEncode'] and crIL:
                infoLabels['isHD'] = True
            if offer['offerType'] == 'SUBSCRIPTION':
                if crIL:
                    infoLabels['isPrime'] = True
            elif 'asin' in offer.keys():
                newasin = offer['asin']
                if newasin not in asins:
                    asins += ',' + newasin
        if crIL:
            if 'STEREO' in offerformat['audioFormatTypes']:
                infoLabels['AudioChannels'] = 2
            if 'AC_3_5_1' in offerformat['audioFormatTypes']:
                infoLabels['AudioChannels'] = 6

    del content

    if crIL:
        infoLabels['Asins'] = asins
        return infoLabels
    return asins


def getInfos(item, export):
    infoLabels = getAsins(item)
    infoLabels['DisplayTitle'] = infoLabels['Title'] = cleanTitle(item['title'])
    infoLabels['contentType'] = contentType = item['contentType'].lower()

    infoLabels['mediatype'] = 'movie'
    infoLabels['Plot'] = item.get('synopsis')
    infoLabels['Director'] = item.get('director')
    infoLabels['Studio'] = item.get('studioOrNetwork')
    infoLabels['Cast'] = item.get('starringCast', '').split(',')
    infoLabels['Duration'] = str(item['runtime']['valueMillis'] / 1000) if 'runtime' in item else None
    infoLabels['TrailerAvailable'] = item.get('trailerAvailable', False)
    infoLabels['Fanart'] = item.get('heroUrl')
    infoLabels['isAdult'] = 1 if 'ageVerificationRequired' in str(item.get('restrictions')) else 0
    infoLabels['Genre'] = ' / '.join(item.get('genres', '')).replace('_', ' & ').replace('Musikfilm & Tanz',
                                                                                         'Musikfilm, Tanz')
    if 'images' in item['formats'][0].keys():
        try:
            thumbnailUrl = item['formats'][0]['images'][0]['uri']
            thumbnailFilename = thumbnailUrl.split('/')[-1]
            thumbnailBase = thumbnailUrl.replace(thumbnailFilename, '')
            infoLabels['Thumb'] = thumbnailBase + thumbnailFilename.split('.')[0] + '.jpg'
        except:
            pass

    if 'releaseOrFirstAiringDate' in item:
        infoLabels['Premiered'] = item['releaseOrFirstAiringDate']['valueFormatted'].split('T')[0]
        infoLabels['Year'] = int(infoLabels['Premiered'].split('-')[0])

    if 'regulatoryRating' in item:
        if item['regulatoryRating'] == 'not_checked' or not item['regulatoryRating']:
            infoLabels['MPAA'] = getString(30171)
        else:
            infoLabels['MPAA'] = AgeRating + item['regulatoryRating']

    if 'customerReviewCollection' in item:
        infoLabels['Rating'] = float(item['customerReviewCollection']['customerReviewSummary']['averageOverallRating']) * 2
        infoLabels['Votes'] = str(item['customerReviewCollection']['customerReviewSummary']['totalReviewCount'])
    elif 'amazonRating' in item:
        infoLabels['Rating'] = float(item['amazonRating']['rating']) * 2 if 'rating' in item['amazonRating'] else None
        infoLabels['Votes'] = str(item['amazonRating']['count']) if 'count' in item['amazonRating'] else None

    if contentType == 'series':
        infoLabels['mediatype'] = 'tvshow'
        infoLabels['TVShowTitle'] = item['title']
        infoLabels['TotalSeasons'] = item['childTitles'][0]['size'] if 'childTitles' in item else None

    elif contentType == 'season':
        infoLabels['mediatype'] = 'season'
        infoLabels['Season'] = item['number']
        if item['ancestorTitles']:
            try:
                infoLabels['TVShowTitle'] = item['ancestorTitles'][0]['title']
                infoLabels['SeriesAsin'] = item['ancestorTitles'][0]['titleId']
            except:
                pass
        else:
            infoLabels['SeriesAsin'] = infoLabels['Asins'].split(',')[0]
            infoLabels['TVShowTitle'] = item['title']
        if 'childTitles' in item:
            infoLabels['TotalSeasons'] = 1
            infoLabels['Episode'] = item['childTitles'][0]['size']

    elif contentType == 'episode':
        infoLabels['mediatype'] = 'episode'
        if item['ancestorTitles']:
            for content in item['ancestorTitles']:
                if content['contentType'] == 'SERIES':
                    infoLabels['SeriesAsin'] = content['titleId'] if 'titleId' in content else None
                    infoLabels['TVShowTitle'] = content['title'] if 'title' in content else None
                elif content['contentType'] == 'SEASON':
                    infoLabels['Season'] = content['number'] if 'number' in content else None
                    infoLabels['SeasonAsin'] = content['titleId'] if 'titleId' in content else None
                    seasontitle = content['title'] if 'title' in content else None
            if 'SeriesAsin' not in infoLabels.keys() and 'SeasonAsin' in infoLabels.keys():
                infoLabels['SeriesAsin'] = infoLabels['SeasonAsin']
                infoLabels['TVShowTitle'] = seasontitle
        else:
            infoLabels['SeriesAsin'] = ''

        if 'number' in item.keys():
            infoLabels['Episode'] = item['number']
            if item['number'] > 0:
                infoLabels['DisplayTitle'] = '%s - %s' % (item['number'], infoLabels['Title'])
            else:
                if ':' in infoLabels['Title']:
                    infoLabels['DisplayTitle'] = infoLabels['Title'].split(':')[1].strip()

    if 'TVShowTitle' in infoLabels:
        infoLabels['TVShowTitle'] = cleanTitle(infoLabels['TVShowTitle'])

    infoLabels = getArtWork(infoLabels, contentType)

    if not export:
        if not infoLabels['Thumb']:
            infoLabels['Thumb'] = DefaultFanart
        if not infoLabels['Fanart']:
            infoLabels['Fanart'] = DefaultFanart
        if not infoLabels['isPrime'] and not contentType == 'series':
            infoLabels['DisplayTitle'] = '[COLOR %s]%s[/COLOR]' % (PayCol, infoLabels['DisplayTitle'])

    return contentType, infoLabels


def PlayVideo(name, asin, adultstr, trailer, forcefb=0):
    isAdult = adultstr == '1'
    amazonUrl = BaseUrl + "/dp/" + (name if UsePrimeVideo else asin)
    playable = False
    fallback = int(addon.getSetting("fallback_method"))
    methodOW = fallback - 1 if forcefb and fallback else playMethod
    videoUrl = "%s/?autoplay=%s" % (amazonUrl, ('trailer' if trailer == 1 else '1'))
    extern = not xbmc.getInfoLabel('Container.PluginName').startswith('plugin.video.amazon')
    fr = ''

    if extern:
        Log('External Call', xbmc.LOGDEBUG)

    while not playable:
        playable = True

        if methodOW == 2 and platform == osAndroid:
            AndroidPlayback(asin, trailer)
        elif methodOW == 3:
            playable = IStreamPlayback(asin, name, trailer, isAdult, extern)
        elif platform != osAndroid:
            ExtPlayback(videoUrl, asin, isAdult, methodOW, fr)

        if not playable or isinstance(playable, unicode):
            if fallback:
                methodOW = fallback - 1
                if isinstance(playable, unicode):
                    fr = playable
                    playable = False
            else:
                xbmc.sleep(500)
                Dialog.ok(getString(30203), getString(30218))
                playable = True

    if methodOW != 3:
        playDummyVid()


def ExtPlayback(videoUrl, asin, isAdult, method, fr):
    waitsec = int(addon.getSetting("clickwait")) * 1000
    waitprepin = int(addon.getSetting("waitprepin")) * 1000
    pin = addon.getSetting("pin")
    waitpin = int(addon.getSetting("waitpin")) * 1000
    pininput = addon.getSetting("pininput") == 'true'
    fullscr = addon.getSetting("fullscreen") == 'true'
    videoUrl += '&playerDebug=true' if verbLog else ''

    xbmc.Player().stop()
    xbmc.executebuiltin('ActivateWindow(busydialog)')

    osLE = False
    if xbmcvfs.exists('/etc/os-release'):
        osLE = 'libreelec' in xbmcvfs.File('/etc/os-release').read()

    suc, url = getCmdLine(videoUrl, asin, method, fr)
    if not suc:
        Dialog.notification(getString(30203), url, xbmcgui.NOTIFICATION_ERROR)
        return

    Log('Executing: %s' % url)
    if platform == osWindows:
        process = subprocess.Popen(url, startupinfo=getStartupInfo())
    else:
        args = shlex.split(url)
        process = subprocess.Popen(args)
        if osLE:
            result = 1
            while result != 0:
                p = subprocess.Popen('pgrep chrome > /dev/null', shell=True)
                p.wait()
                result = p.returncode

    if isAdult and pininput:
        if fullscr:
            waitsec *= 0.75
        else:
            waitsec = waitprepin
        xbmc.sleep(int(waitsec))
        Input(keys=pin)
        waitsec = waitpin

    if fullscr:
        xbmc.sleep(int(waitsec))
        if browser != 0:
            Input(keys='f')
        else:
            Input(mousex=-1, mousey=350, click=2)
            xbmc.sleep(500)
            Input(mousex=9999, mousey=350)

    Input(mousex=9999, mousey=-1)

    xbmc.executebuiltin('Dialog.Close(busydialog)')
    if hasExtRC:
        return

    myWindow = window(process, asin)
    myWindow.wait()


def AndroidPlayback(asin, trailer):
    manu = ''
    if os.access('/system/bin/getprop', os.X_OK):
        manu = check_output(['getprop', 'ro.product.manufacturer'])

    if manu == 'Amazon':
        pkg = 'com.fivecent.amazonvideowrapper'
        act = ''
        url = asin
    else:
        pkg = 'com.amazon.avod.thirdpartyclient'
        act = 'android.intent.action.VIEW'
        url = BaseUrl + '/piv-apk-play?asin=' + asin
        url += '&playTrailer=T' if trailer == 1 else ''

    subprocess.Popen(['log', '-p', 'v', '-t', 'Kodi-Amazon', 'Manufacturer: ' + manu])
    subprocess.Popen(['log', '-p', 'v', '-t', 'Kodi-Amazon', 'Starting App: %s Video: %s' % (pkg, url)])
    Log('Manufacturer: %s' % manu)
    Log('Starting App: %s Video: %s' % (pkg, url))

    if verbLog:
        if os.access('/system/xbin/su', os.X_OK) or os.access('/system/bin/su', os.X_OK):
            Log('Logcat:\n' + check_output(['su', '-c', 'logcat -d | grep -i com.amazon.avod']))
        Log('Properties:\n' + check_output(['sh', '-c', 'getprop | grep -iE "(ro.product|ro.build|google)"']))

    xbmc.executebuiltin('StartAndroidActivity("%s", "%s", "", "%s")' % (pkg, act, url))


def IStreamPlayback(asin, name, trailer, isAdult, extern):
    vMT = ['Feature', 'Trailer', 'LiveStreaming'][trailer]
    dRes = 'PlaybackUrls' if trailer == 2 else 'PlaybackUrls,SubtitleUrls,ForcedNarratives'
    mpaa_str = RestrAges + getString(30171)
    drm_check = addon.getSetting("drm_check") == 'true'
    at_check = addon.getSetting("at_check") == 'true'
    inputstream_helper = Helper('mpd', drm='com.widevine.alpha')

    if not inputstream_helper.check_inputstream():
        Log('No Inputstream Addon found or activated')
        playDummyVid()
        return True

    cookie = MechanizeLogin()
    if not cookie:
        Dialog.notification(getString(30203), getString(30200), xbmcgui.NOTIFICATION_ERROR)
        Log('Login error at playback')
        playDummyVid()
        return True

    mpd, subs = getStreams(*getUrldata('catalog/GetPlaybackResources', asin, extra=True, vMT=vMT,
                                       opt='&titleDecorationScheme=primary-content', dRes=dRes, useCookie=cookie), retmpd=True)

    cj_str = ';'.join(['%s=%s' % (k, v) for k, v in cookie.items()])
    opt = '|Content-Type=application%2Fx-www-form-urlencoded&Cookie=' + urllib.quote_plus(cj_str)
    opt += '|widevine2Challenge=B{SSM}&includeHdcpTestKeyInLicense=true'
    opt += '|JBlicense;hdcpEnforcementResolutionPixels'
    licURL = getUrldata('catalog/GetPlaybackResources', asin, opt=opt, extra=True, vMT=vMT, dRes='Widevine2License', retURL=True)

    if not mpd:
        Dialog.notification(getString(30203), subs, xbmcgui.NOTIFICATION_ERROR)
        playDummyVid()
        return True

    is_version = xbmcaddon.Addon(is_addon).getAddonInfo('version') if is_addon else '0'
    is_binary = xbmc.getCondVisibility('System.HasAddon(kodi.binary.instance.inputstream)')
    orgmpd = mpd
    if trailer != 2:
        mpd = re.sub(r'~', '', mpd)

    if drm_check:
        mpdcontent = getURL(mpd, useCookie=cookie, rjson=False)
        if 'avc1.4D00' in mpdcontent and platform != osAndroid and not is_binary:
            xbmc.executebuiltin('ActivateWindow(busydialog)')
            return extrFr(mpdcontent)
        if mpdcontent.count('EDEF8BA9-79D6-4ACE-A3C8-27DCD51D21ED') > 1 and (platform == osAndroid or is_binary):
            mpd = orgmpd
            at_check = False

    Log(mpd, xbmc.LOGDEBUG)

    if (not extern) or UsePrimeVideo:
        mpaa_check = getListItem('MPAA') in mpaa_str or isAdult
        title = getListItem('Label')
        thumb = getListItem('Art(season.poster)')
        if not thumb:
            thumb = getListItem('Art(tvshow.poster)')
            if not thumb:
                thumb = getListItem('Art(thumb)')
    else:
        content = getATVData('GetASINDetails', 'ASINList=' + asin)['titles'][0]
        ct, Info = getInfos(content, False)
        title = Info['DisplayTitle']
        thumb = Info.get('Poster', Info['Thumb'])
        mpaa_check = str(Info.get('MPAA', mpaa_str)) in mpaa_str or isAdult

    if trailer == 1:
        title += ' (Trailer)'
        Info = {'Plot': getListItem('Plot')}
    if not title:
        title = name

    if mpaa_check and not RequestPin():
        return True

    listitem = xbmcgui.ListItem(label=title, path=mpd)

    if extern or trailer == 1:
        listitem.setInfo('video', getInfolabels(Info))

    if 'adaptive' in is_addon:
        listitem.setProperty('inputstream.adaptive.manifest_type', 'mpd')

    Log('Using %s Version:%s' % (is_addon, is_version))
    listitem.setArt({'thumb': thumb})
    listitem.setSubtitles(subs)
    listitem.setProperty('%s.license_type' % is_addon, 'com.widevine.alpha')
    listitem.setProperty('%s.license_key' % is_addon, licURL)
    listitem.setProperty('%s.stream_headers' % is_addon, 'user-agent=' + getConfig('UserAgent'))
    listitem.setProperty('inputstreamaddon', is_addon)
    listitem.setMimeType('application/dash+xml')
    listitem.setContentLookup(False)
    xbmcplugin.setResolvedUrl(pluginhandle, True, listitem=listitem)

    valid_track = validAudioTrack()

    Log('Video ContentType Movie? %s' % xbmc.getCondVisibility('VideoPlayer.Content(movies)'), 0)
    Log('Video ContentType Episode? %s' % xbmc.getCondVisibility('VideoPlayer.Content(episodes)'), 0)

    if not valid_track and at_check:
        lang = jsonRPC('Player.GetProperties', 'currentaudiostream', {'playerid': 0})['language']
        all_tracks = jsonRPC('Player.GetProperties', 'audiostreams', {'playerid': 0})
        Log(str(all_tracks).replace('},', '}\n'))

        count = 3
        while count and len(all_tracks) > 1:
            cur_track = jsonRPC('Player.GetProperties', 'currentaudiostream', {'playerid': 0})['index']
            all_tracks = [i for i in all_tracks if i['index'] != cur_track]
            Log('Current AudioTrackID %d' % cur_track)
            tracks = all_tracks
            if lang in str(tracks):
                tracks = [i for i in tracks if i['language'] == lang]
            if 'eac3' in str(tracks):
                tracks = [i for i in tracks if i['codec'] == 'eac3']
            chan = max([i['channels'] for i in tracks])
            trackid = -1
            trackbr = 0

            for at in tracks:
                if at['channels'] == chan and at['bitrate'] > trackbr:
                    trackid = at['index']
                    trackbr = at['bitrate']

            if trackid > -1:
                Log('Switching to AudioTrackID %d' % trackid)
                xbmc.Player().setAudioStream(trackid)
                if validAudioTrack():
                    break
            count -= 1
    return True


def validAudioTrack():
    sleeptm = 0.2
    Log('Checking AudioTrack')

    PlayerInfo('Player Starting')
    cac_s = time.time()
    while xbmc.getCondVisibility('!Player.Caching') and cac_s + 5 > time.time():
        sleep(sleeptm)

    PlayerInfo('Player Caching')
    cac_s = time.time()
    while xbmc.getCondVisibility('Player.Caching') and cac_s + 15 > time.time():
        sleep(sleeptm)

    PlayerInfo('Player Resuming')
    chan1_track = xbmc.getInfoLabel('VideoPlayer.AudioChannels')
    sr_track = int(xbmc.getInfoLabel('Player.Process(AudioSamplerate)').replace(',', ''))
    cc_track = xbmc.getInfoLabel('VideoPlayer.AudioCodec')
    ch_track = xbmc.getInfoLabel('Player.Process(AudioChannels)	')
    Log('Codec:%s Samplerate:%s Channels:I(%s)R(%s)' % (cc_track, sr_track, chan1_track, len(ch_track.split(','))))

    if cc_track == 'eac3' and sr_track >= 48000:
        retval = True
    elif cc_track != 'eac3' and sr_track >= 22050:
        retval = True
    else:
        retval = False

    return retval


def PlayerInfo(msg, sleeptm=0.2):
    player = xbmc.Player()
    while not player.isPlayingVideo():
        sleep(sleeptm)
    while player.isPlayingVideo() and (player.getTime() >= player.getTotalTime()):
        sleep(sleeptm)
    if player.isPlayingVideo():
        Log('%s: %s/%s' % (msg, player.getTime(), player.getTotalTime()))
    del player


def getListItem(li):
    return xbmc.getInfoLabel('ListItem.%s' % li).decode('utf-8')


def playDummyVid():
    dummy_video = os.path.join(PluginPath, 'resources', 'dummy.avi')
    xbmcplugin.setResolvedUrl(pluginhandle, True, xbmcgui.ListItem(path=dummy_video))
    Log('Playing Dummy Video', xbmc.LOGDEBUG)
    xbmc.Player().stop()
    return


def check_output(*popenargs, **kwargs):
    p = subprocess.Popen(stdout=subprocess.PIPE, stderr=subprocess.STDOUT, *popenargs, **kwargs)
    out, err = p.communicate()
    retcode = p.poll()
    if retcode != 0:
        c = kwargs.get("args")
        if c is None:
            c = popenargs[0]
            e = subprocess.CalledProcessError(retcode, c)
            e.output = str(out) + str(err)
            Log(e, xbmc.LOGERROR)
    return out.strip()


def getCmdLine(videoUrl, asin, method, fr):
    scr_path = addon.getSetting("scr_path")
    br_path = addon.getSetting("br_path").strip()
    scr_param = addon.getSetting("scr_param").strip()
    kiosk = addon.getSetting("kiosk") == 'true'
    appdata = addon.getSetting("ownappdata") == 'true'
    cust_br = addon.getSetting("cust_path") == 'true'
    nobr_str = getString(30198)
    frdetect = addon.getSetting("framerate") == 'true'

    if method == 1:
        if not xbmcvfs.exists(scr_path):
            return False, nobr_str

        if frdetect:
            suc, fr = getStreams(*getUrldata('catalog/GetPlaybackResources', asin, extra=True, useCookie=True)) if not fr else (True, fr)
            if not suc:
                return False, fr
        else:
            fr = ''

        return True, scr_path + ' ' + scr_param.replace('{f}', fr).replace('{u}', videoUrl)

    os_paths = [None, ('C:\\Program Files\\', 'C:\\Program Files (x86)\\'), ('/usr/bin/', '/usr/local/bin/'), 'open -a ']
    # path(0,win,lin,osx), kiosk, profile, args

    br_config = [[(None, ['Internet Explorer\\iexplore.exe'], '', ''), '-k ', '', ''],
                 [(None, ['Google\\Chrome\\Application\\chrome.exe'],
                   ['google-chrome', 'google-chrome-stable', 'google-chrome-beta', 'chromium-browser'],
                   '"/Applications/Google Chrome.app"'),
                  '--kiosk ', '--user-data-dir=',
                  '--start-maximized --disable-translate --disable-new-tab-first-run --no-default-browser-check --no-first-run '],
                 [(None, ['Mozilla Firefox\\firefox.exe'], ['firefox'], 'firefox'), '', '-profile ', ''],
                 [(None, ['Safari\\Safari.exe'], '', 'safari'), '', '', '']]

    if not cust_br:
        br_path = ''

    if platform != osOSX and not cust_br:
        for path in os_paths[platform]:
            for exe_file in br_config[browser][0][platform]:
                if xbmcvfs.exists(os.path.join(path, exe_file)):
                    br_path = path + exe_file
                    break
                else:
                    Log('Browser %s not found' % (path + exe_file), xbmc.LOGDEBUG)
            if br_path:
                break

    if not xbmcvfs.exists(br_path) and platform != osOSX:
        return False, nobr_str

    br_args = br_config[browser][3]
    if kiosk:
        br_args += br_config[browser][1]
    if appdata and br_config[browser][2]:
        br_args += br_config[browser][2] + '"' + os.path.join(DataPath, str(browser)) + '" '

    if platform == osOSX:
        if not cust_br:
            br_path = os_paths[osOSX] + br_config[browser][0][osOSX]
        if br_args.strip():
            br_args = '--args ' + br_args

    br_path += ' %s"%s"' % (br_args, videoUrl)

    return True, br_path


def getStartupInfo():
    si = subprocess.STARTUPINFO()
    si.dwFlags = subprocess.STARTF_USESHOWWINDOW
    return si


def getStreams(suc, data, retmpd=False):
    HostSet = addon.getSetting("pref_host")
    subUrls = []

    if not suc:
        return False, data

    if retmpd:
        subUrls = parseSubs(data)

    if 'audioVideoUrls' in data.keys():
        hosts = data['audioVideoUrls']['avCdnUrlSets']
    elif 'playbackUrls' in data.keys():
        defid = data['playbackUrls']['defaultUrlSetId']
        h_dict = data['playbackUrls']['urlSets']
        '''
        failover = h_dict[defid]['failover']
        defid_dis = [failover[k]['urlSetId'] for k in failover if failover[k]['mode'] == 'discontinuous']
        defid = defid_dis[0] if defid_dis else defid
        '''
        hosts = [h_dict[k] for k in h_dict]
        hosts.insert(0, h_dict[defid])

    while hosts:
        for cdn in hosts:
            prefHost = False if HostSet not in str(hosts) or HostSet == 'Auto' else HostSet
            cdn_item = cdn

            if 'urls' in cdn:
                cdn = cdn['urls']['manifest']
            if prefHost and prefHost not in cdn['cdn']:
                continue
            Log('Using Host: ' + cdn['cdn'])

            urlset = cdn['avUrlInfoList'][0] if 'avUrlInfoList' in cdn else cdn

            data = getURL(urlset['url'], rjson=False, check=retmpd)
            if not data:
                hosts.remove(cdn_item)
                Log('Host not reachable: ' + cdn['cdn'])
                continue

            return (urlset['url'], subUrls) if retmpd else (True, extrFr(data))

    return False, getString(30217)


def extrFr(data):
    fps_string = re.compile('frameRate="([^"]*)').findall(data)[0]
    fr = round(eval(fps_string + '.0'), 3)
    return str(fr).replace('.0', '')


def parseSubs(data):
    bForcedOnly = False  # Whether or not we should only download forced subtitles
    down_lang = int('0' + addon.getSetting('sub_lang'))
    if 0 == down_lang:
        return []  # Return if the sub_lang is set to None
    lang_main = jsonRPC('Settings.GetSettingValue', param={'setting': 'locale.subtitlelanguage'})
    lang_main = lang_main['value'] if 'value' in lang_main else ''
    
    # Locale.SubtitleLanguage (and .AudioLanguage) can either return a language or:
    # [ S] none: no subtitles
    # [ S] forced_only: forced subtitles only
    # [AS] original: the stream's original language
    # [AS] default: Kodi's UI
    #
    # For simplicity's sake (and temporarily) we will treat original as AudioLanguage, and
    # AudioLanguage 'original' as 'default'
    if lang_main not in ['none', 'forced_only', 'original', 'default']:
        lang_main = xbmc.convertLanguage(lang_main, xbmc.ISO_639_1)
    if 'none' == lang_main:
        return []
    if 'forced_only' == lang_main:
        bForcedOnly = True
    if ('forced_only' == lang_main) or ('original' == lang_main):
        lang_main = jsonRPC('Settings.GetSettingValue', param={'setting': 'locale.audiolanguage'})
        lang_main = lang_main['value'] if 'value' in lang_main else ''
        if lang_main not in ['original', 'default']:
            lang_main = xbmc.convertLanguage(lang_main, xbmc.ISO_639_1)
        if lang_main == 'original':
            lang_main = 'default'
    if 'default' == lang_main:
        lang_main = xbmc.getLanguage(xbmc.ISO_639_1, False)

    # At this point we should have the user's selected language or a valid fallback, although
    # we further sanitize for safety
    lang_main = lang_main if lang_main else xbmc.getLanguage(xbmc.ISO_639_1, False)
    lang_main = lang_main if lang_main else 'en'

    # down_lang: None | All | From Kodi player language settings | From settings, fallback to english | From settings, fallback to all
    lang_main = '' if 1 == down_lang else lang_main
    lang_fallback = None if 3 > down_lang else ('' if 4 == down_lang else 'en')

    localeConversion = {
        'ar-001':'ar',
        'cmn-hans':'zh HANS',
        'cmn-hant':'zh HANT',
        'da-dk':'da',
        'es-419':'es LA',
        'ja-jp':'ja',
        'ko-kr':'ko',
        'nb-no':'nb',
        'sv-se':'sv',
    } # Clean up language and locale information where needed
    subs = []
    if (not down_lang) or (('subtitleUrls' not in data) and ('forcedNarratives' not in data)):
        return subs

    def_subs = []
    fb_subs = []

    for sub in data['subtitleUrls'] + data['forcedNarratives']:
        lang = sub['languageCode'].strip()
        if lang in localeConversion:
            lang = localeConversion[lang]
        # Clean up where needed
        if '-' in lang:
            p1 = re.split('-', lang)[0]
            p2 = re.split('-', lang)[1]
            if (p1 == p2): # Remove redundant locale information when not useful
                lang = p1
            else:
                lang = '%s %s' % (p1, p2.upper())
        # Amazon's en defaults to en_US, not en_UK
        if 'en' == lang:
            lang = 'en US'
        # Read close-caption information where needed
        if '[' in sub['displayName']:
            cc = re.search(r'(\[[^\]]+\])', sub['displayName'])
            if None is not cc:
                lang = lang + (' %s' % cc.group(1))
        # Add forced subs information
        if ' forced ' in sub['displayName']:
            lang = lang + '.Forced'
        if (' forced ' in sub['displayName']) or (False is bForcedOnly):
            sub['languageCode'] = lang
            if lang_main in lang:
                def_subs.append(sub)
            if (None is not lang_fallback) and (lang_fallback in lang):
                fb_subs.append(sub)

    if not def_subs:
        def_subs = fb_subs

    import codecs
    for sub in def_subs:
        escape_chars = [('&amp;', '&'), ('&quot;', '"'), ('&lt;', '<'), ('&gt;', '>'), ('&apos;', "'")]
        srtfile = xbmc.translatePath('special://temp/%s.srt' % sub['languageCode']).decode('utf-8')
        subDisplayLang = '“%s” subtitle (%s)' % (sub['displayName'].strip(), sub['languageCode'])
        content = ''
        with codecs.open(srtfile, 'w', encoding='utf-8') as srt:
            num = 0
            # Since .srt are available on amazon's servers, we strip the default extension and try downloading it just once
            subUrl = re.search(r'^(.*?\.)[^.]{1,}$', sub['url'])
            content = '' if None is subUrl else getURL(subUrl.group(1) + 'srt', rjson=False, attempt=777)
            if 0 < len(content):
                Log('Downloaded %s' % subDisplayLang)
                srt.write(content)
            else:
                content = getURL(sub['url'], rjson=False, attempt=3)
                if 0 < len(content):
                    Log('Converting %s' % subDisplayLang)
                    for tt in re.compile('<tt:p(.*)').findall(content):
                        tt = re.sub('<tt:br[^>]*>', '\n', tt)
                        tt = re.search(r'begin="([^"]*).*end="([^"]*).*>([^<]*).', tt)
                        subtext = tt.group(3)
                        for ec in escape_chars:
                            subtext = subtext.replace(ec[0], ec[1])
                        if tt:
                            num += 1
                            srt.write('%s\n%s --> %s\n%s\n\n' % (num, tt.group(1), tt.group(2), subtext))
        if 0 == len(content):
            Log('Unable to download %s' % subDisplayLang)
        else:
            subs.append(srtfile)
    return subs


def getUrldata(mode, asin, retformat='json', devicetypeid='AOAGZA014O5RE', version=1, firmware='1', opt='', extra=False,
               useCookie=False, retURL=False, vMT='Feature', dRes='PlaybackUrls,SubtitleUrls,ForcedNarratives'):
    url = ATVUrl + '/cdp/' + mode
    url += '?asin=' + asin
    url += '&deviceTypeID=' + devicetypeid
    url += '&firmware=' + firmware
    url += '&deviceID=' + deviceID
    url += '&marketplaceID=' + MarketID
    url += '&format=' + retformat
    url += '&version=' + str(version)
    if extra:
        url += '&resourceUsage=ImmediateConsumption&consumptionType=Streaming&deviceDrmOverride=CENC' \
               '&deviceStreamingTechnologyOverride=DASH&deviceProtocolOverride=Https' \
               '&deviceBitrateAdaptationsOverride=CVBR%2CCBR&audioTrackId=all'
        if UsePrimeVideo:
            url += '&gascEnabled=true'
        url += '&videoMaterialType=' + vMT
        url += '&desiredResources=' + dRes
        url += '&supportedDRMKeyScheme=DUAL_KEY' if platform != osAndroid and 'PlaybackUrls' in dRes else ''
    url += opt
    if retURL:
        return url
    data = getURL(url, useCookie=useCookie, silent=True)
    if data:
        if 'error' in data.keys():
            return False, Error(data['error'])
        elif 'AudioVideoUrls' in data.get('errorsByResource', ''):
            return False, Error(data['errorsByResource']['AudioVideoUrls'])
        elif 'PlaybackUrls' in data.get('errorsByResource', ''):
            return False, Error(data['errorsByResource']['PlaybackUrls'])
        else:
            return True, data
    return False, 'HTTP Error'


def Error(data):
    code = data['errorCode'].lower()
    Log('%s (%s) ' % (data['message'], code), xbmc.LOGERROR)
    if 'invalidrequest' in code:
        return getString(30204)
    elif 'noavailablestreams' in code:
        return getString(30205)
    elif 'notowned' in code:
        return getString(30206)
    elif 'invalidgeoip' or 'dependency' in code:
        return getString(30207)
    elif 'temporarilyunavailable' in code:
        return getString(30208)
    else:
        return '%s (%s) ' % (data['message'], code)


def Input(mousex=0, mousey=0, click=0, keys=None, delay='200'):
    screenWidth = int(xbmc.getInfoLabel('System.ScreenWidth'))
    screenHeight = int(xbmc.getInfoLabel('System.ScreenHeight'))
    keys_only = sc_only = keybd = ''
    mousex = screenWidth / 2 if mousex == -1 else mousex
    mousey = screenHeight / 2 if mousey == -1 else mousey

    spec_keys = {'{EX}': ('!{F4}', 'control+shift+q', 'kd:cmd t:q ku:cmd'),
                 '{SPC}': ('{SPACE}', 'space', 't:p'),
                 '{LFT}': ('{LEFT}', 'Left', 'kp:arrow-left'),
                 '{RGT}': ('{RIGHT}', 'Right', 'kp:arrow-right'),
                 '{U}': ('{UP}', 'Up', 'kp:arrow-up'),
                 '{DWN}': ('{DOWN}', 'Down', 'kp:arrow-down'),
                 '{BACK}': ('{BS}', 'BackSpace', 'kp:delete'),
                 '{RET}': ('{ENTER}', 'Return', 'kp:return')}

    if keys:
        keys_only = keys
        for sc in spec_keys:
            while sc in keys:
                keys = keys.replace(sc, spec_keys[sc][platform - 1]).strip()
                keys_only = keys_only.replace(sc, '').strip()
        sc_only = keys.replace(keys_only, '').strip()

    if platform == osWindows:
        app = os.path.join(PluginPath, 'tools', 'userinput.exe')
        mouse = ' mouse %s %s' % (mousex, mousey)
        mclk = ' ' + str(click)
        keybd = ' key %s %s' % (keys, delay)
    elif platform == osLinux:
        app = 'xdotool'
        mouse = ' mousemove %s %s' % (mousex, mousey)
        mclk = ' click --repeat %s 1' % click
        if keys_only:
            keybd = ' type --delay %s %s' % (delay, keys_only)
        if sc_only:
            if keybd:
                keybd += ' && ' + app
            keybd += ' key ' + sc_only
    elif platform == osOSX:
        app = 'cliclick'
        mouse = ' m:'
        if click == 1:
            mouse = ' c:'
        elif click == 2:
            mouse = ' dc:'
        mouse += '%s,%s' % (mousex, mousey)
        mclk = ''
        keybd = ' -w %s' % delay
        if keys_only:
            keybd += ' t:%s' % keys_only
        if keys != keys_only:
            keybd += ' ' + sc_only

    if keys:
        cmd = app + keybd
    else:
        cmd = app + mouse
        if click:
            cmd += mclk

    Log('Run command: %s' % cmd)
    rcode = subprocess.call(cmd, shell=True)

    if rcode:
        Log('Returncode: %s' % rcode)


def genID(renew=False):
    guid = getConfig("GenDeviceID") if not renew else False
    if not guid or len(guid) != 56:
        guid = hmac.new(getConfig('UserAgent'), uuid.uuid4().bytes, hashlib.sha224).hexdigest()
        writeConfig("GenDeviceID", guid)
    return guid


def MechanizeLogin():
    cj = requests.cookies.RequestsCookieJar()
    cookie = loadUser('cookie')

    if cookie:
        cj.update(pickle.loads(cookie))
        return cj

    Log('Login')
    return LogIn(False)


def LogIn(ask=True):
    user = loadUser(empty=ask)
    email = user['email']
    password = decode(user['password'])
    savelogin = addon.getSetting('save_login') == 'true'
    useMFA = False

    if not user['baseurl']:
        user = getTerritory(user)
        if False is user[1]:
            return False
        user = user[0]

    if ask:
        keyboard = xbmc.Keyboard(email, getString(30002))
        keyboard.doModal()
        if keyboard.isConfirmed() and keyboard.getText():
            email = keyboard.getText()
            password = setLoginPW()
    else:
        if not email or not password:
            Dialog.notification(getString(30200), getString(30216))
            xbmc.executebuiltin('Addon.OpenSettings(%s)' % addon.getAddonInfo('id'))
            return False

    if password:
        xbmc.executebuiltin('ActivateWindow(busydialog)')
        cj = requests.cookies.RequestsCookieJar()
        br = mechanize.Browser()
        br.set_handle_robots(False)
        br.set_cookiejar(cj)
        br.set_handle_gzip(True)
        caperr = -5
        while caperr:
            Log('Connect to SignIn Page %s attempts left' % -caperr)
            br.addheaders = [('User-Agent', getConfig('UserAgent'))]
            br.open(user['baseurl'] + ('/gp/aw/si.html' if not user['pv'] else '/auth-redirect/'))
            response = br.response().read()
            if mobileUA(response) or 'signIn' not in [i.name for i in br.forms()]:
                getUA(True)
                caperr += 1
                WriteLog(response, 'login-si')
                xbmc.sleep(randint(750, 1500))
            else:
                break
        else:
            xbmc.executebuiltin('Dialog.Close(busydialog)')
            Dialog.ok(getString(30200), getString(30213))
            return False

        br.select_form(name='signIn')
        br['email'] = email
        br['password'] = password
        if 'true' == addon.getSetting('rememberme') and user['pv']:
            br.find_control(name='rememberMe').items[0].selected = True
        br.addheaders = [('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'),
                         ('Accept-Encoding', 'gzip, deflate'),
                         ('Accept-Language', userAcceptLanguages),
                         ('Cache-Control', 'max-age=0'),
                         ('Connection', 'keep-alive'),
                         ('Content-Type', 'application/x-www-form-urlencoded'),
                         ('Host', user['baseurl'].split('//')[1]),
                         ('Origin', user['baseurl']),
                         ('User-Agent', getConfig('UserAgent')),
                         ('Upgrade-Insecure-Requests', '1')]
        br.submit()
        response, soup = parseHTML(br)
        xbmc.executebuiltin('Dialog.Close(busydialog)')
        WriteLog(response, 'login')

        while any(s in response for s in ['auth-mfa-form', 'ap_dcq_form', 'ap_captcha_img_label', 'claimspicker', 'fwcim-form']):
            br = MFACheck(br, email, soup)
            if not br:
                return False
            useMFA = 'otpCode' in str(list(br.forms())[0])
            br.submit()
            response, soup = parseHTML(br)
            WriteLog(response, 'login-mfa')
            xbmc.executebuiltin('Dialog.Close(busydialog)')

        if 'action=sign-out' in response:
            regex = r'action=sign-out[^"]*"[^>]*>[^?]+\s+([^?]+?)\s*\?' if user['pv'] else r'config.customerName[^"]*"([^"]*)'
            try:
                usr = re.search(regex, response).group(1)
            except AttributeError:
                usr = getString(30209)

            if multiuser and ask:
                usr = Dialog.input(getString(30135), usr).decode('utf-8')
                if not usr:
                    return False
            if useMFA:
                addon.setSetting('save_login', 'false')
                savelogin = False

            user['name'] = usr
            user['email'] = user['password'] = user['cookie'] = ''

            if savelogin:
                user['email'] = email
                user['password'] = encode(password)
            else:
                user['cookie'] = pickle.dumps(cj)

            if ask:
                remLoginData(False)
                addon.setSetting('login_acc', usr)
                if not multiuser:
                    Dialog.ok(getString(30215), '{0} {1}'.format(getString(30014), usr))

            addUser(user)
            genID()
            return cj
        elif 'message_error' in response:
            writeConfig('login_pass', '')
            msg = soup.find('div', attrs={'id': 'message_error'})
            Log('Login Error: %s' % msg.p.renderContents(None).strip())
            Dialog.ok(getString(30200), getString(30201))
        elif 'message_warning' in response:
            msg = soup.find('div', attrs={'id': 'message_warning'})
            Log('Login Warning: %s' % msg.p.renderContents(None).strip())
        elif 'auth-error-message-box' in response:
            msg = soup.find('div', attrs={'class': 'a-alert-content'})
            Log('Login MFA: %s' % msg.ul.li.span.renderContents(None).strip())
            Dialog.ok(getString(30200), getString(30214))
        else:
            Dialog.ok(getString(30200), getString(30213))

    return False


def loadUsers():
    users = json.loads(getConfig('accounts.lst', '[]'))
    if not users:
        addon.setSetting('login_acc', '')
    return users


def loadUser(key='', empty=False):
    def_keys = {'email': '', 'password': '', 'name': '', 'save': '', 'atvurl': '', 'baseurl': '', 'pv': False, 'mid': '', 'cookie': ''}
    cur_user = addon.getSetting('login_acc').decode('utf-8')
    users = loadUsers()
    user = None if empty else [i for i in users if cur_user == i['name']]
    if user:
        user = user[0]
        if key and key not in user.keys():
            user = getTerritory(user)
            if False is user[1]:
                Dialog.notification(__plugin__, getString(30219), xbmcgui.NOTIFICATION_ERROR)
            user = user[0]
            addUser(user)
        return user.get(key, user)
    else:
        return def_keys.get(key, def_keys)


def addUser(user):
    user['save'] = addon.getSetting('save_login')
    users = loadUsers() if multiuser else []
    num = [n for n, i in enumerate(users) if user['name'] == i['name']]
    if num:
        users[num[0]] = user
    else:
        users.append(user)
    writeConfig('accounts.lst', json.dumps(users))
    if xbmc.getInfoLabel('Container.FolderPath') == sys.argv[0]:
        xbmc.executebuiltin('Container.Refresh')


def switchUser(sel=-1):
    users = loadUsers()
    sel = Dialog.select(getString(30133), [i['name'] for i in users]) if sel < 0 else sel
    if sel > -1:
        if loadUser('name') == users[sel]['name']:
            return False
        user = users[sel]
        addon.setSetting('save_login', user['save'])
        addon.setSetting('login_acc', user['name'])
        xbmc.executebuiltin('Container.Refresh')
    return -1 < sel


def removeUser():
    cur_user = loadUser('name')
    users = loadUsers()
    sel = Dialog.select(getString(30133), [i['name'] for i in users])
    if sel > -1:
        user = users[sel]
        users.remove(user)
        writeConfig('accounts.lst', json.dumps(users))
        if user['name'] == cur_user:
            addon.setSetting('login_acc', '')
            if not switchUser():
                xbmc.executebuiltin('Container.Refresh')


def renameUser():
    cur_user = loadUser('name')
    users = loadUsers()
    sel = Dialog.select(getString(30133), [i['name'] for i in users])
    if sel > -1:
        keyboard = xbmc.Keyboard(users[sel]['name'], getString(30135))
        keyboard.doModal()
        if keyboard.isConfirmed() and keyboard.getText():
            usr = keyboard.getText()
            if users[sel]['name'] == cur_user:
                addon.setSetting('login_acc', usr)
                xbmc.executebuiltin('Container.Refresh')
            users[sel]['name'] = usr
            writeConfig('accounts.lst', json.dumps(users))


def getTerritory(user):
    Log('Retrieve territoral config')

    data = getURL('https://na.api.amazonvideo.com/cdp/usage/v2/GetAppStartupConfig?deviceTypeID=A28RQHJKHM2A2W&deviceID=%s&firmware=1&version=1&format=json'
                  % deviceID)
    if not hasattr(data, 'keys'):
        return (user, False)
    if 'customerConfig' in data.keys():
        host = data['territoryConfig']['defaultVideoWebsite']
        reg = data['customerConfig']['homeRegion'].lower()
        reg = '' if 'na' in reg else '-' + reg
        user['atvurl'] = host.replace('www.', '').replace('//', '//atv-ps%s.' % reg)
        user['baseurl'] = data['territoryConfig']['primeSignupBaseUrl']
        user['mid'] = data['territoryConfig']['avMarketplace']
        user['pv'] = 'primevideo' in host
    return (user, True)


def MFACheck(br, email, soup):
    Log('MFA, DCQ or Captcha form')
    uni_soup = unicode(soup)
    if 'auth-mfa-form' in uni_soup:
        msg = soup.find('form', attrs={'id': 'auth-mfa-form'})
        msgtxt = msg.p.renderContents().strip()
        kb = xbmc.Keyboard('', msgtxt)
        kb.doModal()
        if kb.isConfirmed() and kb.getText():
            xbmc.executebuiltin('ActivateWindow(busydialog)')
            br.select_form(nr=0)
            br['otpCode'] = kb.getText()
            # br.find_control('rememberDevice').items[0].selected = True
        else:
            return False
    elif 'ap_dcq_form' in uni_soup:
        msg = soup.find('div', attrs={'id': 'message_warning'})
        Dialog.ok(__plugin__, msg.p.contents[0].strip())
        dcq = soup.find('div', attrs={'id': 'ap_dcq1a_pagelet'})
        dcq_title = dcq.find('div', attrs={'id': 'ap_dcq1a_pagelet_title'}).h1.contents[0].strip()
        q_title = []
        q_id = []
        for q in dcq.findAll('div', attrs={'class': 'dcq_question'}):
            if q.span.label:
                label = q.span.label.renderContents().strip().replace('  ', '').replace('\n', '')
                if q.span.label.span:
                    label = label.replace(str(q.span.label.span), q.span.label.span.text)
                q_title.append(insertLF(label))
                q_id.append(q.input['id'])

        sel = Dialog.select(insertLF(dcq_title, 60), q_title) if len(q_title) > 1 else 0
        if sel < 0:
            return False

        ret = Dialog.input(q_title[sel])
        if ret:
            xbmc.executebuiltin('ActivateWindow(busydialog)')
            br.select_form(nr=0)
            br[q_id[sel]] = ret
        else:
            return False
    elif 'ap_captcha_img_label' in uni_soup:
        wnd = Captcha((getString(30008).split('…')[0]), soup, email)
        wnd.doModal()
        if wnd.email and wnd.cap and wnd.pwd:
            xbmc.executebuiltin('ActivateWindow(busydialog)')
            br.select_form(nr=0)
            br['email'] = wnd.email
            br['password'] = wnd.pwd
            br['guess'] = wnd.cap
        else:
            return False
        del wnd
    elif 'claimspicker' in uni_soup:
        msg = soup.find('form', attrs={'name': 'claimspicker'})
        cs_title = msg.find('div', attrs={'class': 'a-row a-spacing-small'})
        cs_title = cs_title.h1.contents[0].strip()
        cs_quest = msg.find('label', attrs={'class': 'a-form-label'})
        cs_hint = msg.find('div', attrs={'class': 'a-row'}).contents[0].strip()
        choices = []
        if cs_quest:
            for c in soup.findAll('div', attrs={'data-a-input-name': 'option'}):
                choices.append((c.span.contents[0].strip(), c.input['name'], c.input['value']))
            sel = Dialog.select('%s - %s' % (cs_title, cs_quest.contents[0].strip()), [k[0] for k in choices])
        else:
            sel = 100 if Dialog.ok(cs_title, cs_hint) else -1

        if sel > -1:
            xbmc.executebuiltin('ActivateWindow(busydialog)')
            br.select_form(nr=0)
            if sel < 100:
                br[choices[sel][1]] = [choices[sel][2]]
        else:
            return False
    elif 'fwcim-form' in uni_soup:
        msg = soup.find('div', attrs={'class': 'a-row a-spacing-micro cvf-widget-input-code-label'}).contents[0].strip()
        ret = Dialog.input(msg)
        if ret:
            xbmc.executebuiltin('ActivateWindow(busydialog)')
            br.select_form(nr=0)
            Log(br)
            br['code'] = ret
        else:
            return False
    return br


def setLoginPW():
    keyboard = xbmc.Keyboard('', getString(30003))
    keyboard.doModal(60000)
    if keyboard.isConfirmed() and keyboard.getText():
        password = keyboard.getText()
        return password
    return False


def encode(data):
    k = triple_des(getmac(), CBC, b"\0\0\0\0\0\0\0\0", padmode=PAD_PKCS5)
    d = k.encrypt(data)
    return b64encode(d)


def decode(data):
    if not data:
        return ''
    k = triple_des(getmac(), CBC, b"\0\0\0\0\0\0\0\0", padmode=PAD_PKCS5)
    d = k.decrypt(b64decode(data))
    return d


def getmac():
    mac = uuid.getnode()
    if (mac >> 40) % 2:
        mac = node()
    return uuid.uuid5(uuid.NAMESPACE_DNS, str(mac)).bytes


def remLoginData(info=True):
    for fn in xbmcvfs.listdir(DataPath)[1]:
        if fn.startswith('cookie'):
            xbmcvfs.delete(os.path.join(DataPath, fn))
    writeConfig('accounts', '')
    writeConfig('login_name', '')
    writeConfig('login_pass', '')

    if info:
        writeConfig('accounts.lst', '')
        addon.setSetting('login_acc', '')
        Dialog.notification(__plugin__, getString(30211), xbmcgui.NOTIFICATION_INFO)


def scrapAsins(aurl, cj):
    asins = []
    url = BaseUrl + aurl
    content = getURL(url, useCookie=cj, rjson=False)
    WriteLog(content, 'watchlist')
    if mobileUA(content):
        getUA(True)

    for asin in re.compile('(?:data-asin|data-asinlist)="(.+?)"', re.DOTALL).findall(content):
        if asin not in asins:
            asins.append(asin)
    return ','.join(asins)


def createDB(menu=False):
    if menu:
        c = menuDb.cursor()
        c.execute('drop table if exists menu')
        c.execute('''CREATE TABLE menu(
                    node TEXT,
                    title TEXT,
                    category TEXT,
                    content TEXT,
                    id TEXT,
                    infolabel TEXT
                    );''')
        menuDb.commit()
    else:
        c = db.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS art(
                    asin TEXT,
                    season INTEGER,
                    poster TEXT,
                    banner TEXT,
                    fanart TEXT,
                    lastac DATE,
                    PRIMARY KEY(asin, season)
                    );''')
        c.execute('''CREATE TABLE IF NOT EXISTS miss(
                    asins TEXT,
                    title TEXT,
                    year TEXT,
                    content TEXT,
                    PRIMARY KEY(asins, title)
                    );''')
        db.commit()
    c.close()


def cleanName(name, isfile=True):
    notallowed = ['<', '>', ':', '"', '\\', '/', '|', '*', '?']
    if not isfile:
        notallowed = ['<', '>', '"', '|', '*', '?']
    for c in notallowed:
        name = name.replace(c, '')
    if not os.path.supports_unicode_filenames and not isfile:
        name = name.encode('utf-8')
    return name


def SaveFile(filename, data, isdir=None, mode='w'):
    if isinstance(data, unicode):
        data = data.encode('utf-8')
    if isdir:
        filename = cleanName(filename)
        filename = os.path.join(isdir, filename)
        if not xbmcvfs.exists(isdir):
            xbmcvfs.mkdirs(cleanName(isdir.strip(), isfile=False))
    filename = cleanName(filename, isfile=False)
    outfile = xbmcvfs.File(filename, mode)
    outfile.write(data)
    outfile.close()


def CreateDirectory(dir_path):
    dir_path = cleanName(dir_path.strip(), isfile=False)
    if not xbmcvfs.exists(dir_path):
        return xbmcvfs.mkdirs(dir_path)
    return False


def SetupLibrary():
    CreateDirectory(MOVIE_PATH)
    CreateDirectory(TV_SHOWS_PATH)
    SetupAmazonLibrary()


def CreateInfoFile(nfofile, path, content, Info, language, hasSubtitles=False):
    skip_keys = ('ishd', 'isadult', 'audiochannels', 'genre', 'cast', 'duration', 'asins', 'contentType')
    fileinfo = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>'
    fileinfo += '<%s>' % content
    if 'Duration' in Info.keys():
        fileinfo += '<runtime>%s</runtime>' % Info['Duration']
    if 'Genre' in Info.keys():
        for genre in Info['Genre'].split('/'):
            fileinfo += '<genre>%s</genre>' % genre.strip()
    if 'Cast' in Info.keys():
        for actor in Info['Cast']:
            fileinfo += '<actor>'
            fileinfo += '<name>%s</name>' % actor.strip()
            fileinfo += '</actor>'
    for key, value in Info.items():
        lkey = key.lower()
        if lkey == 'tvshowtitle':
            fileinfo += '<showtitle>%s</showtitle>' % value
        elif lkey == 'premiered' and 'TVShowTitle' in Info:
            fileinfo += '<aired>%s</aired>' % value
        elif lkey == 'fanart':
            fileinfo += '<%s><thumb>%s</thumb></%s>' % (lkey, value, lkey)
        elif lkey not in skip_keys:
            fileinfo += '<%s>%s</%s>' % (lkey, value, lkey)
    if content != 'tvshow':
        fileinfo += '<fileinfo>'
        fileinfo += '<streamdetails>'
        fileinfo += '<audio>'
        fileinfo += '<channels>%s</channels>' % Info['AudioChannels']
        fileinfo += '<codec>aac</codec>'
        fileinfo += '</audio>'
        fileinfo += '<video>'
        fileinfo += '<codec>h264</codec>'
        fileinfo += '<durationinseconds>%s</durationinseconds>' % Info['Duration']
        if Info['isHD']:
            fileinfo += '<height>1080</height>'
            fileinfo += '<width>1920</width>'
        else:
            fileinfo += '<height>480</height>'
            fileinfo += '<width>720</width>'
        if language:
            fileinfo += '<language>%s</language>' % language
        fileinfo += '<scantype>Progressive</scantype>'
        fileinfo += '</video>'
        if hasSubtitles:
            fileinfo += '<subtitle>'
            fileinfo += '<language>ger</language>'
            fileinfo += '</subtitle>'
        fileinfo += '</streamdetails>'
        fileinfo += '</fileinfo>'
    fileinfo += '</%s>' % content

    SaveFile(nfofile + '.nfo', fileinfo, path)
    return


def SetupAmazonLibrary():
    source_path = xbmc.translatePath('special://profile/sources.xml').decode('utf-8')
    source_added = False
    source = {ms_mov: MOVIE_PATH, ms_tv: TV_SHOWS_PATH}

    if xbmcvfs.exists(source_path):
        srcfile = xbmcvfs.File(source_path)
        soup = BeautifulSoup(srcfile)
        srcfile.close()
    else:
        subtags = ['programs', 'video', 'music', 'pictures', 'files']
        soup = BeautifulSoup('<sources></sources>')
        root = soup.sources
        for cat in subtags:
            cat_tag = Tag(soup, cat)
            def_tag = Tag(soup, 'default')
            def_tag['pathversion'] = 1
            cat_tag.append(def_tag)
            root.append(cat_tag)

    video = soup.find("video")

    for name, path in source.items():
        path_tag = Tag(soup, "path")
        path_tag['pathversion'] = 1
        path_tag.append(path)
        source_text = soup.find(text=name)
        if not source_text:
            source_tag = Tag(soup, "source")
            name_tag = Tag(soup, "name")
            name_tag.append(name)
            source_tag.append(name_tag)
            source_tag.append(path_tag)
            video.append(source_tag)
            Log(name + ' source path added!')
            source_added = True
        else:
            source_tag = source_text.findParent('source')
            old_path = source_tag.find('path').contents[0]
            if path not in old_path:
                source_tag.find('path').replaceWith(path_tag)
                Log(name + ' source path changed!')
                source_added = True

    if source_added:
        SaveFile(source_path, str(soup))
        Dialog.ok(getString(30187), getString(30188), getString(30189), getString(30190))
        if Dialog.yesno(getString(30191), getString(30192)):
            xbmc.executebuiltin('RestartApp')


def RequestPin():
    if AgePin:
        pin = Dialog.input('PIN', type=xbmcgui.INPUT_ALPHANUM, option=xbmcgui.ALPHANUM_HIDE_INPUT)
        return True if pin == AgePin else False
    return True


def getConfig(cfile, defvalue=''):
    cfgfile = os.path.join(ConfigPath, cfile)

    value = ''
    if xbmcvfs.exists(cfgfile):
        f = xbmcvfs.File(cfgfile, 'r')
        value = f.read()
        f.close()

    return value if value else defvalue


def writeConfig(cfile, value):
    cfgfile = os.path.join(ConfigPath, cfile)
    cfglockfile = os.path.join(ConfigPath, cfile + '.lock')

    if not xbmcvfs.exists(ConfigPath):
        xbmcvfs.mkdirs(ConfigPath)

    while True:
        if not xbmcvfs.exists(cfglockfile):
            l = xbmcvfs.File(cfglockfile, 'w')
            l.write(str(time.time()))
            l.close()
            if value == '':
                xbmcvfs.delete(cfgfile)
            else:
                f = xbmcvfs.File(cfgfile, 'w')
                f.write(value.__str__())
                f.close()
            xbmcvfs.delete(cfglockfile)
            return True
        else:
            l = xbmcvfs.File(cfglockfile)
            modified = float(l.read())
            l.close()
            if time.time() - modified > 0.1:
                xbmcvfs.delete(cfglockfile)


def insertLF(string, begin=70):
    spc = string.find(' ', begin)
    return string[:spc] + '\n' + string[spc + 1:] if spc > 0 else string


def parseHTML(br):
    response = br.response().read().decode('utf-8')
    response = re.sub(r'(?i)(<!doctype \w+).*>', r'\1>', response)
    soup = BeautifulSoup(response, convertEntities=BeautifulSoup.HTML_ENTITIES)
    return response, soup


def SetVol(step):
    vol = jsonRPC('Application.GetProperties', 'volume')
    xbmc.executebuiltin('SetVolume(%d,showVolumeBar)' % (vol + step))


def getUA(blacklist=False):
    Log('Switching UserAgent')
    UAlist = json.loads(getConfig('UAlist', json.dumps([])))
    UAblist = json.loads(getConfig('UABlacklist', json.dumps([])))

    if blacklist:
        UAcur = getConfig('UserAgent')
        if UAcur not in UAblist:
            UAblist.append(UAcur)
            writeConfig('UABlacklist', json.dumps(UAblist))
            Log('UA: %s blacklisted' % UAcur)

    UAwlist = [i for i in UAlist if i not in UAblist]
    if not UAlist or len(UAwlist) < 5:
        Log('Loading list of common UserAgents')
        html = getURL('https://techblog.willshouse.com/2012/01/03/most-common-user-agents/', rjson=False)
        soup = BeautifulSoup(html, convertEntities=BeautifulSoup.HTML_ENTITIES)
        text = soup.find('textarea')
        UAlist = text.string.split('\n')
        UAblist = []
        writeConfig('UABlacklist', json.dumps(UAblist))
        writeConfig('UAlist', json.dumps(UAlist[0:len(UAlist) - 1]))
        UAwlist = UAlist

    UAnew = UAwlist[randint(0, len(UAwlist) - 1)] if UAwlist else \
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/59.0.3071.115 Safari/537.36'
    writeConfig('UserAgent', UAnew)
    Log('Using UserAgent: ' + UAnew)
    return


def mobileUA(content):
    soup = BeautifulSoup(content, convertEntities=BeautifulSoup.HTML_ENTITIES)
    res = soup.find('html')
    res = res.get('class', '') if res else ''
    return True if 'a-mobile' in res or 'a-tablet' in res else False


def sleep(sec):
    if xbmc.Monitor().waitForAbort(sec):
        return


def getInfolabels(Infos):
    rem_keys = ('ishd', 'isprime', 'asins', 'audiochannels', 'banner', 'displaytitle', 'fanart', 'poster', 'seasonasin',
                'thumb', 'traileravailable', 'contenttype', 'isadult', 'totalseasons', 'seriesasin', 'episodename')
    if not Infos:
        return
    return {k: v for k, v in Infos.items() if k.lower() not in rem_keys}


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

    return res['result'].get(props, res['result'])


class window(xbmcgui.WindowDialog):
    def __init__(self, process, asin):
        xbmcgui.WindowDialog.__init__(self)
        self._stopEvent = threading.Event()
        self._pbStart = time.time()
        self._wakeUpThread = threading.Thread(target=self._wakeUpThreadProc, args=(process,))
        self._vidDur = self.getDuration(asin)

    def _wakeUpThreadProc(self, process):
        starttime = time.time()
        while not self._stopEvent.is_set():
            if time.time() > starttime + 60:
                starttime = time.time()
                xbmc.executebuiltin("playercontrol(wakeup)")
            if process:
                process.poll()
                if process.returncode is not None:
                    self.close()
            self._stopEvent.wait(1)

    def wait(self):
        Log('Starting Thread')
        self._wakeUpThread.start()
        self.doModal()
        self._wakeUpThread.join()

    @staticmethod
    def getDuration(asin):
        li_dur = xbmc.getInfoLabel('ListItem.Duration')
        if li_dur:
            if ':' in li_dur:
                return sum(i * int(t) for i, t in zip([3600, 60, 1], li_dur.split(":")))
            return int(li_dur) * 60
        else:
            content = getATVData('GetASINDetails', 'ASINList=' + asin)['titles'][0]
            ct, Info = getInfos(content, False)
            return int(Info.get('Duration', 0))

    def close(self):
        Log('Stopping Thread')
        self._stopEvent.set()
        xbmcgui.WindowDialog.close(self)
        watched = xbmc.getInfoLabel('Listitem.PlayCount')
        pBTime = time.time() - self._pbStart
        Log('Dur:%s State:%s PlbTm:%s' % (self._vidDur, watched, pBTime), xbmc.LOGDEBUG)

        if pBTime > self._vidDur * 0.9 and not watched:
            xbmc.executebuiltin("Action(ToggleWatched)")

    def onAction(self, action):
        if not useIntRC:
            return

        ACTION_SELECT_ITEM = 7
        ACTION_PARENT_DIR = 9
        ACTION_PREVIOUS_MENU = 10
        ACTION_PAUSE = 12
        ACTION_STOP = 13
        ACTION_SHOW_INFO = 11
        ACTION_SHOW_GUI = 18
        ACTION_MOVE_LEFT = 1
        ACTION_MOVE_RIGHT = 2
        ACTION_MOVE_UP = 3
        ACTION_MOVE_DOWN = 4
        ACTION_PLAYER_PLAY = 79
        ACTION_NAV_BACK = 92
        KEY_BUTTON_BACK = 275
        ACTION_MOUSE_MOVE = 107

        actionId = action.getId()
        showinfo = action == ACTION_SHOW_INFO
        Log('Action: Id:%s ButtonCode:%s' % (actionId, action.getButtonCode()))

        if action in [ACTION_SHOW_GUI, ACTION_STOP, ACTION_PARENT_DIR, ACTION_PREVIOUS_MENU, ACTION_NAV_BACK,
                      KEY_BUTTON_BACK, ACTION_MOUSE_MOVE]:
            Input(keys='{EX}')
        elif action in [ACTION_SELECT_ITEM, ACTION_PLAYER_PLAY, ACTION_PAUSE]:
            Input(keys='{SPC}')
            showinfo = True
        elif action == ACTION_MOVE_LEFT:
            Input(keys='{LFT}')
            showinfo = True
        elif action == ACTION_MOVE_RIGHT:
            Input(keys='{RGT}')
            showinfo = True
        elif action == ACTION_MOVE_UP:
            SetVol(+2) if RMC_vol else Input(keys='{U}')
        elif action == ACTION_MOVE_DOWN:
            SetVol(-2) if RMC_vol else Input(keys='{DWN}')
        # numkeys for pin input
        elif 57 < actionId < 68:
            strKey = str(actionId - 58)
            Input(keys=strKey)

        if showinfo:
            Input(9999, 0)
            xbmc.sleep(500)
            Input(9999, -1)


class AgeSettings(pyxbmct.AddonDialogWindow):
    def __init__(self, title=''):
        super(AgeSettings, self).__init__(title)
        self.age_list = [age[0] for age in Ages]
        self.pin_req = PinReq
        self.pin = pyxbmct.Edit('', _alignment=pyxbmct.ALIGN_CENTER)
        self.btn_ages = pyxbmct.Button(self.age_list[self.pin_req])
        self.btn_save = pyxbmct.Button(getString(30122))
        self.btn_close = pyxbmct.Button(getString(30123))
        self.setGeometry(500, 300, 5, 2)
        self.set_controls()
        self.set_navigation()

    def set_controls(self):
        self.placeControl(pyxbmct.Label(getString(30120), alignment=pyxbmct.ALIGN_CENTER_Y), 1, 0)
        self.placeControl(self.pin, 1, 1)
        self.placeControl(pyxbmct.Label(getString(30121), alignment=pyxbmct.ALIGN_CENTER_Y), 2, 0)
        self.placeControl(self.btn_ages, 2, 1)
        self.placeControl(self.btn_save, 4, 0)
        self.placeControl(self.btn_close, 4, 1)
        self.connect(self.btn_close, self.close)
        self.connect(self.btn_ages, self.select_age)
        self.connect(self.btn_save, self.save_settings)
        self.connect(pyxbmct.ACTION_NAV_BACK, self.close)
        self.pin.setText(AgePin)

    def set_navigation(self):
        self.pin.controlUp(self.btn_save)
        self.pin.controlDown(self.btn_ages)
        self.btn_save.setNavigation(self.btn_ages, self.pin, self.btn_close, self.btn_close)
        self.btn_close.setNavigation(self.btn_ages, self.pin, self.btn_save, self.btn_save)
        self.btn_ages.setNavigation(self.pin, self.btn_save, self.btn_save, self.btn_close)
        self.setFocus(self.pin)

    def save_settings(self):
        writeConfig('age_pin', self.pin.getText().strip())
        writeConfig('pin_req', self.pin_req)
        self.close()

    def select_age(self):
        sel = Dialog.select(getString(30121), self.age_list)
        if sel > -1:
            self.pin_req = sel
            self.btn_ages.setLabel(self.age_list[self.pin_req])


class Captcha(pyxbmct.AddonDialogWindow):
    def __init__(self, title='', soup=None, email=None):
        super(Captcha, self).__init__(title)
        head = soup.find('div', attrs={'id': 'message_warning'})
        if not head:
            head = soup.find('div', attrs={'id': 'message_error'})
        title = soup.find('div', attrs={'id': 'ap_captcha_guess_alert'})
        self.picurl = soup.find('div', attrs={'id': 'ap_captcha_img'}).img.get('src')
        self.setGeometry(500, 550, 9, 2)
        self.email = email
        self.pwd = ''
        self.cap = ''
        self.head = head.p.renderContents().strip()
        self.head = re.sub('(?i)<[^>]*>', '', self.head)
        self.title = title.renderContents().strip()
        self.image = pyxbmct.Image('', aspectRatio=2)
        self.tb_head = pyxbmct.TextBox()
        self.fl_title = pyxbmct.FadeLabel(_alignment=pyxbmct.ALIGN_CENTER)
        self.username = pyxbmct.Edit('', _alignment=pyxbmct.ALIGN_LEFT | pyxbmct.ALIGN_CENTER_Y)
        self.password = pyxbmct.Edit('', _alignment=pyxbmct.ALIGN_LEFT | pyxbmct.ALIGN_CENTER_Y)
        self.captcha = pyxbmct.Edit('', _alignment=pyxbmct.ALIGN_LEFT | pyxbmct.ALIGN_CENTER_Y)
        self.btn_submit = pyxbmct.Button(getString(30008).split('…')[0])
        self.btn_cancel = pyxbmct.Button(getString(30123))
        self.set_controls()
        self.set_navigation()

    def set_controls(self):
        self.placeControl(self.tb_head, 0, 0, columnspan=2, rowspan=3)
        self.placeControl(pyxbmct.Label(getString(30002), alignment=pyxbmct.ALIGN_CENTER_Y | pyxbmct.ALIGN_CENTER), 2, 0)
        self.placeControl(pyxbmct.Label(getString(30003), alignment=pyxbmct.ALIGN_CENTER_Y | pyxbmct.ALIGN_CENTER), 3, 0)
        self.placeControl(self.username, 2, 1, pad_y=8)
        self.placeControl(self.password, 3, 1, pad_y=8)
        self.placeControl(self.image, 4, 0, rowspan=2, columnspan=2)
        self.placeControl(self.fl_title, 6, 0, columnspan=2)
        self.placeControl(self.captcha, 7, 0, columnspan=2, pad_y=8)
        self.placeControl(self.btn_submit, 8, 0)
        self.placeControl(self.btn_cancel, 8, 1)
        self.connect(self.btn_cancel, self.close)
        self.connect(self.btn_submit, self.submit)
        self.connect(pyxbmct.ACTION_NAV_BACK, self.close)
        self.username.setText(self.email)
        self.tb_head.setText(self.head)
        self.fl_title.addLabel(self.title)
        self.image.setImage(self.picurl, False)

    def set_navigation(self):
        self.username.controlUp(self.btn_submit)
        self.username.controlDown(self.password)
        self.password.controlUp(self.username)
        self.password.controlDown(self.captcha)
        self.captcha.controlUp(self.password)
        self.captcha.controlDown(self.btn_submit)
        self.btn_submit.controlUp(self.captcha)
        self.btn_submit.controlDown(self.username)
        self.btn_cancel.controlUp(self.captcha)
        self.btn_cancel.controlDown(self.username)
        self.btn_submit.controlRight(self.btn_cancel)
        self.btn_submit.controlLeft(self.btn_cancel)
        self.btn_cancel.controlRight(self.btn_submit)
        self.btn_cancel.controlLeft(self.btn_submit)
        self.setFocus(self.password)

    def submit(self):
        self.pwd = self.password.getText()
        self.cap = self.captcha.getText()
        self.email = self.username.getText()
        self.close()


args = dict(urlparse.parse_qsl(urlparse.urlparse(sys.argv[2]).query))

Log(args, xbmc.LOGDEBUG)
mode = args.get('mode', None)

if not getConfig('UserAgent'):
    getUA()

deviceID = genID()
if loadUsers():
    if not loadUser('mid'):
        switchUser(0)
    MarketID = loadUser('mid')
    BaseUrl = loadUser('baseurl')
    ATVUrl = loadUser('atvurl')
    UsePrimeVideo = loadUser('pv')

    AgePin = getConfig('age_pin')
    PinReq = int(getConfig('pin_req', '0'))
    Ages = ['', ''] if MarketID not in AgesCfg.keys() else AgesCfg[MarketID]
    AgeRating = Ages[0]
    Ages = Ages[1:]
    RestrAges = ','.join(a[1] for a in Ages[PinReq:]) if AgePin else ''

    Language = jsonRPC('Settings.GetSettingValue', param={'setting': 'locale.audiolanguage'})
    Language = xbmc.convertLanguage(Language['value'], xbmc.ISO_639_1)
    Language = Language if Language else xbmc.getLanguage(xbmc.ISO_639_1, False)
    Language = Language if Language else 'en'

    PrimeVideoCache = os.path.join(DataPath, 'PVCatalog{0}.pvcp'.format(MarketID))
    PrimeVideoData = os.path.join(DataPath, 'PVVideoData{0}.pvdp'.format(MarketID))
    pvCatalog = {}
    pvVideoData = {}

    menuFile = os.path.join(DataPath, 'menu-%s.db' % MarketID)

    if not UsePrimeVideo:
        dbFile = os.path.join(DataPath, 'art.db')
        db = sqlite.connect(dbFile)
        createDB()
        menuDb = sqlite.connect(menuFile)
        loadCategories()
    else:
        if xbmcvfs.exists(PrimeVideoData):
            with open(PrimeVideoData, 'r') as fp:
                pvVideoData = pickle.load(fp)
        if xbmcvfs.exists(PrimeVideoCache):
            with open(PrimeVideoCache, 'r') as fp:
                cached = pickle.load(fp)
            if time.time() < cached['expiration']:
                pvCatalog = cached
elif mode != 'LogIn':
    Dialog.notification(getString(30200), getString(30216))
    xbmc.executebuiltin('Addon.OpenSettings(%s)' % addon.getAddonInfo('id'))
    exit()

if None is mode:
    MainMenu()
elif mode == 'listCategories':
    listCategories(args.get('url', ''), args.get('opt', ''))
elif mode == 'listContent':
    listContent(args.get('cat'), args.get('url', '').decode('utf-8'), int(args.get('page', '1')), args.get('opt', ''))
elif mode == 'PlayVideo':
    PlayVideo(args.get('name'), args.get('asin'), args.get('adult'), int(args.get('trailer', '0')), int(args.get('selbitrate', '0')))
elif mode == 'getList':
    getList(args.get('url', ''), int(args.get('export', '0')), [args.get('opt')])
elif mode == 'getListMenu':
    getListMenu(args.get('url', ''), int(args.get('export', '0')))
elif mode == 'WatchList':
    WatchList(args.get('url', ''), int(args.get('opt', '0')))
elif mode == 'openSettings':
    aid = args.get('url')
    aid = is_addon if aid == 'is' else aid
    xbmcaddon.Addon(aid).openSettings()
elif mode == 'ageSettings':
    if RequestPin():
        AgeSettings(getString(30018).split('…')[0]).doModal()
elif mode == 'PrimeVideo_Browse':
    PrimeVideo_Browse(None if 'path' not in args else args['path'])
else:
    exec mode + '()'
