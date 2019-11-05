#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from collections import OrderedDict
import json
import pickle
import re
import sys
import time
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
    _videodata = {'urn2gti': {}, 'parents': {}}  # Video data cache
    _catalogCache = None  # Catalog cache file name
    _videodataCache = None  # Video data cache file name
    _separator = '/'  # Virtual path separator

    def __init__(self, globalsInstance, settingsInstance):
        self._g = globalsInstance
        self._s = settingsInstance
        self._dateParserData = {
            """ Data for date string deconstruction and reassembly

                Date references:
                https://www.primevideo.com/detail/0LCQSTWDMN9V770DG2DKXY3GVF/  09 10 11 12 01 02 03 04 05
                https://www.primevideo.com/detail/0ND5POOAYD6A4THTH7C1TD3TYE/  06 07 08 09

                Languages: https://www.primevideo.com/settings/language/
            """
            'da_DK': {'deconstruct': r'^([0-9]+)\.?\s+([^\s]+)\s+([0-9]+)', 'reassemble': '{2}-{1:0>2}-{0:0>2}', 'month': 1,
                      'months': {'januar': 1, 'februar': 2, 'marts': 3, 'april': 4, 'maj': 5, 'juni': 6, 'juli': 7, 'august': 8, 'september': 9, 'oktober': 10,
                                 'november': 11, 'december': 12}},
            'de_DE': {'deconstruct': r'^([0-9]+)\.?\s+([^\s]+)\s+([0-9]+)', 'reassemble': '{2}-{1:0>2}-{0:0>2}', 'month': 1,
                      'months': {'januar': 1, 'februar': 2, 'märz': 3, 'april': 4, 'mai': 5, 'juni': 6, 'juli': 7, 'august': 8, 'september': 9, 'oktober': 10,
                                 'november': 11, 'dezember': 12}},
            'en_US': {'deconstruct': r'^([^\s]+)\s+([0-9]+),?\s+([0-9]+)', 'reassemble': '{2}-{0:0>2}-{1:0>2}', 'month': 0,
                      'months': {'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6, 'july': 7, 'august': 8, 'september': 9, 'october': 10,
                                 'november': 11, 'december': 12}},
            'es_ES': {'deconstruct': r'^([0-9]+)\s+de\s+([^\s]+),?\s+de\s+([0-9]+)', 'reassemble': '{2}-{1:0>2}-{0:0>2}', 'month': 1,
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
            'nb_NO': {'deconstruct': r'^([0-9]+)\.?\s+([^\s]+)\s+([0-9]+)', 'reassemble': '{2}-{1:0>2}-{0:0>2}', 'month': 1,
                      'months': {'januar': 1, 'februar': 2, 'mars': 3, 'april': 4, 'mai': 5, 'juni': 6, 'juli': 7, 'august': 8, 'september': 9, 'oktober': 10,
                                 'november': 11, 'desember': 12}},
            'nl_NL': {'deconstruct': r'^([0-9]+)\s+([^\s]+)\s+([0-9]+)', 'reassemble': '{2}-{1:0>2}-{0:0>2}', 'month': 1,
                      'months': {'januari': 1, 'februari': 2, 'maart': 3, 'april': 4, 'mei': 5, 'juni': 6, 'juli': 7, 'augustus': 8, 'september': 9,
                                 'oktober': 10, 'november': 11, 'december': 12}},
            'pl_PL': {'deconstruct': r'^([0-9]+)\s+([^\s]+)\s+([0-9]+)', 'reassemble': '{2}-{1:0>2}-{0:0>2}', 'month': 1,
                      'months': {'stycznia': 1, 'lutego': 2, 'marca': 3, 'kwietnia': 4, 'maja': 5, 'czerwca': 6, 'lipca': 7, 'sierpnia': 8, 'września': 9,
                                 'października': 10, 'listopada': 11, 'grudnia': 12}},
            'pt_BR': {'deconstruct': r'^([0-9]+)\s+de\s+([^\s]+),?\s+de\s+([0-9]+)', 'reassemble': '{2}-{1:0>2}-{0:0>2}', 'month': 1,
                      'months': {'janeiro': 1, 'fevereiro': 2, 'março': 3, 'abril': 4, 'maio': 5, 'junho': 6, 'julho': 7, 'agosto': 8, 'setembro': 9, 'outubro': 10,
                                 'novembro': 11, 'dezembro': 12}},
            'sv_SE': {'deconstruct': r'^([0-9]+)\s+([^\s]+)\s+([0-9]+)', 'reassemble': '{2}-{1:0>2}-{0:0>2}', 'month': 1,
                      'months': {'januari': 1, 'februari': 2, 'mars': 3, 'april': 4, 'maj': 5, 'juni': 6, 'juli': 7, 'augusti': 8, 'september': 9, 'oktober': 10,
                                 'november': 11, 'december': 12}},
            'ta_IN': {'deconstruct': r'^([0-9]+)\s+([^\s]+),?\s+([0-9]+)', 'reassemble': '{2}-{1:0>2}-{0:0>2}', 'month': 1,
                      'months': {'ஜனவரி': 1, 'பிப்ரவரி': 2, 'மார்ச்': 3, 'ஏப்ரல்': 4, 'மே': 5, 'ஜூன்': 6, 'ஜூலை': 7, 'ஆகஸ்ட்': 8, 'செப்டம்பர்': 9,
                                 'அக்டோபர்': 10, 'நவம்பர்': 11, 'டிசம்பர்': 12}},
            'te_IN': {'deconstruct': r'^([0-9]+)\s+([^\s]+),?\s+([0-9]+)', 'reassemble': '{2}-{1:0>2}-{0:0>2}', 'month': 1,
                      'months': {'జనవరి': 1, 'ఫిబ్రవరి': 2, 'మార్చి': 3, 'ఏప్రిల్': 4, 'మే': 5, 'జూన్': 6, 'జులై': 7, 'ఆగస్టు': 8, 'సెప్టెంబర్': 9, 'అక్టోబర్': 10,
                                 'నవంబర్': 11, 'డిసెంబర్': 12}},
        }
        self._LoadCache()

    def _Flush(self, FlushVideoData=False):
        """ Cache catalog and video data """

        with open(self._catalogCache, 'wb+') as fp:
            pickle.dump(self._catalog, fp)
        if FlushVideoData:
            with open(self._videodataCache, 'w+') as fp:
                json.dump(self._videodata, fp)

    def _LoadCache(self):
        """ Load cached catalog and video data """

        from os.path import join as OSPJoin
        from xbmcvfs import exists, delete

        self._catalogCache = OSPJoin(self._g.DATA_PATH, 'PVCatalog{}.pvcp'.format(self._g.MarketID))
        self._videodataCache = OSPJoin(self._g.DATA_PATH, 'PVVideoData{}.pvdp'.format(self._g.MarketID))

        if exists(self._videodataCache):
            try:
                with open(self._videodataCache, 'r') as fp:
                    data = json.load(fp)
                if ('urn2gti' not in data) or ('parents' not in data):
                    raise Exception('Old, unsafe cache data')
                self._videodata = data
            except:
                Log('Removing corrupted cache file “{}”'.format(self._videodataCache), Log.DEBUG)
                delete(self._videodataCache)
                self._g.dialog.notification('Corrupted video cache', 'Unable to load the video cache data', xbmcgui.NOTIFICATION_ERROR)

        if exists(self._catalogCache):
            try:
                with open(self._catalogCache, 'rb') as fp:
                    cached = pickle.load(fp)
                if time.time() < cached['expiration']:
                    self._catalog = cached
            except:
                Log('Removing corrupted cache file “{}”'.format(self._catalogCache), Log.DEBUG)
                delete(self._catalogCache)
                self._g.dialog.notification('Corrupted catalog cache', 'Unable to load the catalog cache data', xbmcgui.NOTIFICATION_ERROR)

    def _BeautifyText(self, title):
        """ Correct stylistic errors in Amazon's titles """

        for t in [(r'\s+-\s*([^&])', r' – \1'),  # Convert dash from small to medium where needed
                  (r'\s*-\s+([^&])', r' – \1'),  # Convert dash from small to medium where needed
                  (r'^\s+', ''),  # Remove leading spaces
                  (r'\s+$', ''),  # Remove trailing spaces
                  (r' {2,}', ' '),  # Remove double spacing
                  (r'\.\.\.', '…')]:  # Replace triple dots with ellipsis
            title = re.sub(t[0], t[1], title)
        return title

    def _FQify(self, URL):
        """ Makes sure to provide correct fully qualified URLs """
        base = self._g.BaseUrl
        if '://' in URL:  # FQ
            return URL
        elif URL.startswith('//'):  # Specified domain, same schema
            return base.split(':')[0] + ':' + URL
        elif URL.startswith('/'):  # Relative URL
            return base + URL
        else:  # Hope and pray we never reach this ¯\_(ツ)_/¯
            return base + '/' + URL

    def _GrabJSON(self, url, bRaw=False):
        """ Extract JSON objects from HTMLs while keeping the API ones intact """

        def Unescape(text):
            """ Unescape various html/xml entities in dictionary values, courtesy of Fredrik Lundh """

            def fixup(m):
                """ Unescape entities except for double quotes, lest the JSON breaks """
                try:
                    from html.entities import name2codepoint
                except:
                    from htmlentitydefs import name2codepoint

                text = m.group(0)  # First group is the text to replace

                # Unescape if possible
                if text[:2] == "&#":
                    # character reference
                    try:
                        bHex = ("&#x" == text[:3])
                        char = int(text[3 if bHex else 2:-1], 16 if bHex else 10)
                        if 34 == char:
                            text = u'\\"'
                        else:
                            try:
                                text = unichr(char)
                            except NameError:
                                text = chr(char)
                    except ValueError:
                        pass
                else:
                    # named entity
                    char = text[1:-1]
                    if 'quot' == char:
                        text = u'\\"'
                    elif char in name2codepoint:
                        char = name2codepoint[char]
                        try:
                            text = unichr(char)
                        except NameError:
                            text = chr(char)
                return text

            text = re.sub('&#?\\w+;', fixup, text)
            try:
                text = text.encode('latin-1').decode('utf-8')
            except (UnicodeEncodeError, UnicodeDecodeError):
                pass

            return text

        def Merge(o, n):
            """ Merge JSON objects with multiple multi-level collisions """
            if (not n) or (o == n):  # Nothing to do
                return
            elif (type(n) == list) or (type(n) == set):  # Insert into list/set
                for item in n:
                    if item not in o:
                        if type(n) == list:
                            o.append(item)
                        else:
                            o.add(item)
            elif type(n) == dict:
                for k in list(n):  # list() instead of .keys() to avoid py3 iteration errors
                    if k not in o:
                        o[k] = n[k]  # Insert into dictionary
                    else:
                        Merge(o[k], n[k])  # Recurse
            else:
                Log('Collision detected during JSON objects merging, overwriting and praying', Log.WARNING)
                o = n

        def Prune(d):
            """ Prune some commonly found sensitive info from JSON response bodies """
            if not d:
                return

            l = d
            if isinstance(l, dict):
                for k in list(l):  # list() instead of .keys() to avoid py3 iteration errors
                    if k == 'strings':
                        l[k] = {s: l[k][s] for s in ['AVOD_DP_season_selector'] if s in l[k]}
                    if (not l[k]) or (k in ['context', 'params', 'playerConfig', 'refine']):
                        del l[k]
                l = d.values()
            for v in l:
                if isinstance(v, dict) or isinstance(v, list):
                    Prune(v)

        try:
            from urlparse import urlparse, parse_qs
            from urllib import urlencode
        except:
            from urllib.parse import urlparse, parse_qs, urlencode
        if url.startswith('/search/'):
            np = urlparse(url)
            qs = parse_qs(np.query)
            if 'from' in list(qs):  # list() instead of .keys() to avoid py3 iteration errors
                qs['startIndex'] = qs['from']
                del qs['from']
            np = np._replace(path='/gp/video/api' + np.path, query=urlencode([(k, v) for k, l in qs.items() for v in l]))
            url = np.geturl()

        r = getURL(self._FQify(url), silent=True, useCookie=True, rjson=False)
        if not r:
            return None
        try:
            r = r.strip()
            if '{' == r[0:1]:
                o = json.loads(Unescape(r))
                if not bRaw:
                    Prune(o)
                return o
        except:
            pass

        matches = re.findall(r'\s*(?:<script type="text/template">|state:)\s*({[^\n]+})\s*(?:,|</script>)\s*', r)
        if not matches:
            Log('No JSON objects found in the page', Log.ERROR)
            return None

        # Create a single object containing all the data from the multiple JSON objects in the page
        o = {}
        for m in matches:
            m = json.loads(Unescape(m))
            if 'props' not in m:
                m = m['widgets']['Storefront']
            else:
                m = m['props']

                if not bRaw:
                    # Prune useless/sensitive info
                    for k in list(m):  # list() instead of .keys() to avoid py3 iteration errors
                        if (not m[k]) or (k in ['copyright', 'links', 'logo', 'params', 'playerConfig', 'refine']):
                            del m[k]
                    if 'state' in m:
                        st = m['state']
                        for k in list(st):  # list() instead of .keys() to avoid py3 iteration errors
                            if not st[k]:
                                del st[k]
                            elif k in ['features', 'customerPreferences']:
                                del st[k]

            # Prune sensitive context info and merge into o
            if not bRaw:
                Prune(m)
            Merge(o, m)

        return o if o else None

    def _TraverseCatalog(self, path, bRefresh=False):
        """ Extract current node, grandparent node and their names """

        try:
            from urllib.parse import unquote_plus
        except:
            from urllib import unquote_plus

        # Fix the unquote_plus problem with unicode_literals by encoding to latin-1 (byte string) and then decoding
        pathList = [unquote_plus(p).encode('latin-1').decode('utf-8') for p in path.split(self._separator)]

        if 0 == len(self._catalog):
            self.BuildRoot()

        # Traverse
        node = self._catalog
        pathLen = len(pathList)
        for i in range(0, pathLen):
            nodeName = pathList[i]

            # Stop one short while refreshing, due to python mutability reasons
            if bRefresh and (i == (pathLen - 1)):
                break

            if nodeName not in node:
                self._g.dialog.notification('Catalog error', 'Catalog path not available…', xbmcgui.NOTIFICATION_ERROR)
                return (None, None)
            elif 'lazyLoadURL' in node[nodeName]:
                self._LazyLoad(node[nodeName], pathList[0:1 + i])
            node = node[nodeName]

        return (node, pathList)

    def BrowseRoot(self):
        """ Build and load the root PrimeVideo menu """

        if 0 == len(self._catalog):
            ''' Build the root catalog '''
            if not self.BuildRoot():
                return
        self.Browse('root')

    def BuildRoot(self):
        """ Parse the top menu on primevideo.com and build the root catalog """

        home = self._GrabJSON(self._g.BaseUrl)
        if not home:
            return False
        self._catalog['root'] = OrderedDict()

        # Insert the watchlist
        try:
            watchlist = next((x for x in home['yourAccount']['links'] if '/watchlist/' in x['href']), None)
            self._catalog['root']['Watchlist'] = {'title': self._BeautifyText(watchlist['text']), 'lazyLoadURL': watchlist['href']}
        except:
            Log('Watchlist link not found', Log.ERROR)

        # Insert the main sections, in order
        try:
            for link in home['mainMenu']['links']:
                self._catalog['root'][link['text']] = {'title': self._BeautifyText(link['text']), 'lazyLoadURL': link['href']}
                if '/home/' in link['href']:
                    self._catalog['root'][link['text']]['lazyLoadData'] = home
        except:
            self._g.dialog.notification('PrimeVideo error', 'Unable to find the navigation menu for primevideo.com', xbmcgui.NOTIFICATION_ERROR)
            Log('Unable to parse the navigation menu for primevideo.com', Log.ERROR)
            return False

        # Insert the searching mechanism
        try:
            sfa = home['searchBar']['searchFormAction']
            # Build the query parametrization
            query = ''
            if 'query' in sfa:
                query += '&'.join(['{}={}'.format(k, v) for k, v in sfa['query'].items()])
            query = query if not query else query + '&'
            self._catalog['root']['Search'] = {
                'title': self._BeautifyText(home['searchBar']['searchFormPlaceholder']),
                'verb': 'pv/search/',
                'endpoint': '{}?{}phrase={{}}'.format(sfa['partialURL'], query)
            }
        except:
            Log('Search functionality not found', Log.ERROR)

        # Set the expiration in 11 hours and flush to disk
        self._catalog['expiration'] = 39600 + int(time.time())
        self._Flush()

        return True

    def Browse(self, path, forceSort=None):
        """ Display and navigate the menu for PrimeVideo users """

        # Add multiuser menu if needed
        if (self._s.multiuser) and ('root' == path) and (1 < len(loadUsers())):
            li = xbmcgui.ListItem(getString(30134).format(loadUser('name')))
            li.addContextMenuItems(self._g.CONTEXTMENU_MULTIUSER)
            xbmcplugin.addDirectoryItem(self._g.pluginhandle, '{}pv/browse/root{}SwitchUser'.format(self._g.pluginid, self._separator), li, isFolder=False)
        if ('root' + self._separator + 'SwitchUser') == path:
            if switchUser():
                self.BuildRoot()
            return

        try:
            from urllib.parse import quote_plus
        except ImportError:
            from urllib import quote_plus

        node, breadcrumb = self._TraverseCatalog(path)
        if None is node:
            return

        # Populate children list with empty references
        nodeName = breadcrumb[-1]
        if (nodeName in self._videodata) and ('children' in self._videodata[nodeName]):
            for c in self._videodata[nodeName]['children']:
                if c not in node:
                    node[c] = {}

        folderType = 0 if 'root' == path else 1
        metaKeys = ['ref', 'verb', 'title', 'metadata', 'parent', 'siblings', 'children']
        nodeKeys = [k for k in node if k not in metaKeys]
        i = 0
        while i < len(nodeKeys):
            key = nodeKeys[i]
            i += 1
            url = self._g.pluginid
            entry = node[key] if key not in self._videodata else self._videodata[key]
            bIsVideo = False
            try: bIsVideo = self._videodata[key]['metadata']['videometa']['mediatype'] in ['episode', 'movie']
            except: pass
            """
            # Skip items that are out of catalog
            if ('metadata' in entry):
                continue

            try:
                bSeason = 'season' == self._videodata[key]['metadata']['videometa']['mediatype']

                "" "
                # Load series upon entering the show directory
                if bSeason and ('lazyLoadURL' in node[key]):
                    self._LazyLoad(node[key], key /*breadcrumbs*/)
                    # Due to python mutability shenanigans we need to manually alter the nodes
                    # instead of waiting for changes to propagate
                    for ka in [k for k in ancestorNode[ancestorName][nodeName] if k not in metaKeys]:
                        if ka not in nodeKeys:
                            nodeKeys.append(ka)
                        if ka not in node:
                            node[ka] = ancestorNode[ancestorName][nodeName][ka]
                    for ka in [k for k in node if k not in metaKeys]:
                        if ka not in ancestorNode[ancestorName][nodeName]:
                            ancestorNode[ancestorName][nodeName][ka] = node[ka]
                    self._Flush()
                "" "

                # If the series is squashable override the seasons list with the episodes list
                if 1 == len(nodeKeys):
                    node = node[key]
                    i = 0
                    nodeKeys = [k for k in node if k not in metaKeys]
                    if (0 == len(nodeKeys)) and (key in self._videodata) and ('children' in self._videodata[key]):
                        for c in self._videodata[key]['children']:
                            nodeKeys.append(c)
                            if c not in node:
                                node[c] = {}
                    continue
            except KeyError:
                pass
            """

            # Can we refresh the cache on this/these item(s)?
            bCanRefresh = ('ref' in node[key]) or ('lazyLoadURL' in node[key]) or ((key in self._videodata) and ('ref' in self._videodata[key]))
            if ('children' in entry) and (0 < len(entry['children'])):
                bCanRefresh = bCanRefresh or (0 < len([k for k in entry['children'] if (k in self._videodata) and ('ref' in self._videodata[k])]))

            refreshPath = '{}{}{}'.format(path, self._separator, quote_plus(key.encode('utf-8')))
            if bIsVideo:
                url += '?mode=PlayVideo&name={}&asin={}'.format(self._videodata[key]['metadata']['compactGTI'], key)
            elif 'verb' in entry:
                url += entry['verb']
                refreshPath = ''
            else:
                url += 'pv/browse/' + refreshPath
            # Log('Encoded PrimeVideo URL: {}'.format(url), Log.DEBUG)
            title = entry['title'] if 'title' in entry else nodeName
            item = xbmcgui.ListItem(title)

            if bCanRefresh and (0 < len(refreshPath)):
                # Log('Encoded PrimeVideo refresh URL: pv/refresh/{}'.format(refreshPath), Log.DEBUG)
                item.addContextMenuItems([('Refresh', 'RunPlugin({}pv/refresh/{})'.format(self._g.pluginid, refreshPath))])

            folder = True
            """
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
            """

            if 'metadata' in entry:
                m = entry['metadata']
                if 'artmeta' in m:
                    item.setArt(m['artmeta'])
                if 'videometa' in m:
                    # https://codedocs.xyz/xbmc/xbmc/group__python__xbmcgui__listitem.html#ga0b71166869bda87ad744942888fb5f14
                    item.setInfo('video', m['videometa'])
                    try:
                        folderType = {'movie': 5, 'episode': 4, 'tvshow': 2, 'season': 3}[m['videometa']['mediatype']]
                    except:
                        folderType = 5  # Default to movie

                    if bIsVideo:
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

    def Search(self):
        """ Provide search functionality for PrimeVideo """

        searchString = self._g.dialog.input(getString(24121)).strip(' \t\n\r')
        if 0 == len(searchString):
            xbmcplugin.endOfDirectory(self._g.pluginhandle, succeeded=False)
            return
        Log('Searching "{}"…'.format(searchString), Log.INFO)
        self._catalog['search'] = OrderedDict([('lazyLoadURL', self._catalog['root']['Search']['endpoint'].format(searchString))])
        self.Browse('search', xbmcplugin.SORT_METHOD_NONE)

    def Refresh(self, path):
        """ Provides cache refresh functionality """

        refreshes = []
        node, breadcrumb = self._TraverseCatalog(path, True)
        if None is node:
            return

        # Only refresh if previously loaded. If not loaded, and specifically asked, perform a full (lazy) loading
        if 'lazyLoadURL' in node[nodeName]:
            refreshes.append((node[nodeName], nodeName, False, None))
        else:
            bShow = False
            if 'ref' in node[nodeName]:  # ref's in the cache already
                Log('Refreshing element in the cache: {}'.format(nodeName), Log.DEBUG)
                targetURL = node[nodeName]['ref']
            elif 'ref' in self._videodata[nodeName]:  # Movie or Season
                Log('Refreshing element: {}'.format(nodeName), Log.DEBUG)
                targetURL = self._videodata[nodeName]['ref']
            else:  # Show
                Log('Refreshing Show: {}'.format(nodeName), Log.DEBUG)
                bShow = True
                for season in [k for k in self._videodata[nodeName]['children'] if (k in self._videodata) and ('ref' in self._videodata[k])]:
                    node[nodeName][season] = {'lazyLoadURL': self._videodata[season]['ref']}
                    refreshes.append((node[nodeName][season], season, None, None, True))

            if not bShow:
                # Reset the basic metadata
                title = node[nodeName]['title'] if 'title' in node[nodeName] else None
                node[nodeName] = {'lazyLoadURL': targetURL}
                if title:
                    node[nodeName]['title'] = title
                refreshes.append((node[nodeName], nodeName, ancestorNode, ancestorName, True))

        from contextlib import contextmanager

        @contextmanager
        def _busy_dialog():
            xbmc.executebuiltin('ActivateWindow(busydialognocancel)')
            try:
                yield
            finally:
                xbmc.executebuiltin('Dialog.Close(busydialognocancel)')

        with _busy_dialog():
            for r in refreshes:
                self._LazyLoad(r[0], r[1], r[2], r[3], r[4])

    def _LazyLoad(self, obj, breadcrumb=None, bCacheRefresh=False):
        """ Loader and parser of all the PrimeVideo.com queries """

        def MaxSize(imgUrl):
            """ Strip the dynamic resize triggers from the URL (and other effects, such as blur) """

            return re.sub(r'\._.*_\.', '.', imgUrl)

        def ExtractURN(url):
            """ Extract the unique resource name identifier """

            ret = re.search(r'(?:/gp/video)?/d(?:p|etail)/([^/]+)/', url)
            return None if not ret else ret.group(1)

        def DelocalizeDate(lang, datestr):
            """ Convert language based timestamps into YYYY-MM-DD """

            if lang not in self._dateParserData:
                Log('Unable to decode date "{}": language "{}" not supported'.format(datestr, lang), Log.WARNING)
                return datestr
            p = re.search(self._dateParserData[lang]['deconstruct'], datestr.lower())
            if None is p:
                Log('Unable to parse date "{}" with language "{}"{}'.format(datestr, lang, '' if 'en_US' == lang else ': trying english'), Log.WARNING)
                if 'en_US' == lang:
                    return datestr
                # Sometimes Amazon returns english everything, let's try to figure out if this is the case
                lang = 'en_US'
                p = re.search(self._dateParserData[lang]['deconstruct'], datestr.lower())
                if None is p:
                    Log('Unable to parse date "{}" with language "{}": format changed?'.format(datestr, lang), Log.WARNING)
                    return datestr
            p = list(p.groups())
            p[self._dateParserData[lang]['month']] = self._dateParserData[lang]['months'][p[self._dateParserData[lang]['month']]]
            return self._dateParserData[lang]['reassemble'].format(p[0], p[1], p[2])

        def NotifyUser(msg):
            """ Pop up messages while scraping to inform users of progress """

            if not hasattr(NotifyUser, 'lastNotification'):
                NotifyUser.lastNotification = 0
            if NotifyUser.lastNotification < time.time():
                # Only update once every other second, to avoid endless message queue
                NotifyUser.lastNotification = 1 + time.time()
                self._g.dialog.notification(self._g.addon.getAddonInfo('name'), msg, time=1000, sound=False)

        def MultiRegexParsing(content, o):
            """ Takes a dictionary of regex and applies them to content, returning a filtered dictionary of results """

            for i in o:
                o[i] = re.search(o[i], content, flags=re.DOTALL)
                if None is not o[i]:
                    o[i] = o[i].groups()
                    o[i] = Unescape(o[i][0]) if 1 == len(o[i]) else list(o[i])
                    if 'image' == i:
                        o[i] = MaxSize(o[i])
                    elif 'season' == i:
                        o[i] = {'locale': Unescape(o[i][0]), 'season': int(o[i][1]), 'format': Unescape('{} {}'.format(o[i][0], o[i][1]))}
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

        def AddSeason(oid, o, title, thumbnail, url):
            """ Given a season, adds TV Shows to the catalog """
            urn = ExtractURN(iu)
            parent = None
            season = {}
            bUpdatedVideoData = False
            if urn not in self._videodata['urn2gti']:
                # Find the show the season belongs to
                bUpdatedVideoData |= ParseSinglePage(oid, season, False, url=url)
                seasonGTI = self._videodata['urn2gti'][urn]
                try:
                    # Query an episode to find its ancestors
                    family = getURLData('catalog/GetPlaybackResources', self._videodata[seasonGTI]['children'][0], silent=True, extra=True, useCookie=True,
                                        opt='&titleDecorationScheme=primary-content', dRes='CatalogMetadata')[1]['catalogMetadata']['family']['tvAncestors']
                    # Grab the 'SHOW' ancestor ({SHOW: [{SEASON: [EPISODE, …], …}])
                    parent = [a['catalog'] for a in family if 'SHOW' == a['catalog']['type']][0]
                except: pass
                if parent:
                    # {'id': gti, 'title': …, 'type': 'SHOW', …}
                    pid = parent['id']
                    self._videodata[seasonGTI]['parent'] = pid
                    self._videodata[pid] = {'title': parent['title'], 'metadata': {'videometa': {'mediatype': 'tvshow'}}, 'children': [seasonGTI]}
                    for gti in self._videodata[seasonGTI]['siblings']:
                        self._videodata[gti]['parent'] = pid
                        if gti not in self._videodata[pid]['children']:
                            self._videodata[pid]['children'].append(gti)
                    parent = pid
                    bUpdatedVideoData = True
            else:
                parent = self._videodata[self._videodata['urn2gti'][urn]]['parent']
            bSeasonOnly = (not parent) or (oid == parent)
            if not bSeasonOnly:
                o[parent] = self._videodata[parent]
                o = o[parent]
            for sid in season:
                o[sid] = season[sid]
            return bUpdatedVideoData

        def ParseSinglePage(oid, o, bCacheRefresh, data=None, url=None):
            """ Parse PrimeVideo.com single movie/season pages.
                `url` is discarded in favour of `data`, if present.
            """
            urn = ExtractURN(url)

            # Load from cache, if available
            if (not bCacheRefresh) and (urn in self._videodata['urn2gti']) and (self._videodata['urn2gti'][urn] in self._videodata):
                gti = self._videodata['urn2gti'][urn]
                vd = self._videodata[gti]
                # Movie
                if 'children' not in vd:
                    if gti not in o:
                        o[gti] = vd
                    return False

                # TV Series
                bEpisodesOnly = oid == gti
                siblings = [] if bEpisodesOnly else vd['siblings'][:]
                siblings.append(gti)
                siblings = sorted(siblings, key=(lambda k: self._videodata[k]['metadata']['videometa']['season']))
                for gti in siblings:
                    # Add season if we're not inside a season already
                    if (not bEpisodesOnly) and (gti not in o):
                        o[gti] = self._videodata[gti]
                        dest = o[gti]
                    else:
                        o = self._videodata[gti]
                        dest = o
                    # Add cached episodes
                    for c in dest['children']:
                        if c not in dest:
                            dest[c] = {}
                return False

            if url:
                url = self._FQify(url)
            if not data:
                if not url:
                    return False
                data = self._GrabJSON(url)
                # from .logging import LogJSON
                # LogJSON(data, url)

            # Video/season/movie data are in the `state` field of the response
            if 'state' not in data:
                return False

            state = data['state']  # Video info
            GTIs = []  # List of inserted GTIs
            parents = {}  # Map of parents
            bUpdated = False  # Video data updated

            # Seasons (episodes are now listed in self too)
            # Only add seasons if we are not inside a season already
            if ('self' in state) and (oid not in state['self']):
                # "self": {"amzn1.dv.gti.[…]": {"gti": "amzn1.dv.gti.[…]", "link": "/detail/[…]"}}
                for gti in [k for k in state['self'] if 'season' == state['self'][k]['titleType']]:
                    s = state['self'][gti]
                    gti = s['gti']
                    if gti not in self._videodata:
                        o[gti] = {('ref' if state['pageTitleId'] == gti else 'lazyLoadURL'): s['link']}
                        self._videodata[gti] = {'ref': s['link'], 'children': [], 'siblings': []}
                        bUpdated = True
                    else:
                        o[gti] = self._videodata[gti]
                    GTIs.append(gti)
                    siblings = [k for k, ss in state['self'].items() if k != gti and ss['titleType'] == s['titleType']]
                    if siblings != self._videodata[gti]['siblings']:
                        self._videodata[gti]['siblings'] = siblings
                        bUpdated = True

            # Episodes lists
            if 'collections' in state:
                # "collections": {"amzn1.dv.gti.[…]": [{"titleIds": ["amzn1.dv.gti.[…]", "amzn1.dv.gti.[…]"]}]}
                for gti, lc in state['collections'].items():
                    for le in lc:
                        for e in le['titleIds']:
                            if oid == gti:  # Inside the season folder already
                                o[e] = {}
                            else:
                                o[gti][e] = {}
                            GTIs.append(e)
                            # Save parent/children relationships
                            parents[e] = gti
                            if e not in self._videodata[gti]['children']:
                                self._videodata[gti]['children'].append(e)
                                bUpdated = True

            # Video info
            if 'detail' not in state:
                return bUpdated

            if urn not in self._videodata['urn2gti']:
                self._videodata['urn2gti'][urn] = state['pageTitleId']

            # Both of these versions have been spotted in the wild
            # { "detail": { … } }
            # { "detail": { "detail": {…}, "headerDetail": {…} } }
            details = state['detail']
            if 'detail' in details:
                details = details['detail']

            from json import dumps
            # Get details, seasons first
            for gti in sorted(details, key=lambda x: 'season' != details[x]['titleType']):
                item = details[gti]
                if (oid not in details) and (gti not in GTIs):  # Most likely (surely?) movie
                    GTIs.append(gti)
                    o[gti] = {}
                if gti not in self._videodata:
                    self._videodata[gti] = {}
                vd = self._videodata[gti]

                # Meta prep
                if 'metadata' not in vd:
                    vd['metadata'] = {'compactGTI': urn, 'artmeta': {}, 'videometa': {}}
                    bUpdate = True
                if 'artmeta' not in vd['metadata']:
                    vd['metadata']['artmeta'] = {}
                    bUpdate = True
                if 'videometa' not in vd['metadata']:
                    vd['metadata']['videometa'] = {}
                    bUpdate = True

                # Parent
                if gti in parents:
                    vd['parent'] = parents[gti]
                    bUpdate = True

                # Title
                if bCacheRefresh or ('title' not in vd):
                    if 'seasonNumber' not in item:
                        vd['title'] = self._BeautifyText(item['title'])
                    else:
                        try:
                            vd['title'] = state['strings']['AVOD_DP_season_selector'].format(seasonNumber=item['seasonNumber'])
                        except:
                            vd['title'] = 'Season {}'.format(item['seasonNumber'])
                    bUpdated = True

                # Images
                for k, v in {'thumb': 'packshot', 'poster': 'titleshot', 'fanart': 'heroshot'}.items():
                    if (bCacheRefresh or (k not in vd['metadata']['artmeta'])) and \
                       ('images' in item) and (v in item['images']) and item['images'][v]:
                        vd['metadata']['artmeta'][k] = item['images'][v]
                        bUpdated = True

                # Synopsis, media type, year, duration
                for k, v in {'plot': 'synopsis', 'mediatype': 'titleType', 'year': 'releaseYear', 'duration': 'duration'}.items():
                    if (bCacheRefresh or (k not in vd['metadata']['videometa'])) and (v in item):
                        vd['metadata']['videometa'][k] = item[v]
                        bUpdated = True

                # Genres
                if (bCacheRefresh or ('genre' not in vd['metadata']['videometa'])) and ('genres' in item) and item['genres']:
                    vd['metadata']['videometa']['genre'] = [g['text'] for g in item['genres']]
                    bUpdated = True

                # Premiered/Aired
                if (bCacheRefresh or ('premiered' not in vd['metadata']['videometa'])) and ('releaseDate' in item) and item['releaseDate']:
                    vd['metadata']['videometa']['premiered'] = DelocalizeDate(amzLang, item['releaseDate'])
                    vd['metadata']['videometa']['aired'] = vd['metadata']['videometa']['premiered']
                    bUpdated = True

                # MPAA
                if (bCacheRefresh or ('mpaa' not in vd['metadata']['videometa'])) and \
                   ('ratingBadge' in item) and ('displayText' in item['ratingBadge']) and item['ratingBadge']['displayText']:
                    vd['metadata']['videometa']['mpaa'] = item['ratingBadge']['displayText']
                    bUpdated = True

                # Contributors (`producers` are ignored)
                if 'contributors' in item:
                    for k, v in {'director': 'directors', 'cast': 'starringActors', 'cast': 'supportingActors'}.items():
                        if v in item['contributors']:
                            for p in item['contributors'][v]:
                                try:
                                    vd['metadata']['videometa'][k].append(p['name'])
                                    bUpdated = True
                                except KeyError:
                                    vd['metadata']['videometa'][k] = [p['name']]
                                    bUpdated = True

                # Season, TV show title
                if ('seasonNumber' in item) and item['seasonNumber']:
                    if bCacheRefresh or ('season' not in vd['metadata']['videometa']):
                        vd['metadata']['videometa']['season'] = item['seasonNumber']
                        bUpdated = True
                    if bCacheRefresh or ('tvshowtitle' not in vd['metadata']['videometa']):
                        vd['metadata']['videometa']['tvshowtitle'] = item['parentTitle']
                        bUpdated = True

                # Episode, Season, TV show title
                if ('episodeNumber' in item) and item['episodeNumber']:
                    if bCacheRefresh or ('episode' not in vd['metadata']['videometa']):
                        vd['metadata']['videometa']['episode'] = item['episodeNumber']
                        bUpdated = True
                    if bCacheRefresh or ('season' not in vd['metadata']['videometa']):
                        try:
                            vd['metadata']['videometa']['season'] = self._videodata[vd['parent']]['metadata']['videometa']['season']
                            bUpdated = True
                        except: pass
                    if bCacheRefresh or ('tvshowtitle' not in vd['metadata']['videometa']):
                        try:
                            vd['metadata']['videometa']['tvshowtitle'] = self._videodata[vd['parent']]['metadata']['videometa']['parentTitle']
                            bUpdated = True
                        except: pass

            # IMDB ratings — "imdb": {"amzn1.dv.gti.[…]": {"score": 8.5}}
            if ('imdb' in state) and state['imdb']:
                for gti in state['imdb']:
                    vmd = self._videodata[gti]['metadata']['videometa']
                    if (bCacheRefresh or ('rating' not in vmd)) and ('score' in state['imdb'][gti]) and state['imdb'][gti]['score']:
                        vmd['rating'] = state['imdb'][gti]['score']
                        bUpdated = True

            # Trailer — "trailer": {"amzn1.dv.gti.[…]": {"playbackID": "amzn1.dv.gti.[…]", "playbackURL": "/detail/[ShortGTI]/ref=atv_dp_watch_trailer?autoplay=trailer"}}
            if ('trailer' in state) and state['trailer']:
                for gti in state['trailer']:
                    if 'trailer' not in self._videodata[gti]:
                        self._videodata[gti]['trailer'] = True
                        bUpdated = True

            return bUpdated

        if 'lazyLoadURL' not in obj:
            return
        requestURLs = [obj['lazyLoadURL']]

        amzLang = None
        if None is not requestURLs[0]:
            # Fine the locale amazon's using
            cj = MechanizeLogin()
            if cj:
                amzLang = cj.get('lc-main-av', path='/')
        amzLang = amzLang if amzLang else 'en_US'

        bUpdatedVideoData = False  # Whether or not the pvData has been updated

        while 0 < len(requestURLs):
            requestURL = requestURLs.pop(0)  # rULRs: FIFO stack
            o = obj

            # Load content
            bCouldNotParse = False
            try:
                cnt = None

                # Use cached data, if available
                if 'lazyLoadData' in o:
                    cnt = o['lazyLoadData']
                    del o['lazyLoadData']

                # Load content from an external url
                if not cnt:
                    urn = ExtractURN(requestURL)
                    if (not bCacheRefresh) and urn and (urn in self._videodata['urn2gti']):
                        # There are no API endpoints for movie/series pages, so we handle them in a separate function
                        bUpdatedVideoData |= ParseSinglePage(breadcrumb[-1], o, False, url=requestURL)
                        if 'lazyLoadURL' in o:
                            if 'ref' not in o:
                                o['ref'] = o['lazyLoadURL']
                            del o['lazyLoadURL']
                        continue
                    else:
                        cnt = self._GrabJSON(requestURL)

                # Don't switch direct action for reference until we have content to show for it
                if cnt and ('lazyLoadURL' in o):
                    if 'ref' not in o:
                        o['ref'] = o['lazyLoadURL']
                    del o['lazyLoadURL']
            except:
                bCouldNotParse = True
            if bCouldNotParse or (not cnt):
                self._g.dialog.notification(getString(30251), requestURL, xbmcgui.NOTIFICATION_ERROR)
                Log('Unable to fetch the url: {}'.format(requestURL), Log.ERROR)
                continue

            # Categories
            if 'collections' in cnt:
                for collection in cnt['collections']:
                    o[collection['text']] = {'title': self._BeautifyText(collection['text'])}
                    if 'seeMoreLink' in collection:
                        o[collection['text']]['lazyLoadURL'] = collection['seeMoreLink']['url']
                    else:
                        o[collection['text']]['lazyLoadURL'] = requestURL
                        o[collection['text']]['lazyLoadData'] = collection

            # Widow list / API Search
            if ('items' in cnt):
                for item in cnt['items']:
                    if 'heading' in item:
                        # Search results
                        title = item['heading']
                        iu = item['href']
                        try:
                            t = item['watchlistAction']['endpoint']['query']['titleType']
                        except:
                            t = None
                        if 'season' != t:
                            bUpdatedVideoData |= ParseSinglePage(breadcrumb[-1], o, bCacheRefresh, url=iu)
                        else:
                            bUpdatedVideoData |= AddSeason(breadcrumb[-1], o, title, item['imageSrc'], iu)
                    else:
                        # Watchlist
                        Log('Show all seasons in watchlist: {}'.format(self._s.dispShowOnly))

            # Search/list
            if ('results' in cnt) and ('items' in cnt['results']):
                for item in cnt['results']['items']:
                    iu = item['title']['url']
                    if 'season' not in item:
                        bUpdatedVideoData |= ParseSinglePage(breadcrumb[-1], o, bCacheRefresh, url=iu)
                    else:
                        bUpdatedVideoData |= AddSeason(breadcrumb[-1], o, item['title']['text'], MaxSize(item['packshot']['image']['src']), iu)

            # Watchlist
            if 'filters' in cnt:
                for f in cnt['filters']:
                    o[f['id']] = {'title': f['text'], 'lazyLoadURL': f['apiUrl' if 'apiUrl' in f else 'href']}
                    if 'applied' in cnt['filters'][0]:
                        o[f['id']]['lazyLoadData'] = cnt['content']

            # Single page
            if 'state' in cnt:
                bUpdatedVideoData |= ParseSinglePage(breadcrumb[-1], o, bCacheRefresh, data=cnt, url=requestURL)

            # Pagination
            if 'pagination' in cnt:
                page = None
                if 'apiUrl' in cnt['pagination']:
                    page = cnt['pagination']['apiUrl']
                elif 'paginator' in cnt['pagination']:
                    page = next((x['href'] for x in cnt['pagination']['paginator'] if 'atv.wps.PaginatorNext' == x['*className*']), None)
                if page:
                    requestURLs.append(page)
                else:
                    Log('Unknown error while parsing pagination', Log.ERROR)

            # Notify new page
            if 0 < len(requestURLs):
                NotifyUser(getString(30252))

        # Flush catalog and data
        self._Flush(bCacheRefresh or bUpdatedVideoData)
