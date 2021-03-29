#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import os.path
from datetime import date

try:
    from urllib.parse import quote_plus
except ImportError:
    from urllib import quote_plus

from .ages import AgeRestrictions
from .singleton import Singleton
from .network import *
from .itemlisting import *
from .users import *


class AmazonTLD(Singleton):
    """ Wrangler of all things Amazon.(com|co.uk|de|jp) """

    def __init__(self, globalsInstance, settingsInstance):
        self._g = globalsInstance
        self._s = settingsInstance
        self.recentsdb = OSPJoin(g.DATA_PATH, 'recent.db')
        self._initialiseDB()
        self.loadCategories()

    def BrowseRoot(self):
        cm_wl = [(getString(30185) % 'Watchlist', 'RunPlugin(%s?mode=getListMenu&url=%s&export=1)' % (self._g.pluginid, self._g.watchlist))]
        cm_lb = [(getString(30185) % getString(30100),
                 'RunPlugin(%s?mode=getListMenu&url=%s&export=1)' % (self._g.pluginid, self._g.library))]

        if self._s.multiuser:
            addDir(getString(30134).format(loadUser('name')), 'switchUser', '', cm=self._g.CONTEXTMENU_MULTIUSER)
        if self._s.profiles:
            act, profiles = self.getProfiles()
            if act is not False:
                addDir(profiles[act][0], 'switchProfile', '', thumb=profiles[act][2])
        addDir('Watchlist', 'getListMenu', self._g.watchlist, cm=cm_wl)
        self.listCategories(0)
        addDir('Channels', 'Channel', '/gp/video/storefront/ref=nav_shopall_nav_sa_aos?filterId=OFFER_FILTER%3DSUBSCRIPTIONS', opt='root')
        addDir(getString(30136), 'Recent', '')
        addDir(getString(30108), 'Search', '')
        addDir(getString(30100), 'getListMenu', self._g.library, cm=cm_lb)
        xbmcplugin.endOfDirectory(self._g.pluginhandle, updateListing=False, cacheToDisc=False)

    @staticmethod
    def _cleanName(name, isfile=True):
        notallowed = ['<', '>', ':', '"', '\\', '/', '|', '*', '?', '´']
        if not isfile:
            notallowed = ['<', '>', '"', '|', '*', '?', '´']
        for c in notallowed:
            name = name.replace(c, '')
        if not os.path.supports_unicode_filenames and not isfile:
            name = name.encode('utf-8')
        return name

    def SaveFile(self, filename, data, isdir=None, mode='w'):
        from contextlib import closing
        if isdir:
            filename = self._cleanName(filename)
            filename = os.path.join(isdir, filename)
            if not xbmcvfs.exists(isdir):
                xbmcvfs.mkdirs(self._cleanName(isdir.strip(), isfile=False))
        filename = self._cleanName(filename, isfile=False)
        with closing(xbmcvfs.File(filename, mode)) as outfile:
            outfile.write(bytearray(py2_decode(data).encode('utf-8')))

    def CreateDirectory(self, dir_path):
        dir_path = self._cleanName(dir_path.strip(), isfile=False)
        if not xbmcvfs.exists(dir_path):
            return xbmcvfs.mkdirs(dir_path)
        return False

    def SetupLibrary(self):
        self.CreateDirectory(self._s.MOVIE_PATH)
        self.CreateDirectory(self._g.HOME_PATH)
        self.SetupAmazonLibrary()

    def CreateInfoFile(self, nfofile, path, content, Info, language, hasSubtitles=False):
        skip_keys = ('ishd', 'isadult', 'audiochannels', 'genre', 'cast', 'duration', 'asins', 'contentType', 'seriesasin', 'contenttype', 'mediatype',
                     'poster', 'isprime', 'seasonasin')
        fileinfo = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'
        fileinfo += '<%s>\n' % content
        if 'Duration' in Info.keys():
            fileinfo += '<runtime>%s</runtime>\n' % Info['Duration']
        if 'Genre' in Info.keys():
            for genre in Info['Genre'].split('/'):
                fileinfo += '<genre>%s</genre>\n' % genre.strip()
        if 'Cast' in Info.keys():
            for actor in Info['Cast']:
                fileinfo += '<actor>\n'
                fileinfo += '    <name>%s</name>\n' % actor.strip()
                fileinfo += '</actor>\n'
        for key, value in Info.items():
            lkey = key.lower()
            if value:
                if lkey == 'tvshowtitle':
                    fileinfo += '<showtitle>%s</showtitle>\n' % value
                elif lkey == 'premiered' and 'TVShowTitle' in Info:
                    fileinfo += '<aired>%s</aired>\n' % value
                elif lkey == 'thumb':
                    aspect = '' if 'episode' in content else ' aspect="poster"'
                    fileinfo += '<%s%s>%s</%s>\n' % (lkey, aspect, value, lkey)
                elif lkey == 'fanart' and not 'episode' in content:
                    fileinfo += '<%s>\n    <thumb>%s</thumb>\n</%s>\n' % (lkey, value, lkey)
                elif lkey not in skip_keys:
                    fileinfo += '<%s>%s</%s>\n' % (lkey, value, lkey)

        if content != 'tvshow':
            fileinfo += '<fileinfo>\n'
            fileinfo += '   <streamdetails>\n'
            fileinfo += '       <audio>\n'
            fileinfo += '           <channels>%s</channels>\n' % Info['AudioChannels']
            fileinfo += '           <codec>aac</codec>\n'
            fileinfo += '       </audio>\n'
            fileinfo += '       <video>\n'
            fileinfo += '           <codec>h264</codec>\n'
            fileinfo += '           <durationinseconds>%s</durationinseconds>\n' % Info['Duration']
            if Info['isHD']:
                fileinfo += '           <height>1080</height>\n'
                fileinfo += '           <width>1920</width>\n'
            else:
                fileinfo += '           <height>480</height>\n'
                fileinfo += '           <width>720</width>\n'
            if language:
                fileinfo += '           <language>%s</language>\n' % language
            fileinfo += '           <scantype>Progressive</scantype>\n'
            fileinfo += '       </video>\n'
            if hasSubtitles:
                fileinfo += '       <subtitle>\n'
                fileinfo += '           <language>ger</language>\n'
                fileinfo += '       </subtitle>\n'
            fileinfo += '   </streamdetails>\n'
            fileinfo += '</fileinfo>\n'
        fileinfo += '</%s>\n' % content

        self.SaveFile(nfofile + '.nfo', fileinfo, path)
        return

    def SetupAmazonLibrary(self):
        import xml.etree.ElementTree as et
        from contextlib import closing
        source_path = py2_decode(xbmc.translatePath('special://profile/sources.xml'))
        source_added = False
        source_dict = {self._s.ms_mov: self._s.MOVIE_PATH, self._s.ms_tv: self._s.TV_SHOWS_PATH}

        if xbmcvfs.exists(source_path) and xbmcvfs.Stat(source_path).st_size() > 0:
            with closing(xbmcvfs.File(source_path)) as fo:
                byte_string = bytes(fo.readBytes())
            root = et.fromstring(byte_string)
        else:
            subtags = ['programs', 'video', 'music', 'pictures', 'files']
            root = et.Element('sources')
            for cat in subtags:
                cat_tag = et.SubElement(root, cat)
                et.SubElement(cat_tag, 'default', attrib={'pathversion': '1'})

        for src_name, src_path in source_dict.items():
            video_tag = root.find('video')
            if not any(src_name == i.text for i in video_tag.iter()):
                source_tag = et.SubElement(video_tag, 'source')
                name_tag = et.SubElement(source_tag, 'name')
                path_tag = et.SubElement(source_tag, 'path', attrib={'pathversion': '1'})
                name_tag.text = src_name
                path_tag.text = src_path
                Log(src_name + ' source path added')
                source_added = True
            else:
                for tag in video_tag.iter('source'):
                    if tag.findtext('name') == src_name and tag.findtext('path') != src_path:
                        tag.find('path').text = src_path
                        Log(src_name + ' source path changed')
                        source_added = True

        if source_added:
            with closing(xbmcvfs.File(source_path, 'w')) as fo:
                fo.write(bytearray(et.tostring(root, 'utf-8')))
            self._g.dialog.ok(getString(30187), getString(30188))
            if self._g.dialog.yesno(getString(30191), getString(30192)):
                xbmc.executebuiltin('RestartApp')

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
        all_rec, rec = self.getRecents()
        if rem == 0:
            content = getATVData('GetASINDetails', 'ASINList=' + asin)['titles']
            if len(content) < 1:
                return
            ct, Info = g.amz.getInfos(content[0], False)
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

    def loadCategories(self, force=False):
        if xbmcvfs.exists(self._menuFile) and not force:
            ftime = self.updateTime(False)
            ctime = time.time()
            if ctime - ftime < 8 * 3600:
                return

        Log('Parse Menufile', Log.DEBUG)
        parseStart = time.time()
        data = getURL('https://raw.githubusercontent.com/Sandmann79/xbmc/master/plugin.video.amazon-test/resources/menu/%s.json' % self._g.MarketID)
        if not data:
            jsonfile = os.path.join(self._g.PLUGIN_PATH, 'resources', 'menu', self._g.MarketID + '.json')
            jsonfile = jsonfile.replace(self._g.MarketID, 'ATVPDKIKX0DER') if not xbmcvfs.exists(jsonfile) else jsonfile
            data = json.load(open(jsonfile))
        self._createDB(self._menu_tbl)
        self.parseNodes(data)
        self.updateTime()
        self._menuDb.commit()
        Log('Parse MenuTime: %s' % (time.time() - parseStart), Log.DEBUG)

    def updateTime(self, savetime=True):
        c = self._menuDb.cursor()
        if savetime:
            self.wMenuDB(['last_update', '', '', str(time.time()), str(self._g.DBVersion), ''], self._menu_tbl)
        else:
            try:
                result = c.execute('select content, id from menu where node = ("last_update")').fetchone()
            except:
                result = 0
            c.close()
            if result:
                if self._g.DBVersion > float(result[1]):
                    return 0
                return float(result[0])
            return 0
        c.close()

    def parseNodes(self, data, node_id=''):
        if type(data) != list:
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
                self.wMenuDB([node_id, entry.get('title', ''), category, content, entry.get('id', ''), json.dumps(entry.get('infolabel', ''))], self._menu_tbl)

    def wMenuDB(self, menudata, table):
        asterix = '?,' * len(menudata)
        c = self._menuDb.cursor()
        c.execute('insert or ignore into %s values (%s)' % (table, asterix[:-1]), menudata)
        c.close()

    def getNode(self, node, dist='distinct *', opt=''):
        c = self._menuDb.cursor()
        result = c.execute('select {} from menu where node = (?){}'.format(dist, opt), (node,)).fetchall()
        c.close()
        return result

    def listCategories(self, node, root=None):
        self.loadCategories()
        cat = self.getNode(node)
        all_vid = {'movies': [30143, 'Movie', 'root'], 'tv_shows': [30160, 'TVSeason', 'root_show']}

        if root in all_vid.keys():
            url = 'OrderBy=Title%s&contentType=%s' % (self._s.OfferGroup, all_vid[root][1])
            addDir(getString(all_vid[root][0]), 'listContent', url, opt=all_vid[root][2])

        for n, title, category, content, menu_id, infolabel in cat:
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
                    st = 'all' if self._s.payCont else 'prime'
                    url = self.getNode(content, 'content', ' and id = "{}"'.format(st))
                    url = url[0][0] if url else content
                    opt = menu_id
                if menu_id == 'channels' and node == 0:
                    continue
            elif category == 'query':
                mode = 'listContent'
                opt = 'listcat'
                url = re.sub('\n|\\n', '', content)
            elif category == 'play':
                addVideo(info['Title'], info['Asins'], info)
            elif category == 'link':
                mode = 'Channel'
                opt = 'root'
                url = content
            if mode:
                addDir(title, mode, url, info, opt)
        if node != 0:
            xbmcplugin.endOfDirectory(self._g.pluginhandle)

    def listContent(self, catalog, url, page, parent, export=0):
        oldurl = url
        titlelist = []
        ResPage = self._s.MaxResults
        contentType = ''

        if export:
            ResPage = 240
            self.SetupLibrary()

        if catalog in (self._g.watchlist, self._g.library):
            titles, parent = self.getList(catalog, export, url, page)
            ResPage = 60
        else:
            url = '%s&NumberOfResults=%s&StartIndex=%s&Detailed=T' % (url, ResPage, (page - 1) * ResPage)
            titles = getATVData(catalog, url)
        if page != 1 and not export:
            addDir(' --= %s =--' % getString(30112), thumb=self._s.HomeIcon)

        if not titles or not len(titles.get('titles', [])):
            if 'search' in parent:
                self._g.dialog.ok(self._g.__plugin__, getString(30202))
            else:
                xbmcplugin.endOfDirectory(self._g.pluginhandle)
            return

        endIndex = titles['endIndex']
        numItems = len(titles['titles'])
        if 'approximateSize' not in titles.keys():
            if numItems > self._s.MaxResults:
                endIndex = 0
        else:
            if endIndex == 0:
                if (page * ResPage) <= titles['approximateSize']:
                    endIndex = 1

        for item in titles['titles']:
            url = ''
            if 'title' not in item:
                continue
            wl_asin = item['titleId']
            if item.get('ancestorTitles'):
                if '_show' in parent:
                    item.update(item['ancestorTitles'][0])
                    url = 'SeriesASIN=%s&ContentType=TVSeason&IncludeBlackList=T' % item['titleId']
                elif re.search('(?i)rolluptoseason=t|contenttype=tvseason', oldurl):
                    for i in item['ancestorTitles']:
                        if i['contentType'] == 'SEASON':
                            item.update(i)
                            url = 'SeasonASIN=%s&ContentType=TVEpisode&IncludeBlackList=T' % item['titleId']

            contentType, infoLabels = self.getInfos(item, export)
            if export and catalog == "Browse" and not infoLabels['isPrime'] and not self._s.payCont and self._g.library not in parent:
                continue
            name = infoLabels['DisplayTitle']
            asin = item['titleId']
            wlmode = 1 if self._g.watchlist in parent else 0
            cm = [(getString(wlmode + 30180) % getString(self._g.langID[contentType]),
                   'RunPlugin(%s?mode=WatchList&url=%s&opt=%s)' % (self._g.pluginid, wl_asin, wlmode)),
                  (getString(30185) % getString(self._g.langID[contentType]),
                   'RunPlugin({}?mode=listContent&cat=GetASINDetails&url=asinList%3D{}&export=1)'.format(self._g.pluginid, asin)),
                  (getString(30186), 'UpdateLibrary(video)')]

            if parent == 'recent':
                cm.append((getString(30184).format(getString(self._g.langID[contentType])),
                          'RunPlugin(%s?mode=updateRecents&asin=%s&rem=1)' % (self._g.pluginid, asin)))
            if contentType == 'movie' or contentType == 'episode':
                addVideo(name, asin, infoLabels, cm, export)
            else:
                mode = 'listContent'
                url = url if url != '' else item['childTitles'][0]['feedUrl']

                if self._g.watchlist in parent:
                    url += self._s.OfferGroup
                if contentType == 'season':
                    name = self.formatSeason(infoLabels, parent)
                    if self._g.library not in parent and parent != '':
                        curl = 'SeriesASIN=%s&ContentType=TVSeason&IncludeBlackList=T%s' % (
                            infoLabels['SeriesAsin'], self._s.OfferGroup)
                        cm.insert(0, (getString(30182), 'Container.Update(%s?mode=listContent&cat=Browse&url=%s&page=1)' % (
                            self._g.pluginid, quote_plus(curl))))

                if export:
                    url = re.sub(r'(?i)contenttype=\w+', 'ContentType=TVEpisode', url)
                    url = re.sub(r'(?i)&rollupto\w+=\w+', '', url)
                    self.listContent('Browse', url, 1, parent.replace('_show', ''), export)
                else:
                    if name not in titlelist:
                        titlelist.append(name)
                        addDir(name, mode, url, infoLabels, cm=cm, export=export)

        if endIndex > 0:
            if export:
                self.listContent(catalog, oldurl, page + 1, parent, export)
            else:
                addDir(' --= %s =--' % (getString(30111) % int(page + 1)), 'listContent', oldurl, page=page + 1,
                       catalog=catalog, opt=parent, thumb=self._s.NextIcon)
        if not export:
            self._db.commit()
            xbmc.executebuiltin('RunPlugin(%s?mode=checkMissing)' % self._g.pluginid)
            if 'search' in parent:
                setContentAndView('season')
            else:
                setContentAndView(contentType)

    @staticmethod
    def cleanTitle(title):
        if title.isupper():
            title = title.title().replace('[Ov]', '[OV]').replace('Bc', 'BC')
        title = title.replace('\u2013', '-').replace('\u00A0', ' ').replace('[dt./OV]', '').replace('_DUPLICATE_', '')
        return title.strip()

    def Export(self, infoLabels, url):
        isEpisode = infoLabels['contentType'] != 'movie'
        language = xbmc.convertLanguage(self._s.Language, xbmc.ISO_639_2)
        ExportPath = self._s.MOVIE_PATH
        nfoType = 'movie'
        title = infoLabels['Title']

        if isEpisode:
            ExportPath = self._s.TV_SHOWS_PATH
            title = infoLabels['TVShowTitle']

        tl = title.lower()
        if '[omu]' in tl or '[ov]' in tl or ' omu' in tl:
            language = ''
        filename = re.sub(r'(?i)\[.*| omu| ov', '', title).strip()
        ExportPath = os.path.join(ExportPath, self._cleanName(filename))

        if isEpisode:
            infoLabels['TVShowTitle'] = filename
            nfoType = 'episodedetails'
            filename = '%s - S%02dE%02d - %s' % (infoLabels['TVShowTitle'], infoLabels['Season'],
                                                 infoLabels['Episode'], infoLabels['Title'])

        if self._g.addon.getSetting('cr_nfo') == 'true':
            self.CreateInfoFile(filename, ExportPath, nfoType, infoLabels, language)

        self.SaveFile(filename + '.strm', url, ExportPath)
        Log('Export: ' + filename)

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
            data = getURL('%s/gp/video/api/enrichItemMetadata?itemsToEnrich=%s' % (self._g.BaseUrl, quote_plus(params)), useCookie=cookie)
            endp = self.findKey('endpoint', data)

        if endp:
            action = 'Remove' if remove else 'Add'
            url = self._g.BaseUrl + endp.get('partialURL')
            query = endp.get('query')
            query['tag'] = action
            data = getURL(url, postdata=query, useCookie=cookie, check=True)
            if data:
                Log(action + ' ' + asin)
                if remove:
                    cPath = xbmc.getInfoLabel('Container.FolderPath').replace(asin, '').replace('opt=' + self._g.watchlist,
                                                                                                'opt=rem_%s' % self._g.watchlist)
                    xbmc.executebuiltin('Container.Update("%s", replace)' % cPath)
                elif self._s.wl_export:
                    self.listContent('GetASINDetails', 'asinList%3D' + asin, 1, '_show' if self._s.dispShowOnly else '', 1)
                    xbmc.executebuiltin('UpdateLibrary(video)')

    def getArtWork(self, infoLabels, contentType):
        if contentType == 'movie' and self._s.tmdb_art == '0':
            return infoLabels
        if contentType != 'movie' and self._s.tvdb_art == '0':
            return infoLabels

        c = self._db.cursor()
        asins = infoLabels['Asins']
        infoLabels['Banner'] = None
        season = -1 if contentType == 'series' else -2

        if contentType == 'season' or contentType == 'episode':
            asins = infoLabels.get('SeriesAsin', asins)
        if 'Season' in infoLabels.keys():
            season = int(infoLabels['Season'])

        extra = ' and season = %s' % season if season > -2 else ''

        for asin in asins.split(','):
            result = c.execute('select poster,fanart,banner from art where asin like (?)' + extra,
                               ('%' + asin + '%',)).fetchone()
            if result:
                if result[0] and contentType != 'episode' and result[0] != self._g.na:
                    infoLabels['Thumb'] = result[0]
                if result[0] and contentType != 'movie' and result[0] != self._g.na:
                    infoLabels['Poster'] = result[0]
                if result[1] and result[1] != self._g.na:
                    infoLabels['Fanart'] = result[1]
                if result[2] and result[2] != self._g.na:
                    infoLabels['Banner'] = result[2]
                if season > -1:
                    result = c.execute('select poster, fanart from art where asin like (?) and season = -1',
                                       ('%' + asin + '%',)).fetchone()
                    if result:
                        if result[0] and result[0] != self._g.na and contentType == 'episode':
                            infoLabels['Poster'] = result[0]
                        if result[1] and result[1] != self._g.na and self._s.showfanart:
                            infoLabels['Fanart'] = result[1]
                return infoLabels
            elif season > -1 and self._s.showfanart:
                result = c.execute('select poster,fanart from art where asin like (?) and season = -1',
                                   ('%' + asin + '%',)).fetchone()
                if result:
                    if result[0] and result[0] != self._g.na and contentType == 'episode':
                        infoLabels['Poster'] = result[0]
                    if result[1] and result[1] != self._g.na:
                        infoLabels['Fanart'] = result[1]
                    return infoLabels

        if contentType != 'episode':
            title = infoLabels['Title']
            if contentType == 'season':
                title = infoLabels['TVShowTitle']
            c.execute('insert or ignore into miss values (?,?,?,?)', (asins, title, infoLabels['Year'], contentType))
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
        season = infoLabels['Season']
        if parent:
            if infoLabels['Title'].lower().strip() != infoLabels['TVShowTitle'].lower().strip():
                return infoLabels['DisplayTitle']
            name = infoLabels['Title'] + ' - '
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
            self.listContent(listing, 'movie', 1, listing, export)
            self.listContent(listing, 'tv', 1, listing, export)
            if export == 2: xbmc.executebuiltin('UpdateLibrary(video)')
        else:
            addDir(getString(30104), 'listContent', 'movie', catalog=listing, export=export)
            addDir(getString(30107), 'listContent', 'tv', catalog=listing, export=export)
            xbmcplugin.endOfDirectory(self._g.pluginhandle, updateListing=False)

    def findKey(self, key, obj):
        if key in obj.keys():
            return obj[key]
        for v in obj.values():
            if isinstance(v, dict):
                res = self.findKey(key, v)
                if res: return res
            elif isinstance(v, list):
                for d in v:
                    if isinstance(d, dict):
                        res = self.findKey(key, d)
                        if res:
                            return res
        return []

    def _scrapeAsins(self, aurl, cj):
        asins = []
        url = self._g.BaseUrl + aurl
        json = GrabJSON(url)
        if not json:
            return False, False
        WriteLog(str(json), 'watchlist')
        cont = self.findKey('content', json)
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
            url = '/gp/video/mystuff/{}/{}/?page={}&sort={}'.format(listing, cont, page, self._s.wl_order)
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

    def getInfos(self, item, export):
        infoLabels = self.getAsins(item)
        infoLabels['DisplayTitle'] = infoLabels['Title'] = self.cleanTitle(item['title'])
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
        infoLabels['Genre'] = ' / '.join(item.get('genres', ''))\
            .replace('_', ' & ')\
            .replace('Musikfilm & Tanz', 'Musikfilm, Tanz')\
            .replace('ã–', 'ö')

        if 'formats' in item and 'images' in item['formats'][0].keys():
            try:
                infoLabels['Thumb'] = self.cleanIMGurl(item['formats'][0]['images'][0]['uri'])
            except:
                pass

        if 'releaseOrFirstAiringDate' in item:
            infoLabels['Premiered'] = item['releaseOrFirstAiringDate']['valueFormatted'].split('T')[0]
            infoLabels['Year'] = int(infoLabels['Premiered'].split('-')[0])

        if 'regulatoryRating' in item:
            if item['regulatoryRating'] == 'not_checked' or not item['regulatoryRating']:
                infoLabels['MPAA'] = getString(30171)
            else:
                infoLabels['MPAA'] = AgeRestrictions().GetAgeRating() + item['regulatoryRating']

        if 'customerReviewCollection' in item:
            infoLabels['Rating'] = float(item['customerReviewCollection']['customerReviewSummary']['averageOverallRating']) * 2
            infoLabels['Votes'] = str(item['customerReviewCollection']['customerReviewSummary']['totalReviewCount'])
        elif 'amazonRating' in item:
            infoLabels['Rating'] = float(item['amazonRating']['rating']) * 2 if 'rating' in item['amazonRating'] else None
            infoLabels['Votes'] = str(item['amazonRating']['count']) if 'count' in item['amazonRating'] else None

        if contentType == 'series':
            infoLabels['mediatype'] = 'tvshow'
            infoLabels['TVShowTitle'] = item['title']
            infoLabels['TotalSeasons'] = item['childTitles'][0]['size'] if item.get('childTitles') else None

        elif contentType == 'season':
            infoLabels['mediatype'] = 'season'
            infoLabels['Season'] = item['number']
            if item['ancestorTitles']:
                for content in item['ancestorTitles']:
                    if content['contentType'] == 'SERIES':
                        infoLabels['SeriesAsin'] = content['titleId'] if 'titleId' in content else None
                        infoLabels['TVShowTitle'] = content['title'] if 'title' in content else None
            else:
                infoLabels['SeriesAsin'] = infoLabels['Asins'].split(',')[0]
                infoLabels['TVShowTitle'] = item['title']
            if item.get('childTitles'):
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
            infoLabels['TVShowTitle'] = self.cleanTitle(infoLabels['TVShowTitle'])

        infoLabels = self.getArtWork(infoLabels, contentType)

        if not export:
            if not infoLabels['Thumb']:
                infoLabels['Thumb'] = self._s.DefaultFanart
            if not infoLabels['Fanart']:
                infoLabels['Fanart'] = self._s.DefaultFanart
            if not infoLabels['isPrime'] and not contentType == 'series':
                infoLabels['DisplayTitle'] = '[COLOR %s]%s[/COLOR]' % (self._g.PayCol, infoLabels['DisplayTitle'])
        return contentType, infoLabels

    @staticmethod
    def cleanIMGurl(img):
        # r'\.[^/]+(\.[^/]+$)', '\\1'
        return re.sub(r'\._.*_\.', r'.', img) if img else None

    def Channel(self, url, uid):
        def getInfos(item):
            # runtime: de "1 Std. 26 Min." uk "1h 22min"
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
            il['Title'] = '%s - %s' % (n, title) if n else title
            il['Plot'] = item.get('synopsis', '').strip()
            il['contentType'] = item.get('titleType', '')
            il['Duration'] = item.get('duration')
            il['MPAA'] = item.get('ratingBadge', {}).get('simplifiedId')
            il['isPrime'] = item.get('isPrime', True)
            il['Genre'] = ' / '.join(i.get('text', '') for i in item.get('genres', []))
            il['Studio'] = ', '.join(item.get('studios', []))
            il['Director'] = ', '.join(i['name'] for i in contr.get('directors', []))
            il['Cast'] = [i['name'] for i in contr.get('starringActors', []) + contr.get('supportingActors', [])]
            il['Year'] = item.get('releaseYear')
            if num:
                il['Episode'] = item.get('episodeNumber')
                il['Title'] = '%s - %s' % (num, il['Title'])
            if wl:
                il['contentType'] = wl['endpoint']['query'].get('titleType', '')
            if 'images' in item:
                img = item['images']
                il['Thumb'] = self.cleanIMGurl(img.get('packshot', img.get('titleshot')))
                il['Fanart'] = self.cleanIMGurl(img.get('heroshot'))
            else:
                il['Thumb'] = self.cleanIMGurl(item.get('image', {}).get('url', facet.get('image', '') if facet else item.get('facetImage')))
            if rating and rating.get('value'):
                il['Rating'] = float(rating['value']) * 2
                il['Votes'] = str(rating['count'])
            if live:
                il['Plot'] += '\n\n' if il['Plot'] else ''
                il['contentType'] = 'live'
                il['Plot'] += ' - '.join([live.get('timeBadge', live.get('label', '')), live.get('venue', '')])
            if livestate:
                il['Plot'] += '\n\n' if il['Plot'] else ''
                il['contentType'] = livestate.get('id', il['contentType'])
                if livestate.get('isLive', False):
                    il['contentType'] = 'live'
                il['Plot'] += ' - '.join([livestate.get('text', ''), item.get('pageDateTimeBadge', '')])
            if not il['Title']:
                il['Title'] = item.get('image', {}).get('alternateText', '')
                il['contentType'] = 'thumbnail'
            if item.get('itemType', '').lower() == 'label':
                il['Plot'] = il['Title']
                il['Title'] = '-= %s =-' % item['link']['label']
                il['Thumb'] = self._s.NextIcon
            if not il['Duration'] and runtime:
                t = re.findall(r'\d+', runtime)
                t = ['0'] * (2 - len(t)) + t
                il['Duration'] = sum(map(lambda a, b: int(a) * b, t, (3600, 60)))
            if 'playbackActions' in item:
                il['contentType'] = self.findKey('videoMaterialType', item['playbackActions'])
            elif 'notificationActions' in item:
                il['contentType'] = 'nostream'
                il['Title'] = '%s (%s)' % (il['Title'], item['notificationActions'][0]['message']['string'])
            il['DisplayTitle'] = self.cleanTitle(il['Title'])
            il['contentType'] = il['contentType'].lower()
            # il = self.getArtWork(il, il['contentType'])
            return il, il['contentType']

        def getcache(uid):
            j = {}
            c = self._menuDb.cursor()
            for data in c.execute('select data from channels where uid = (?)', (uid,)).fetchall():
                j = json.loads(data[0])
            c.close()
            return j

        def remref(url):
            f = re.findall('ref=[^?^&]*', url)
            return url.replace(f[0], '') if f else url

        def crctxmenu(item):
            cm = []
            wl = item.get('watchlistAction', item.get('watchlistButton'))
            if wl:
                cm.append((wl['text']['string'], 'RunPlugin(%s?mode=WatchList&url=%s)' % (self._g.pluginid, quote_plus(json.dumps(wl['endpoint'])))))
            return cm

        data = getcache(uid) if not url else GrabJSON(url)
        s = time.time()
        props = data.get('search', data.get('results', data))
        vw = ''
        urls = []
        num_items = 0

        if 'collections' in props:
            if uid == 'root':
                self._createDB(self._chan_tbl)
                if 'epgIngress' in props:
                    title = props['epgIngress'].get('label', 'Channel Guide')
                    url = props['epgIngress'].get('url')
                    addDir(title, 'Channel', url)

            for col in props.get('collections', []):
                if col.get('collectionType', '') in ['TwinHero', 'Carousel']:
                    num_items += 1
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
                    il['contentType'] = item.get('playbackAction', item).get('videoMaterialType', ct).lower()
                cm = crctxmenu(item)
                if playable or chid:
                    addVideo(il['DisplayTitle'], chid if chid else item['titleID'], il, cm=cm)
                else:
                    url = item['link']['url']
                    if ct == 'season':
                        url += '?episodeListSize=999'
                    if il['Title']:
                        addDir(il['DisplayTitle'], 'Channel', url, infoLabels=il, opt=ct, cm=cm)
                    urls.append(remref(url))
                vw = ct if ct else vw
        elif 'state' in props:
            pgid = props['state'].get('pageTitleId', '')
            act = props['state'].get('action', {})
            action = act.get('btf', act.get('atf', {}))
            detail = props['state'].get('detail', {})
            col = props['state'].get('collections', [])
            titleids = []
            if col and len(col.get(pgid, [])) > 0:
                [titleids.extend(i.get('titleIds', [])) for i in col[pgid] if i.get('collectionType', '') in ['episodes', 'bonus', 'schedule']]
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
                    id = self.findKey('playbackID', item.get('playbackActions', {}))
                    asin = id if id else asin
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
                il['Title'] = item.get('channelName')
                il['Thumb'] = self.cleanIMGurl(item.get('logo', ''))
                il['DisplayTitle'] = self.cleanTitle(il['Title'])
                il['Plot'] = ''
                upnext = False
                if shed:
                    ts = time.time()
                    for sh in shed:
                        us = sh.get('unixStart') / 1000
                        ue = sh.get('unixEnd') / 1000
                        if (us <= ts <= ue) or upnext:
                            il['Plot'] += '{:%H:%M}-{:%H:%M}  {}\n'.format(datetime.fromtimestamp(us), datetime.fromtimestamp(ue), sh.get('title', ''))
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
                addDir('-= %s =-' % more['label'], 'Channel', nextpage, thumb=self._s.NextIcon)

        Log('Parsing Channels Page: %ss' % (time.time()-s), Log.DEBUG)
        '''
        Log(vw)
        self._db.commit()
        xbmc.executebuiltin('RunPlugin(%s?mode=checkMissing)' % self._g.pluginid)
        '''
        setContentAndView(vw)
        return

    def getProfiles(self):
        j = GrabJSON(self._g.BaseUrl + '/gp/video/profiles')
        if not j:
            return False, False
        profiles = []
        active = 0
        for item in j['profiles']:
            url = self._g.BaseUrl + item['switchLink']['partialURL']
            q = urlencode(item['switchLink']['query'])
            n = item.get('name', 'Default').encode('utf-8')
            profiles.append((n, '{}?{}'.format(url, q), item['avatarUrl']))
            if item.get('isSelected', False):
                active = len(profiles) - 1
                writeConfig('profileID', '' if item.get('isDefault', False) else n)
        return active, profiles

    def switchProfile(self):
        active, profiles = self.getProfiles()
        if active is not False:
            ret = self._g.dialog.select('Amazon', [i[0] for i in profiles])
            if ret >= 0 and ret != active:
                getURL(profiles[ret][1], useCookie=True, rjson=False, silent=True, check=True)
        exit()
