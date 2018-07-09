#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from base64 import b64encode, b64decode
from BeautifulSoup import BeautifulSoup, Tag
from datetime import date
from platform import node
from random import randint
from sqlite3 import dbapi2 as sqlite
import hashlib
import hmac
import json
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

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs

from resources.lib.network import *
from resources.lib.users import *
from resources.lib.l10n import *
from resources.lib.itemlisting import *
from resources.lib.logging import *
from resources.lib.configs import *
from resources.lib import PrimeVideo
from resources.lib.common import Globals, Settings, jsonRPC
from resources.lib.playback import ParseStreams, PlayVideo
from resources.lib.ages import AgeRestrictions


def Search():
    searchString = g.dialog.input(getString(24121))
    if searchString:
        url = 'searchString=%s%s' % (urllib.quote_plus(searchString), s.OfferGroup)
        listContent('Search', url, 1, 'search')


def loadCategories(force=False):
    if xbmcvfs.exists(menuFile) and not force:
        ftime = updateTime(False)
        ctime = time.time()
        if ctime - ftime < 8 * 3600:
            return

    Log('Parse Menufile', Log.DEBUG)
    parseStart = time.time()
    data = getURL('https://raw.githubusercontent.com/Sandmann79/xbmc/master/plugin.video.amazon-test/resources/menu/%s.json' % g.MarketID)
    if not data:
        jsonfile = os.path.join(g.PLUGIN_PATH, 'resources', 'menu', g.MarketID + '.json')
        jsonfile = jsonfile.replace(g.MarketID, 'ATVPDKIKX0DER') if not xbmcvfs.exists(jsonfile) else jsonfile
        data = json.load(open(jsonfile))
    createDB(True)
    parseNodes(data)
    updateTime()
    menuDb.commit()
    Log('Parse MenuTime: %s' % (time.time() - parseStart), Log.DEBUG)


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
    st = 'all' if s.payCont else 'prime'
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
    all_vid = {'movies': [30143, 'Movie', 'root'], 'tv_shows': [30160, 'TVSeason&RollupToSeason=T', 'root_show']}

    if root in all_vid.keys():
        url = 'OrderBy=Title%s&contentType=%s' % (s.OfferGroup, all_vid[root][1])
        addDir(getString(all_vid[root][0]), 'listContent', url, opt=all_vid[root][2])

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
    xbmcplugin.endOfDirectory(g.pluginhandle)


def listContent(catalog, url, page, parent, export=False):
    oldurl = url
    ResPage = 240 if export else s.MaxResults
    url = '%s&NumberOfResults=%s&StartIndex=%s&Detailed=T' % (url, ResPage, (page - 1) * ResPage)
    titles = getATVData(catalog, url)
    titlelist = []

    if page != 1 and not export:
        addDir(' --= %s =--' % getString(30112), thumb=s.HomeIcon)

    if not titles or not len(titles['titles']):
        if 'search' in parent:
            g.dialog.ok(g.__plugin__, getString(30202))
        else:
            xbmcplugin.endOfDirectory(g.pluginhandle)
        return
    endIndex = titles['endIndex']
    numItems = len(titles['titles'])
    if 'approximateSize' not in titles.keys():
        endIndex = 1 if numItems >= s.MaxResults else 0
    else:
        if endIndex == 0:
            if (page * ResPage) <= titles['approximateSize']:
                endIndex = 1

    for item in titles['titles']:
        if 'title' not in item:
            continue
        if '_show' in parent:
            item.update(item['ancestorTitles'][0])
            url = 'SeriesASIN=%s&ContentType=TVSeason&IncludeBlackList=T' % item['titleId']
        contentType, infoLabels = getInfos(item, export)
        name = infoLabels['DisplayTitle']
        asin = item['titleId']
        wlmode = 1 if watchlist in parent else 0
        simiUrl = urllib.quote_plus('ASIN=' + asin + s.OfferGroup)
        cm = [(getString(30183),
               'Container.Update(%s?mode=listContent&cat=GetSimilarities&url=%s&page=1&opt=gs)' % (g.pluginid, simiUrl)),
              (getString(wlmode + 30180) % getString(g.langID[contentType]),
               'RunPlugin(%s?mode=WatchList&url=%s&opt=%s)' % (g.pluginid, asin, wlmode)),
              (getString(30185) % getString(g.langID[contentType]),
               'RunPlugin(%s?mode=getListMenu&url=%s&export=1)' % (g.pluginid, asin)),
              (getString(30186), 'UpdateLibrary(video)')]

        if contentType == 'movie' or contentType == 'episode':
            addVideo(name, asin, infoLabels, cm, export)
        else:
            mode = 'listContent'
            url = item['childTitles'][0]['feedUrl'] if '_show' not in parent else url

            if watchlist in parent:
                url += s.OfferGroup
            if contentType == 'season':
                name = formatSeason(infoLabels, parent)
                if library not in parent and parent != '':
                    curl = 'SeriesASIN=%s&ContentType=TVSeason&IncludeBlackList=T%s' % (
                        infoLabels['SeriesAsin'], s.OfferGroup)
                    cm.insert(0, (getString(30182), 'Container.Update(%s?mode=listContent&cat=Browse&url=%s&page=1)' % (
                        g.pluginid, urllib.quote_plus(curl))))

            if export:
                url = re.sub(r'(?i)contenttype=\w+', 'ContentType=TVEpisode', url)
                url = re.sub(r'(?i)&rollupto\w+=\w+', '', url)
                listContent('Browse', url, 1, '', export)
            else:
                if name not in titlelist:
                    titlelist.append(name)
                    addDir(name, mode, url, infoLabels, cm=cm, export=export)

    if endIndex > 0:
        if export:
            listContent(catalog, oldurl, page + 1, parent, export)
        else:
            addDir(' --= %s =--' % (getString(30111) % int(page + 1)), 'listContent', oldurl, page=page + 1,
                   catalog=catalog, opt=parent, thumb=s.NextIcon)
    if not export:
        db.commit()
        xbmc.executebuiltin('RunPlugin(%s?mode=checkMissing)' % g.pluginid)
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
    language = xbmc.convertLanguage(s.Language, xbmc.ISO_639_2)
    ExportPath = s.MOVIE_PATH
    nfoType = 'movie'
    title = infoLabels['Title']

    if isEpisode:
        ExportPath = s.TV_SHOWS_PATH
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

    if g.addon.getSetting('cr_nfo') == 'true':
        CreateInfoFile(filename, ExportPath, nfoType, infoLabels, language)

    SaveFile(filename + '.strm', url, ExportPath)
    Log('Export: ' + filename)


def WatchList(asin, remove):
    action = 'remove' if remove else 'add'
    cookie = MechanizeLogin()

    if not cookie:
        return

    par = getParams(asin, cookie)
    data = getURL(par['data-%s-url' % action],
                  postdata={'itemId': asin,
                            'dataType': 'json',
                            'csrfToken': par['data-csrf-token'],
                            'action': action,
                            'pageType': par['data-page-type'],
                            'subPageType': par['data-sub-page-type']},
                  useCookie=cookie, headers={'x-requested-with': 'XMLHttpRequest'})

    if data['success'] == 1:
        Log(asin + ' ' + data['status'])
        if remove:
            cPath = xbmc.getInfoLabel('Container.FolderPath').replace(asin, '').replace('opt=' + watchlist,
                                                                                        'opt=rem_%s' % watchlist)
            xbmc.executebuiltin('Container.Update("%s", replace)' % cPath)
    else:
        Log(data['status'] + ': ' + data['reason'])


def getParams(asin, cookie):
    url = g.BaseUrl + '/gp/video/hover/%s?format=json&refTag=dv-hover&requesterPageType=Detail' % asin
    data = getURL(url, useCookie=cookie, rjson=False)
    if data:
        data = re.compile('(<form.*</form>)').findall(data)[0]
        form = BeautifulSoup(data.replace('\\\"', '"'), convertEntities=BeautifulSoup.HTML_ENTITIES)
        return form.button
    return ''


def getArtWork(infoLabels, contentType):
    if contentType == 'movie' and s.tmdb_art == '0':
        return infoLabels
    if contentType != 'movie' and s.tvdb_art == '0':
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
                    if result[1] and result[1] != na and s.showfanart:
                        infoLabels['Fanart'] = result[1]
            return infoLabels
        elif season > -1 and s.showfanart:
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
    langcodes = [s.Language.split('_')[0]]
    langcodes += ['en'] if 'en' not in langcodes else []
    TVDB_URL = 'http://www.thetvdb.com/banners/'

    while not tvdb_id and title:
        tv = urllib.quote_plus(title.encode('utf-8'))
        result = getURL('http://www.thetvdb.com/api/GetSeries.php?seriesname=%s&language=%s' % (tv, s.Language),
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
    result = getURL('http://www.thetvdb.com/api/%s/series/%s/banners.xml' % (g.tvdb, tvdb_id), silent=True, rjson=False)
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
            content, g.tmdb, s.Language, movie, str_year), silent=True)
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
        xbmcplugin.endOfDirectory(g.pluginhandle, updateListing=False)


def getList(listing, export, cont):
    if listing == watchlist or listing == library:
        cj = MechanizeLogin()
        if not cj:
            return
        asins = ''
        for content in cont:
            asins += scrapAsins('/gp/video/%s/%s/?ie=UTF8&sort=%s' % (listing, content, s.wl_order), cj) + ','
    else:
        asins = listing

    if export:
        SetupLibrary()

    url = 'ASINList=' + asins
    listing += '_show' if s.dispShowOnly and 'movie' not in cont and not export else ''
    listContent('GetASINDetails', url, 1, listing, export)


def getAsins(content, crIL=True):
    if crIL:
        infoLabels = {'Plot': None, 'MPAA': None, 'Cast': [], 'Year': None, 'Premiered': None, 'Rating': None,
                      'Votes': None, 'isAdult': 0, 'Director': None,
                      'Genre': None, 'Studio': None, 'Thumb': None, 'Fanart': None, 'isHD': False, 'isPrime': False,
                      'AudioChannels': 1, 'TrailerAvailable': False}
    asins = content.get('titleId', '')

    for offerformat in content.get('formats', []):
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
    if 'formats' in item and'images' in item['formats'][0].keys():
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
            infoLabels['Thumb'] = s.DefaultFanart
        if not infoLabels['Fanart']:
            infoLabels['Fanart'] = s.DefaultFanart
        if not infoLabels['isPrime'] and not contentType == 'series':
            infoLabels['DisplayTitle'] = '[COLOR %s]%s[/COLOR]' % (PayCol, infoLabels['DisplayTitle'])

    return contentType, infoLabels


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
            Log(e, Log.ERROR)
    return out.strip()


def getCmdLine(videoUrl, asin, method, fr):
    scr_path = g.addon.getSetting("scr_path")
    br_path = g.addon.getSetting("br_path").strip()
    scr_param = g.addon.getSetting("scr_param").strip()
    kiosk = g.addon.getSetting("kiosk") == 'true'
    appdata = g.addon.getSetting("ownappdata") == 'true'
    cust_br = g.addon.getSetting("cust_path") == 'true'
    nobr_str = getString(30198)
    frdetect = g.addon.getSetting("framerate") == 'true'

    if method == 1:
        if not xbmcvfs.exists(scr_path):
            return False, nobr_str

        if frdetect:
            suc, fr = ParseStreams(*getURLData('catalog/GetPlaybackResources', asin, extra=True, useCookie=True)) if not fr else (True, fr)
            if not suc:
                return False, fr
        else:
            fr = ''

        return True, scr_path + ' ' + scr_param.replace('{f}', fr).replace('{u}', videoUrl)

    os_path = None
    if g.OS_WINDOWS & g.platform: os_path = ('C:\\Program Files\\', 'C:\\Program Files (x86)\\')
    if g.OS_LINUX & g.platform: os_path = ('/usr/bin/', '/usr/local/bin/')
    if g.OS_OSX & g.platform: os_path = 'open -a '
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

    if (not g.platform & g.OS_OSX) and (not cust_br):
        for path in os_path:
            for exe_file in br_config[s.browser][0][g.platform]:
                if xbmcvfs.exists(os.path.join(path, exe_file)):
                    br_path = path + exe_file
                    break
                else:
                    Log('Browser %s not found' % (path + exe_file), Log.DEBUG)
            if br_path:
                break

    if (not xbmcvfs.exists(br_path)) and (not g.platform & g.OS_OSX):
        return False, nobr_str

    br_args = br_config[s.browser][3]
    if kiosk:
        br_args += br_config[s.browser][1]
    if appdata and br_config[s.browser][2]:
        br_args += br_config[s.browser][2] + '"' + os.path.join(g.DATA_PATH, str(s.browser)) + '" '

    if g.platform & g.OS_OSX:
        if not cust_br:
            br_path = os_path + br_config[s.browser][0][g.OS_OSX]
        if br_args.strip():
            br_args = '--args ' + br_args

    br_path += ' %s"%s"' % (br_args, videoUrl)

    return True, br_path


def getStartupInfo():
    si = subprocess.STARTUPINFO()
    si.dwFlags = subprocess.STARTF_USESHOWWINDOW
    return si


def extrFr(data):
    fps_string = re.compile('frameRate="([^"]*)').findall(data)[0]
    fr = round(eval(fps_string + '.0'), 3)
    return str(fr).replace('.0', '')


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
                keys = keys.replace(sc, spec_keys[sc][g.platform - 1]).strip()
                keys_only = keys_only.replace(sc, '').strip()
        sc_only = keys.replace(keys_only, '').strip()

    if g.platform & g.OS_WINDOWS:
        app = os.path.join(g.PLUGIN_PATH, 'tools', 'userinput.exe')
        mouse = ' mouse %s %s' % (mousex, mousey)
        mclk = ' ' + str(click)
        keybd = ' key %s %s' % (keys, delay)
    elif g.platform & g.OS_LINUX:
        app = 'xdotool'
        mouse = ' mousemove %s %s' % (mousex, mousey)
        mclk = ' click --repeat %s 1' % click
        if keys_only:
            keybd = ' type --delay %s %s' % (delay, keys_only)
        if sc_only:
            if keybd:
                keybd += ' && ' + app
            keybd += ' key ' + sc_only
    elif g.platform & g.OS_OSX:
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
        user['baseurl'] = data['territoryConfig']['primeSignupg.BaseUrl']
        user['mid'] = data['territoryConfig']['avMarketplace']
        user['pv'] = 'primevideo' in host
    return (user, True)


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
    for fn in xbmcvfs.listdir(g.DATA_PATH)[1]:
        if fn.startswith('cookie'):
            xbmcvfs.delete(os.path.join(g.DATA_PATH, fn))
    writeConfig('accounts', '')
    writeConfig('login_name', '')
    writeConfig('login_pass', '')

    if info:
        writeConfig('accounts.lst', '')
        g.addon.setSetting('login_acc', '')
        g.dialog.notification(g.__plugin__, getString(30211), xbmcgui.NOTIFICATION_INFO)


def scrapAsins(aurl, cj):
    asins = []
    url = g.BaseUrl + aurl
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
    CreateDirectory(s.MOVIE_PATH)
    CreateDirectory(g.HOME_PATH)
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
    source = {ms_mov: s.MOVIE_PATH, ms_tv: s.TV_SHOWS_PATH}

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
        g.dialog.ok(getString(30187), getString(30188), getString(30189), getString(30190))
        if g.dialog.yesno(getString(30191), getString(30192)):
            xbmc.executebuiltin('RestartApp')


def insertLF(string, begin=70):
    spc = string.find(' ', begin)
    return string[:spc] + '\n' + string[spc + 1:] if spc > 0 else string


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


def getInfolabels(Infos):
    rem_keys = ('ishd', 'isprime', 'asins', 'audiochannels', 'banner', 'displaytitle', 'fanart', 'poster', 'seasonasin',
                'thumb', 'traileravailable', 'contenttype', 'isadult', 'totalseasons', 'seriesasin', 'episodename')
    if not Infos:
        return
    return {k: v for k, v in Infos.items() if k.lower() not in rem_keys}


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
        Log('Dur:%s State:%s PlbTm:%s' % (self._vidDur, watched, pBTime), Log.DEBUG)

        if pBTime > self._vidDur * 0.9 and not watched:
            xbmc.executebuiltin("Action(ToggleWatched)")

    def onAction(self, action):
        if not s.useIntRC:
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
            SetVol(+2) if s.RMC_vol else Input(keys='{U}')
        elif action == ACTION_MOVE_DOWN:
            SetVol(-2) if s.RMC_vol else Input(keys='{DWN}')
        # numkeys for pin input
        elif 57 < actionId < 68:
            strKey = str(actionId - 58)
            Input(keys=strKey)

        if showinfo:
            Input(9999, 0)
            xbmc.sleep(500)
            Input(9999, -1)


g = Globals()
s = Settings()

if not xbmcvfs.exists(os.path.join(g.DATA_PATH, 'settings.xml')):
    g.addon.openSettings()

socket.setdefaulttimeout(30)

warnings.simplefilter('error', requests.packages.urllib3.exceptions.SNIMissingWarning)
warnings.simplefilter('error', requests.packages.urllib3.exceptions.InsecurePlatformWarning)

args = dict(urlparse.parse_qsl(urlparse.urlparse(sys.argv[2]).query))

Log(args, Log.DEBUG)
mode = args.get('mode', None)

if not getConfig('UserAgent'):
    getUA()

users = loadUsers()
if users:
    if not loadUser('mid', cachedUsers=users):
        switchUser(0)

    # Set marketplace, base and atv urls, and prime video usage
    g.SetMarketplace(loadUser('mid', cachedUsers=users), loadUser('baseurl', cachedUsers=users),
            loadUser('atvurl', cachedUsers=users), loadUser('pv', cachedUsers=users))

    if g.UsePrimeVideo:
        g.pv.LoadCache()
    else:
        dbFile = os.path.join(g.DATA_PATH, 'art.db')
        db = sqlite.connect(dbFile)
        createDB()
        menuFile = os.path.join(g.DATA_PATH, 'menu-%s.db' % g.MarketID)
        menuDb = sqlite.connect(menuFile)
        loadCategories()
elif mode != 'LogIn':
    g.dialog.notification(getString(30200), getString(30216))
    xbmc.executebuiltin('g.addon.OpenSettings(%s)' % g.addon.getAddonInfo('id'))
    exit()

if None is mode:
    Log('Version: %s' % g.__version__)
    Log('Unicode filename support: %s' % os.path.supports_unicode_filenames)
    Log('Locale: %s / Language: %s' % (g.userAcceptLanguages.split(',')[0], s.Language))
    if False is not g.UsePrimeVideo:
        g.pv.BrowseRoot()
    else:
        loadCategories()

        cm_wl = [(getString(30185) % 'Watchlist', 'RunPlugin(%s?mode=getListMenu&url=%s&export=1)' % (g.pluginid, watchlist))]
        cm_lb = [(getString(30185) % getString(30100),
                  'RunPlugin(%s?mode=getListMenu&url=%s&export=1)' % (g.pluginid, library))]

        if s.multiuser:
            addDir(getString(30134).format(loadUser('name')), 'switchUser', '', cm=g.CONTEXTMENU_MULTIUSER)
        addDir('Watchlist', 'getListMenu', watchlist, cm=cm_wl)
        getRootNode()
        addDir(getString(30108), 'Search', '')
        addDir(getString(30100), 'getListMenu', library, cm=cm_lb)
        xbmcplugin.endOfDirectory(g.pluginhandle, updateListing=False)
elif mode == 'listCategories':
    listCategories(args.get('url', ''), args.get('opt', ''))
elif mode == 'listContent':
    listContent(args.get('cat'), args.get('url', '').decode('utf-8'), int(args.get('page', '1')), args.get('opt', ''))
elif mode == 'PlayVideo':
    PlayVideo(args.get('name', ''), args.get('asin'), args.get('adult', '0'), int(args.get('trailer', '0')), int(args.get('selbitrate', '0')))
elif mode == 'getList':
    getList(args.get('url', ''), int(args.get('export', '0')), [args.get('opt')])
elif mode == 'getListMenu':
    getListMenu(args.get('url', ''), int(args.get('export', '0')))
elif mode == 'WatchList':
    WatchList(args.get('url', ''), int(args.get('opt', '0')))
elif mode == 'openSettings':
    aid = args.get('url')
    aid = g.is_addon if aid == 'is' else aid
    xbmcaddon.Addon(aid).openSettings()
elif mode == 'ageSettings':
    AgeRestrictions().Settings()
elif mode == 'PrimeVideo_Browse':
    g.pv.Browse(None if 'path' not in args else args['path'])
elif mode == 'PrimeVideo_Search':
    g.pv.Search()
else:
    exec mode + '()'
