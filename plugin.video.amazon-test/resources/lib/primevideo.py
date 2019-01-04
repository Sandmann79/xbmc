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
    _separator = '-!!-'  # Virtual path separator

    def __init__(self, globalsInstance, settingsInstance):
        self._g = globalsInstance
        self._s = settingsInstance
        """ Data for text extrapolation

            References:
            https://www.primevideo.com/detail/0ND5POOAYD6A4THTH7C1TD3TYE/ Season, Starring, Genres
            https://www.primevideo.com/detail/0I5LVHEYZFZ51QTL86QYXWQ1QW/ Director, Starring, Genres
        """
        self._seasonRex = r'(Stagione|Staffel|Season|Temporada|Saison|Seizoen|Sezon|S[æeä]song?|सीज़न|சீசன்|సీజన్)'
        self._directorRex = r'(Direc?tor|Regia|Regie|Réalisation|Regisseur|Reżyser|Instruktør|Regiss[øö]r|निर्देशक|இயக்குனர்|దర్శకుడు)'
        self._starringRex = r'(Starring|Interpreti|Hauptdarsteller|Reparto|Acteurs principaux|In de hoofdrol|Występują|Atores principais|Medvirkende|I huvudrollerna|' \
                            r'मुख्य भूमिका में|நடித்தவர்கள்|నటులు:)'
        self._genresRex = r'(Gene?re[rs]?|Géneros|Gatunki|Gêneros|Sjangrer|शैलियां|வகைகள்|శైలీలు)'
        self._dateParserData = {
            """ Data for date string deconstruction and reassembly

                Date references:
                https://www.primevideo.com/detail/0LCQSTWDMN9V770DG2DKXY3GVF/  09 10 11 12 01 02 03 04 05
                https://www.primevideo.com/detail/0ND5POOAYD6A4THTH7C1TD3TYE/  06 07 08 09
            """
            'da_DK': {'deconstruct': r'^([0-9]+)\.\s+([^\s]+)\s+([0-9]+)', 'reassemble': '{2}-{1:0>2}-{0:0>2}', 'month': 1,
                      'months': {'januar': 1, 'februar': 2, 'marts': 3, 'april': 4, 'maj': 5, 'juni': 6, 'juli': 7, 'august': 8, 'september': 9, 'oktober': 10,
                                 'november': 11, 'december': 12}},
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
            'hi_IN': {'deconstruct': r'^([0-9]+)\s+([^\s]+)\s+([0-9]+)', 'reassemble': '{2}-{1:0>2}-{0:0>2}', 'month': 1,
                      'months': {'जनवरी': 1, 'फ़रवरी': 2, 'मार्च': 3, 'अप्रैल': 4, 'मई': 5, 'जून': 6, 'जुलाई': 7, 'अगस्त': 8, 'सितंबर': 9, 'अक्तूबर': 10,
                                 'नवंबर': 11, 'दिसंबर': 12}},
            'it_IT': {'deconstruct': r'^([0-9]+)\s+([^\s]+)\s+([0-9]+)', 'reassemble': '{2}-{1:0>2}-{0:0>2}', 'month': 1,
                      'months': {'gennaio': 1, 'febbraio': 2, 'marzo': 3, 'aprile': 4, 'maggio': 5, 'giugno': 6, 'luglio': 7, 'agosto': 8, 'settembre': 9,
                                 'ottobre': 10, 'novembre': 11, 'dicembre': 12}},
            'nb_NO': {'deconstruct': r'^([0-9]+)\.\s+([^\s]+)\s+([0-9]+)', 'reassemble': '{2}-{1:0>2}-{0:0>2}', 'month': 1,
                      'months': {'januar': 1, 'februar': 2, 'mars': 3, 'april': 4, 'mai': 5, 'juni': 6, 'juli': 7, 'august': 8, 'september': 9, 'oktober': 10,
                                 'november': 11, 'desember': 12}},
            'nl_NL': {'deconstruct': r'^([0-9]+)\s+([^\s]+)\s+([0-9]+)', 'reassemble': '{2}-{1:0>2}-{0:0>2}', 'month': 1,
                      'months': {'januari': 1, 'februari': 2, 'maart': 3, 'april': 4, 'mei': 5, 'juni': 6, 'juli': 7, 'augustus': 8, 'september': 9,
                                 'oktober': 10, 'november': 11, 'december': 12}},
            'pl_PL': {'deconstruct': r'^([0-9]+)\s+([^\s]+)\s+([0-9]+)', 'reassemble': '{2}-{1:0>2}-{0:0>2}', 'month': 1,
                      'months': {'stycznia': 1, 'lutego': 2, 'marca': 3, 'kwietnia': 4, 'maja': 5, 'czerwca': 6, 'lipca': 7, 'sierpnia': 8, 'września': 9,
                                 'października': 10, 'listopada': 11, 'grudnia': 12}},
            'pt_BR': {'deconstruct': r'^([0-9]+)\s+de\s+([^\s]+),\s+de\s+([0-9]+)', 'reassemble': '{2}-{1:0>2}-{0:0>2}', 'month': 1,
                      'months': {'janeiro': 1, 'fevereiro': 2, 'março': 3, 'abril': 4, 'maio': 5, 'junho': 6, 'julho': 7, 'agosto': 8, 'setembro': 9, 'outubro': 10,
                                 'novembro': 11, 'dezembro': 12}},
            'sv_SE': {'deconstruct': r'^([0-9]+)\s+([^\s]+)\s+([0-9]+)', 'reassemble': '{2}-{1:0>2}-{0:0>2}', 'month': 1,
                      'months': {'januari': 1, 'februari': 2, 'mars': 3, 'april': 4, 'maj': 5, 'juni': 6, 'juli': 7, 'augusti': 8, 'september': 9, 'oktober': 10,
                                 'november': 11, 'december': 12}},
            'ta_IN': {'deconstruct': r'^([0-9]+)\s+([^\s]+),\s+([0-9]+)', 'reassemble': '{2}-{1:0>2}-{0:0>2}', 'month': 1,
                      'months': {'ஜனவரி': 1, 'பிப்ரவரி': 2, 'மார்ச்': 3, 'ஏப்ரல்': 4, 'மே': 5, 'ஜூன்': 6, 'ஜூலை': 7, 'ஆகஸ்ட்': 8, 'செப்டம்பர்': 9, 'அக்டோபர்': 10,
                                 'நவம்பர்': 11, 'டிசம்பர்': 12}},
            'te_IN': {'deconstruct': r'^([0-9]+)\s+([^\s]+),\s+([0-9]+)', 'reassemble': '{2}-{1:0>2}-{0:0>2}', 'month': 1,
                      'months': {'జనవరి': 1, 'ఫిబ్రవరి': 2, 'మార్చి': 3, 'ఏప్రిల్': 4, 'మే': 5, 'జూన్': 6, 'జులై': 7, 'ఆగస్టు': 8, 'సెప్టెంబర్': 9, 'అక్టోబర్': 10,
                                 'నవంబర్': 11, 'డిసెంబర్': 12}},
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
        watchlist = re.search(r'<a[^>]* href="(([^"]+)?/watchlist/)[^"]*"[^>]*>(.*?)</a>', home)
        if None is not watchlist:
            self._catalog['root']['Watchlist'] = {'title': watchlist.group(3), 'lazyLoadURL': self._g.BaseUrl + watchlist.group(1)}

        # PrimeVideo.com top navigation menu
        home = re.search('<div id="av-nav-main-menu".*?<ul role="navigation"[^>]*>\s*(.*?)\s*</ul>', home)
        if None is home:
            self._g.dialog.notification('PrimeVideo error', 'Unable to find the main primevideo.com navigation section', xbmcgui.NOTIFICATION_ERROR)
            Log('Unable to find the main primevideo.com navigation section', Log.ERROR)
            return False
        for item in re.findall('<li[^>]*>\s*(.*?)\s*</li>', home.group(1)):
            item = re.search('<a href="([^"]+)"[^>]*>\s*(.*?)\s*</a>', item)
            if None is not re.match(r'(/region/[^/]+)?/storefront/home/', item.group(1)):
                continue
            # Remove react comments
            title = re.sub('^<!--\s*[^>]+\s*-->', '', re.sub('<!--\s*[^>]+\s*-->$', '', item.group(2)))
            self._catalog['root'][title] = {'title': title, 'lazyLoadURL': self._g.BaseUrl + item.group(1) + '?_encoding=UTF8'}
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
            xbmcplugin.addDirectoryItem(self._g.pluginhandle, '{0}?mode=PrimeVideo_Browse&path=root{1}SwitchUser'.format(self._g.pluginid, self._separator), li, isFolder=False)
        if ('root' + self._separator + 'SwitchUser') == path:
            if switchUser():
                self.BuildRoot()
            return

        from urllib import quote_plus, unquote

        node = self._catalog
        nodeName = None
        for n in [unquote(p) for p in path.split(self._separator)]:
            nodeName = n
            node = node[n]

        if (nodeName in self._videodata) and ('metadata' in self._videodata[nodeName]) and ('video' in self._videodata[nodeName]['metadata']):
            ''' Start the playback if on a video leaf '''
            PlayVideo(self._videodata[nodeName]['metadata']['video'], self._videodata[nodeName]['metadata']['asin'], '', 0)
            return

        if (None is not node) and ('lazyLoadURL' in node):
            self._LazyLoad(node, nodeName)

        if None is node:
            self._g.dialog.notification('General error', 'Something went terribly wrong…', xbmcgui.NOTIFICATION_ERROR)
            return

        folderType = 0 if 'root' == path else 1
        for key in node:
            if key in ['metadata', 'ref', 'title', 'verb', 'children', 'parent']:
                continue
            url = '{0}?mode='.format(self._g.pluginid)
            urlPath = ''
            entry = node[key] if key not in self._videodata else self._videodata[key]

            # Skip items that are out of catalog
            if ('metadata' in entry) and ('unavailable' in entry['metadata']):
                continue

            # Can we refresh the cache on this item?
            bCanRefresh = ('ref' in node[key]) or ('lazyLoadURL' in node[key])

            if 'verb' in entry:
                url += entry['verb']
            else:
                url += 'PrimeVideo_Browse&path='
                urlPath += '{0}{1}{2}'.format(path, self._separator, key)
                # Squash season number folder when only one season is available
                if ('children' in entry) and (1 == len(entry['children'])):
                    child = entry['children'][0]
                    urlPath += '{0}{1}'.format(self._separator, child)
                    # Propagate refresh if we squashed the season
                    bCanRefresh = bCanRefresh or (('ref' in node[key][child]) or ('lazyLoadURL' in node[key][child]))
            if (0 < len(urlPath)):
                url += self._separator.join([quote_plus(x.encode('utf-8')) for x in urlPath.split(self._separator)])
            Log('Encoded PrimeVideo URL: {0}'.format(url), Log.DEBUG)
            title = entry['title'] if 'title' in entry else nodeName
            item = xbmcgui.ListItem(title)

            if bCanRefresh:
                item.addContextMenuItems([('Refresh', 'RunPlugin({0}?mode=PrimeVideo_Refresh&path={1})'.format(self._g.pluginid, re.sub(r'^.*&path=', '', url)))])
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
            # If it's a video leaf without an actual video, something went wrong with Amazon servers, just hide it
            if (not folder) or (4 > folderType):
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

    def Refresh(self, path):
        """ Provides cache refresh functionality """

        from urllib import unquote
        path = [unquote(p) for p in path.decode('utf-8').split(self._separator)]

        # Traverse the catalog cache
        node = self._catalog
        name = path.pop()  # Remove the leaf to stop early
        for n in path:
            node = node[n]

        # Safety check, don't refresh if a video leaf or not yet loaded
        if ('lazyLoadURL' in node[name]) or ('ref' not in node[name]):
            return

        # Reset the basic metadata and reload
        node[name] = {'title': node[name]['title'], 'lazyLoadURL': node[name]['ref']}
        self._LazyLoad(node[name], name, True)

    def _LazyLoad(self, obj, objName, bCacheRefresh=False):
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

                for t in [(r'\s+-\s*([^&])', r' – \1'),  # Convert dash from small to medium where needed
                          (r'\s*-\s+([^&])', r' – \1'),  # Convert dash from small to medium where needed
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
                Log('Unable to parse date "{0}" with language "{1}"{2}'.format(datestr, lang, '' if 'en_US' != lang else ': trying english'), Log.WARNING)
                if 'en_US' == lang:
                    return datestr
                # Sometimes Amazon returns english everything, let's try to figure out if this is the case
                lang = 'en_US'
                p = re.search(self._dateParserData[lang]['deconstruct'], datestr)
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

        def MultiRegexParsing(content, o):
            """ Takes a dictionary of regex and applies them to content, returning a filtered dictionary of results """

            for i in o:
                o[i] = re.search(o[i], content)
                if None is not o[i]:
                    o[i] = o[i].groups()
                    o[i] = Unescape(o[i][0]) if 1 == len(o[i]) else list(o[i])
                    if 'image' == i:
                        o[i] = MaxSize(o[i])
                    elif 'season' == i:
                        o[i] = {'locale': Unescape(o[i][0]), 'season': int(o[i][1]), 'format': Unescape('{0} {1}'.format(o[i][0], o[i][1]))}
                    elif ('episode' == i) or ('year' == i):
                        o[i] = int(o[i])
                    elif ('cast' == i) or ('genre' == i) or ('director' == i):
                        o[i] = re.sub(r'\s*</?(a|span|input|label.*?/label)\s*[^>]*>\s*', '', o[i][1])  # Strip everything useless
                        o[i] = re.split(r'\s*[,;]\s*', o[i])
                        # Cast is always to be sent as a list, single string is only required/preferred for Genre and Director
                        if ('cast' != i) and (1 == len(o[i])):
                            o[i] = o[i][0]
                    elif 'rating' == i:
                        o[i] = int(o[i][0]) + (int(o[i][1]) / 10.0)
                    elif 'premiered' == i:
                        o[i] = DelocalizeDate(amzLang, o[i])
            return o

        if 'lazyLoadURL' not in obj:
            return
        requestURLs = [obj['lazyLoadURL']]

        amzLang = None
        if None is not requestURLs[0]:
            # Fine the locale amazon's using
            cj = MechanizeLogin()
            if cj:
                amzLang = cj.get('lc-main-av', domain='.primevideo.com', path='/')
        amzLang = amzLang if amzLang else 'en_US'

        bUpdatedVideoData = False  # Whether or not the pvData has been updated

        while 0 < len(requestURLs):
            # We linearize and avoid recursion through requestURLs differentiation
            # - String: request url, the obj parameter is the root object
            # - Tuple(URL, object, urn, [bFromWidow]): request url, object reference, URN, and if it's from a widow carousel
            if not isinstance(requestURLs[0], tuple):
                requestURL = requestURLs[0]
                o = obj
                refUrn = objName
                bFromWidowCarousel = False
            else:
                requestURL = requestURLs[0][0]
                o = requestURLs[0][1]
                refUrn = requestURLs[0][2]
                bFromWidowCarousel = 3 < len(requestURLs[0])
            del requestURLs[0]

            # If we're coming from a widowed carousel we could exploit the cached video data to further improve loading times
            if (not bCacheRefresh) and bFromWidowCarousel and (refUrn in self._videodata):
                if ('unavailable' not in self._videodata[refUrn]['metadata']) and ('season' == self._videodata[refUrn]['metadata']['videometa']['mediatype']):
                    o[self._videodata[refUrn]['parent']] = self._videodata[self._videodata[refUrn]['parent']]
                    o = o[self._videodata[refUrn]['parent']]
                o[refUrn] = self._videodata[refUrn]
                if ('children' in self._videodata[refUrn]) and (0 < len(self._videodata[refUrn]['children'])):
                    o[refUrn] = {k: {} for k in self._videodata[refUrn]['children']}
                continue

            couldNotParse = False
            try:
                cnt = getURL(requestURL, silent=False, useCookie=True, rjson=False)
                if (0 < len(cnt)) and ('lazyLoadURL' in o):
                    o['ref'] = o['lazyLoadURL']
                    del o['lazyLoadURL']
            except:
                couldNotParse = True
            if couldNotParse or (0 == len(cnt)):
                self._g.dialog.notification(getString(30251), requestURL, xbmcgui.NOTIFICATION_ERROR)
                Log('Unable to fetch the url: {0}'.format(requestURL), Log.ERROR)
                continue

            for t in [('\\\\n', '\n'), ('\\n', '\n'), ('\\\\"', '"'), (r'^\s+', '')]:
                cnt = re.sub(t[0], t[1], cnt, flags=re.DOTALL)
            if None is not re.search('<div id="Storefront">', cnt):
                ''' Categories list '''
                from BeautifulSoup import BeautifulSoup
                soup = BeautifulSoup(cnt, convertEntities=BeautifulSoup.HTML_ENTITIES)

                # Pagination
                try:
                    requestURLs.append(self._g.BaseUrl + Unescape(soup.find("a", "tst-pagination")['href']))
                except:
                    pass

                # Categories
                for section in soup.findAll('div', 'tst-collection'):

                    # We skip carousels without a name (such as the giant one in the homepage)
                    try:
                        title = Unescape(section.find('h2').next.strip())
                    except:
                        continue

                    # Widow carousels have no exploration links in the header
                    o[title] = {'title': title}
                    try:
                        link = self._g.BaseUrl + Unescape(section.find('a', 'tst-see-more')['href'])
                    except:
                        ''' The carousel has no explore link, we need to parse what we can from the carousel itself '''
                        for entry in section.findAll('li'):
                            e = entry.find('div', 'DigitalVideoWebNodeStorefront_TextOverlay__OverlayedTextWrapper')
                            link = self._g.BaseUrl + Unescape(entry.find('a')['href'])
                            if None is not e:
                                # Genres/Categories
                                e = e.next.strip()
                                image = MaxSize(Unescape(entry.find('img')['src']))
                                if None is not re.search(r'/search/', link):
                                    o[title][e] = {'metadata': {'artmeta': {'thumb': image, 'poster': image}}, 'lazyLoadURL': link, 'title': e}
                            else:
                                # Widow carousel with movies/TV series. Most information has been stripped away from
                                # the carousel, so we can't do more than just forwarding a request
                                requestURLs.append((link, o[title], ExtractURN(link), True))
                    else:
                        ''' The carousel has explore link '''
                        NotifyUser(getString(30253).format(title))
                        o[title]['lazyLoadURL'] = link
            else:
                if None is not re.search(r'<div\s+[^>]*(id="Watchlist"|class="DVWebNode-watchlist-wrapper")[^>]*>', cnt, flags=re.DOTALL):
                    ''' Watchlist '''
                    if None is not re.search(r'<div\s+[^>]*id="Watchlist"[^>]*>', cnt, flags=re.DOTALL):
                        ''' Old watchlist, possibly (about to be) deprecated. Leaving it in because I stopped trusting anyone '''
                        if ('Watchlist' == objName):
                            for entry in re.findall(r'<a href="([^"]+/)[^"/]+" class="DigitalVideoUI_TabHeading__tab[^"]*">(.*?)</a>', cnt, flags=re.DOTALL):
                                o[Unescape(entry[1])] = {'title': Unescape(entry[1]), 'lazyLoadURL': self._g.BaseUrl + entry[0] + '?sort=DATE_ADDED_DESC'}
                            continue
                        for entry in re.findall(r'<div[^>]* class="[^"]*DigitalVideoWebNodeLists_Item__item[^"]*"[^>]*>\s*<a href="((/region/[^/]+)?/detail/[^/]+/)[^"]*"[^>]*>*.*?'
                                                r'<img src="([^"]+)".*?"[^"]*DigitalVideoWebNodeLists_Item__coreTitle[^"]*"[^>]*>\s*(.*?)\s*</', cnt):
                            requestURLs.append((self._g.BaseUrl + entry[0], o, ExtractURN(entry[0]), True))
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
                    else:
                        ''' New type of watchlist nobody asked for '''
                        if ('Watchlist' == objName):
                            entries = re.search(r'<div class="DVWebNode-watchlist-wrapper">(<div[^>]*>)<div[^>]*>.*?</div><div[^>]*><div[^>]*>'
                                                r'((<a href="[^"]+"[^>]*>[^<]+</a>)+)', cnt, flags=re.DOTALL).group(2)
                            for entry in re.findall(r'href="([^"]+)"[^>]*>(.*?)</a', entries, flags=re.DOTALL):
                                o[Unescape(entry[1])] = {'title': Unescape(entry[1]), 'lazyLoadURL': self._g.BaseUrl + entry[0]}
                            continue
                        for entry in re.findall(r'data-asin="amzn1\.dv\.[^>]+>.*?href="([^"]+)"[^>]*>\s*<img\s*src="[^"]+"\s*alt="[^"]+"', cnt, flags=re.DOTALL):
                            requestURLs.append((self._g.BaseUrl + entry, o, ExtractURN(entry), True))
                        pagination = re.search(r'href="([^"]+)"\s*class="[^"]*u-pagination', cnt, flags=re.DOTALL)
                        if None is not pagination:
                            requestURLs.append((self._g.BaseUrl + pagination.group(1), o, refUrn))
                elif None is not re.search('<div class="av-dp-container">', cnt, flags=re.DOTALL):
                    ''' Movie/series page '''
                    # Are we getting the old or new version of the page?
                    bNewVersion = None is not re.search(r'<h1 [^>]*class="[^"]*DigitalVideoUI', cnt, flags=re.DOTALL)

                    # Find the biggest fanart available
                    bgimg = re.search(r'<div class="av-hero-background[^"]*"[^>]*url\(([^)]+)\)', cnt, flags=re.DOTALL)
                    if None is not bgimg:
                        bgimg = MaxSize(bgimg.group(1))

                    # Extract the global data
                    gres = MultiRegexParsing(re.search(r'<section\s+[^>]*class="av-detail-section"[^>]*>\s*(.*?)\s*</section>', cnt, flags=re.DOTALL).group(1), {
                        'cast': self._starringRex + r'\s*</dt>\s*<dd[^>]*>\s*(.*?)\s*</dd>',  # Starring
                        'director': self._directorRex + r'\s*</dt>\s*<dd[^>]*>\s*(.*?)\s*</dd>',  # Director
                        'genre': self._genresRex + r'\s*</dt>\s*<dd[^>]*>\s*(.*?)\s*</dd>',  # Genre
                        'mpaa': r'<span data-automation-id="' + (r'' if bNewVersion else r'maturity-') +
                                r'rating-badge"[^>]*>\s*(.*?)\s*</span>',  # Age rating
                        'plot': r'<div [^>]*data-automation-id="synopsis"[^>]*>\s*<div [^>]*>.*?<div [^>]*>\s*(.*?)\s*</div>'
                                if bNewVersion else r'<div data-automation-id="synopsis"[^>]*>[^<]*<p>\s*(.*?)\s*</p>',  # Synopsis
                        'rating': r'<span data-automation-id="imdb-rating-badge"[^>]*>\s*([0-9]+)[,.]([0-9]+)\s*</span>',  # IMDb rating
                        'year': r'<span data-automation-id="release-year-badge"[^>]*>\s*([0-9]+)\s*</span>',  # Year
                    })
                    # In case of widowed carousels, we might actually have no videodata
                    if refUrn not in self._videodata:
                        self._videodata[refUrn] = {'metadata': {'videometa': {}}, 'children': []}

                    results = re.search(r'<ol\s+[^>]*class="[^"]*av-episode-list[^"]*"[^>]*>\s*(.*?)\s*</ol>', cnt, flags=re.DOTALL)
                    if None is results:
                        ''' Standalone movie '''
                        if bFromWidowCarousel and (refUrn not in o):
                            o[refUrn] = {}
                        if bCacheRefresh or ('video' not in self._videodata[refUrn]['metadata']):
                            asin = re.search(r'"asin":"([^"]*)"', cnt, flags=re.DOTALL)
                            if None is asin:
                                self._videodata[refUrn]['metadata']['unavailable'] = True
                            else:
                                bUpdatedVideoData = True

                                meta = self._videodata[refUrn]['metadata']
                                if 'artmeta' not in meta:
                                    meta['artmeta'] = {}
                                if None is not bgimg:
                                    meta['artmeta']['fanart'] = bgimg

                                meta['asin'] = asin.group(1)
                                meta['video'] = ExtractURN(requestURL)

                                if 'mediatype' not in meta['videometa']:
                                    meta['videometa']['mediatype'] = 'movie'

                                # Insert movie information
                                for i in gres:
                                    if None is not gres[i]: meta['videometa'][i] = gres[i]

                                # Extract the runtime
                                success, gpr = getURLData('catalog/GetPlaybackResources', meta['asin'], useCookie=True, extra=True,
                                                          opt='&titleDecorationScheme=primary-content', dRes='CatalogMetadata')
                                if not success:
                                    gpr = None
                                else:
                                    if 'runtimeSeconds' in gpr['catalogMetadata']['catalog']:
                                        meta['runtime'] = gpr['catalogMetadata']['catalog']['runtimeSeconds']
                                    if 'thumb' not in meta['artmeta']:
                                        image = MaxSize(gpr['catalogMetadata']['images']['imageUrls']['title'])
                                        meta['artmeta']['thumb'] = image
                                        meta['artmeta']['poster'] = image
                                    if bCacheRefresh or ('title' not in self._videodata[refUrn]):
                                        self._videodata[refUrn]['title'] = gpr['catalogMetadata']['catalog']['title']
                                if 'title' in self._videodata[refUrn]:
                                    NotifyUser(getString(30253).format(self._videodata[refUrn]['title']))
                    else:
                        ''' Episode list '''
                        for entry in re.findall(r'<li[^>]*>\s*(.*?)\s*</li>', results.group(1), flags=re.DOTALL):
                            md = MultiRegexParsing(entry, {
                                # Episode data
                                'id': r'<a data-automation-id="ep-playback-[0-9]+"[^>]*data-ref="([^"]*)"',
                                'url': r'<a data-automation-id="ep-playback-[0-9]+"[^>]*data-ref="[^"]*"[^>]*data-title-id="[^"]*"[^>]*href="([^"]*)"',
                                'asin': r'\s+data-title-id="\s*([^"]+?)\s*"',
                                'image': r'<div class="av-bgimg__div"[^>]*url\(([^)]+)\)',
                                'title': r'<span class="av-play-title-text">\s*(.*?)\s*</span>',
                            })
                            res = MultiRegexParsing(entry, {
                                'episode': r'id="ep-playback-([0-9]+)"',  # Episode number
                                'mpaa': r'<span data-automation-id="ep-amr-badge-[0-9]+"[^>]*>\s*(.*?)\s*</span>',  # Age rating
                                'plot': r'<p data-automation-id="ep-synopsis-[0-9]+"[^>]*>\s*(.*?)\s*</p>',  # Synopsis
                                'premiered': r'<span data-automation-id="ep-air-date-badge-[0-9]+"[^>]*>\s*(.*?)\s*</span>',  # Original air date
                            })
                            if (None is md['url']) or (None is md['title']):
                                ''' Some episodes might be not playable until a later date or just N/A, although listed '''
                                continue
                            meta = {'artmeta': {'thumb': md['image'], 'poster': md['image'], 'fanart': bgimg},
                                    'videometa': {'mediatype': 'episode'}, 'id': md['id'], 'asin': md['asin'], 'videoURL': md['url']}
                            if None is not re.match(r'/[^/]', meta['videoURL']):
                                meta['videoURL'] = self._g.BaseUrl + meta['videoURL']
                            meta['video'] = ExtractURN(meta['videoURL'])
                            eid = meta['video']

                            if bCacheRefresh or (
                                (eid not in self._videodata) or
                                ('metadata' not in self._videodata[eid]) or
                                ('videometa' not in self._videodata[eid]['metadata']) or
                                (0 == len(self._videodata[eid]['metadata']['videometa']))
                            ):
                                # Extract the runtime
                                success, gpr = getURLData('catalog/GetPlaybackResources', md['asin'], useCookie=True, extra=True,
                                                          opt='&titleDecorationScheme=primary-content', dRes='CatalogMetadata')
                                if not success:
                                    gpr = None
                                else:
                                    if 'runtimeSeconds' in gpr['catalogMetadata']['catalog']:
                                        meta['runtime'] = gpr['catalogMetadata']['catalog']['runtimeSeconds']

                                # If we come from a widowed carousel, we need to build the ancestry
                                if bFromWidowCarousel:
                                    for d in gpr['catalogMetadata']['family']['tvAncestors']:
                                        if 'SHOW' == d['catalog']['type']:
                                            showId = d['catalog']['id']
                                            if (showId not in self._videodata):
                                                self._videodata[showId] = {'title': d['catalog']['title'], 'children': []}
                                    if 'season' not in self._videodata[refUrn]['metadata']['videometa']:
                                        for d in gpr['catalogMetadata']['family']['tvAncestors']:
                                            if 'SEASON' == d['catalog']['type']:
                                                self._videodata[refUrn]['metadata']['videometa']['season'] = int(d['catalog']['seasonNumber'])
                                                self._videodata[refUrn]['metadata']['videometa']['mediatype'] = 'season'
                                    if 'artmeta' not in self._videodata[refUrn]['metadata']:
                                        thumbnail = MaxSize(Unescape(gpr['catalogMetadata']['images']['imageUrls']['title']))
                                        self._videodata[refUrn]['metadata']['artmeta'] = {'thumb': thumbnail, 'poster': thumbnail, 'fanart': bgimg}
                                    if 'title' not in self._videodata[refUrn]:
                                        bSingle = None is not re.search(r'(av-season-single|DigitalVideoWebNodeDetail_seasons__single)', cnt, flags=re.DOTALL)
                                        self._videodata[refUrn]['title'] = Unescape(re.search([
                                            r'<span class="av-season-single av-badge-text">\s*(.*?)\s*</a>',  # Old, single
                                            r'<a class="av-droplist--selected"[^>]*>\s*(.*?)\s*</a>',  # Old, multi
                                            r'<span class="[^"]*DigitalVideoWebNodeDetail_seasons__single[^"]*"[^>]*>\s*<span[^>]*>\s*(.*?)\s*</span>',  # New, single
                                            r'<div class="[^*]*dv-node-dp-seasons.*?<label[^>]*>\s*<span[^>]*>\s*(.*?)\s*</span>\s*</label>',  # New, multi
                                        ][(2 if bNewVersion else 0) + (0 if bSingle else 1)], cnt, flags=re.DOTALL).group(1))
                                    if 'parent' not in self._videodata[refUrn]:
                                        self._videodata[refUrn]['parent'] = showId
                                        if refUrn not in self._videodata[showId]['children']:
                                            self._videodata[showId]['children'].append(refUrn)

                                # Insert series information
                                for i in gres:
                                    if None is not gres[i]:
                                        meta['videometa'][i] = gres[i]
                                        if bCacheRefresh or (i not in self._videodata[refUrn]['metadata']['videometa']):
                                            self._videodata[refUrn]['metadata']['videometa'][i] = gres[i]

                                # Insert episode specific information
                                for i in res:
                                    if None is not res[i]:
                                        meta['videometa'][i] = res[i]

                                if ('season' not in meta['videometa']) and ('season' in self._videodata[refUrn]['metadata']['videometa']):
                                    meta['videometa']['season'] = self._videodata[refUrn]['metadata']['videometa']['season']

                                # Episode title cleanup
                                if None is not re.match(r'[0-9]+[.]\s*', md['title']):
                                    ''' Strip the episode number '''
                                    md['title'] = re.sub(r'^[0-9]+.\s*', '', md['title'])
                                else:
                                    ''' Probably an extra trailer or something, remove episode information '''
                                    del meta['videometa']['season']
                                    del meta['videometa']['episode']

                                bUpdatedVideoData = True
                                self._videodata[eid] = {'metadata': meta, 'title': md['title'], 'parent': refUrn}
                                NotifyUser(getString(30253).format(md['title']))

                            if bFromWidowCarousel:
                                bFromWidowCarousel = False  # Initialisations done (or about to be), avoid nesting
                                o[self._videodata[refUrn]['parent']] = self._videodata[self._videodata[refUrn]['parent']]
                                o[self._videodata[refUrn]['parent']][refUrn] = self._videodata[refUrn]
                                o = o[self._videodata[refUrn]['parent']][refUrn]
                            if eid not in o:
                                o[eid] = {}
                            if (refUrn in self._videodata) and ('children' in self._videodata[refUrn]) and (eid not in self._videodata[refUrn]['children']):
                                bUpdatedVideoData = True
                                self._videodata[refUrn]['children'].append(eid)
                else:
                    ''' Movie and series list '''
                    # Are we getting the old or new version of the list?
                    bNewVersion = None is re.search(r'<li class="av-result-card">', cnt, flags=re.DOTALL)
                    for entry in re.findall(r'<div class="[^"]*dvui-beardContainer[^"]*">\s*(.*?)\s*</form>\s*</div>\s*</div>\s*</div>'
                                            if bNewVersion else r'<li class="av-result-card">\s*(.*?)\s*</li>',
                                            cnt, flags=re.DOTALL):
                        res = MultiRegexParsing(entry, {
                            'asin': r'\s+data-asin="\s*([^"]+?)\s*"',
                            'image': r'<a [^>]+><img\s+[^>]*src="([^"]+)"',
                            'link': r'<a href="([^"]+)"><img',
                            'season': (r'<span>\s*' if bNewVersion else r'<span class="av-result-card-season">\s*') + self._seasonRex + r'\s+([0-9]+)\s*</span>',
                            'title': r'<a class="' + (r'av-beard-title-link' if bNewVersion else r'av-result-card-title') + r'"[^>]*>\s*(.*?)\s*</a>',
                        })
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
                            if bCacheRefresh or ((urn not in self._videodata) or ('metadata' not in self._videodata[urn]) or ('video' not in self._videodata[urn]['metadata'])):
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
                                if id not in self._videodata:
                                    self._videodata[id] = {'title': res['title'], 'children': []}
                            if (sid in self._videodata) and ('children' in self._videodata[sid]) and (0 < len(self._videodata[sid]['children'])):
                                o[id][sid] = {k: {} for k in self._videodata[sid]['children']}
                            else:
                                # Save tree information if id is a URN and not a title name
                                if (id is not res['title']) and (sid not in self._videodata[id]['children']):
                                        self._videodata[id]['children'].append(sid)
                                meta['videometa']['season'] = res['season']['season']
                                o[id][sid] = {'lazyLoadURL': res['link']}
                                bUpdatedVideoData = True
                                self._videodata[sid]['title'] = res['season']['format']
                                self._videodata[sid]['metadata'] = meta

                    # Next page
                    pagination = re.search(
                        r'<li\s+[^>]*class="[^"]*av-pagination-current-page[^"]*"[^>]*>.*?</li>\s*<li\s+[^>]*class="av-pagination[^>]*>\s*(.*?)\s*</li>',
                        cnt, flags=re.DOTALL)
                    if None is not pagination:
                        nru = Unescape(re.search(r'href="([^"]+)"', pagination.group(1), flags=re.DOTALL).group(1))
                        if None is not re.match(r'/[^/]', nru):
                            nru = self._g.BaseUrl + nru
                        requestURLs.append(nru)
            if 0 < len(requestURLs):
                NotifyUser(getString(30252))

        # Flush catalog and data
        self._flush(bCacheRefresh or bUpdatedVideoData)
