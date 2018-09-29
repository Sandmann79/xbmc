#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from collections import OrderedDict
import pickle
import time
import re
import sys
import xbmcgui
import xbmcplugin
from urllib import quote_plus

from .singleton import Singleton
from .network import getURL, getURLData, MechanizeLogin
from .logging import Log
from .itemlisting import setContentAndView
from .l10n import *
from .users import *
from .playback import PlayVideo


class PrimeVideo(Singleton):
    """ Wrangler of all things PrimeVideo.com """

    _catalog = {}  # Catalog cache
    _videodata = {}  # Video data cache
    _catalogCache = None  # Catalog cache file name
    _videodataCache = None  # Video data cache file name
    _WatchlistPages = {}  # Avoid LazyLoad infinite recursion on watchlist parsing

    def __init__(self, globalsInstance, settingsInstance):
        self._g = globalsInstance
        self._s = settingsInstance
        self._dateParserData = {
            """ Data for date string deconstruction and reassembly

                Date references:
                https://www.primevideo.com/detail/0LCQSTWDMN9V770DG2DKXY3GVF/  01 02 03 04 05 09 10 11 12
                https://www.primevideo.com/detail/0ND5POOAYD6A4THTH7C1TD3TYE/  06 07 08 09
            """
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
                      'months': {'janvier': 1, 'février': 2, 'mars': 3, 'avril': 4, 'mai': 5, 'juin': 6, 'juillet': 7, 'aout': 8, 'août': 8, 'septembre': 9,
                                 'octobre': 10, 'novembre': 11, 'décembre': 12}},
            'it_IT': {'deconstruct': r'^([0-9]+)\s+([^\s]+)\s+([0-9]+)', 'reassemble': '{2}-{1:0>2}-{0:0>2}', 'month': 1,
                      'months': {'gennaio': 1, 'febbraio': 2, 'marzo': 3, 'aprile': 4, 'maggio': 5, 'giugno': 6, 'luglio': 7, 'agosto': 8, 'settembre': 9,
                                 'ottobre': 10, 'novembre': 11, 'dicembre': 12}},
            'nl_NL': {'deconstruct': r'^([0-9]+)\s+([^\s]+)\s+([0-9]+)', 'reassemble': '{2}-{1:0>2}-{0:0>2}', 'month': 1,
                      'months': {'januari': 1, 'februari': 2, 'maart': 3, 'april': 4, 'mei': 5, 'juni': 6, 'juli': 7, 'augustus': 8, 'september': 9,
                                 'oktober': 10, 'november': 11, 'december': 12}},
            'pl_PL': {'deconstruct': r'^([0-9]+)\s+([^\s]+)\s+([0-9]+)', 'reassemble': '{2}-{1:0>2}-{0:0>2}', 'month': 1,
                      'months': {'stycznia': 1, 'lutego': 2, 'marca': 3, 'kwietnia': 4, 'maja': 5, 'czerwca': 6, 'lipca': 7, 'sierpnia': 8, 'września': 9,
                                 'października': 10, 'listopada': 11, 'grudnia': 12}},
            'pt_BR': {'deconstruct': r'^([0-9]+)\s+de\s+([^\s]+),\s+de\s+([0-9]+)', 'reassemble': '{2}-{1:0>2}-{0:0>2}', 'month': 1,
                      'months': {'janeiro': 1, 'fevereiro': 2, 'março': 3, 'abril': 4, 'maio': 5, 'junho': 6, 'julho': 7, 'agosto': 8, 'setembro': 9, 'outubro': 10,
                                 'novembro': 11, 'dezembro': 12}},
        }
        self._LoadCache()

    def _flush(self, FlushVideoData=False):
        """ Cache catalog and video data """

        with open(self._catalogCache, 'w+') as fp:
            pickle.dump(self._catalog, fp)
        if FlushVideoData:
            with open(self._videodataCache, 'w+') as fp:
                pickle.dump(self._videodata, fp)

    def _LoadCache(self):
        """ Load cached catalog and video data """
        from os.path import join as OSPJoin
        from xbmcvfs import exists

        self._catalogCache = OSPJoin(self._g.DATA_PATH, 'PVCatalog{0}.pvcp'.format(self._g.MarketID))
        self._videodataCache = OSPJoin(self._g.DATA_PATH, 'PVVideoData{0}.pvdp'.format(self._g.MarketID))

        if exists(self._videodataCache):
            with open(self._videodataCache, 'r') as fp:
                self._videodata = pickle.load(fp)
        if exists(self._catalogCache):
            with open(self._catalogCache, 'r') as fp:
                cached = pickle.load(fp)
            if time.time() < cached['expiration']:
                self._catalog = cached

    def BrowseRoot(self):
        """ Build and load the root PrimeVideo menu """
        if 0 == len(self._catalog):
            ''' Build the root catalog '''
            if not self.BuildRoot():
                return
        self.Browse('root')

    def BuildRoot(self):
        """ Parse the top menu on primevideo.com and build the root catalog """
        self._catalog['root'] = OrderedDict()
        home = getURL(self._g.BaseUrl, silent=True, useCookie=True, rjson=False)
        if None is home:
            self._g.dialog.notification('Connection error', 'Unable to fetch the primevideo.com homepage', xbmcgui.NOTIFICATION_ERROR)
            Log('Unable to fetch the primevideo.com homepage', Log.ERROR)
            return False

        # Setup watchlist
        watchlist = re.search(r'<a[^>]* href="(/watchlist/)[^"]*"[^>]*>(.*?)</a>', home)
        if None is not watchlist:
            self._catalog['root']['Watchlist'] = {'title': watchlist.group(2), 'lazyLoadURL': self._g.BaseUrl + watchlist.group(1)}

        # PrimeVideo.com top navigation menu
        home = re.search('<div id="av-nav-main-menu".*?<ul role="navigation"[^>]*>\s*(.*?)\s*</ul>', home)
        if None is home:
            self._g.dialog.notification('PrimeVideo error', 'Unable to find the main primevideo.com navigation section', xbmcgui.NOTIFICATION_ERROR)
            Log('Unable to find the main primevideo.com navigation section', Log.ERROR)
            return False
        for item in re.findall('<li[^>]*>\s*(.*?)\s*</li>', home.group(1)):
            item = re.search('<a href="([^"]+)"[^>]*>\s*(.*?)\s*</a>', item)
            if None is not re.match('/storefront/home/', item.group(1)):
                continue
            # Remove react comments
            title = re.sub('^<!--\s*[^>]+\s*-->', '', re.sub('<!--\s*[^>]+\s*-->$', '', item.group(2)))
            self._catalog['root'][title] = {'title': title, 'lazyLoadURL': self._g.BaseUrl + item.group(1) + '?_encoding=UTF8&format=json'}
        if 0 == len(self._catalog['root']):
            self._g.dialog.notification('PrimeVideo error', 'Unable to build the root catalog from primevideo.com', xbmcgui.NOTIFICATION_ERROR)
            Log('Unable to build the root catalog from primevideo.com', Log.ERROR)
            return False

        # Search method
        self._catalog['root']['Search'] = {'title': getString(30108), 'verb': 'PrimeVideo_Search'}

        # Set the expiration in 11 hours and flush to disk
        self._catalog['expiration'] = 39600 + int(time.time())
        self._flush()

        return True

    def Search(self):
        """ Provide search functionality for PrimeVideo """
        searchString = self._g.dialog.input(getString(24121)).strip(' \t\n\r')
        if 0 == len(searchString):
            xbmcplugin.endOfDirectory(self._g.pluginhandle, succeeded=False)
            return
        Log('Searching "{0}"…'.format(searchString), Log.INFO)
        self._catalog['search'] = OrderedDict([('lazyLoadURL', 'https://www.primevideo.com/search/ref=atv_nb_sr?ie=UTF8&phrase={0}'.format(searchString))])
        self.Browse('search', xbmcplugin.SORT_METHOD_NONE)

    def Browse(self, path, forceSort=None):
        """ Display and navigate the menu for PrimeVideo users """

        path = path.decode('utf-8')

        # Add multiuser menu if needed
        if (self._s.multiuser) and ('root' == path) and (1 < len(loadUsers())):
            li = xbmcgui.ListItem(getString(30134).format(loadUser('name')))
            li.addContextMenuItems(self._g.CONTEXTMENU_MULTIUSER)
            xbmcplugin.addDirectoryItem(self._g.pluginhandle, '{0}?mode=PrimeVideo_Browse&path=root-//-SwitchUser'.format(self._g.pluginid), li, isFolder=False)
        if 'root-//-SwitchUser' == path:
            if switchUser():
                self.BuildRoot()
            return

        node = self._catalog
        nodeName = None
        for n in path.split('-//-'):
            nodeName = n
            node = node[n]

        if (nodeName in self._videodata) and ('metadata' in self._videodata[nodeName]) and ('video' in self._videodata[nodeName]['metadata']):
            """ Start the playback if on a video leaf """
            PlayVideo(self._videodata[nodeName]['metadata']['video'], self._videodata[nodeName]['metadata']['asin'], '', 0)
            return

        if (None is not node) and ('lazyLoadURL' in node):
            self._LazyLoad(node, nodeName)

        if None is node:
            self._g.dialog.notification('General error', 'Something went terribly wrong…', xbmcgui.NOTIFICATION_ERROR)
            return

        folderType = 0 if 'root' == path else 1
        for key in node:
            if key in ['metadata', 'ref', 'title', 'verb', 'children']:
                continue
            url = '{0}?mode='.format(self._g.pluginid)
            entry = node[key] if key not in self._videodata else self._videodata[key]
            if 'verb' not in entry:
                url += 'PrimeVideo_Browse&path={0}-//-{1}'.format(quote_plus(path.encode('utf-8')), quote_plus(key.encode('utf-8')))
                # Squash season number folder when only one season is available
                if ('metadata' not in entry) and ('children' in entry) and (1 == len(entry['children'])):
                    url += '-//-{0}'.format(quote_plus(entry['children'][0].encode('utf-8')))
            else:
                url += entry['verb']
            title = entry['title'] if 'title' in entry else nodeName
            item = xbmcgui.ListItem(title)
            folder = True
            # In case of series find the oldest series and apply its art, also update metadata in case of squashed series
            if ('metadata' not in entry) and ('children' in entry) and (0 < len(entry['children'])):
                if 1 == len(entry['children']):
                    entry['metadata'] = {'artmeta': self._videodata[entry['children'][0]]['metadata']['artmeta'],
                                         'videometa': self._videodata[entry['children'][0]]['metadata']['videometa']}
                else:
                    sn = 90001
                    snid = None
                    for child in entry['children']:
                        if ('season' in self._videodata[child]['metadata']['videometa']) and (sn > self._videodata[child]['metadata']['videometa']['season']):
                            sn = self._videodata[child]['metadata']['videometa']['season']
                            snid = child
                    if None is not snid:
                        entry['metadata'] = {'artmeta': self._videodata[snid]['metadata']['artmeta'], 'videometa': {'mediatype': 'tvshow'}}
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
            xbmcplugin.addDirectoryItem(self._g.pluginhandle, url, item, isFolder=folder)
            del item

        # Set sort method and view
        # https://codedocs.xyz/xbmc/xbmc/group__python__xbmcplugin.html#ga85b3bff796fd644fb28f87b136025f40
        xbmcplugin.addSortMethod(self._g.pluginhandle, [
            xbmcplugin.SORT_METHOD_NONE,
            xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE,
            xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE,
            xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE,
            xbmcplugin.SORT_METHOD_EPISODE,
            xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE,
        ][folderType if None is forceSort else forceSort])

        if 'false' == self._g.addon.getSetting("viewenable"):
            # Only vfs and videos to keep Kodi's watched functionalities
            folderType = 0 if 2 > folderType else 1
        else:
            # Actual views, set the main categories as vfs
            folderType = 0 if 2 > folderType else 2

        setContentAndView([None, 'videos', 'series', 'season', 'episode', 'movie'][folderType])

    def _LazyLoad(self, obj, objName):
        """ Loader and parser of all the PrimeVideo.com queries """

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

            def BeautifyText(title):
                """ Correct stylistic errors in Amazon's titles """
                for t in [(r'\s+-\s*', ' – '),  # Convert dash from small to medium where needed
                          (r'\s*-\s+', ' – '),  # Convert dash from small to medium where needed
                          (r'^\s+', ''),  # Remove leading spaces
                          (r'\s+$', ''),  # Remove trailing spaces
                          (r' {2,}', ' '),  # Remove double spacing
                          (r'\.\.\.', '…')]:  # Replace triple dots with ellipsis
                    title = re.sub(t[0], t[1], title)
                return title

            return BeautifyText(ret)

        def MaxSize(imgUrl):
            """ Strip the dynamic resize triggers from the URL (and other effects, such as blur) """
            return re.sub(r'\._.*_\.', '.', imgUrl)

        def ExtractURN(url):
            """ Extract the unique resource name identifier """
            ret = re.search(r'(/gp/video)?/detail/([^/]+)/', url)
            if None is not ret:
                ret = ret.group(2)
            return ret

        def DelocalizeDate(lang, datestr):
            """ Convert language based timestamps into YYYY-MM-DD """
            if lang not in self._dateParserData:
                Log('Unable to decode date "{0}": language "{1}" not supported'.format(datestr, lang), Log.WARNING)
                return datestr
            p = re.search(self._dateParserData[lang]['deconstruct'], datestr)
            if None is p:
                # Sometimes Amazon returns english everything, let's try to figure out if this is the case
                p = re.search(self._dateParserData['en_US']['deconstruct'], datestr)
                if None is p:
                    Log('Unable to parse date "{0}" with language "{1}": format changed?'.format(datestr, lang), Log.WARNING)
                    return datestr
            p = list(p.groups())
            p[self._dateParserData[lang]['month']] = self._dateParserData[lang]['months'][p[self._dateParserData[lang]['month']]]
            return self._dateParserData[lang]['reassemble'].format(p[0], p[1], p[2])

        def NotifyUser(msg):
            """ Pop up messages while scraping to inform users of progress """
            if not hasattr(NotifyUser, 'lastNotification'):
                NotifyUser.lastNotification = 0
            if NotifyUser.lastNotification < time.time():
                ''' Only update once every other second, to avoid endless message queue '''
                NotifyUser.lastNotification = 1 + time.time()
                self._g.dialog.notification(self._g.addon.getAddonInfo('name'), msg, time=1000, sound=False)

        def PopulateInlineMovieSeries(obj, rq, title, image, url):
            """ Takes a sequence of Movies or TV Series such as in watchlist and carousels and fetches the metadata """
            # Log('PIMS: %s %s %s %s %s' % (obj, rq, title, image, url))
            urn = ExtractURN(url)
            obj[urn] = {}
            if urn in self._videodata:
                return False
            self._videodata[urn] = {
                'metadata': {'artmeta': {'thumb': MaxSize(image), 'poster': MaxSize(image)}, 'videometa': {}},
                'title': Unescape(title)
            }
            rq.append((url, obj[urn], urn))
            return True

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
                self._g.dialog.notification(getString(30251), requestURL, xbmcgui.NOTIFICATION_ERROR)
                Log('Unable to fetch the url: {0}'.format(requestURL), Log.ERROR)
                break

            for t in [('\\\\n', '\n'), ('\\n', '\n'), ('\\\\"', '"'), (r'^\s+', '')]:
                cnt = re.sub(t[0], t[1], cnt, flags=re.DOTALL)
            if None is not re.search('<html[^>]*>', cnt):
                ''' If there's an HTML tag it's no JSON-AmazonUI-Streaming object '''
                if None is not re.search(r'<div[^>]* id="Watchlist"[^>]*>', cnt, flags=re.DOTALL):
                    ''' Watchlist '''
                    if ('Watchlist' == objName):
                        for entry in re.findall(r'<a href="([^"]+/)[^"/]+" class="DigitalVideoUI_TabHeading__tab([^"]*DigitalVideoUI_TabHeading__active)?">(.*?)</a>', cnt, flags=re.DOTALL):
                            obj[Unescape(entry[2])] = {'title': Unescape(entry[2]), 'lazyLoadURL': self._g.BaseUrl + entry[0] + '?sort=DATE_ADDED_DESC'}
                        continue
                    for entry in re.findall(r'<div[^>]* class="[^"]*DigitalVideoWebNodeLists_Item__item[^"]*"[^>]*>\s*<a href="(/detail/[^/]+/)[^"]*"[^>]*>*.*?<img src="([^"]+)".*?"[^"]*DigitalVideoWebNodeLists_Item__coreTitle[^"]*"[^>]*>\s*(.*?)\s*</', cnt):
                        bUpdatedVideoData = True if PopulateInlineMovieSeries(obj, requestURLs, entry[2], entry[1], self._g.BaseUrl + entry[0]) else bUpdatedVideoData
                    pagination = re.search(r'<ol[^>]* class="[^"]*DigitalVideoUI_Pagination__pagination[^"]*"[^>]*>(.*?)</ol>', cnt)
                    if None is not pagination:
                        # We save a semi-static list of scraped pages, to avoid circular loops
                        if (refUrn not in self._WatchlistPages):
                            self._WatchlistPages[refUrn] = []
                        currentPage = re.search(r'<a[^>]* href="#"[^>]*>\s*<span>\s*([0-9]+)\s*</span>', pagination.group(0), flags=re.DOTALL).group(1)
                        if currentPage not in self._WatchlistPages[refUrn]:
                            self._WatchlistPages[refUrn].append(currentPage)
                        for entry in re.findall(r'<li[^>]*>\s*<a href="(/[^"]+)"[^>]*>\s*<span>\s*([0-9]+)\s*', pagination.group(0)):
                            if entry[1] not in self._WatchlistPages[refUrn]:
                                requestURLs.append((self._g.BaseUrl + entry[0], o, refUrn))
                elif re.search('<div class="av-dp-container">', cnt, flags=re.DOTALL):
                    ''' Movie/series page '''
                    # Find the biggest fanart available
                    bgimg = re.search(r'<div class="av-hero-background[^"]*"[^>]*url\(([^)]+)\)', cnt, flags=re.DOTALL)
                    if None is not bgimg:
                        bgimg = MaxSize(bgimg.group(1))

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
                    results = re.search(r'<section\s+[^>]*class="avu-page-container[^>]*>\s*(.*?)\s*</section>', cnt, flags=re.DOTALL).group(1)
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
                        if 'video' not in self._videodata[refUrn]['metadata']:
                            asin = re.search(r'"asin":"([^"]*)"', cnt, flags=re.DOTALL)
                            if None is not asin:
                                bUpdatedVideoData = True

                                meta = self._videodata[refUrn]['metadata']
                                if None is not bgimg:
                                    meta['artmeta']['fanart'] = bgimg
                                NotifyUser(getString(30253).format(self._videodata[refUrn]['title']))
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
                                success, gpr = getURLData('catalog/GetPlaybackResources', meta['asin'], useCookie=True, extra=True,
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
                                r'<div class="av-bgimg__div"[^>]*url\(([^)]+)\)',  # Image
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
                            if (None is res[0]) or (None is res[2]):
                                ''' Some episodes might be not playable until a later date or just N/A, although listed '''
                                continue
                            meta = {'artmeta': {'thumb': MaxSize(res[1]), 'poster': MaxSize(res[1]), 'fanart': bgimg, }, 'videometa': {'mediatype': 'episode'},
                                    'id': res[0][0], 'asin': res[0][1], 'videoURL': res[0][2]}
                            if None is not re.match(r'/[^/]', meta['videoURL']):
                                meta['videoURL'] = self._g.BaseUrl + meta['videoURL']
                            meta['video'] = ExtractURN(meta['videoURL'])
                            eid = meta['video']
                            # if None is not res[7]:
                            #     eid = res[7]

                            if (eid not in self._videodata) or ('videometa' not in self._videodata[eid]) or (0 == len(self._videodata[eid]['videometa'])):
                                # Extract the runtime
                                success, gpr = getURLData('catalog/GetPlaybackResources', res[7], useCookie=True, extra=True,
                                                          opt='&titleDecorationScheme=primary-content', dRes='CatalogMetadata')
                                if not success:
                                    gpr = None
                                else:
                                    if 'runtimeSeconds' in gpr['catalogMetadata']['catalog']:
                                        meta['runtime'] = gpr['catalogMetadata']['catalog']['runtimeSeconds']

                                # Sometimes the chicken comes before the egg
                                # if refUrn not in self._videodata:
                                #     self._videodata[refUrn] = { 'metadata': { 'videometa': {} }, 'children': [] }

                                # Insert series information
                                if None is not gres[0]: meta['videometa']['year'] = gres[0]
                                if None is not gres[1]: meta['videometa']['rating'] = int(gres[1][0]) + (int(gres[1][1]) / 10.0)
                                if None is not gres[2]: meta['videometa']['mpaa'] = gres[2]
                                if None is not gres[3]:
                                    meta['videometa']['cast'] = gres[3]
                                    self._videodata[refUrn]['metadata']['videometa']['cast'] = gres[3]
                                if None is not gres[4]:
                                    meta['videometa']['genre'] = gres[4]
                                    self._videodata[refUrn]['metadata']['videometa']['genre'] = gres[4]
                                if None is not gres[5]:
                                    meta['videometa']['director'] = gres[5]
                                    self._videodata[refUrn]['metadata']['videometa']['director'] = gres[5]

                                # Insert episode specific information
                                if None is not res[3]: meta['videometa']['premiered'] = DelocalizeDate(amzLang, res[3])
                                if None is not res[4]: meta['videometa']['mpaa'] = res[4]
                                if None is not res[5]: meta['videometa']['plot'] = res[5]
                                if None is not res[6]:
                                    if 'season' in self._videodata[refUrn]['metadata']['videometa']:
                                        meta['videometa']['season'] = self._videodata[refUrn]['metadata']['videometa']['season']
                                    else:
                                        ''' We're coming from a widow carousel '''
                                        self._videodata[refUrn]['metadata']['videometa']['mediatype'] = 'tvshow'
                                        # Try with page season selector
                                        ssn = re.search(r'<a class="av-droplist--selected"[^>]*>[^0-9]*([0-9]+)[^0-9]*</a>', cnt)
                                        if None is ssn:
                                            # Try with single season
                                            ssn = re.search(r'<span class="av-season-single av-badge-text">[^0-9]*([0-9]+)[^0-9]*</span>', cnt)
                                        if None is not ssn:
                                            ssn = ssn.group(1)
                                            meta['videometa']['season'] = ssn
                                            self._videodata[refUrn]['metadata']['videometa']['season'] = ssn
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
                                self._videodata[eid] = {'metadata': meta, 'title': title, 'parent': refUrn}
                                NotifyUser(getString(30253).format(title))
                            if eid not in o:
                                o[eid] = {}
                            if (refUrn in self._videodata) and ('children' in self._videodata[refUrn]) and (eid not in self._videodata[refUrn]['children']):
                                self._videodata[refUrn]['children'].append(eid)

                else:
                    ''' Movie and series list '''
                    for entry in re.findall(r'<div class="[^"]*dvui-beardContainer[^"]*">\s*(.*?)\s*</form>\s*</div>\s*</div>\s*</div>', cnt, flags=re.DOTALL):
                        res = {
                            'title': r'<a class="av-beard-title-link"[^>]*>\s*(.*?)\s*</a>',
                            'asin': r'\s+data-asin="\s*([^"]+?)\s*"',
                            'image': r'<a [^>]+><img\s+[^>]*src="([^"]+)"',
                            'link': r'<a href="([^"]+)"><img',
                            'season': r'<span>\s*(Stagione|Staffel|Season|Temporada|Saison|Seizoen|Sezon)\s+([0-9]+)\s*</span>',
                        }
                        for i in res:
                            res[i] = re.search(res[i], entry)
                            if None is not res[i]:
                                res[i] = res[i].groups()
                                res[i] = Unescape(res[i][0]) if 1 == len(res[i]) else list(res[i])
                                if 'image' == i:
                                    res[i] = MaxSize(res[i])
                                elif 'season' == i:
                                    res[i] = {'locale': Unescape(res[i][0]), 'episode': int(res[i][1]), 'format': Unescape('{0} {1}'.format(res[i][0], res[i][1]))}
                        NotifyUser(getString(30253).format(res['title']))
                        if None is not re.match(r'/[^/]', res['link']):
                            res['link'] = self._g.BaseUrl + res['link']
                        meta = {'artmeta': {'thumb': res['image'], 'poster': res['image']}, 'videometa': {}}
                        meta['videometa']['mediatype'] = 'movie' if None is res['season'] else 'season'

                        if None is res['season']:
                            ''' Movie '''
                            # Queue the movie page instead of parsing partial information here
                            urn = ExtractURN(res['link'])
                            if urn not in o:
                                o[urn] = {}
                            if (urn not in self._videodata) or ('metadata' not in self._videodata[urn]) or ('video' not in self._videodata[urn]['metadata']):
                                bUpdatedVideoData = True
                                self._videodata[urn] = {'metadata': meta, 'title': res['title']}
                                requestURLs.append((res['link'], o[urn], urn))
                        else:
                            ''' Series '''
                            id = res['title']
                            sid = ExtractURN(res['link'])

                            if sid not in self._videodata:
                                self._videodata[sid] = {'children': []}

                            # Extract video metadata
                            if 'parent' in self._videodata[sid]:
                                id = self._videodata[sid]['parent']
                            elif (id is res['title']) and (None is not res['asin']):
                                success, gpr = getURLData('catalog/GetPlaybackResources', res['asin'], useCookie=True, extra=True,
                                                          opt='&titleDecorationScheme=primary-content', dRes='CatalogMetadata')
                                if not success:
                                    Log('Unable to get the video metadata for {0} ({1})'.format(res['title'], res['link']), Log.WARNING)
                                else:
                                    # Find the show Asin URN, if possible
                                    for d in gpr['catalogMetadata']['family']['tvAncestors']:
                                        if 'SHOW' == d['catalog']['type']:
                                            id = d['catalog']['id']
                                            self._videodata[sid]['parent'] = id
                                            break
                            if id not in o:
                                o[id] = {'title': res['title']}
                            if (sid in self._videodata) and ('children' in self._videodata[sid]) and (0 < len(self._videodata[sid]['children'])):
                                o[id][sid] = {k: {} for k in self._videodata[sid]['children']}
                            else:
                                # Save tree information if id is a URN and not a title name
                                if (id is not res['title']):
                                    if id not in self._videodata:
                                        self._videodata[id] = {'children': []}
                                    if sid not in self._videodata[id]['children']:
                                        self._videodata[id]['children'].append(sid)
                                    if 'title' not in self._videodata[id]:
                                        self._videodata[id]['title'] = res['title']
                                meta['videometa']['season'] = res['season']['episode']
                                o[id][sid] = {'lazyLoadURL': res['link']}
                                bUpdatedVideoData = True
                                self._videodata[sid]['title'] = res['season']['format']
                                self._videodata[sid]['metadata'] = meta

                    # Next page
                    pagination = re.search(
                        r'<ol\s+[^>]*id="[^"]*av-pagination[^"]*"[^>]*>.*?<li\s+[^>]*class="[^"]*av-pagination-current-page[^"]*"[^>]*>.*?</li>\s*<li\s+[^>]*class="av-pagination[^>]*>\s*(.*?)\s*</li>\s*</ol>',
                        cnt, flags=re.DOTALL)
                    if None is not pagination:
                        nru = Unescape(re.search(r'href="([^"]+)"', pagination.group(1), flags=re.DOTALL).group(1))
                        if None is not re.match(r'/[^/]', nru):
                            nru = self._g.BaseUrl + nru
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
                                    bUpdatedVideoData = True if PopulateInlineMovieSeries(o[title], requestURLs, parts.group(4), parts.group(3), parts.group(1)) else bUpdatedVideoData
                    pagination = re.search(r'data-ajax-pagination="{&quot;href&quot;:&quot;([^}]+)&quot;}"', section[2], flags=re.DOTALL)
                    if ('dvupdate' == section[0]) and (None is not pagination):
                        requestURLs.append(re.sub(r'(&quot;,&quot;|&amp;)', '&', re.sub('&quot;:&quot;', '=', pagination.group(1) + '&format=json')))
            if 0 < len(requestURLs):
                NotifyUser(getString(30252))

        # Flush catalog and data
        self._flush(bUpdatedVideoData)
