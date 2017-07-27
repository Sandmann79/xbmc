#!/usr/bin/env python
# -*- coding: utf-8 -*-
from BeautifulSoup import BeautifulSoup, BeautifulStoneSoup, Tag
from datetime import date
from pyDes import *
from platform import node
from sqlite3 import dbapi2 as sqlite
import uuid
import cookielib
import mechanize
import sys
import urllib
import urllib2
import re
import os
import xbmcplugin
import xbmcgui
import xbmcaddon
import xbmc
import urlparse
import base64
import time
import random
import subprocess
import hashlib
import hmac
import threading
import json
import xbmcvfs
import pyxbmct
import socket
import ssl
import shlex

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
osLE = socket.gethostname() == 'LibreELEC'
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
tmdb = base64.b64decode('YjM0NDkwYzA1NmYwZGQ5ZTNlYzlhZjIxNjdhNzMxZjQ=')
tvdb = base64.b64decode('MUQ2MkYyRjkwMDMwQzQ0NA==')
DefaultFanart = os.path.join(PluginPath, 'fanart.jpg')
NextIcon = os.path.join(PluginPath, 'resources', 'next.png')
HomeIcon = os.path.join(PluginPath, 'resources', 'home.png')
country = int(addon.getSetting('country'))
BaseUrl = 'https://www.amazon.' + ['de', 'co.uk', 'com', 'co.jp', ''][country]
ATVUrl = 'https://atv-%s.amazon.com' % ['eu', 'eu', 'ext', 'ext-fe', 'ext'][country]
wl_order = ['DATE_ADDED_DESC', 'TITLE_DESC', 'TITLE_ASC'][int('0'+addon.getSetting("wl_order"))]
MarketID = ['A1PA6795UKMFR9', 'A1F83G8C2ARO7P', 'ATVPDKIKX0DER', 'A1VC38T7YXB528', 'ART4WZ8MWBX2Y'][country]
Language = ['de', 'en', 'en', 'jp', ''][country]
AgeRating = ['FSK ', '', '', '', ''][country]
menuFile = os.path.join(DataPath, 'menu-%s.db' % MarketID)
CookieFile = os.path.join(DataPath, 'cookie-%s.lwp' % MarketID)
na = 'not available'
UserAgent = 'Mozilla/5.0 (Windows NT 10.0; WOW64; Trident/7.0; Avant Browser; rv:11.0) like Gecko'
watchlist = 'watchlist'
library = 'video-library'
DBVersion = 1.1
PayCol = 'FFE95E01'
Ages = [[('FSK 0', 'FSK 0'), ('FSK 6', 'FSK 6'), ('FSK 12', 'FSK 12'), ('FSK 16', 'FSK 16'), ('FSK 18', 'FSK 18')],
        [('Universal', 'U'), ('Parental Guidance', 'PG'), ('12 and older', '12,12A'), ('15 and older', '15'),
         ('18 and older', '18')],
        [('General Audiences', 'G,TV-G,TV-Y'), ('Family', 'PG,NR,TV-Y7,TV-Y7-FV,TV-PG'),
         ('Teen', 'PG-13,TV-14'), ('Mature', 'R,NC-17,TV-MA,Unrated,Not rated')],
        [('全ての観客', 'g'), ('親の指導・助言', 'pg12'), ('R-15指定', 'r15+'), ('成人映画', 'r18+,nr')],
        [('全ての観客', 'g'), ('親の指導・助言', 'pg12'), ('R-15指定', 'r15+'), ('成人映画', 'r18+,nr')]]

# ids: A28RQHJKHM2A2W - ps3 / AFOQV1TK6EU6O - ps4 / A1IJNVP3L4AY8B - samsung / A2E0SNTXJVT7WK - firetv1 /
#      ADVBD696BHNV5 - montoya / A3VN4E5F7BBC7S - roku / A1MPSLFC7L5AFK - kindle / A2M4YX06LWP8WI - firetv2 /
# TypeIDs = {'GetCategoryList': 'firmware=fmw:15-app:1.1.23&deviceTypeID=A1MPSLFC7L5AFK',
#            'GetSimilarities': 'firmware=fmw:15-app:1.1.23&deviceTypeID=A1MPSLFC7L5AFK',
#                        'All': 'firmware=fmw:17-app:1.0.1433.3&deviceTypeID=A43PXU4ZN2AL1'}
#                        'All': 'firmware=fmw:045.01E01164A-app:4.7&deviceTypeID=A3VN4E5F7BBC7S'}
# TypeIDs = {'All': 'firmware=fmw:17-app:2.0.45.1210&deviceTypeID=A2RJLFEH0UEKI9'}

TypeIDs = {'All': 'firmware=fmw:17-app:2.0.45.1210&deviceTypeID=A2M4YX06LWP8WI',
           'GetCategoryList_ftv': 'firmware=fmw:17-app:2.0.45.1210&deviceTypeID=ADVBD696BHNV5'}

langID = {'movie': 30165, 'series': 30166, 'season': 30167, 'episode': 30173}
OfferGroup = '' if payCont else '&OfferGroups=B0043YVHMY'
socket.setdefaulttimeout(30)

if not BaseUrl:
    BaseUrl = 'https://www.primevideo.com'

if addon.getSetting('ssl_verif') == 'true' and hasattr(ssl, '_create_unverified_context'):
    ssl._create_default_https_context = ssl._create_unverified_context

if addon.getSetting('enablelibraryfolder') == 'true':
    MOVIE_PATH = os.path.join(xbmc.translatePath(addon.getSetting('customlibraryfolder')), 'Movies').decode('utf-8')
    TV_SHOWS_PATH = os.path.join(xbmc.translatePath(addon.getSetting('customlibraryfolder')), 'TV').decode('utf-8')
else:
    MOVIE_PATH = os.path.join(DataPath, 'Movies')
    TV_SHOWS_PATH = os.path.join(DataPath, 'TV')


def setView(content, view=False, updateListing=False):
    # 501-POSTER WRAP 503-MLIST3 504=MLIST2 508-FANARTPOSTER
    if content == 'movie':
        ctype = 'movies'
        cview = 'movieview'
    elif content == 'series':
        ctype = 'tvshows'
        cview = 'showview'
    elif content == 'season':
        ctype = 'seasons'
        cview = 'seasonview'
    else:
        ctype = 'episodes'
        cview = 'episodeview'

    confluence_views = [500, 501, 502, 503, 504, 508, -1]
    xbmcplugin.setContent(pluginhandle, ctype)
    viewenable = addon.getSetting("viewenable") == 'true'
    if viewenable and view:
        viewid = confluence_views[int(addon.getSetting(cview))]
        if viewid == -1:
            viewid = int(addon.getSetting(cview.replace('view', 'id')))
        xbmc.executebuiltin('Container.SetViewMode(%s)' % viewid)
    xbmcplugin.endOfDirectory(pluginhandle, updateListing=updateListing)


def getURL(url, useCookie=False, silent=False, headers=[], UA=UserAgent, rjson=True, attempt=1, check=False):
    cj = cookielib.LWPCookieJar()
    retval = [] if rjson else ''
    if useCookie:
        cj = MechanizeLogin() if isinstance(useCookie, bool) else useCookie
        if isinstance(cj, bool):
            return retval
    if not silent or verbLog:
        dispurl = url
        dispurl = re.sub('(?i)%s|%s|&token=\w+|&customerId=\w+' % (tvdb, tmdb), '', url).strip()
        Log('getURL: ' + dispurl)
    headers.append(('User-Agent', UA))
    headers.append(('Host', BaseUrl.split('//')[1]))
    try:
        opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cj), urllib2.HTTPRedirectHandler)
        opener.addheaders = headers
        usock = opener.open(url)
        response = usock.read() if not check else 'OK'
        usock.close()
    except (socket.timeout, ssl.SSLError, urllib2.URLError), e:
        Log('Error reason: %s' % e, xbmc.LOGERROR)
        if '429' or 'timed out' in e:
            attempt += 1 if not check else 10
            logout = 'Attempt #%s' % attempt
            if '429' in e:
                logout += '. Too many requests - Pause 10 sec'
                xbmc.sleep(10000)
            Log(logout)
            if attempt < 3:
                return getURL(url, useCookie, silent, headers, UA, rjson, attempt)
        return retval
    return json.loads(response) if rjson else response


def getATVData(pg_mode, query='', version=2, useCookie=False, site_id=None):
    if '?' in query:
        query = query.split('?')[1]
    if query:
        query = '&IncludeAll=T&AID=T&' + query
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
    u = {'mode': mode, 'url': url, 'page': page, 'opt': opt, 'cat': catalog}
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
        item.setInfo(type='Video', infoLabels=infoLabels)
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
    url += '&trailer=0'

    if export:
        url += '&selbitrate=0'
        Export(infoLabels, url)
    else:
        cm.insert(0, (getString(30101), 'Action(ToggleWatched)'))
        cm.insert(1, (getString(30102), 'RunPlugin(%s)' % (url+'&selbitrate=1')))
        url += '&selbitrate=0'
        item.setInfo(type='Video', infoLabels=infoLabels)
        item.addContextMenuItems(cm)
        xbmcplugin.addDirectoryItem(pluginhandle, url, item, isFolder=False)


def MainMenu():
    loadCategories()
    cm_wl = [(getString(30185) % 'Watchlist', 'RunPlugin(%s?mode=getList&url=%s&export=1)' % (sys.argv[0], watchlist))]
    cm_lb = [(getString(30185) % getString(30100),
              'RunPlugin(%s?mode=getList&url=%s&export=1)' % (sys.argv[0], library))]
    addDir('Watchlist', 'getList', watchlist, cm=cm_wl)
    addDir(getString(30104), 'listCategories', getNodeId('movies'), opt='30143')
    addDir(getString(30107), 'listCategories', getNodeId('tv_shows'), opt='30160')
    addDir(getString(30108), 'Search', '')
    addDir(getString(30100), 'getList', library, cm=cm_lb)
    xbmcplugin.endOfDirectory(pluginhandle, updateListing=False)


def Search():
    searchString = Dialog.input(getString(24121))
    if searchString:
        url = 'searchString=%s%s' % (urllib.quote_plus(searchString), OfferGroup)
        listContent('Search', url, 1, 'search')


def swapDB():
    data = getATVData('GetCategoryList_ftv')
    parseNodes(data, '99')


def loadCategories(force=False):
    if xbmcvfs.exists(menuFile) and not force:
        ftime = updateTime(False)
        ctime = time.time()
        if ctime - ftime < 8 * 3600:
            return

    parseStart = time.time()
    createDB(True)
    data = getATVData('GetCategoryList')
    Log('Download MenuTime: %s' % (time.time() - parseStart), 0)
    parseNodes(data)
    updateTime()

    newcat = '&OrderBy=AvailabilityDate&MinAmazonRatingCount=80&HideNum=T&Preorder=F'  # &HideNum=T (w/o UHD)
    replCat('ContentType=TVEpisode&RollupToSeason=T'+newcat, 'prime-tv-2', '&OfferGroups=B0043YVHMY')
    replCat('ContentType=TVEpisode&RollupToSeason=T'+newcat, 'all-tv-2')
    replCat('ContentType=Movie&Preorder=F&OrderBy=SalesRank,Rating&Preorder=F&OfferGroups=B0043YVHMY', 'prime-movie-1')

    menuDb.commit()
    Log('Parse MenuTime: %s' % (time.time() - parseStart), 0)


def replCat(src, dest, extra='', strrepl=True):
    c = menuDb.cursor()
    result = [src] if strrepl else c.execute('select content from menu where id = (?)', (src,)).fetchone()

    if result:
        c.execute('update menu set content = (?) where id = (?)', (result[0]+extra, dest))


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


def getNodeId(mainid):
    c = menuDb.cursor()
    menu_id = c.execute('select content from menu where id = (?)', (mainid,)).fetchone()
    result = ''

    if menu_id:
        st = 'all' if payCont else 'prime'
        result = c.execute('select content from menu where node = (?) and id = (?)', (menu_id[0], st)).fetchone()
    c.close()

    if result:
        return result[0]
    return '0'


def parseNodes(data, node_id=''):
    if type(data) != list:
        data = [data]

    for count, entry in enumerate(data):
        category = None
        if 'categories' in entry.keys():
            parseNodes(entry['categories'], '%s%s' % (node_id, count))
            content = '%s%s' % (node_id, count)
            category = 'node'
        elif 'query' in entry.keys():
            content = entry['query']
            category = 'query'
        if category and 'title' in entry.keys() and 'id' in entry.keys():
            if 'refTag' not in entry:
                entry['refTag'] = ''
            if entry['title']:
                wMenuDB([node_id, entry['title'], category, content, entry['id'].lower(), entry['refTag']])


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

    if root:
        url = 'OrderBy=Title%s&contentType=' % OfferGroup
        url += 'tvseason,tvepisodes&RollUpToSeries=T' if root == '30160' else 'movie'
        addDir(getString(int(root)), 'listContent', url)

    for node, title, category, content, menu_id, reftag in cat:
        mode = None
        opt = ''
        if category == 'node':
            mode = 'listCategories'
            url = content
        elif category == 'query':
            mode = 'listContent'
            opt = 'listcat'
            url = content.replace('\n', '').replace("\n", '')
        if mode:
            addDir(title, mode, url, opt=opt)
    xbmcplugin.endOfDirectory(pluginhandle)


def listContent(catalog, url, page, parent, export=False):
    oldurl = url
    ResPage = 240 if export else MaxResults
    url += '&NumberOfResults=%s&StartIndex=%s&Detailed=T' % (ResPage, (page - 1) * ResPage)
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
               'RunPlugin(%s?mode=getList&url=%s&export=1)' % (sys.argv[0], asin)),
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
            setView('season', True)
        else:
            setView(contentType, True)


def cleanTitle(title):
    if title.isupper():
        title = title.title().replace('[Ov]', '[OV]').replace('Bc', 'BC')
    title = title.replace(u'\u2013', '-').replace(u'\u00A0', ' ').replace('[dt./OV]', '')
    return title.strip()


def Export(infoLabels, url):
    isEpisode = infoLabels['contentType'] != 'movie'
    language = ['ger', 'eng', 'eng', 'jpn'][country]
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
    url = BaseUrl + '/gp/video/watchlist/ajax/addRemove.html?&ASIN=%s&dataType=json&token=%s&action=%s' % (
        asin, token, action)
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
    url = BaseUrl + '/gp/video/watchlist/ajax/hoverbubble.html?ASIN=' + asin
    data = getURL(url, useCookie=cookie, rjson=False)
    if data:
        tree = BeautifulSoup(data, convertEntities=BeautifulSoup.HTML_ENTITIES)
        form = tree.find('form', attrs={'id': 'watchlistForm'})
        token = form.find('input', attrs={'id': 'token'})['value']
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
        if isinstance(title, unicode):
            title = title.encode('utf-8')
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
        content = getATVData('GetASINDetails', 'ASINList=' + asins)['titles'][0]
        asins = getAsins(content, False)
        del content

    cur = db.cursor()
    if fanart:
        cur.execute('insert or ignore into art values (?,?,?,?,?,?)', (asins, season_number, poster, None, fanart, date.today()))
    if seasons:
        for season, url in seasons.items():
            cur.execute('insert or ignore into art values (?,?,?,?,?,?)',
                        (asins, season, url, None, None, date.today()))
    db.commit()
    cur.close()


def getTVDBImages(title, tvdb_id=None):
    Log('searching fanart for %s at thetvdb.com' % title.upper())
    posterurl = fanarturl = None
    splitter = [' - ', ': ', ', ']
    if country == 0 or country == 3:
        langcodes = [Language, 'en']
    else:
        langcodes = ['en']
    TVDB_URL = 'http://www.thetvdb.com/banners/'

    while not tvdb_id and title:
        tv = urllib.quote_plus(title)
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
        movie = urllib.quote_plus(title)
        data = getURL('http://api.themoviedb.org/3/search/%s?api_key=%s&language=%s&query=%s%s' % (
            content, tmdb, Language, movie, str_year), silent=True)
        if not data:
            continue

        if data['total_results'] > 0:
            result = data['results'][0]
            if result['backdrop_path']:
                fanart = TMDB_URL + result['backdrop_path']
            tmdb_id = result['id']
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


def getList(listing, export):
    if listing == watchlist or listing == library:
        cj = MechanizeLogin()
        if not cj:
            return
        asins_movie = scrapAsins('/gp/video/%s/movie/?ie=UTF8&sort=%s' % (listing, wl_order), cj)
        asins_tv = scrapAsins('/gp/video/%s/tv/?ie=UTF8&sort=%s' % (listing, wl_order), cj)
    else:
        asins_movie = listing
        asins_tv = ''

    url = 'ASINList='
    extraArgs = '&RollUpToSeries=T' if dispShowOnly else ''

    if export:
        url += asins_movie + ',' + asins_tv
        SetupLibrary()
        listContent('GetASINDetails', url, 1, listing, export)
    else:
        addDir(getString(30104), 'listContent', url + asins_movie, catalog='GetASINDetails', opt=listing)
        addDir(getString(30107), 'listContent', url + asins_tv + extraArgs, catalog='GetASINDetails', opt=listing)
        xbmcplugin.endOfDirectory(pluginhandle, updateListing=False)


def Log(msg, level=xbmc.LOGNOTICE):
    if level == xbmc.LOGDEBUG and verbLog:
        level = xbmc.LOGNOTICE
    if isinstance(msg, unicode):
        msg = msg.encode('utf-8')
    xbmc.log('[%s] %s' % (__plugin__, msg.__str__()), level)


def WriteLog(data, fn=''):
    if not verbLog:
        return

    fn = '-' + fn if fn else ''
    fn = 'amazon%s.log' % fn
    path = os.path.join(HomePath, fn)
    if isinstance(data, unicode):
        data = data.encode('utf-8')
    logfile = xbmcvfs.File(path, 'w')
    logfile.write(data.__str__())
    logfile.write('\n')
    logfile.close()


def getString(string_id):
    src = xbmc if string_id < 30000 else addon
    locString = src.getLocalizedString(string_id)
    if isinstance(locString, unicode):
        locString = locString.encode('utf-8')
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
    amazonUrl = BaseUrl + "/dp/" + asin
    playable = False
    fallback = int(addon.getSetting("fallback_method"))
    methodOW = fallback - 1 if forcefb and fallback else playMethod
    videoUrl = "%s/?autoplay%s=1" % (amazonUrl, ('trailer' if trailer == '1' else ''))
    extern = not xbmc.getInfoLabel('Container.PluginName').startswith('plugin.video.amazon')

    if extern:
        Log('External Call', xbmc.LOGDEBUG)

    while not playable:
        playable = True

        if methodOW == 2 and platform == osAndroid:
            AndroidPlayback(asin, trailer)
        elif methodOW == 3:
            playable = IStreamPlayback(asin, name, trailer, isAdult, extern)
        elif platform != osAndroid:
            ExtPlayback(videoUrl, asin, isAdult, methodOW)

        if not playable:
            if fallback:
                methodOW = fallback - 1
            else:
                xbmc.sleep(500)
                Dialog.ok(getString(30203), getString(30218))
                playable = True

    if methodOW !=3:
        playDummyVid()


def ExtPlayback(videoUrl, asin, isAdult, method):
    waitsec = int(addon.getSetting("clickwait")) * 1000
    waitprepin = int(addon.getSetting("waitprepin")) * 1000
    pin = addon.getSetting("pin")
    waitpin = int(addon.getSetting("waitpin")) * 1000
    pininput = addon.getSetting("pininput") == 'true'
    fullscr = addon.getSetting("fullscreen") == 'true'
    videoUrl += '&playerDebug=true' if verbLog else ''

    xbmc.Player().stop()
    xbmc.executebuiltin('ActivateWindow(busydialog)')
    suc, url = getCmdLine(videoUrl, asin, method)
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
        url += '&playTrailer=T' if trailer == '1' else ''

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
    mpaa_str = RestrAges + getString(30171)
    vMT = 'Trailer' if trailer == '1' else 'Feature'

    if not is_addon:
        Log('No Inputstream Addon found or activated')
        Dialog.notification(getString(30203), 'No Inputstream Addon found or activated', xbmcgui.NOTIFICATION_ERROR)
        return True

    values = getFlashVars(asin)
    if not values:
        return True

    mpd, subs = getStreams(*getUrldata('catalog/GetPlaybackResources', values, extra=True, vMT=vMT,
                                       opt='&titleDecorationScheme=primary-content'), retmpd=True)
    licURL = getUrldata('catalog/GetPlaybackResources', values, extra=True, vMT=vMT, dRes='Widevine2License', retURL=True)

    if not mpd:
        Dialog.notification(getString(30203), subs, xbmcgui.NOTIFICATION_ERROR)
        return True

    orgmpd = mpd
    mpd = re.sub(r'~', '', mpd) if mpd != re.sub(r'~', '', mpd) else re.sub(r'/[1-9][$].*?/', '/', mpd)
    mpdcontent = getURL(mpd, rjson=False)
    is_version = xbmcaddon.Addon(is_addon).getAddonInfo('version') if is_addon else '0'

    if len(re.compile(r'(?i)edef8ba9-79d6-4ace-a3c8-27dcd51d21ed').findall(mpdcontent)) < 2:
        if platform != osAndroid and int(is_version[0:1]) < 2:
            xbmc.executebuiltin('ActivateWindow(busydialog)')
            return False
    elif platform == osAndroid or int(is_version[0:1]) >= 2:
        mpd = orgmpd

    Log(mpd)

    if not extern:
        mpaa_check = xbmc.getInfoLabel('ListItem.MPAA') in mpaa_str or isAdult
        number = xbmc.getInfoLabel('ListItem.Episode')
        title = xbmc.getInfoLabel('ListItem.Title')
        thumb = xbmc.getInfoLabel('ListItem.Art(season.poster)')
        if not thumb:
            thumb = xbmc.getInfoLabel('ListItem.Art(tvshow.poster)')
            if not thumb:
                thumb = xbmc.getInfoLabel('ListItem.Art(thumb)')
    else:
        content = getATVData('GetASINDetails', 'ASINList=' + asin)['titles'][0]
        ct, Info = getInfos(content, False)
        title = Info['DisplayTitle']
        thumb = Info.get('Poster', Info['Thumb'])
        number = Info.get('Episode', False)
        mpaa_check = str(Info.get('MPAA', mpaa_str)) in mpaa_str or isAdult

    if trailer == '1':
        title += ' (Trailer)'
        Info = {'Plot': xbmc.getInfoLabel('ListItem.Plot')}
    if number and not extern:
        title = '%s - %s' % (number, title)
    if not title:
        title = name

    if mpaa_check and not RequestPin():
        return True

    listitem = xbmcgui.ListItem(label=title, path=mpd)

    if extern or trailer == '1':
        listitem.setInfo('video', Info)

    if 'adaptive' in is_addon:
        listitem.setProperty('inputstream.adaptive.manifest_type', 'mpd')

    Log('Using %s Version:%s' %(is_addon, is_version))
    listitem.setArt({'thumb': thumb})
    listitem.setSubtitles(subs)
    listitem.setProperty('%s.license_type' % is_addon, 'com.widevine.alpha')
    listitem.setProperty('%s.license_key' % is_addon, licURL)
    listitem.setProperty('inputstreamaddon', is_addon)
    xbmcplugin.setResolvedUrl(pluginhandle, True, listitem=listitem)

    while not xbmc.Player().isPlayingVideo():
        xbmc.sleep(2000)

    Log('Playback started...', 0)
    Log('Video ContentType Movie? %s' % xbmc.getCondVisibility('VideoPlayer.Content(movies)'), 0)
    Log('Video ContentType Episode? %s' % xbmc.getCondVisibility('VideoPlayer.Content(episodes)'), 0)
    return True


def AddonEnabled(addon_id):
    result = xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Addons.GetAddonDetails","id":1,\
                                   "params":{"addonid":"%s", "properties": ["enabled"]}}' % addon_id)
    return False if '"error":' in result or '"enabled":false' in result else True


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


def getCmdLine(videoUrl, asin, method):
    scr_path = addon.getSetting("scr_path")
    br_path = addon.getSetting("br_path").strip()
    scr_param = addon.getSetting("scr_param").strip()
    kiosk = addon.getSetting("kiosk") == 'true'
    appdata = addon.getSetting("ownappdata") == 'true'
    cust_br = addon.getSetting("cust_path") == 'true'
    nobr_str = getString(30198)

    if method == 1:
        if not xbmcvfs.exists(scr_path):
            return False, nobr_str

        suc, fr = getPlaybackInfo(asin)
        if not suc:
            return False, fr

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

    hosts = data['audioVideoUrls']['avCdnUrlSets']

    while hosts:
        for cdn in hosts:
            prefHost = False if HostSet not in str(hosts) or HostSet == 'Auto' else HostSet
            if prefHost and prefHost not in cdn['cdn']:
                continue
            Log('Using Host: ' + cdn['cdn'])

            for urlset in cdn['avUrlInfoList']:
                data = getURL(urlset['url'], rjson=False, check=retmpd)
                if not data:
                    hosts.remove(cdn)
                    Log('Host not reachable: ' + cdn['cdn'])
                    break
                if retmpd:
                    return urlset['url'], subUrls
                else:
                    fps_string = re.compile('frameRate="([^"]*)').findall(data)[0]
                    fr = round(eval(fps_string + '.0'), 3)
                    return True, str(fr).replace('.0', '')

    return False, getString(30217)


def parseSubs(data):
    subs = []
    if addon.getSetting('subtitles') == 'false' or 'subtitleUrls' not in data:
        return subs

    import codecs
    for sub in data['subtitleUrls']:
        lang = sub['displayName'].split('(')[0].strip()
        Log('Convert %s Subtitle' % lang)
        srtfile = xbmc.translatePath('special://temp/%s.srt' % lang).decode('utf-8')
        srt = codecs.open(srtfile, 'w', encoding='utf-8')
        soup = BeautifulStoneSoup(getURL(sub['url'], rjson=False), convertEntities=BeautifulStoneSoup.XML_ENTITIES)
        enc = soup.originalEncoding
        num = 0
        for caption in soup.findAll('tt:p'):
            num += 1
            subtext = caption.renderContents().decode(enc).replace('<tt:br>', '\n').replace('</tt:br>', '')
            srt.write(u'%s\n%s --> %s\n%s\n\n' % (num, caption['begin'], caption['end'], subtext))
        srt.close()
        subs.append(srtfile)
    return subs


def getPlaybackInfo(asin):
    if addon.getSetting("framerate") == 'false':
        return True, ''
    values = getFlashVars(asin)
    if not values:
        return False, 'getFlashVars'
    suc, fr = getStreams(*getUrldata('catalog/GetPlaybackResources', values, extra=True))
    return suc, fr


def getFlashVars(asin):
    cookie = MechanizeLogin()
    if not cookie:
        return False
    url = BaseUrl + '/gp/deal/ajax/getNotifierResources.html'
    showpage = getURL(url, useCookie=cookie)

    if not showpage:
        Dialog.notification(__plugin__, Error({'errorCode': 'invalidrequest', 'message': 'getFlashVars'}),
                            xbmcgui.NOTIFICATION_ERROR)
        return False

    values = {'asin': asin,
              'deviceTypeID': 'AOAGZA014O5RE',
              'userAgent': UserAgent}
    values.update(showpage['resourceData']['GBCustomerData'])

    if 'customerId' not in values:
        Dialog.notification(getString(30200), getString(30210), xbmcgui.NOTIFICATION_ERROR)
        return False

    rand = 'onWebToken_' + str(random.randint(0, 484))
    pltoken = getURL(BaseUrl + "/gp/video/streaming/player-token.json?callback=" + rand, useCookie=cookie, rjson=False)
    try:
        values['token'] = re.compile('"([^"]*).*"([^"]*)"').findall(pltoken)[0][1]
    except IndexError:
        Dialog.notification(getString(30200), getString(30201), xbmcgui.NOTIFICATION_ERROR)
        return False
    return values


def getUrldata(mode, values, retformat='json', devicetypeid=False, version=1, firmware='1', opt='', extra=False,
               useCookie=False, retURL=False, vMT='Feature', dRes='AudioVideoUrls,SubtitleUrls'):
    if not devicetypeid:
        devicetypeid = values['deviceTypeID']
    url = ATVUrl + '/cdp/' + mode
    url += '?asin=' + values['asin']
    url += '&deviceTypeID=' + devicetypeid
    url += '&firmware=' + firmware
    url += '&customerID=' + values['customerId']
    url += '&deviceID=' + deviceID
    url += '&marketplaceID=' + MarketID
    url += '&token=' + values['token']
    url += '&format=' + retformat
    url += '&version=' + str(version)
    url += opt
    if extra:
        url += '&resourceUsage=ImmediateConsumption&consumptionType=Streaming&deviceDrmOverride=CENC' \
               '&deviceStreamingTechnologyOverride=DASH&deviceProtocolOverride=Http&audioTrackId=all' \
               '&deviceBitrateAdaptationsOverride=CVBR%2CCBR'
        url += '&videoMaterialType=' + vMT
        url += '&desiredResources=' + dRes
        url += '&supportedDRMKeyScheme=DUAL_KEY' if platform != osAndroid and 'AudioVideoUrls' in dRes else ''
    if retURL:
        return url
    data = getURL(url, useCookie=useCookie, rjson=False)
    if data:
        error = re.findall('{[^"]*"errorCode[^}]*}', data)
        if error:
            return False, Error(json.loads(error[0]))
        return True, json.loads(data)
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
        guid = hmac.new(UserAgent, uuid.uuid4().bytes, hashlib.sha224).hexdigest()
        writeConfig("GenDeviceID", guid)
    return guid


def MechanizeLogin():
    cj = cookielib.LWPCookieJar()
    if xbmcvfs.exists(CookieFile):
        cj.load(CookieFile, ignore_discard=True, ignore_expires=True)
        return cj

    Log('Login')

    return LogIn(False)


def LogIn(ask=True):
    addon.setSetting('login_acc', '')
    addon.setSetting('use_mfa', 'false')
    email = getConfig('login_name')
    password = decode(getConfig('login_pass'))
    savelogin = addon.getSetting('save_login') == 'true'
    useMFA = False

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
        if xbmcvfs.exists(CookieFile):
            xbmcvfs.delete(CookieFile)
        cj = cookielib.LWPCookieJar()
        br = mechanize.Browser()
        br.set_handle_robots(False)
        br.set_cookiejar(cj)
        br.set_handle_gzip(True)
        br.addheaders = [('User-Agent', UserAgent)]
        br.open(BaseUrl + '/gp/aw/si.html')
        br.select_form(name='signIn')
        br['email'] = email
        br['password'] = password
        br.addheaders = [('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'),
                         ('Accept-Encoding', 'gzip, deflate'),
                         ('Accept-Language', 'de,en-US;q=0.8,en;q=0.6'),
                         ('Cache-Control', 'max-age=0'),
                         ('Connection', 'keep-alive'),
                         ('Content-Type', 'application/x-www-form-urlencoded'),
                         ('Host', BaseUrl.split('//')[1]),
                         ('Origin', BaseUrl),
                         ('User-Agent', UserAgent),
                         ('Upgrade-Insecure-Requests', '1')]
        br.submit()
        response = br.response().read()
        soup = parseHTML(response)
        xbmc.executebuiltin('Dialog.Close(busydialog)')

        while 'auth-mfa-form' in response or 'ap_dcq_form' in response:
            Log('MFA or DCQ form')
            if 'auth-mfa-form' in response:
                msg = soup.find('form', attrs={'id': 'auth-mfa-form'})
                msgtxt = msg.p.renderContents().strip()
                kb = xbmc.Keyboard('', msgtxt)
                kb.doModal()
                if kb.isConfirmed() and kb.getText():
                    xbmc.executebuiltin('ActivateWindow(busydialog)')
                    br.select_form(nr=0)
                    br['otpCode'] = kb.getText()
                else:
                    return False
            elif 'ap_dcq_form' in response:
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

            br.submit()
            response = br.response().read()
            soup = parseHTML(response)
            WriteLog(response, 'login-mfa')
            xbmc.executebuiltin('Dialog.Close(busydialog)')

        if 'action=sign-out' in response:
            msg = soup.body.findAll('center')
            wlc = msg[1].renderContents().strip()
            usr = wlc.split(',', 1)[1][:-1].strip()
            addon.setSetting('login_acc', usr)
            addon.setSetting('use_mfa', str(useMFA).lower())
            if useMFA:
                addon.setSetting('save_login', 'false')
                savelogin = False
            if savelogin:
                writeConfig('login_name', email)
                writeConfig('login_pass', encode(password))
            else:
                cj.save(CookieFile, ignore_discard=True, ignore_expires=True)
            if ask:
                Dialog.ok(getString(30215), wlc)
            genID()
            return cj
        elif 'message_error' in response:
            writeConfig('login_pass', '')
            msg = soup.find('div', attrs={'id': 'message_error'})
            Log('Login Error: %s' % msg.p.renderContents().strip())
            Dialog.ok(getString(30200), getString(30201))
        elif 'message_warning' in response:
            msg = soup.find('div', attrs={'id': 'message_warning'})
            Log('Login Warning: %s' % msg.p.renderContents().strip())
            Dialog.ok(getString(30200), getString(30212))
        elif 'auth-error-message-box' in response:
            msg = soup.find('div', attrs={'class': 'a-alert-content'})
            Log('Login MFA: %s' % msg.ul.li.span.renderContents().strip())
            Dialog.ok(getString(30200), getString(30214))
        else:
            WriteLog(response, 'login')
            Dialog.ok(getString(30200), getString(30213))

    return False


def setLoginPW():
    keyboard = xbmc.Keyboard('', getString(30003))
    keyboard.doModal(60000)
    if keyboard.isConfirmed() and keyboard.getText():
        password = keyboard.getText()
        return password
    return False


def encode(data):
    k = triple_des(getmac(), CBC, "\0\0\0\0\0\0\0\0", padmode=PAD_PKCS5)
    d = k.encrypt(data)
    return base64.b64encode(d)


def decode(data):
    if not data:
        return ''
    k = triple_des(getmac(), CBC, "\0\0\0\0\0\0\0\0", padmode=PAD_PKCS5)
    d = k.decrypt(base64.b64decode(data))
    return d


def getmac():
    mac = uuid.getnode()
    if (mac >> 40) % 2:
        mac = node()
    return uuid.uuid5(uuid.NAMESPACE_DNS, str(mac)).bytes


def remLoginData(savelogin=False, info=True):
    if savelogin or info:
        for fn in xbmcvfs.listdir(DataPath)[1]:
            if fn.startswith('cookie'):
                xbmcvfs.delete(os.path.join(DataPath, fn))

    if not savelogin or info:
        writeConfig('login_name', '')
        writeConfig('login_pass', '')

    if info:
        addon.setSetting('login_acc', '')
        addon.setSetting('use_mfa', 'false')
        Dialog.notification(__plugin__, getString(30211), xbmcgui.NOTIFICATION_INFO)


def scrapAsins(url, cj):
    asins = []
    url = BaseUrl + url
    content = getURL(url, useCookie=cj, rjson=False)
    asins += re.compile('data-asin="(.+?)"', re.DOTALL).findall(content)
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
                    reftag TEXT
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
        if not os.path.supports_unicode_filenames:
            name = name.encode('utf-8')

    for c in notallowed:
        name = name.replace(c, '')
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
    source = {'Amazon Movies': MOVIE_PATH, 'Amazon TV': TV_SHOWS_PATH}

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


def getConfig(cfile, value=''):
    cfgfile = os.path.join(ConfigPath, cfile)

    if xbmcvfs.exists(cfgfile):
        f = xbmcvfs.File(cfgfile, 'r')
        value = f.read()
        f.close()

    return value


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

    return False


def insertLF(string, begin=70):
    spc = string.find(' ', begin)
    return string[:spc] + '\n' + string[spc + 1:] if spc > 0 else string


def parseHTML(response):
    response = re.sub(r'(?i)(<!doctype \w+).*>', r'\1>', response)
    soup = BeautifulSoup(response, convertEntities=BeautifulSoup.HTML_ENTITIES)
    return soup


def SetVol(step):
    rpc = '{"jsonrpc": "2.0", "method": "Application.GetProperties", "params": {"properties": ["volume"]}, "id": 1}'
    vol = json.loads(xbmc.executeJSONRPC(rpc))["result"]["volume"]
    xbmc.executebuiltin('SetVolume(%d,showVolumeBar)' % (vol + step))


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
        if xbmc.getInfoLabel('ListItem.Duration'):
            return int(xbmc.getInfoLabel('ListItem.Duration')) * 60
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
        self.age_list = [age[0] for age in Ages[country]]
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


if AddonEnabled('inputstream.adaptive'):
    is_addon = 'inputstream.adaptive'
elif AddonEnabled('inputstream.mpd'):
    is_addon = 'inputstream.mpd'
else:
    is_addon = None

remLoginData(addon.getSetting('save_login') == 'true', False)
AgePin = getConfig('age_pin')
PinReq = int(getConfig('pin_req', '0'))
RestrAges = ','.join(a[1] for a in Ages[country][PinReq:]) if AgePin else ''

deviceID = genID()
dbFile = os.path.join(DataPath, 'art.db')
db = sqlite.connect(dbFile)
db.text_factory = str
createDB()

menuDb = sqlite.connect(menuFile)
menuDb.text_factory = str
loadCategories()
args = dict(urlparse.parse_qsl(urlparse.urlparse(sys.argv[2]).query))
Log(args)
mode = args.get('mode', '')

if mode == 'listCategories':
    listCategories(args.get('url', ''), args.get('opt', ''))
elif mode == 'listContent':
    listContent(args.get('cat'), args.get('url', ''), int(args.get('page', '1')), args.get('opt', ''))
elif mode == 'PlayVideo':
    PlayVideo(args.get('name'), args.get('asin'), args.get('adult'), args.get('trailer'), int(args.get('selbitrate')))
elif mode == 'getList':
    getList(args.get('url', ''), int(args.get('export', '0')))
elif mode == 'WatchList':
    WatchList(args.get('url', ''), int(args.get('opt', '0')))
elif mode == 'openSettings':
    aid = args.get('url')
    aid = is_addon if aid == 'is' else aid
    xbmcaddon.Addon(aid).openSettings()
elif mode == 'ageSettings':
    if RequestPin():
        wnd = AgeSettings(getString(30018).split('.')[0])
        wnd.doModal()
        del wnd
elif mode == '':
    MainMenu()
else:
    exec mode + '()'
