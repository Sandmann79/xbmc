#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import os.path
import pickle
from datetime import date
from base64 import b64decode

try:
    from urllib.parse import quote_plus
except ImportError:
    from urllib import quote_plus

from .ages import AgeRestrictions
from .singleton import Singleton
from .network import *
from .itemlisting import *
from .users import *
from .common import findKey
from .export import SetupLibrary


class PrimeVideo(Singleton):
    """ Wrangler of all things Amazon.(com|co.uk|de|jp) """

    def __init__(self, globalsInstance, settingsInstance):
        self._g = globalsInstance
        self._s = settingsInstance
        self.recentsdb = OSPJoin(g.DATA_PATH, 'recent.db')
        self._initialiseDB()
        self.filter = {}
        self.def_dtid = 'A43PXU4ZN2AL1'
        self.defparam = 'deviceTypeID={}' \
                        '&firmware=fmw%3A26-app%3A3.0.265.20347' \
                        '&priorityLevel=2' \
                        '&format=json' \
                        '&featureScheme=mobile-android-features-v9' \
                        '&deviceID={}' \
                        '&version=default' \
                        '&screenWidth=sw800dp' \
                        '&swiftPriorityLevel=critical'.format(self.def_dtid, g.deviceID)

    def BrowseRoot(self):
        cm_wl = [(getString(30185) % 'Watchlist', 'RunPlugin(%s?mode=getListMenu&url=%s&export=1)' % (self._g.pluginid, self._g.watchlist))]
        cm_lb = [(getString(30185) % getString(30100),
                 'RunPlugin(%s?mode=getListMenu&url=%s&export=1)' % (self._g.pluginid, self._g.library))]

        if self._s.multiuser:
            addDir(getString(30134).format(loadUser('name')), 'switchUser', '', cm=self._g.CONTEXTMENU_MULTIUSER)
        '''
        if self._s.profiles:
            act, profiles = self.getProfiles()
            if act is not False:
                addDir(profiles[act][0], 'switchProfile', '', thumb=profiles[act][3])
        '''
        addDir('Watchlist', 'getListMenu', self._g.watchlist, cm=cm_wl)
        self.getPage(root=True)

        if self._s.show_recents:
            addDir(getString(30136), 'Recent', '')
        addDir(getString(30108), 'Search', '')
        addDir(getString(30100), 'getListMenu', self._g.library, cm=cm_lb)
        xbmcplugin.endOfDirectory(self._g.pluginhandle, updateListing=False, cacheToDisc=False)

    def getPage(self, page='landing', params='pageType=home&pageId=home', root=False):
        url_path = '/cdp/mobile/getDataByTransform/v1/'
        url_dict = {'landing': {'js': 'dv-android/landing/v2/landing.js', 'q': '&removeFilters=false'},
                    'home': {'js': 'dv-android/landing/v2/landingCollections.js', 'q': ''},
                    'browse': {'js': 'dv-android/browse/v1/browseInitial.js', 'q': ''},
                    'browsenext': {'js': 'dv-android/browse/v1/browseNext.js', 'q': ''},
                    'detail': {'js': 'dv-android/detail/v2/user/v2.2.js', 'q': '&capabilities='},
                    'details': {'js': 'android/atf/v3.jstl', 'q': '&capabilities='}}
        url = self._g.ATVUrl + url_path + url_dict[page]['js']
        params += url_dict[page]['q']
        resp = getURL('%s?%s&%s' % (url, self.defparam, params), useCookie=True)['resource']
        LogJSON(resp)

        if resp:
            if root:
                for item in findKey('filters', resp):
                    d = findKey('parameters', item)
                    d['text'] = item['text']
                    d['swiftId'] = item['id']
                    t = json.loads(b64decode(d['serviceToken']))
                    id = [k for k in t['filter'].keys()][0]
                    Log(id)
                    self.filter[id] = d

                for item in resp['navigations']:
                    q = findKey('parameters', item)
                    q['serviceToken'] = self.filter['PRIME']['serviceToken']
                    addDir(item['text'].capitalize(), 'getPage', 'landing', opt=urlencode(q))
                return

            if page == 'details':
                if 'episodes' in resp:
                    for item in resp['episodes']:
                        il = self.getInfos(item, False)
                        if il.get('episode', 1) > 0:
                            addVideo(il['title'], il['asins'], il)
                else:
                    il = self.getInfos(resp, False)
                    addVideo(il['title'], il['asins'], il)
                setContentAndView(il['contentType'])
                return

            if page == 'landing':
                pgmodel = resp.get('paginationModel')
                if pgmodel:
                    q = findKey('parameters', pgmodel)
                    q['swiftId'] = pgmodel['id']
                    q['pageSize'] = 20
                    q['startIndex'] = 0
                    self.getPage('home', urlencode(q))
                    return

            col = findKey('collections', resp)
            if col:
                for item in col:
                    col_act = item.get('collectionAction')
                    if col_act:
                        q = findKey('parameters', col_act)
                        q_flt = {k: v for k, v in q.items() if v is not None}
                        addDir(item['headerText'], 'getPage', col_act['type'], opt=urlencode(q_flt))
            else:
                titles = resp['titles'][0] if len(resp.get('titles', {})) > 0 else resp
                pgmodel = titles.get('paginationModel')
                items = titles.get('collectionItemList', [])

                for item in items:
                    il = self.getInfos(item['model'], False)
                    ct = il['contentType']
                    if ct == 'movie' or ct == 'episode':
                        addVideo(il['title'], il['asins'], il)
                    else:
                        addDir(il['title'], 'getPage', 'details', infoLabels=il, opt='itemId='+il['asins'])

                if pgmodel:
                    nextp = pgmodel['parameters']
                    nextp['pageSize'] = 40
                    pagenr = int(nextp['startIndex'] / len(items) + 1)
                    addDir(' --= %s =--' % (getString(30111) % pagenr), 'getPage', 'browsenext', opt=urlencode(nextp), thumb=self._s.NextIcon)

            xbmcplugin.endOfDirectory(g.pluginhandle)
        return

    def Search(self, searchString=None):
        if searchString is None:
            searchString = self._g.dialog.input(getString(24121)).encode('utf-8')
        if searchString:
            url = 'searchString=%s%s' % (quote_plus(searchString), self._s.OfferGroup)
            self.listContent('Search', url, 1, 'search')
        else:
            xbmc.executebuiltin('RunPlugin(%s)' % g.pluginid)

    def getRecents(self):
        all_rec = {}
        if xbmcvfs.exists(self.recentsdb):
            with open(self.recentsdb, 'rb') as fp:
                try:
                    all_rec = pickle.load(fp)
                except:
                    pass

        cur_user = loadUser('name') + getConfig('profileID')
        user_rec = all_rec.get(cur_user, [])
        return all_rec, user_rec

    def Recent(self, export=0):
        all_rec, rec = self.getRecents()
        asins = ','.join(rec)
        url = 'asinlist=' + asins
        self.listContent('Browse', url, 1, 'recent', export)

    def updateRecents(self, asin, rem=0):
        if not self._s.show_recents:
            return

        all_rec, rec = self.getRecents()
        if rem == 0:
            content = getATVData('GetASINDetails', 'ASINList=' + asin)['titles']
            if len(content) < 1:
                return
            ct, Info = g.pv.getInfos(content[0], False)
            asin = Info.get('SeasonAsin', Info.get('SeriesAsin', asin))
        if asin in rec:
            rec.remove(asin)
        if rem == 0:
            rec.insert(0, asin)
        if len(rec) > 200:
            rec = rec[0:200]

        with open(self.recentsdb, 'wb') as fp:
            cur_user = loadUser('name') + getConfig('profileID')
            if cur_user in all_rec.keys():
                all_rec[cur_user] = rec
            else:
                all_rec.update({cur_user: rec})
            pickle.dump(all_rec, fp)
        if rem == 1:
            xbmc.executebuiltin('Container.Update("%s", replace)' % xbmc.getInfoLabel('Container.FolderPath'))

    def _createDB(self, table):
        c = self._menuDb.cursor()
        if table == self._menu_tbl:
            c.execute('drop table if exists %s' % self._menu_tbl)
            c.execute('''CREATE TABLE %s(
                        node TEXT,
                        title TEXT,
                        category TEXT,
                        content TEXT,
                        id TEXT,
                        infolabel TEXT
                        );''' % self._menu_tbl)
            self._menuDb.commit()
        elif table == self._chan_tbl:
            c.execute('drop table if exists %s' % self._chan_tbl)
            c.execute('''CREATE TABLE %s(
                        uid TEXT,
                        data JSON,
                        time TIMESTAMP,
                        ref TEXT
                        );''' % self._chan_tbl)
            self._menuDb.commit()
        elif table == self._art_tbl:
            c = self._db.cursor()
            c.execute('''CREATE TABLE IF NOT EXISTS %s(
                        asin TEXT,
                        season INTEGER,
                        poster TEXT,
                        banner TEXT,
                        fanart TEXT,
                        lastac DATE,
                        PRIMARY KEY(asin, season)
                        );''' % self._art_tbl)
            c.execute('''CREATE TABLE IF NOT EXISTS miss(
                        asins TEXT,
                        title TEXT,
                        year TEXT,
                        content TEXT,
                        PRIMARY KEY(asins, title)
                        );''')
            self._db.commit()
        c.close()

    def _initialiseDB(self):
        from sqlite3 import dbapi2 as sqlite
        self._menu_tbl = 'menu'
        self._chan_tbl = 'channels'
        self._art_tbl = 'art'
        self._dbFile = os.path.join(self._g.DATA_PATH, 'art.db')
        self._db = sqlite.connect(self._dbFile)
        self._menuFile = os.path.join(self._g.DATA_PATH, 'menu-%s.db' % self._g.MarketID)
        self._menuDb = sqlite.connect(self._menuFile)
        self._createDB(self._art_tbl)

    @staticmethod
    def cleanTitle(title):
        if title.isupper():
            title = title.title().replace('[Ov]', '[OV]').replace('Bc', 'BC')
        title = title.replace('\u2013', '-').replace('\u00A0', ' ').replace('[dt./OV]', '').replace('_DUPLICATE_', '')
        return title.strip()

    def getArtWork(self, infoLabels, contentType):
        if contentType == 'movie' and self._s.tmdb_art == '0':
            return infoLabels
        if contentType != 'movie' and self._s.tvdb_art == '0':
            return infoLabels

        c = self._db.cursor()
        asins = infoLabels['asins']
        infoLabels['banner'] = None
        season = -1 if contentType == 'series' else -2

        if contentType == 'season' or contentType == 'episode':
            asins = infoLabels.get('SeriesAsin', asins)
        if 'Season' in infoLabels.keys():
            season = int(infoLabels['season'])

        extra = ' and season = %s' % season if season > -2 else ''

        for asin in asins.split(','):
            result = c.execute('select poster,fanart,banner from art where asin like (?)' + extra,
                               ('%' + asin + '%',)).fetchone()
            if result:
                if result[0] and contentType != 'episode' and result[0] != self._g.na:
                    infoLabels['thumb'] = result[0]
                if result[0] and contentType != 'movie' and result[0] != self._g.na:
                    infoLabels['poster'] = result[0]
                if result[1] and result[1] != self._g.na:
                    infoLabels['fanart'] = result[1]
                if result[2] and result[2] != self._g.na:
                    infoLabels['banner'] = result[2]
                if season > -1:
                    result = c.execute('select poster, fanart from art where asin like (?) and season = -1',
                                       ('%' + asin + '%',)).fetchone()
                    if result:
                        if result[0] and result[0] != self._g.na and contentType == 'episode':
                            infoLabels['poster'] = result[0]
                        if result[1] and result[1] != self._g.na and self._s.showfanart:
                            infoLabels['fanart'] = result[1]
                return infoLabels
            elif season > -1 and self._s.showfanart:
                result = c.execute('select poster,fanart from art where asin like (?) and season = -1',
                                   ('%' + asin + '%',)).fetchone()
                if result:
                    if result[0] and result[0] != self._g.na and contentType == 'episode':
                        infoLabels['poster'] = result[0]
                    if result[1] and result[1] != self._g.na:
                        infoLabels['fanart'] = result[1]
                    return infoLabels

        if contentType != 'episode':
            title = infoLabels['title']
            if contentType == 'season':
                title = infoLabels['tvshowtitle']
            c.execute('insert or ignore into miss values (?,?,?,?)', (asins, title, infoLabels['year'], contentType))
        c.close()
        self._db.commit()
        return infoLabels

    def checkMissing(self):
        Log('Starting Fanart Update')
        c = self._db.cursor()
        for data in c.execute('select distinct * from miss').fetchall():
            self.loadArtWork(*data)
        c.execute('drop table if exists miss')
        c.close()
        self._db.commit()
        self._createDB(self._art_tbl)
        Log('Finished Fanart Update')

    def loadArtWork(self, asins, title, year, contentType):
        seasons = None
        season_number = None
        poster = None
        fanart = None
        title = title.lower().replace('?', '').replace('omu', '').split('(')[0].split('[')[0].strip()

        if not title:
            return

        if contentType == 'movie':
            fanart = self.getTMDBImages(title, year=year)
        if contentType == 'season' or contentType == 'series':
            seasons, poster, fanart = self.getTVDBImages(title)
            if not fanart:
                fanart = self.getTMDBImages(title, content='tv')
            season_number = -1
            content = getATVData('GetASINDetails', 'ASINList=' + asins)['titles']
            if content:
                asins = self.getAsins(content[0], False)
                del content

        cur = self._db.cursor()
        if fanart:
            cur.execute('insert or ignore into art values (?,?,?,?,?,?)', (asins, season_number, poster, None, fanart, date.today()))
        if seasons:
            for season, url in seasons.items():
                cur.execute('insert or ignore into art values (?,?,?,?,?,?)', (asins, season, url, None, None, date.today()))
        self._db.commit()
        cur.close()

    def getTVDBImages(self, title, tvdb_id=None):
        Log('searching fanart for %s at thetvdb.com' % title.upper())
        posterurl = fanarturl = None
        splitter = [' - ', ': ', ', ']
        langcodes = [self._s.Language.split('_')[0]]
        langcodes += ['en'] if 'en' not in langcodes else []
        TVDB_URL = 'http://www.thetvdb.com/banners/'

        while not tvdb_id and title:
            tv = quote_plus(title.encode('utf-8'))
            result = getURL('http://www.thetvdb.com/api/GetSeries.php?seriesname=%s&language=%s' % (tv, self._s.Language),
                            silent=True, rjson=False)
            if not result:
                continue
            soup = BeautifulSoup(result, 'html.parser')
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
        result = getURL('http://www.thetvdb.com/api/%s/series/%s/banners.xml' % (self._g.tvdb, tvdb_id), silent=True, rjson=False)
        if result:
            soup = BeautifulSoup(result, 'html.parser')
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

    def getTMDBImages(self, title, content='movie', year=None):
        Log('searching fanart for %s at tmdb.com' % title.upper())
        fanart = tmdb_id = None
        splitter = [' - ', ': ', ', ']
        TMDB_URL = 'http://image.tmdb.org/t/p/original'
        yearorg = year

        while not tmdb_id and title:
            str_year = '&year=' + str(year) if year else ''
            movie = quote_plus(title.encode('utf-8'))
            data = getURL('http://api.themoviedb.org/3/search/%s?api_key=%s&language=%s&query=%s%s' % (
                content, self._g.tmdb, self._s.Language, movie, str_year), silent=True)
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
            fanart = self._g.na
        return fanart

    def formatSeason(self, infoLabels, parent):
        name = ''
        season = infoLabels['season']
        if parent:
            if infoLabels['title'].lower().strip() != infoLabels['tvshowtitle'].lower().strip():
                return infoLabels['DisplayTitle']
            name = infoLabels['title'] + ' - '
        if season != 0 and season < 100:
            name += getString(30167) + ' ' + str(season)
        elif season > 1900:
            name += getString(30168) + str(season)
        elif season > 99:
            name += getString(30167) + ' ' + str(season).replace('0', '.')
        else:
            name += getString(30169)
        if not infoLabels['isPrime']:
            name = '[COLOR %s]%s[/COLOR]' % (self._g.PayCol, name)
        return name

    def getListMenu(self, listing, export):
        if export:
            self.listContent(listing, 'MOVIE', 1, listing, export)
            self.listContent(listing, 'TV', 1, listing, export)
            if export == 2:
                writeConfig('last_wl_export', time.time())
                xbmc.executebuiltin('UpdateLibrary(video)')
        else:
            addDir(getString(30104), 'listContent', 'MOVIE', catalog=listing, export=export)
            addDir(getString(30107), 'listContent', 'TV', catalog=listing, export=export)
            xbmcplugin.endOfDirectory(self._g.pluginhandle, updateListing=False)

    def _scrapeAsins(self, aurl, cj):
        asins = []
        url = self._g.BaseUrl + aurl
        json = getURL(url, useCookie=cj)
        if not json:
            return False, False
        WriteLog(str(json), 'watchlist')
        cont = findKey('content', json)
        info = {'approximateSize': cont.get('totalItems', 0),
                'endIndex': cont.get('nextPageStartIndex', 0)}

        for item in cont.get('items', []):
            asins.append(item['titleID'])
        return info, ','.join(asins)

    def getList(self, listing, export, cont, page=1):
        info = {}
        if listing in [self._g.watchlist, self._g.library]:
            cj = MechanizeLogin()
            if not cj:
                return [], ''
            args = {listing: {'sort': self._s.wl_order,
                              'libraryType': 'Items',
                              'primeOnly': False,
                              'startIndex': (page - 1) * 60,
                              'contentType': cont},
                    'shared': {'isPurchaseRow': 0}}

            url = '/gp/video/api/myStuff{}?viewType={}&args={}'.format(listing.capitalize(), listing, json.dumps(args, separators=(',', ':')))
            info, asins = self._scrapeAsins(url, cj)
            if info is False:
                Log('Cookie invalid', Log.ERROR)
                g.dialog.notification(g.__plugin__, getString(30266), xbmcgui.NOTIFICATION_ERROR)
                return [], ''
        else:
            asins = listing

        url = 'asinlist=%s&StartIndex=0&Detailed=T' % asins
        listing += '_show' if (self._s.dispShowOnly and not (export and asins == listing)) or cont == '_show' else ''
        titles = getATVData('Browse', url)
        titles.update(info)
        return titles, listing

    @staticmethod
    def getAsins(content, crIL=True):
        infoLabels = {'plot': None, 'mpaa': None, 'cast': [], 'year': None, 'premiered': None, 'rating': None, 'votes': None, 'isAdult': 0,
                      'director': None, 'genre': None, 'studio': None, 'thumb': None, 'fanart': None, 'isHD': False,
                      'audiochannels': 1, 'TrailerAvailable': False,
                      'asins': content.get('id', content.get('titleId', '')),
                      'isPrime': content.get('showPrimeEmblem', False)}

        if 'badges' in content:
            b = content['badges']
            infoLabels['isAdult'] = 1 if b['adult'] else 0
            infoLabels['isPrime'] = b['prime']
            infoLabels['audiochannels'] = 6 if b['dolby51'] else 2
        if 'playbackActions' in content and len(content['playbackActions']) > 0:
            pa = content['playbackActions'][0]
            infoLabels['isHD'] = pa['userPlaybackMetadata']['videoQuality'] is not 'SD'

        del content
        return infoLabels if crIL else infoLabels['asins']

    def getInfos(self, title, export):
        def getFullImage(url):
            if url:
                thumbnailFilename = url.split('/')[-1]
                thumbnailBase = url.replace(thumbnailFilename, '')
                url = thumbnailBase + thumbnailFilename.split('.')[0] + '.jpg'
            return url
        import datetime
        item = {k: v for k, v in title.items() if v is not None}
        imgurls = item.get('titleImageUrls', {})
        reldate = item.get('publicReleaseDate', item.get('releaseDate', 0))
        reldate = reldate * -1 if reldate < 0 else reldate
        infoLabels = self.getAsins(item)
        infoLabels['contentType'] = infoLabels['mediatype'] = ct = item['contentType'].lower()
        infoLabels['DisplayTitle'] = infoLabels['title'] = self.cleanTitle(item['title'])
        infoLabels['plot'] = item['synopsis']
        infoLabels['isAdult'] = False
        infoLabels['traileravailable'] = True
        infoLabels['fanart'] = getFullImage(imgurls.get('WIDE', imgurls.get('WIDE_PRIME', item.get('detailPageHeroImageUrl'))))
        infoLabels['thumb'] = getFullImage(imgurls.get('LEGACY', imgurls.get('LEGACY_PRIME', item.get('titleImageUrl'))))
        infoLabels['votes'] = item.get('amazonRatingsCount', 0)
        infoLabels['premiered'] = datetime.datetime.fromtimestamp(reldate / 1000).strftime('%Y-%m-%d')
        infoLabels['genre'] = item.get('genres')
        infoLabels['studio'] = item.get('studios')
        if item.get('runtimeMillis'):
            infoLabels['duration'] = item['runtimeMillis'] / 1000
        if item.get('runtimeSeconds'):
            infoLabels['duration'] = item['runtimeSeconds']
        if 'episode' in ct:
            infoLabels['episode'] = item['episodeNumber']
            infoLabels['season'] = item['seasonNumber']
        if infoLabels['votes'] > 0:
            infoLabels['rating'] = item.get('amazonAverageRating', 1) * 2
        if 'regulatoryRating' in item:
            if item['regulatoryRating'] == 'not_checked' or not item['regulatoryRating']:
                infoLabels['mpaa'] = getString(30171)
            else:
                infoLabels['mpaa'] = '%s %s' % (AgeRestrictions().GetAgeRating(), item['regulatoryRating'])
        return infoLabels

    @staticmethod
    def cleanIMGurl(img):
        # r'\.[^/]+(\.[^/]+$)', '\\1'
        return re.sub(r'\._.*_\.', r'.', img) if img else None

    def getProfiles(self):
        j = GrabJSON(self._g.BaseUrl + '/gp/video/profiles')
        if not j:
            return False, False
        profiles = []
        active = 0
        for item in j['profiles']:
            url = self._g.BaseUrl + item['switchLink']['partialURL']
            n = item.get('name', 'Default').encode('utf-8')
            profiles.append((n, url, item['switchLink']['query'], item['avatarUrl']))
            if item.get('isSelected', False):
                active = len(profiles) - 1
                writeConfig('profileID', '' if item.get('isDefault', False) else n)
        return active, profiles

    def switchProfile(self):
        active, profiles = self.getProfiles()
        if active is not False:
            ret = self._g.dialog.select('Amazon', [i[0] for i in profiles])
            if ret >= 0 and ret != active:
                getURL(profiles[ret][1], postdata=profiles[ret][2], useCookie=True, rjson=False, check=True)
        exit()

    def Route(self, mode, args):
        if mode == 'listCategories':
            self.listCategories(args.get('url', ''), args.get('opt', ''))
        elif mode == 'listContent':
            url = py2_decode(args.get('url', ''))
            self.listContent(args.get('cat'), url, int(args.get('page', '1')), args.get('opt', ''), int(args.get('export', '0')))
        elif mode == 'getList':
            self.getList(args.get('url', ''), int(args.get('export', '0')), args.get('opt'))
        elif mode == 'getListMenu':
            self.getListMenu(args.get('url', ''), int(args.get('export', '0')))
        elif mode == 'WatchList':
            self.WatchList(args.get('url', ''), int(args.get('opt', '0')))
        elif mode == 'Search':
            searchString = args.get('searchstring')
            self.Search(searchString)
        elif mode in ['checkMissing', 'Recent', 'switchProfile']:
            exec ('g.pv.{}()'.format(mode))
        elif mode == 'Channel':
            self.Channel(url=args.get('url'), uid=args.get('opt'))
        elif mode == 'updateRecents':
            self.updateRecents(args.get('asin', ''), int(args.get('rem', '0')))
        elif mode == 'languageselect':
            g.dialog.notification(g.__plugin__, getString(30269))
        elif mode == 'ageSettings':
            AgeRestrictions().Settings()
        elif mode == 'getPage':
            self.getPage(args.get('url'), args.get('opt'))







