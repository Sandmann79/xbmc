#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import json
import os.path
import pickle
import re
import time
from datetime import date
from os.path import join as OSPJoin

from kodi_six import xbmc, xbmcgui, xbmcplugin, xbmcvfs
from kodi_six.utils import py2_decode

from .ages import AgeRestrictions
from .common import findKey, MechanizeLogin
from .configs import getConfig, writeConfig
from .export import SetupLibrary
from .l10n import getString
from .logging import Log, WriteLog
from .network import getATVData, getURL, GrabJSON
from .itemlisting import addDir, addVideo, setContentAndView
from .singleton import Singleton
from .users import loadUser

try:
    from urllib.parse import quote_plus
except ImportError:
    from urllib import quote_plus


class PrimeVideo(Singleton):
    """Wrangler of all things Amazon.(com|co.uk|de|jp)"""

    # ---------------------------------------------------------------------
    # lifecycle
    # ---------------------------------------------------------------------
    def __init__(self, globalsInstance, settingsInstance):
        self._g = globalsInstance
        self._s = settingsInstance
        self.recentsdb = OSPJoin(self._g.DATA_PATH, 'recent.db')

        # guard to avoid repeating heavy artwork operations -> less UI stutter
        self._art_update_ran = False

        self._initialiseDB()
        self.loadCategories()

    # =====================================================================
    # 1. CENTRALIZED POST-LIST ACTIONS (Template-style)
    # =====================================================================
    def _should_run_art_update(self, page, content_type):
        """
        Encapsulate decision logic so we don't keep adding ifs in the main path.
        """
        if page != 1:
            return False
        if self._art_update_ran:
            return False
        if content_type not in ('movie', 'episode', 'season', 'series', 'tvshow'):
            return False
        return True

    def _run_art_update(self):
        """
        Actually trigger the heavy artwork backfill through the existing plugin hook.
        """
        self._art_update_ran = True
        xbmc.executebuiltin('RunPlugin(%s?mode=checkMissing)' % self._g.pluginid)

    def _post_list_actions(self, page, parent, content_type, export):
        """
        Perform common follow-up actions after a listContent call.
        Kept lean; heavy stuff is guarded to avoid stalls.
        """
        if export:
            return

        # always flush
        self._db.commit()

        # restore view
        if 'search' in parent:
            setContentAndView('season')
        else:
            setContentAndView(content_type)

        # heavy part
        if self._should_run_art_update(page, content_type):
            self._run_art_update()

    # =====================================================================
    # 2. ROOT BROWSING
    # =====================================================================
    def BrowseRoot(self):
        cm_wl = [
            (
                getString(30185) % 'Watchlist',
                'RunPlugin(%s?mode=getListMenu&url=%s&export=1)'
                % (self._g.pluginid, self._g.watchlist),
            )
        ]
        cm_lb = [
            (
                getString(30185) % getString(30100),
                'RunPlugin(%s?mode=getListMenu&url=%s&export=1)'
                % (self._g.pluginid, self._g.library),
            )
        ]

        if self._s.multiuser:
            addDir(
                getString(30134).format(loadUser('name')),
                'switchUser',
                '',
                cm=self._g.CONTEXTMENU_MULTIUSER,
            )

        if self._s.profiles:
            act, profiles = self.getProfiles()
            if act is not False:
                addDir(profiles[act][0], 'switchProfile', '', thumb=profiles[act][3])

        addDir('Watchlist', 'getListMenu', self._g.watchlist, cm=cm_wl)
        self.listCategories(0)
        addDir(
            'Channels',
            'Channel',
            '/gp/video/storefront/ref=nav_shopall_nav_sa_aos?filterId=OFFER_FILTER%3DSUBSCRIPTIONS',
            opt='root',
        )
        if self._s.show_recents:
            addDir(getString(30136), 'Recent', '')
        addDir(getString(30108), 'Search', '')
        addDir(getString(30100), 'getListMenu', self._g.library, cm=cm_lb)
        xbmcplugin.endOfDirectory(self._g.pluginhandle, updateListing=False, cacheToDisc=False)

    # =====================================================================
    # 3. SEARCH / RECENTS
    # =====================================================================
    def Search(self, searchString=None):
        if searchString is None:
            searchString = self._g.dialog.input(getString(24121)).encode('utf-8')
        if searchString:
            url = 'searchString=%s%s' % (quote_plus(searchString), self._s.OfferGroup)
            self.listContent('Search', url, 1, 'search')
        else:
            xbmc.executebuiltin('RunPlugin(%s)' % self._g.pluginid)

    def getRecents(self):
        all_rec = {}
        if xbmcvfs.exists(self.recentsdb):
            with open(self.recentsdb, 'rb') as fp:
                try:
                    all_rec = pickle.load(fp)
                except Exception:
                    pass

        cur_user = loadUser('name') + getConfig('profileID')
        user_rec = all_rec.get(cur_user, [])
        return all_rec, user_rec

    def Recent(self, export=0):
        _, rec = self.getRecents()
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
            _, info = self._g.pv.getInfos(content[0], False)
            asin = info.get('SeasonAsin', info.get('SeriesAsin', asin))
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
            xbmc.executebuiltin(
                'Container.Update("%s", replace)' % xbmc.getInfoLabel('Container.FolderPath')
            )

    # =====================================================================
    # 4. DB INIT
    # =====================================================================
    def _createDB(self, table):
        from sqlite3 import dbapi2 as sqlite
        c = self._menuDb.cursor()
        if table == self._menu_tbl:
            c.execute('drop table if exists %s' % self._menu_tbl)
            c.execute(
                '''CREATE TABLE %s(
                        node TEXT,
                        title TEXT,
                        category TEXT,
                        content TEXT,
                        id TEXT,
                        infolabel TEXT
                        );''' % self._menu_tbl
            )
            self._menuDb.commit()
        elif table == self._chan_tbl:
            c.execute('drop table if exists %s' % self._chan_tbl)
            c.execute(
                '''CREATE TABLE %s(
                        uid TEXT,
                        data JSON,
                        time TIMESTAMP,
                        ref TEXT
                        );''' % self._chan_tbl
            )
            self._menuDb.commit()
        elif table == self._art_tbl:
            c = self._db.cursor()
            c.execute(
                '''CREATE TABLE IF NOT EXISTS %s(
                        asin TEXT,
                        season INTEGER,
                        poster TEXT,
                        banner TEXT,
                        fanart TEXT,
                        lastac DATE,
                        PRIMARY KEY(asin, season)
                        );''' % self._art_tbl
            )
            c.execute(
                '''CREATE TABLE IF NOT EXISTS miss(
                        asins TEXT,
                        title TEXT,
                        year TEXT,
                        content TEXT,
                        PRIMARY KEY(asins, title)
                        );'''
            )
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

    # =====================================================================
    # 5. MENU / CATEGORIES
    # =====================================================================
    def loadCategories(self, force=False):
        if xbmcvfs.exists(self._menuFile) and not force:
            ftime = self.updateTime(False)
            ctime = time.time()
            if ctime - ftime < 8 * 3600:
                return

        Log('Parse Menufile', Log.DEBUG)
        parseStart = time.time()
        data = getURL(
            'https://raw.githubusercontent.com/Sandmann79/xbmc/master/plugin.video.amazon-test/resources/menu/%s.json'
            % self._g.MarketID
        )
        if not data:
            jsonfile = os.path.join(
                self._g.PLUGIN_PATH, 'resources', 'menu', self._g.MarketID + '.json'
            )
            jsonfile = (
                jsonfile.replace(self._g.MarketID, 'ATVPDKIKX0DER')
                if not xbmcvfs.exists(jsonfile)
                else jsonfile
            )
            data = json.load(open(jsonfile))
        self._createDB(self._menu_tbl)
        self.parseNodes(data)
        self.updateTime()
        self._menuDb.commit()
        Log('Parse MenuTime: %s' % (time.time() - parseStart), Log.DEBUG)

    def updateTime(self, savetime=True):
        c = self._menuDb.cursor()
        if savetime:
            self.wMenuDB(
                ['last_update', '', '', str(time.time()), str(self._g.DBVersion), ''],
                self._menu_tbl,
            )
        else:
            try:
                result = c.execute(
                    'select content, id from menu where node = ("last_update")'
                ).fetchone()
            except Exception:
                result = 0
            c.close()
            if result:
                if self._g.DBVersion > float(result[1]):
                    return 0
                return float(result[0])
            return 0
        c.close()

    def parseNodes(self, data, node_id=''):
        if not isinstance(data, list):
            data = [data]

        for count, entry in enumerate(data):
            category = None
            if 'categories' in entry.keys():
                self.parseNodes(entry['categories'], '%s%s' % (node_id, count))
                content = '%s%s' % (node_id, count)
                category = 'node'
            else:
                for e in ['query', 'play', 'link']:
                    if e in entry.keys():
                        content = entry[e]
                        category = e
            if category:
                self.wMenuDB(
                    [
                        node_id,
                        entry.get('title', ''),
                        category,
                        content,
                        entry.get('id', ''),
                        json.dumps(entry.get('infolabel', '')),
                    ],
                    self._menu_tbl,
                )

    def wMenuDB(self, menudata, table):
        asterix = '?,' * len(menudata)
        c = self._menuDb.cursor()
        c.execute('insert or ignore into %s values (%s)' % (table, asterix[:-1]), menudata)
        c.close()

    def getNode(self, node, dist='distinct *', opt=''):
        c = self._menuDb.cursor()
        result = c.execute(
            'select {} from menu where node = (?){}'.format(dist, opt), (node,)
        ).fetchall()
        c.close()
        return result

    def listCategories(self, node, root=None):
        self.loadCategories()
        cat = self.getNode(node)
        all_vid = {
            'movies': [30143, 'Movie', 'root'],
            'tv_shows': [30160, 'TVSeason', 'root_show'],
        }

        if root in all_vid.keys():
            url = 'OrderBy=Title%s&contentType=%s' % (self._s.OfferGroup, all_vid[root][1])
            addDir(getString(all_vid[root][0]), 'listContent', url, opt=all_vid[root][2])

        for _, title, category, content, menu_id, infolabel in cat:
            infolabel = json.loads(infolabel)
            mode = None
            info = None
            opt = ''
            if infolabel:
                info = self.getAsins({'formats': []}, True)
                info.update(infolabel)

            if category == 'node':
                url = content
                mode = 'listCategories'
                if menu_id in all_vid.keys() and node == 0:
                    st = 'all' if self._s.paycont else 'prime'
                    inner = self.getNode(content, 'content', ' and id = "{}"'.format(st))
                    url = inner[0][0] if inner else content
                    opt = menu_id
                if menu_id == 'channels' and node == 0:
                    continue
            elif category == 'query':
                mode = 'listContent'
                opt = 'listcat'
                url = re.sub('\n|\\n', '', content)
            elif category == 'play':
                addVideo(info['title'], info['Asins'], info)
            elif category == 'link':
                mode = 'Channel'
                opt = 'root'
                url = content

            if mode:
                addDir(title, mode, url, info, opt)
        if node != 0:
            xbmcplugin.endOfDirectory(self._g.pluginhandle)

    # =====================================================================
    # 6. CONTENT LISTING (core)
    # =====================================================================
    def _should_continue_paging(self, titles, page, res_page):
        """
        Classic guard method to decide whether to show the "next page" entry.
        """
        end_index = titles['endIndex']
        if 'approximateSize' not in titles.keys():
            # old/non-paged responses
            if len(titles['titles']) > self._s.items_perpage:
                end_index = 0
        else:
            if end_index == 0 and (page * res_page) <= titles['approximateSize']:
                end_index = 1
        return end_index > 0

    def _build_context_menu(self, parent, contentType, asin, wl_asin):
        """
        Build context menu entries once; reuse everywhere.
        """
        wlmode = 1 if self._g.watchlist in parent else 0
        cm = [
            (
                getString(wlmode + 30180) % getString(self._g.langID[contentType]),
                'RunPlugin(%s?mode=WatchList&url=%s&opt=%s)'
                % (self._g.pluginid, wl_asin, wlmode),
            ),
            (
                getString(30185) % getString(self._g.langID[contentType]),
                'RunPlugin({}?mode=listContent&cat=GetASINDetails&url=asinList%3D{}&export=1)'.format(
                    self._g.pluginid, asin
                ),
            ),
            (getString(30186), 'UpdateLibrary(video)'),
        ]
        return cm

    def _skip_item_for_export(self, export, catalog, infoLabels, parent):
        return (
            export
            and catalog == "Browse"
            and not infoLabels['isPrime']
            and not self._s.paycont
            and self._g.library not in parent
        )

    def listContent(self, catalog, url, page, parent, export=0):
        oldurl = url
        titlelist = []
        ResPage = self._s.items_perpage
        contentType = ''

        if export:
            ResPage = 240
            SetupLibrary()

        if catalog in (self._g.watchlist, self._g.library):
            titles, parent = self.getList(catalog, export, url, page)
            ResPage = 60
        else:
            url = '%s&NumberOfResults=%s&StartIndex=%s&Detailed=T' % (
                url,
                ResPage,
                (page - 1) * ResPage,
            )
            titles = getATVData(catalog, url)

        if page != 1 and not export:
            addDir(' --= %s =--' % getString(30112), thumb=self._g.HomeIcon)

        if not titles or not len(titles.get('titles', [])):
            if 'search' in parent:
                self._g.dialog.ok(self._g.__plugin__, getString(30202))
            else:
                xbmcplugin.endOfDirectory(self._g.pluginhandle)
            return

        for item in titles['titles']:
            url = ''
            if 'title' not in item:
                continue
            wl_asin = item['titleId']

            # handle ancestry to derive child URLs
            if item.get('ancestorTitles'):
                if '_show' in parent:
                    item.update(item['ancestorTitles'][0])
                    url = (
                        'SeriesASIN=%s&ContentType=TVSeason&IncludeBlackList=T'
                        % item['titleId']
                    )
                elif re.search('(?i)rolluptoseason=t|contenttype=tvseason', oldurl):
                    for i in item['ancestorTitles']:
                        if i['contentType'] == 'SEASON':
                            item.update(i)
                            url = (
                                'SeasonASIN=%s&ContentType=TVEpisode&IncludeBlackList=T'
                                % item['titleId']
                            )

            contentType, infoLabels = self.getInfos(item, export)

            if self._skip_item_for_export(export, catalog, infoLabels, parent):
                continue

            name = infoLabels['DisplayTitle']
            asin = item['titleId']
            cm = self._build_context_menu(parent, contentType, asin, wl_asin)

            if parent == 'recent':
                cm.append(
                    (
                        getString(30184).format(getString(self._g.langID[contentType])),
                        'RunPlugin(%s?mode=updateRecents&asin=%s&rem=1)'
                        % (self._g.pluginid, asin),
                    )
                )

            if contentType in ('movie', 'episode'):
                addVideo(name, asin, infoLabels, cm, export)
            else:
                mode = 'listContent'
                url = url if url != '' else item['childTitles'][0]['feedUrl']

                if self._g.watchlist in parent:
                    url += self._s.OfferGroup

                if contentType == 'season':
                    name = self.formatSeason(infoLabels, parent)
                    if self._g.library not in parent and parent != '':
                        curl = (
                            'SeriesASIN=%s&ContentType=TVSeason&IncludeBlackList=T%s'
                            % (infoLabels['SeriesAsin'], self._s.OfferGroup)
                        )
                        cm.insert(
                            0,
                            (
                                getString(30182),
                                'Container.Update(%s?mode=listContent&cat=Browse&url=%s&page=1)'
                                % (self._g.pluginid, quote_plus(curl)),
                            ),
                        )

                if export:
                    url = re.sub(r'(?i)contenttype=\w+', 'ContentType=TVEpisode', url)
                    url = re.sub(r'(?i)&rollupto\w+=\w+', '', url)
                    self.listContent('Browse', url, 1, parent.replace('_show', ''), export)
                else:
                    if name not in titlelist:
                        titlelist.append(name)
                        addDir(name, mode, url, infoLabels, cm=cm, export=export)

        if self._should_continue_paging(titles, page, ResPage):
            if export:
                self.listContent(catalog, oldurl, page + 1, parent, export)
            else:
                addDir(
                    ' --= %s =--' % (getString(30111) % int(page + 1)),
                    'listContent',
                    oldurl,
                    page=page + 1,
                    catalog=catalog,
                    opt=parent,
                    thumb=self._g.NextIcon,
                )

        # centralized actions
        self._post_list_actions(page, parent, contentType, export)

    # =====================================================================
    # 7. TITLE HELPERS / WATCHLIST
    # =====================================================================
    @staticmethod
    def cleanTitle(title):
        if title.isupper():
            title = (
                title.title()
                .replace('[Ov]', '[OV]')
                .replace('Bc', 'BC')
            )
        title = (
            title.replace('\u2013', '-')
            .replace('\u00A0', ' ')
            .replace('[dt./OV]', '')
            .replace('_DUPLICATE_', '')
        )
        return title.strip()

    def WatchList(self, asin, remove):
        cookie = MechanizeLogin()
        if not cookie:
            return

        if asin.startswith('{'):
            endp = json.loads(asin)
            asin = endp['query']['titleID']
            remove = endp['query']['tag'].lower() == 'remove'
        else:
            params = '[{"titleID":"%s","watchlist":true}]' % asin
            data = getURL(
                '%s/gp/video/api/enrichItemMetadata?itemsToEnrich=%s'
                % (self._g.BaseUrl, quote_plus(params)),
                useCookie=cookie,
            )
            endp = findKey('endpoint', data)

        if endp:
            action = 'Remove' if remove else 'Add'
            url = self._g.BaseUrl + endp.get('partialURL')
            query = endp.get('query')
            query['tag'] = action
            data = getURL(url, postdata=query, useCookie=cookie, check=True)
            if data:
                Log(action + ' ' + asin)
                if remove:
                    cPath = (
                        xbmc.getInfoLabel('Container.FolderPath')
                        .replace(asin, '')
                        .replace(
                            'opt=' + self._g.watchlist,
                            'opt=rem_%s' % self._g.watchlist,
                        )
                    )
                    xbmc.executebuiltin('Container.Update("%s", replace)' % cPath)
                elif self._s.wl_export:
                    self.listContent(
                        'GetASINDetails',
                        'asinList%3D' + asin,
                        1,
                        '_show' if self._s.disptvshow else '',
                        1,
                    )
                    xbmc.executebuiltin('UpdateLibrary(video)')
            else:
                Log('Error while {}ing {}'.format(action.lower(), asin), Log.ERROR)

    def getArtWork(self, infoLabels, contentType):
        if contentType == 'movie' and self._s.tmdb_art == '0':
            return infoLabels
        if contentType != 'movie' and self._s.tvdb_art == '0':
            return infoLabels

        c = self._db.cursor()
        asins = infoLabels['Asins']
        infoLabels['banner'] = None
        season = -1 if contentType == 'series' else -2

        if contentType in ('season', 'episode'):
            asins = infoLabels.get('SeriesAsin', asins)
        if 'Season' in infoLabels.keys():
            season = int(infoLabels['season'])

        extra = ' and season = %s' % season if season > -2 else ''

        for asin in asins.split(','):
            result = c.execute(
                'select poster,fanart,banner from art where asin like (?)' + extra,
                ('%' + asin + '%',),
            ).fetchone()
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
                    result = c.execute(
                        'select poster, fanart from art where asin like (?) and season = -1',
                        ('%' + asin + '%',),
                    ).fetchone()
                    if result:
                        if result[0] and result[0] != self._g.na and contentType == 'episode':
                            infoLabels['poster'] = result[0]
                        if result[1] and result[1] != self._g.na and self._s.useshowfanart:
                            infoLabels['fanart'] = result[1]
                c.close()
                return infoLabels
            elif season > -1 and self._s.useshowfanart:
                result = c.execute(
                    'select poster,fanart from art where asin like (?) and season = -1',
                    ('%' + asin + '%',),
                ).fetchone()
                if result:
                    if result[0] and result[0] != self._g.na and contentType == 'episode':
                        infoLabels['poster'] = result[0]
                    if result[1] and result[1] != self._g.na:
                        infoLabels['fanart'] = result[1]
                    c.close()
                    return infoLabels

        if contentType != 'episode':
            title = infoLabels['title']
            if contentType == 'season':
                title = infoLabels['tvshowtitle']
            c.execute(
                'insert or ignore into miss values (?,?,?,?)',
                (asins, title, infoLabels['year'], contentType),
            )
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
        from .art import Artwork
        aw = Artwork()
        seasons = None

        season_number = None
        poster = None
        fanart = None
        title = (
            title.lower()
            .replace('?', '')
            .replace('omu', '')
            .split('(')[0]
            .split('[')[0]
            .strip()
        )

        if not title:
            return

        if contentType == 'movie':
            fanart = aw.getTMDBImages(title, year=year)
        if contentType in ('season', 'series'):
            seasons, poster, fanart = aw.getTVDBImages(title)
            if not fanart:
                fanart = aw.getTMDBImages(title, content='tv')
            season_number = -1
            content = getATVData('GetASINDetails', 'ASINList=' + asins)['titles']
            if content:
                asins = self.getAsins(content[0], False)
                del content

        cur = self._db.cursor()
        if fanart:
            cur.execute(
                'insert or ignore into art values (?,?,?,?,?,?)',
                (asins, season_number, poster, None, fanart, date.today()),
            )
        if seasons:
            for season, url in seasons.items():
                cur.execute(
                    'insert or ignore into art values (?,?,?,?,?,?)',
                    (asins, season, url, None, None, date.today()),
                )
        self._db.commit()
        cur.close()

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
        json_data = getURL(url, useCookie=cj)
        if not json_data:
            return False, False
        WriteLog(str(json_data), 'watchlist')
        cont = findKey('content', json_data)
        info = {
            'approximateSize': cont.get('totalItems', 0),
            'endIndex': cont.get('nextPageStartIndex', 0),
        }

        for item in cont.get('items', []):
            asins.append(item['titleID'])
        return info, ','.join(asins)

    def getList(self, listing, export, cont, page=1):
        info = {}
        if listing in [self._g.watchlist, self._g.library]:
            cj = MechanizeLogin()
            if not cj:
                return [], ''
            args = {
                listing: {
                    'sort': self._s.wl_order,
                    'libraryType': 'Items',
                    'primeOnly': False,
                    'startIndex': (page - 1) * 60,
                    'contentType': cont,
                },
                'shared': {'isPurchaseRow': 0},
            }

            url = '/gp/video/api/myStuff{}?viewType={}&args={}'.format(
                listing.capitalize(), listing, json.dumps(args, separators=(',', ':'))
            )
            info, asins = self._scrapeAsins(url, cj)
            if info is False:
                Log('Cookie invalid', Log.ERROR)
                self._g.dialog.notification(
                    self._g.__plugin__, getString(30266), xbmcgui.NOTIFICATION_ERROR
                )
                return [], ''
        else:
            asins = listing

        url = 'asinlist=%s&StartIndex=0&Detailed=T' % asins
        listing += (
            '_show'
            if (self._s.disptvshow and not (export and asins == listing)) or cont == '_show'
            else ''
        )
        titles = getATVData('Browse', url)
        titles.update(info)
        return titles, listing

    @staticmethod
    def getAsins(content, crIL=True):
        if crIL:
            infoLabels = {
                'plot': None,
                'mpaa': None,
                'cast': [],
                'year': None,
                'premiered': None,
                'rating': None,
                'votes': None,
                'isAdult': 0,
                'director': None,
                'genre': None,
                'studio': None,
                'thumb': None,
                'fanart': None,
                'isHD': False,
                'isPrime': False,
                'audiochannels': 1,
                'TrailerAvailable': False,
            }
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
                    infoLabels['audiochannels'] = 2
                if 'AC_3_5_1' in offerformat['audioFormatTypes']:
                    infoLabels['audiochannels'] = 6

        del content

        if crIL:
            infoLabels['Asins'] = asins
            return infoLabels
        return asins

    def getInfos(self, item, export):
        # ---------- helpers (scoped to keep drop-in) ----------
        def _init_base_labels(obj):
            labels = self.getAsins(obj)
            base_title = self.cleanTitle(obj['title'])
            labels['DisplayTitle'] = labels['title'] = base_title
            labels['contentType'] = obj['contentType'].lower()
            labels['mediatype'] = 'movie'
            labels['plot'] = obj.get('synopsis')
            labels['director'] = obj.get('director')
            labels['studio'] = obj.get('studioOrNetwork')
            labels['cast'] = obj.get('starringCast', '').split(',')
            labels['duration'] = (
                str(obj['runtime']['valueMillis'] / 1000) if 'runtime' in obj else None
            )
            labels['TrailerAvailable'] = obj.get('trailerAvailable', False)
            labels['fanart'] = obj.get('heroUrl')
            labels['isAdult'] = 1 if 'ageVerificationRequired' in str(obj.get('restrictions')) else 0
            labels['genre'] = (
                ' / '.join(obj.get('genres', ''))
                .replace('_', ' & ')
                .replace('Musikfilm & Tanz', 'Musikfilm, Tanz')
                .replace('ã–', 'ö')
            )
            labels['audioflags'] = []   # for HI/AD/etc
            return labels

        def _apply_images(obj, labels):
            if 'formats' in obj and 'images' in obj['formats'][0].keys():
                try:
                    labels['thumb'] = self.cleanIMGurl(obj['formats'][0]['images'][0]['uri'])
                except Exception:
                    pass

        def _apply_dates(obj, labels):
            if 'releaseOrFirstAiringDate' in obj:
                labels['premiered'] = obj['releaseOrFirstAiringDate']['valueFormatted'].split('T')[0]
                labels['year'] = int(labels['premiered'].split('-')[0])

        def _apply_mpaa(obj, labels):
            rr = obj.get('regulatoryRating')
            if rr is None:
                return
            if rr == 'not_checked' or not rr:
                labels['mpaa'] = getString(30171)
            else:
                labels['mpaa'] = AgeRestrictions().GetAgeRating() + rr

        def _apply_user_ratings(obj, labels):
            crc = obj.get('customerReviewCollection')
            if crc:
                summ = crc['customerReviewSummary']
                labels['rating'] = float(summ['averageOverallRating']) * 2
                labels['votes'] = str(summ['totalReviewCount'])
                return
            ar = obj.get('amazonRating')
            if ar:
                labels['rating'] = float(ar['rating']) * 2 if 'rating' in ar else None
                labels['votes'] = str(ar['count']) if 'count' in ar else None

        # --- audio/subtitle parsing ---

        def _nice_lang(code_or_name):
            # try to keep code short and readable
            if not code_or_name:
                return ''
            # amazon sometimes sends "en_US", "de_DE"
            return code_or_name.replace('_', '-')

        def _parse_audio_tracks(obj):
            """
            Return list of strings like:
              ["en – Audio Description", "de – 5.1", "fr – Stereo"]
            from the various possible audio containers.
            """
            tracks = []
            containers = [
                obj.get('audioTracks'),
                obj.get('playbackAudioTracks'),
                obj.get('audioLanguages'),
            ]
            for container in containers:
                if not container:
                    continue
                for t in container:
                    lang = _nice_lang(t.get('languageCode') or t.get('language') or t.get('locale'))
                    # technical bits
                    ch = t.get('channels') or t.get('channelLayout')
                    # features/purpose
                    feat = t.get('features') or t.get('flags') or []
                    if isinstance(feat, str):
                        feat = [feat]
                    labels = []
                    # try to map common flags
                    for f in feat:
                        lf = f.lower()
                        if 'audio_description' in lf or 'described' in lf:
                            labels.append('Audio Description')
                        elif 'hearing' in lf:
                            labels.append('HI')
                        else:
                            labels.append(f)
                    # build display
                    parts = []
                    if lang:
                        parts.append(lang)
                    if ch:
                        parts.append(str(ch))
                    if labels:
                        parts.append(', '.join(labels))
                    if parts:
                        tracks.append(' – '.join([parts[0], ' '.join(parts[1:]).strip()]) if len(parts) > 1 else parts[0])
            # dedupe while preserving order
            seen = set()
            uniq = []
            for x in tracks:
                if x not in seen:
                    uniq.append(x)
                    seen.add(x)
            return uniq

        def _parse_subtitle_tracks(obj):
            """
            Return list of strings like:
              ["en – SDH", "de – Forced", "es – CC"]
            """
            tracks = []
            containers = [
                obj.get('subtitles'),
                obj.get('subtitleTracks'),
                obj.get('captionTracks'),
            ]
            for container in containers:
                if not container:
                    continue
                for t in container:
                    lang = _nice_lang(t.get('languageCode') or t.get('language') or t.get('locale'))
                    kind = t.get('type') or t.get('category') or ''
                    flags = t.get('flags') or t.get('features') or []
                    if isinstance(flags, str):
                        flags = [flags]
                    labels = []
                    if kind:
                        labels.append(kind)
                    for f in flags:
                        lf = f.lower()
                        if 'sdh' in lf:
                            labels.append('SDH')
                        elif 'forced' in lf:
                            labels.append('Forced')
                        elif 'cc' in lf or 'closed' in lf:
                            labels.append('CC')
                        else:
                            labels.append(f)
                    parts = []
                    if lang:
                        parts.append(lang)
                    if labels:
                        parts.append(', '.join(labels))
                    if parts:
                        tracks.append(' – '.join(parts))
            seen = set()
            uniq = []
            for x in tracks:
                if x not in seen:
                    uniq.append(x)
                    seen.add(x)
            return uniq

        def _detect_hi(obj):
            containers = [
                obj.get('audioTracks'),
                obj.get('playbackAudioTracks'),
                obj.get('audioLanguages'),
            ]
            for container in containers:
                if not container:
                    continue
                for track in container:
                    if track.get('hearingImpaired') is True:
                        return True
                    flags = track.get('flags') or track.get('features')
                    if flags:
                        if isinstance(flags, str):
                            flags = [flags]
                        for f in flags:
                            lf = f.lower()
                            if 'hearing_impaired' in lf or 'hearing-impaired' in lf or lf == 'hi':
                                return True
            return False

        def _apply_hi_flag(labels, found):
            if found:
                labels['audioflags'].append('HI')
                labels['DisplayTitle'] += ' [HI]'

        def _apply_series_like(obj, labels, ctype):
            if ctype == 'series':
                labels['mediatype'] = 'tvshow'
                labels['tvshowtitle'] = obj['title']
                labels['totalseasons'] = (
                    obj['childTitles'][0]['size'] if obj.get('childTitles') else None
                )
                return

            if ctype == 'season':
                labels['mediatype'] = 'season'
                labels['season'] = obj['number']
                if obj['ancestorTitles']:
                    for content in obj['ancestorTitles']:
                        if content['contentType'] == 'SERIES':
                            labels['SeriesAsin'] = content.get('titleId')
                            labels['tvshowtitle'] = content.get('title')
                else:
                    labels['SeriesAsin'] = labels['Asins'].split(',')[0]
                    labels['tvshowtitle'] = obj['title']
                if obj.get('childTitles'):
                    labels['totalseasons'] = 1
                    labels['episode'] = obj.get('childTitles')[0]['size']
                return

            if ctype == 'episode':
                labels['mediatype'] = 'episode'
                if obj['ancestorTitles']:
                    seasontitle = None
                    for content in obj['ancestorTitles']:
                        if content['contentType'] == 'SERIES':
                            labels['SeriesAsin'] = content.get('titleId')
                            labels['tvshowtitle'] = content.get('title')
                        elif content['contentType'] == 'SEASON':
                            labels['season'] = content.get('number')
                            labels['SeasonAsin'] = content.get('titleId')
                            seasontitle = content.get('title')
                    if 'SeriesAsin' not in labels and 'SeasonAsin' in labels:
                        labels['SeriesAsin'] = labels['SeasonAsin']
                        labels['tvshowtitle'] = seasontitle
                else:
                    labels['SeriesAsin'] = ''

                if 'number' in obj:
                    labels['episode'] = obj['number']
                    if obj['number'] > 0:
                        labels['DisplayTitle'] = '%s - %s' % (obj['number'], labels['title'])
                    else:
                        if ':' in labels['title']:
                            labels['DisplayTitle'] = labels['title'].split(':')[1].strip()

        # ---------- main ----------
        infoLabels = _init_base_labels(item)
        contentType = infoLabels['contentType']

        _apply_images(item, infoLabels)
        _apply_dates(item, infoLabels)
        _apply_mpaa(item, infoLabels)
        _apply_user_ratings(item, infoLabels)

        # detect and mark HI
        hi_found = _detect_hi(item)
        _apply_hi_flag(infoLabels, hi_found)

        # series/season/episode specifics
        _apply_series_like(item, infoLabels, contentType)

        # tvshowtitle cleanup
        if 'tvshowtitle' in infoLabels:
            infoLabels['tvshowtitle'] = self.cleanTitle(infoLabels['tvshowtitle'])

        # NEW: extract tracks
        audio_tracks = _parse_audio_tracks(item)
        subtitle_tracks = _parse_subtitle_tracks(item)

        # tuck them into infoLabels so other code can consume
        if audio_tracks:
            infoLabels['audio_tracks'] = audio_tracks
        if subtitle_tracks:
            infoLabels['subtitle_tracks'] = subtitle_tracks

        # and make sure user sees it even if skin ignores custom keys
        if (audio_tracks or subtitle_tracks) and infoLabels.get('plot'):
            extra_lines = []
            if audio_tracks:
                extra_lines.append('Audio:\n  ' + '\n  '.join(audio_tracks))
            if subtitle_tracks:
                extra_lines.append('Subtitles:\n  ' + '\n  '.join(subtitle_tracks))
            infoLabels['plot'] = infoLabels['plot'] + '\n\n' + '\n'.join(extra_lines)
        elif (audio_tracks or subtitle_tracks) and not infoLabels.get('plot'):
            txt = []
            if audio_tracks:
                txt.append('Audio:\n  ' + '\n  '.join(audio_tracks))
            if subtitle_tracks:
                txt.append('Subtitles:\n  ' + '\n  '.join(subtitle_tracks))
            infoLabels['plot'] = '\n'.join(txt)

        # artwork backfill
        infoLabels = self.getArtWork(infoLabels, contentType)

        # final display tweaks
        if not export:
            if not infoLabels.get('thumb'):
                infoLabels['thumb'] = self._g.DefaultFanart
            if not infoLabels.get('fanart'):
                infoLabels['fanart'] = self._g.DefaultFanart
            if not infoLabels['isPrime'] and contentType != 'series':
                infoLabels['DisplayTitle'] = '[COLOR %s]%s[/COLOR]' % (
                    self._g.PayCol,
                    infoLabels['DisplayTitle'],
                )

        return contentType, infoLabels

    @staticmethod
    def cleanIMGurl(img):
        return re.sub(r'\._.*_\.', r'.', img) if img else None

    # =====================================================================
    # 8. CHANNELS (left mostly as-is, just clearer locals)
    # =====================================================================
    def Channel(self, url, uid):
        def getInfos(item):
            if isinstance(item.get('title'), dict):
                item['link'] = {'url': item['title'].get('url')}
                for p in ['title', 'synopsis', 'year']:
                    item[p] = item.get(p, {}).get('text', '')
            facet = item.get('facet')
            n = facet.get('alternateText', '') if facet else item.get('facetAlternateText', '')
            wl = item.get('watchlistAction', item.get('watchlistButton'))
            title = item.get('text', item.get('title', ''))
            num = item.get('episodeNumber')
            live = item.get('liveInfo')
            contr = item.get('contributors', {})
            rating = item.get('customerReviews', item.get('amazonRating'))
            runtime = item.get('runtime')
            livestate = item.get('liveState')
            il = self.getAsins(item, True)
            il['title'] = '%s - %s' % (n, title) if n else title
            il['plot'] = item.get('synopsis', '').strip()
            il['contentType'] = item.get('titleType', '')
            il['duration'] = item.get('duration')
            il['mpaa'] = item.get('ratingBadge', {}).get('simplifiedId')
            il['isPrime'] = item.get('isPrime', True)
            il['genre'] = ' / '.join(i.get('text', '') for i in item.get('genres', []))
            il['studio'] = ', '.join(item.get('studios', []))
            il['director'] = ', '.join(i['name'] for i in contr.get('directors', []))
            il['cast'] = [
                i['name']
                for i in (contr.get('starringActors', []) + contr.get('supportingActors', []))
            ]
            il['year'] = item.get('releaseYear')
            if num:
                il['episode'] = item.get('episodeNumber')
                il['title'] = '%s - %s' % (num, il['title'])
            if wl:
                il['contentType'] = wl['endpoint']['query'].get('titleType', '')
            if 'images' in item:
                img = item['images']
                il['thumb'] = self.cleanIMGurl(img.get('packshot', img.get('titleshot')))
                il['fanart'] = self.cleanIMGurl(img.get('heroshot'))
            else:
                il['thumb'] = self.cleanIMGurl(
                    item.get('image', {}).get(
                        'url', facet.get('image', '') if facet else item.get('facetImage')
                    )
                )
            if rating and rating.get('value'):
                il['rating'] = float(rating['value']) * 2
                il['votes'] = str(rating['count'])
            if live:
                il['plot'] += '\n\n' if il['plot'] else ''
                il['contentType'] = 'live'
                il['plot'] += ' - '.join(
                    [live.get('timeBadge', live.get('label', '')), live.get('venue', '')]
                )
            if livestate:
                il['plot'] += '\n\n' if il['plot'] else ''
                il['contentType'] = livestate.get('id', il['contentType'])
                if livestate.get('isLive', False):
                    il['contentType'] = 'live'
                il['plot'] += ' - '.join(
                    [livestate.get('text', ''), item.get('pageDateTimeBadge', '')]
                )
            if not il['title']:
                il['title'] = item.get('image', {}).get('alternateText', '')
                il['contentType'] = 'thumbnail'
            if item.get('itemType', '').lower() == 'label':
                il['plot'] = il['title']
                il['title'] = '-= %s =-' % item['link']['label']
                il['thumb'] = self._g.NextIcon
            if not il['duration'] and runtime:
                t = re.findall(r'\d+', runtime)
                t = ['0'] * (2 - len(t)) + t
                il['duration'] = sum(map(lambda a, b: int(a) * b, t, (3600, 60)))
            if 'playbackActions' in item:
                il['contentType'] = findKey('videoMaterialType', item['playbackActions'])
            elif 'notificationActions' in item:
                il['contentType'] = 'nostream'
                il['title'] = '%s (%s)' % (
                    il['title'],
                    item['notificationActions'][0]['message']['string'],
                )
            il['DisplayTitle'] = self.cleanTitle(il['title'])
            il['contentType'] = il['contentType'].lower()
            return il, il['contentType']

        def getcache(uid_):
            j = {}
            c = self._menuDb.cursor()
            for data in c.execute('select data from channels where uid = (?)', (uid_,)).fetchall():
                j = json.loads(data[0])
            c.close()
            return j

        def remref(url_):
            f = re.findall('ref=[^?^&]*', url_)
            return url_.replace(f[0], '') if f else url_

        def crctxmenu(item_):
            cm_ = []
            wl_ = item_.get('watchlistAction', item_.get('watchlistButton'))
            if wl_:
                cm_.append(
                    (
                        wl_['text']['string'],
                        'RunPlugin(%s?mode=WatchList&url=%s)'
                        % (self._g.pluginid, quote_plus(json.dumps(wl_['endpoint']))),
                    )
                )
            return cm_

        data = getcache(uid) if not url else GrabJSON(url)
        s = time.time()
        props = data.get('search', data.get('results', data))
        vw = ''
        urls = []

        if 'collections' in props:
            if uid == 'root':
                self._createDB(self._chan_tbl)
                if 'epgIngress' in props:
                    title = props['epgIngress'].get('label', 'Channel Guide')
                    url = props['epgIngress'].get('url')
                    addDir(title, 'Channel', url)

            for col in props.get('collections', []):
                if col.get('collectionType', '') in ['TwinHero', 'Carousel']:
                    il, ct = getInfos(col)
                    vw = ct if ct else vw
                    uid = col['webUid']
                    cm = crctxmenu(col)
                    addDir(il['DisplayTitle'], 'Channel', '', infoLabels=il, opt=uid, cm=cm)
                    self.wMenuDB([uid, json.dumps(col), time.time(), ''], self._chan_tbl)
            self._menuDb.commit()

        elif 'items' in props:
            items = props.get('items', [])
            for item in items:
                il, ct = getInfos(item)
                chid = item.get('playbackAction', item).get('channelId')
                playable = item.get('properties', {}).get('isIdPlayable', False)
                if chid:
                    ct = 'live'
                    il['contentType'] = item.get('playbackAction', item).get(
                        'videoMaterialType', ct
                    ).lower()
                cm = crctxmenu(item)
                if playable or chid:
                    addVideo(il['DisplayTitle'], chid if chid else item['titleID'], il, cm=cm)
                else:
                    next_url = item['link']['url']
                    if ct == 'season':
                        next_url += '?episodeListSize=999'
                    if il['title']:
                        addDir(il['DisplayTitle'], 'Channel', next_url, infoLabels=il, opt=ct, cm=cm)
                    urls.append(remref(next_url))
                vw = ct if ct else vw

        elif 'state' in props:
            pgid = props['state'].get('pageTitleId', '')
            act = props['state'].get('action', {})
            action = act.get('btf', act.get('atf', {}))
            detail = props['state'].get('detail', {})
            col = props['state'].get('collections', [])
            titleids = []
            if col and len(col.get(pgid, [])) > 0:
                [
                    titleids.extend(i.get('titleIds', []))
                    for i in col[pgid]
                    if i.get('collectionType', '') in ['episodes', 'bonus', 'schedule']
                ]
            if not titleids:
                titleids.append(pgid)
            for asin in titleids:
                item = detail.get('headerDetail', {}).get(pgid, {})
                item.update(detail.get('detail', {}).get(asin, {}))
                item.update(action.get(asin, {}))
                if item:
                    il, ct = getInfos(item)
                    vw = ct if ct else vw
                    cm = crctxmenu(item)
                    playback_id = findKey('playbackID', item.get('playbackActions', {}))
                    asin = playback_id if playback_id else asin
                    if 'nostream' in ct:
                        addDir(il['DisplayTitle'], 'text', infoLabels=il)
                    else:
                        addVideo(il['DisplayTitle'], asin, il, cm=cm)

        elif 'sections' in props:
            from datetime import datetime
            channels = props['sections'][0].get('channels', [])
            for item in channels:
                il = self.getAsins(item, True)
                pa = item.get('playbackAction')
                shed = item.get('schedule')
                asin = ''
                il['title'] = item.get('channelName')
                il['thumb'] = self.cleanIMGurl(item.get('logo', ''))
                il['DisplayTitle'] = self.cleanTitle(il['title'])
                il['Plot'] = ''
                upnext = False
                if shed:
                    ts = time.time()
                    for sh in shed:
                        us = sh.get('unixStart') / 1000
                        ue = sh.get('unixEnd') / 1000
                        if (us <= ts <= ue) or upnext:
                            il['Plot'] += '{:%H:%M}-{:%H:%M}  {}\n'.format(
                                datetime.fromtimestamp(us),
                                datetime.fromtimestamp(ue),
                                sh.get('title', ''),
                            )
                            if upnext:
                                break
                            upnext = True
                if pa:
                    il['contentType'] = vw = pa.get('videoMaterialType').lower()
                    asin = pa.get('channelId')
                if asin:
                    addVideo(il['DisplayTitle'], asin, il)
                else:
                    addDir(il['DisplayTitle'], 'text', infoLabels=il)

        more = props.get('pagination', props.get('seeMoreLink'))
        if more:
            nextpage = more.get('apiUrl', more['url'])
            if remref(nextpage) not in urls:
                addDir('-= %s =-' % more['label'], 'Channel', nextpage, thumb=self._g.NextIcon)

        Log('Parsing Channels Page: %ss' % (time.time() - s), Log.DEBUG)
        setContentAndView(vw)
        return

    # =====================================================================
    # 9. PROFILES
    # =====================================================================
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
                getURL(
                    profiles[ret][1],
                    postdata=profiles[ret][2],
                    useCookie=True,
                    rjson=False,
                    check=True,
                )
        exit()

    # =====================================================================
    # 10. ROUTER (battle-tested command table)
    # =====================================================================
    def Route(self, mode, args):
        """
        Classic dispatch table instead of long if/elif chain.
        Easy to extend, easy to read, and typical for Kodi plugins.
        """
        commands = {
            'listCategories': lambda: self.listCategories(args.get('url', ''), args.get('opt', '')),
            'listContent': lambda: self.listContent(
                args.get('cat'),
                py2_decode(args.get('url', '')),
                int(args.get('page', '1')),
                args.get('opt', ''),
                int(args.get('export', '0')),
            ),
            'getList': lambda: self.getList(args.get('url', ''), int(args.get('export', '0')), args.get('opt')),
            'getListMenu': lambda: self.getListMenu(args.get('url', ''), int(args.get('export', '0'))),
            'WatchList': lambda: self.WatchList(args.get('url', ''), int(args.get('opt', '0'))),
            'Search': lambda: self.Search(args.get('searchstring')),
            'Channel': lambda: self.Channel(url=args.get('url'), uid=args.get('opt')),
            'updateRecents': lambda: self.updateRecents(args.get('asin', ''), int(args.get('rem', '0'))),
            'languageselect': lambda: self._g.dialog.notification(self._g.__plugin__, getString(30269)),
            'ageSettings': lambda: AgeRestrictions().Settings(),
            # passthrough calls
            'checkMissing': lambda: self._g.pv.checkMissing(),
            'Recent': lambda: self._g.pv.Recent(),
            'switchProfile': lambda: self._g.pv.switchProfile(),
        }

        cmd = commands.get(mode)
        if cmd:
            cmd()
        else:
            # fallback to no-op to stay safe
            Log('Unknown mode: %s' % mode, Log.DEBUG)
