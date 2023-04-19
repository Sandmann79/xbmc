#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from collections import OrderedDict
from copy import deepcopy
from kodi_six import xbmcplugin
import re

from .common import key_exists, return_item, return_value, sleep, findKey
from .singleton import Singleton
from .network import getURL, getURLData, MechanizeLogin, FQify, GrabJSON
from .logging import Log, LogJSON
from .itemlisting import setContentAndView, addVideo, addDir
from .users import *
from .export import SetupLibrary

try:
    import cPickle as pickle
except ImportError:
    import pickle

try:
    from urllib.parse import quote_plus, unquote_plus
except ImportError:
    from urllib import quote_plus, unquote_plus


class PrimeVideo(Singleton):
    """ Wrangler of all things PrimeVideo.com """

    _catalog = {}  # Catalog cache
    _videodata = {'urn2gti': {}}  # Video data cache
    _catalogCache = None  # Catalog cache file name
    _videodataCache = None  # Video data cache file name
    _separator = '/'  # Virtual path separator

    def __init__(self, globalsInstance, settingsInstance):
        self._g = globalsInstance
        self._s = settingsInstance
        """ Data for date string deconstruction and reassembly

            Date references:
            https://www.primevideo.com/detail/0LCQSTWDMN9V770DG2DKXY3GVF/  09 10 11 12 01 02 03 04 05
            https://www.primevideo.com/detail/0ND5POOAYD6A4THTH7C1TD3TYE/  06 07 08 09

            Languages: https://www.primevideo.com/settings/language/
        """
        self._dateParserData = {
            'generic': r'^(?P<m>[^W]+)[.,:;\s-]+(?P<d>[0-9]+),\s+(?P<y>[0-9]+)(?:\s+[0-9]+|$)',
            'asianMonthExtractor': r'^([0-9]+)[월月]',
            'da_DK': {'deconstruct': r'^(?P<d>[0-9]+)\.?\s+(?P<m>[^\s]+)\s+(?P<y>[0-9]+)',
                      'months': {'januar': 1, 'februar': 2, 'marts': 3, 'april': 4, 'maj': 5, 'juni': 6, 'juli': 7, 'august': 8, 'september': 9, 'oktober': 10,
                                 'november': 11, 'december': 12}},
            'de_DE': {'deconstruct': r'^(?P<d>[0-9]+)\.?\s+(?P<m>[^\s]+)\s+(?P<y>[0-9]+)',
                      'months': {'januar': 1, 'februar': 2, 'märz': 3, 'april': 4, 'mai': 5, 'juni': 6, 'juli': 7, 'august': 8, 'september': 9, 'oktober': 10,
                                 'november': 11, 'dezember': 12, 'jan.': 1, 'feb.': 2, 'mär.': 3, 'apr.': 4, 'jun.': 6, 'jul.': 7, 'aug.': 8, 'sept.': 9, 'okt.': 10,
                                 'nov.': 11, 'dez.': 12}},
            'en_US': {'deconstruct': r'^(?P<m>[^\s]+)\s+(?P<d>[0-9]+),?\s+(?P<y>[0-9]+)',
                      'months': {'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6, 'july': 7, 'august': 8, 'september': 9, 'october': 10,
                                 'november': 11, 'december': 12}},
            'es_ES': {'deconstruct': r'^(?P<d>[0-9]+)\s+de\s+(?P<m>[^\s]+),?\s+de\s+(?P<y>[0-9]+)',
                      'months': {'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6, 'julio': 7, 'agosto': 8, 'septiembre': 9, 'octubre': 10,
                                 'noviembre': 11, 'diciembre': 12}},
            'fi_FI': {'deconstruct': r'^(?P<d>[0-9]+)\.?\s+(?P<m>[^\s]+)\s+(?P<y>[0-9]+)',
                      'months': {'tammikuuta': 1, 'helmikuuta': 2, 'maaliskuuta': 3, 'huhtikuuta': 4, 'toukokuuta': 5, 'kesäkuuta': 6, 'heinäkuuta': 7, 'elokuuta': 8,
                                 'syyskuuta': 9, 'lokakuuta': 10, 'marraskuuta': 11, 'joulukuuta': 12}},
            'fr_FR': {'deconstruct': r'^(?P<d>[0-9]+)\s+(?P<m>[^\s]+)\s+(?P<y>[0-9]+)',
                      'months': {'janvier': 1, 'janv.': 1, 'février': 2, 'févr.': 2, 'mars': 3, 'avril': 4, 'avr.': 4, 'mai': 5, 'juin': 6, 'juillet': 7, 'juil.': 7,
                                  'aout': 8, 'août': 8, 'septembre': 9, 'sept.': 9, 'octobre': 10, 'oct.': 10, 'novembre': 11, 'nov.': 11, 'décembre': 12, 'déc.': 12}},
            'hi_IN': {'deconstruct': r'^(?P<d>[0-9]+)\s+(?P<m>[^\s]+)\s+(?P<y>[0-9]+)',
                      'months': {'जनवरी': 1, 'फ़रवरी': 2, 'मार्च': 3, 'अप्रैल': 4, 'मई': 5, 'जून': 6, 'जुलाई': 7, 'अगस्त': 8, 'सितंबर': 9, 'अक्तूबर': 10,
                                 'नवंबर': 11, 'दिसंबर': 12}},
            'id_ID': {'deconstruct': r'^(?P<d>[0-9]+)\s+(?P<m>[^\s]+)\s+(?P<y>[0-9]+)',
                      'months': {'januari': 1, 'februari': 2, 'maret': 3, 'april': 4, 'mei': 5, 'juni': 6, 'juli': 7, 'agustus': 8, 'september': 9,
                                 'oktober': 10, 'november': 11, 'desember': 12}},
            'it_IT': {'deconstruct': r'^(?P<d>[0-9]+)\s+(?P<m>[^\s]+)\s+(?P<y>[0-9]+)',
                      'months': {'gennaio': 1, 'febbraio': 2, 'marzo': 3, 'aprile': 4, 'maggio': 5, 'giugno': 6, 'luglio': 7, 'agosto': 8, 'settembre': 9,
                                 'ottobre': 10, 'novembre': 11, 'dicembre': 12}},
            'ko_KR': {'deconstruct': r'^(?P<y>[0-9]+)년\s+(?P<m>[0-9]+)월\s+(?P<d>[0-9]+)일'},
            'nb_NO': {'deconstruct': r'^(?P<d>[0-9]+)\.?\s+(?P<m>[^\s]+)\s+(?P<y>[0-9]+)',
                      'months': {'januar': 1, 'februar': 2, 'mars': 3, 'april': 4, 'mai': 5, 'juni': 6, 'juli': 7, 'august': 8, 'september': 9, 'oktober': 10,
                                 'november': 11, 'desember': 12}},
            'nl_NL': {'deconstruct': r'^(?P<d>[0-9]+)\s+(?P<m>[^\s]+)\s+(?P<y>[0-9]+)',
                      'months': {'januari': 1, 'februari': 2, 'maart': 3, 'april': 4, 'mei': 5, 'juni': 6, 'juli': 7, 'augustus': 8, 'september': 9,
                                 'oktober': 10, 'november': 11, 'december': 12}},
            'pl_PL': {'deconstruct': r'^(?P<d>[0-9]+)\s+(?P<m>[^\s]+)\s+(?P<y>[0-9]+)',
                      'months': {'stycznia': 1, 'lutego': 2, 'marca': 3, 'kwietnia': 4, 'maja': 5, 'czerwca': 6, 'lipca': 7, 'sierpnia': 8, 'września': 9,
                                 'października': 10, 'listopada': 11, 'grudnia': 12}},
            'pt_BR': {'deconstruct': r'^(?P<d>[0-9]+)\s+de\s+(?P<m>[^\s]+),?\s+de\s+(?P<y>[0-9]+)',
                      'months': {'janeiro': 1, 'fevereiro': 2, 'março': 3, 'abril': 4, 'maio': 5, 'junho': 6, 'julho': 7, 'agosto': 8, 'setembro': 9, 'outubro': 10,
                                 'novembro': 11, 'dezembro': 12}},
            'pt_PT': {'deconstruct': r'^(?P<d>[0-9]+)\s+de\s+(?P<m>[^\s]+),?\s+de\s+(?P<y>[0-9]+)',
                      'months': {'janeiro': 1, 'fevereiro': 2, 'março': 3, 'abril': 4, 'maio': 5, 'junho': 6, 'julho': 7, 'agosto': 8, 'setembro': 9, 'outubro': 10,
                                 'novembro': 11, 'dezembro': 12}},
            'ru_RU': {'deconstruct': r'^(?P<d>[0-9]+)\s+(?P<m>[^\s]+)\s+(?P<y>[0-9]+)',
                      'months': {'января': 1, 'февраля': 2, 'марта': 3, 'апреля': 4, 'мая': 5, 'июня': 6, 'июля': 7, 'августа': 8, 'сентября': 9,
                                 'октября': 10, 'ноября': 11, 'декабря': 12}},
            'sv_SE': {'deconstruct': r'^(?P<d>[0-9]+)\s+(?P<m>[^\s]+)\s+(?P<y>[0-9]+)',
                      'months': {'januari': 1, 'februari': 2, 'mars': 3, 'april': 4, 'maj': 5, 'juni': 6, 'juli': 7, 'augusti': 8, 'september': 9, 'oktober': 10,
                                 'november': 11, 'december': 12}},
            'ta_IN': {'deconstruct': r'^(?P<d>[0-9]+)\s+(?P<m>[^\s]+),?\s+(?P<y>[0-9]+)',
                      'months': {'ஜனவரி': 1, 'பிப்ரவரி': 2, 'மார்ச்': 3, 'ஏப்ரல்': 4, 'மே': 5, 'ஜூன்': 6, 'ஜூலை': 7, 'ஆகஸ்ட்': 8, 'செப்டம்பர்': 9,
                                 'அக்டோபர்': 10, 'நவம்பர்': 11, 'டிசம்பர்': 12}},
            'te_IN': {'deconstruct': r'^(?P<d>[0-9]+)\s+(?P<m>[^\s]+),?\s+(?P<y>[0-9]+)',
                      'months': {'జనవరి': 1, 'ఫిబ్రవరి': 2, 'మార్చి': 3, 'ఏప్రిల్': 4, 'మే': 5, 'జూన్': 6, 'జులై': 7, 'ఆగస్టు': 8, 'సెప్టెంబర్': 9, 'అక్టోబర్': 10,
                                 'నవంబర్': 11, 'డిసెంబర్': 12}},
            'th_TH': {'deconstruct': r'^(?P<d>[0-9]+)\s+(?P<m>[^\s]+),?\s+(?P<y>[0-9]+)',
                      'months': {'มกราคม': 1, 'กุมภาพันธ์': 2, 'มีนาคม': 3, 'เมษายน': 4, 'พฤษภาคม': 5, 'มิถุนายน': 6, 'กรกฎาคม': 7, 'สิงหาคม': 8, 'กันยายน': 9, 'ตุลาคม': 10,
                                 'พฤศจิกายน': 11, 'ธันวาคม': 12}},
            'tr_TR': {'deconstruct': r'^(?P<d>[0-9]+)\s+(?P<m>[^\s]+)\s+(?P<y>[0-9]+)',
                      'months': {'ocak': 1, 'şubat': 2, 'mart': 3, 'nisan': 4, 'mayıs': 5, 'haziran': 6, 'temmuz': 7, 'ağustos': 8, 'eylül': 9,
                                 'ekim': 10, 'kasım': 11, 'aralık': 12}},
            'zh_CN': {'deconstruct': r'^(?P<y>[0-9]+)年(?P<m>[0-9]+)月(?P<d>[0-9]+)日',
                      'months': {'一月': 1, '二月': 2, '三月': 3, '四月': 4, '五月': 5, '六月': 6, '七月': 7, '八月': 8, '九月': 9, '十月': 10, '十一月': 11, '十二月': 12}},
            'zh_TW': {'deconstruct': r'^(?P<y>[0-9]+)年(?P<m>[0-9]+)月(?P<d>[0-9]+)日',
                      'months': {'一月': 1, '二月': 2, '三月': 3, '四月': 4, '五月': 5, '六月': 6, '七月': 7, '八月': 8, '九月': 9, '十月': 10, '十一月': 11, '十二月': 12}},
            'ja_JP': {'deconstruct': r'^(?P<y>[0-9]+)\/(?P<m>[0-9]+)\/(?P<d>[0-9]+)$'},
            'en_GB': {'deconstruct': r'^(?P<d>[0-9]+)\s+(?P<m>[^\s]+)?\s+(?P<y>[0-9]+)',
                      'months': {'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6, 'july': 7, 'august': 8, 'september': 9,
                                 'october': 10, 'november': 11, 'december': 12}}
        }
        self._languages = [
            ('id_ID', 'Bahasa Indonesia'),
            ('da_DK', 'Dansk'),
            ('de_DE', 'Deutsch'),
            ('en_US', 'English'),
            ('en_GB', 'English'),
            ('es_ES', 'Español'),
            ('fr_FR', 'Français'),
            ('it_IT', 'Italiano'),
            ('nl_NL', 'Nederlands'),
            ('nb_NO', 'Norsk'),
            ('pl_PL', 'Polski'),
            ('pt_BR', 'Português (Brasil)'),
            ('pt_PT', 'Português (Portugal)'),
            ('fi_FI', 'Suomi'),
            ('sv_SE', 'Svenska'),
            ('tr_TR', 'Türkçe'),
            ('ru_RU', 'Русский'),
            ('hi_IN', 'हिन्दी'),
            ('ta_IN', 'தமிழ்'),
            ('te_IN', 'తెలుగు'),
            ('th_TH', 'ไทย'),
            ('zh_CN', '简体中文'),
            ('zh_TW', '繁體中文'),
            ('ko_KR', '한국어'),
            ('ja_JP', '日本語')
        ]
        self._TextCleanPatterns = [[r'\s+-\s*([^&])', r' – \1'],  # Convert dash from small to medium where needed
                                   [r'\s*-\s+([^&])', r' – \1'],  # Convert dash from small to medium where needed
                                   [r'^\s+', ''],  # Remove leading spaces
                                   [r'\s+$', ''],  # Remove trailing spaces
                                   [r' {2,}', ' '],  # Remove double spacing
                                   [r'\.\.\.', '…']]  # Replace triple dots with ellipsis
        # rex compilation
        self._imageRefiner = re.compile(r'\._.*_\.')
        self._reURN = re.compile(r'(?:/gp/video)?/d(?:p|etail)/([^/]+)/')
        self._dateParserData['generic'] = re.compile(self._dateParserData['generic'], re.UNICODE)
        self._dateParserData['asianMonthExtractor'] = re.compile(self._dateParserData['asianMonthExtractor'])
        for k in self._dateParserData:
            try:
                self._dateParserData[k]['deconstruct'] = re.compile(self._dateParserData[k]['deconstruct'])
            except: pass
        for i, s in enumerate(self._TextCleanPatterns):
            self._TextCleanPatterns[i][0] = re.compile(s[0])

        self._LoadCache()

    def _Flush(self, bFlushCacheData=True, bFlushVideoData=False):
        """ Cache catalog and video data """

        if bFlushCacheData:
            with open(self._catalogCache, 'wb+') as fp:
                pickle.dump(self._catalog, fp, -1)
        if bFlushVideoData:
            with open(self._videodataCache, 'w+') as fp:
                bPretty = self._s.verbLog
                json.dump(self._videodata, fp, indent=2 if bPretty else None, separators=None if bPretty else (',', ':'), sort_keys=True)

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
                if 'urn2gti' not in data:
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

        for r in self._TextCleanPatterns:
            title = r[0].sub(r[1], title)
        return title

    def _TraverseCatalog(self, path, bRefresh=False):
        """ Extract current node, grandparent node and their names """
        # Fix the unquote_plus problem with unicode_literals by encoding to latin-1 (byte string) and then decoding
        pathList = [unquote_plus(p) for p in path.split(self._separator)]
        for k in range(len(pathList)):
            try:
                pathList[k] = pathList[k].encode('latin-1').decode('utf-8')
            except: pass

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

            # Populate children list to avoid favourite/library traversal errors
            if 'children' in node:
                for cid in node['children']:
                    if cid not in node:
                        node[cid] = {}
                        try:
                            if 0 == len(self._videodata[cid]['children']):
                                node[cid]['lazyLoadURL'] = self._videodata[cid]['ref']
                        except: pass
            if nodeName not in node:
                self._g.dialog.notification('Catalog error', 'Catalog path not available…', xbmcgui.NOTIFICATION_ERROR)
                return None, None
            elif ('lazyLoadURL' in node[nodeName]) or ('lazyLoadData' in node[nodeName]):
                self._LazyLoad(node[nodeName], pathList[0:1 + i])
            node = node[nodeName]
        return node, pathList

    def _UpdateProfiles(self, data):
        data = data.get('lists', data)
        pr = data.get('cerberus', data.get('profiles'))
        if pr is not None:
            profiles = []
            if 'activeProfile' in pr:
                profiles.append(pr['activeProfile'])
            if 'otherProfiles' in pr:
                profiles += pr['otherProfiles']
            if isinstance(pr, list):
                profiles = pr
            self._catalog['profiles'] = {}
            for p in profiles:
                if p.get('isSelected', False):
                    self._catalog['profiles']['active'] = p['id']
                self._catalog['profiles'][p['id']] = {
                    'title': p.get('name', 'Default').encode('utf-8'),
                    'metadata': {'artmeta': {'thumb': p['avatarUrl']}},
                    'verb': 'pv/profiles/switch/{}'.format(p['id']),
                    'endpoint': p['switchLink'],
                }

    def Route(self, verb, path):
        if 'search' == verb: g.pv.Search()
        elif 'browse' == verb: g.pv.Browse(path)
        elif 'refresh' == verb: g.pv.Refresh(path)
        elif 'profiles' == verb: g.pv.Profile(path)
        elif 'languageselect' == verb: g.pv.LanguageSelect()
        elif 'clearcache' == verb: g.pv.DeleteCache()
        elif 'wltoogle' == verb: g.pv.Watchlist(path)
        elif 'ageSettings' == verb: g.dialog.ok(g.__plugin__, 'Age Restrictions are currently unavailable for WebApi users')
        elif 'sethome' == verb: g.pv.SetHome(path)

    def Watchlist(self, path):
        path = path.split(self._separator)
        remove = int(path[-1])
        action = ['Add', 'Remove'][remove]
        gtis = unquote_plus(path[-2]).split(',')
        params = '['
        for gti in gtis if remove else [gtis[0]]:
            params += '{"titleID":"%s","watchlist":true},' % gti
        data = GrabJSON(self._g.BaseUrl + '/gp/video/api/enrichItemMetadata?itemsToEnrich=' + quote_plus(params[:-1]+']'))
        for enrich in list(data['enrichments']):
            endp = data['enrichments'][enrich]['watchlistAction']['endpoint']
            if (endp['query']['tag'] == action and remove) or not remove:
                endp['query']['tag'] = action
                result = getURL(self._g.BaseUrl + endp['partialURL'], postdata=endp['query'], useCookie=True, check=True)
                if result:
                    Log('Watchlist: {} {}'.format(endp['query']['tag'].lower(), enrich))

        if result:
            if remove == 1:
                self.Refresh(self._separator.join(path[:-2]), False)
                xbmc.executebuiltin('Container.Refresh')
            else:
                self.Refresh('root/Watchlist', False)

    def Profile(self, path):
        """ Profile actions """
        path = path.split(self._separator)

        def List():
            """ List all inactive profiles """
            # Hit a fast endpoint to grab and update CSRF tokens
            home = GrabJSON(self._g.BaseUrl + '/gp/video/profiles')
            self._UpdateProfiles(home)
            for k, p in self._catalog['profiles'].items():
                if 'active' == k or k == self._catalog['profiles']['active']:
                    continue
                addDir(p['title'], 'True', p['verb'], p['metadata']['artmeta'])
            xbmcplugin.endOfDirectory(self._g.pluginhandle, succeeded=True, cacheToDisc=False, updateListing=False)

        def Switch():
            """ Switch to an inactive profile """
            # Sometimes the switch just fails due to CSRF, possibly due to problems on Amazon's servers,
            # so we patiently try a few times
            for _ in range(0, 5):
                endpoint = self._catalog['profiles'][path[1]]['endpoint']
                Log('{} {}'.format(self._g.BaseUrl + endpoint['partialURL'], endpoint['query']))
                home = GrabJSON(self._g.BaseUrl + endpoint['partialURL'], endpoint['query'])
                self._UpdateProfiles(home)
                if path[1] == self._catalog['profiles']['active']:
                    break
                sleep(3)
            if path[1] == self._catalog['profiles']['active']:
                self.BuildRoot(home if home else {})
            else:
                self._g.dialog.notification(self._g.addon.getAddonInfo('name'), 'Profile switching unavailable at the moment, please try again', time=1000, sound=False)
            xbmcplugin.endOfDirectory(self._g.pluginhandle, succeeded=False, cacheToDisc=False, updateListing=True)

        if 'list' == path[0]: List()
        elif 'switch' == path[0]: Switch()

    def DeleteCache(self, clear=0):
        """ Pops up a dialog asking cache purge confirmation """
        from .dialogs import PV_ClearCache
        from xbmcvfs import delete

        # ClearCache.value returns a boolean bitmask
        if 0 == clear:
            clear = PV_ClearCache().value
        if 0 > clear:
            return

        # Clear catalog (PVCP)
        if 1 & clear:
            self._catalog = {}
            delete(self._catalogCache)
            Log('Deleting catalog', Log.DEBUG)

        # Clear video data (PVDP)
        if 2 & clear:
            self._videodata = {'urn2gti': {}}
            delete(self._videodataCache)
            Log('Deleting video data', Log.DEBUG)

        del clear

    def LanguageSelect(self):
        cj = MechanizeLogin()
        if not cj:
            return
        if self._g.UsePrimeVideo:
            l = cj.get('lc-main-av', path='/')
            langs = self._languages
            presel = [i for i, x in enumerate(langs) if x[0] == l]
        else:
            # TLDs doesn't store locale in cookie by default
            from mechanicalsoup import StatefulBrowser
            br = StatefulBrowser(soup_config={'features': 'html.parser'})
            br.set_cookiejar(cj)
            br.session.headers.update({'User-Agent': getConfig('UserAgent')})
            br.open(g.BaseUrl + '/customer-preferences/edit')
            langs = [(elem.label.input.get('value'), elem.get_text(strip=True), elem.label.input.get('checked') is not None)
                     for elem in br.get_current_page().find_all('div', attrs={'data-a-input-name': 'lop'})]
            presel = [i for i, x in enumerate(langs) if x[2] is True]

        if len(langs) < 1:
            self._g.dialog.notification(g.__plugin__, getString(30270))
            return

        sel = self._g.dialog.select(getString(30115), [x[1] for x in langs], preselect=presel[0] if presel else -1)
        if sel < 0:
            self._g.addon.openSettings()
        else:
            Log('Changing text language to [{}] {}'.format(langs[sel][0], langs[sel][1]), Log.DEBUG)
            if self._g.UsePrimeVideo:
                cj.set('lc-main-av', langs[sel][0], path='/')
            else:
                ck = [k for k, v in cj.items() if 'sess-at-' in k][0].replace('sess-at-', 'lc-')
                cj.set(ck, langs[sel][0], path='/')
            saveUserCookies(cj)
            self.DeleteCache()

    @staticmethod
    def SetHome(path):
        path = unquote_plus(path) if path else 'root'
        writeConfig('home', path)

    def BrowseRoot(self):
        """ Build and load the root PrimeVideo menu """

        if 0 == len(self._catalog):
            ''' Build the root catalog '''
            if not self.BuildRoot():
                return
        self.Browse(getConfig('home', 'root'))

    def BuildRoot(self, home=None):
        """ Parse the top menu on primevideo.com and build the root catalog """

        # Specify `None` instead of just not empty to avoid multiple queries to the same endpoint
        if home is None:
            home = GrabJSON(self._g.BaseUrl + ('' if self._g.UsePrimeVideo else '/gp/video/storefront'))
            LogJSON(home)
            if not home:
                return False
            self._UpdateProfiles(home)
        self._catalog['root'] = OrderedDict()

        # Insert the watchlist
        navigation = None
        try:
            watchlist = next((x for x in home['yourAccount']['links'] if '/watchlist/' in x['href']), None)
            self._catalog['root']['Watchlist'] = {'title': watchlist['text'], 'lazyLoadURL': FQify(watchlist['href'])}
        except: pass
        try:
            navigation = deepcopy(home['mainMenu']['links'] if 'mainMenu' in home else home['lists']['mainMenuLinks'])
            watchlist = next((x for x in navigation if 'pv-nav-mystuff' in x['id']), None)
            self._catalog['root']['Watchlist'] = {'title': self._BeautifyText(watchlist['text']), 'lazyLoadURL': watchlist['href']}
        except: pass
        try:
            navigation = deepcopy(home['nav']['navigationNodes'])
            watchlist = next((x for x in navigation if 'pv-nav-my-stuff' in x['id']), None)
            self._catalog['root']['Watchlist'] = {'title': self._BeautifyText(watchlist['label'])}
            if watchlist['subMenu'][0].get('subNodes') is None:
                ms = watchlist['url'].rsplit('/', 1)
                data = {'subNodes': [{'id': 'watchlist', 'label': getString(30245), 'url': '/watchlist/'.join(ms)},
                                     {'id': 'library', 'label': getString(30100), 'url': '/library/'.join(ms)}]}
            else:
                data = watchlist['subMenu'][0]
            self._catalog['root']['Watchlist']['lazyLoadData'] = data
        except: pass

        if 'Watchlist' not in self._catalog['root']:
            Log('Watchlist link not found', Log.ERROR)

        # Insert the main sections, in order
        if navigation is not None:
            cn = 0
            while navigation:
                link = navigation.pop(0)
                mml = 'links' in link
                # Skip watchlist
                if link['id'] in ['pv-nav-mystuff', 'pv-nav-my-stuff']:
                    continue
                if self._g.UsePrimeVideo and mml:
                    navigation = link['links'] + navigation
                    continue
                cn += 1
                title = link.get('text', link.get('label'))
                id = 'coll{}_{}'.format(cn, title + ('_mmlinks' if mml else ''))
                self._catalog['root'][id] = {'title': self._BeautifyText(title), 'lazyLoadURL': link.get('href', link.get('url'))}
                # Avoid unnecessary calls when loading the current page in the future
                if 'isHighlighted' in link and link['isHighlighted']:
                    self._catalog['root'][id]['lazyLoadData'] = home
                # Adding main menu categories
                if mml:
                    self._catalog['root'][id]['lazyLoadData'] = home
        else:
            self._g.dialog.ok(getString(30278), getString(30279).format(self._g.BaseUrl, getString(30280) if self._s.register_device else ''))
            Log('Unable to parse the navigation menu for {}'.format(self._g.BaseUrl), Log.ERROR)
            return False

        # Insert the searching mechanism
        if self._g.UsePrimeVideo:
            # Insert the searching mechanism
            try:
                if 'nav' in home:
                    sfa = home['nav']['searchBar']['submitSearchDestructuredEndpoint']
                    title = home['nav']['searchBar']['searchBarPlaceholderLabel']
                else:
                    sfa = home['searchBar']['searchFormAction']
                    title = home['searchBar']['searchFormPlaceholder']
                # Build the query parametrization
                query = ''
                if 'query' in sfa:
                    query += '&'.join(['{}={}'.format(k, v) for k, v in sfa['query'].items()])
                query = query if not query else query + '&'
                self._catalog['root']['Search'] = {
                    'title': self._BeautifyText(title),
                    'verb': 'pv/search/',
                    'endpoint': '{}?{}phrase={{}}'.format(sfa['partialURL'], query)
                }
            except:
                Log('Search functionality not found', Log.ERROR)
        else:
            self._catalog['root']['Search'] = {
                'title': getString(30108),
                'verb': 'pv/search/',
                'endpoint': '/gp/video/search?phrase={}'
            }

        # Set the expiration based on settings (defaults to 12 hours) and flush to disk
        self._catalog['expiration'] = self._s.catalogCacheExpiry + int(time.time())
        self._Flush()

        return True

    def Browse(self, path, bNoSort=False, export=0):
        """ Display and navigate the menu for PrimeVideo users """

        nodeKeys = []
        maincall = False
        path_sep = path.split(self._separator)
        # export: 1=folder without refresh 2=single file (episode/movie) 3=folder with refresh 4=watchlist 5=watchlist (auto)
        if 'export=' in path_sep[-1]:
            export = int(path_sep[-1].split('=')[1])
            path = '/'.join(path_sep[:-1])
            if export > 9:
                Log('Export started')
                maincall = True
                export -= 10
            if export == 2:
                nodeKeys = [path_sep[-2]]
                nodeName = ''
        if export:
            SetupLibrary()
            writeConfig('exporting', time.time())
        if export == 3:
            self.Refresh(path, busy=False)
        elif export > 3:
            Log('Export of watchlist started')
            self.Browse(path + '/all', export=3)
            if export == 5:
                writeConfig('last_wl_export', time.time())
                xbmc.executebuiltin('UpdateLibrary(video)')
            Log('Export of watchlist finished')
            writeConfig('exporting', '')
            return

        if export == 0 and getConfig('exporting') != '':
            if (float(getConfig('exporting', 0)) + 60) > time.time():
                self._g.dialog.notification(self._g.__plugin__, 'Export process is running, please wait until it is finished')
                return
            else:
                writeConfig('exporting', '')

        # Add multiuser menu if needed
        if self._s.multiuser and ('root' == path) and (1 < len(loadUsers())):
            addDir(getString(30134).format(loadUser('name')), '', 'pv/browse/root{}SwitchUser'.format(self._separator), cm=self._g.CONTEXTMENU_MULTIUSER)
        if ('root' + self._separator + 'SwitchUser') == path:
            if switchUser():
                self.DeleteCache(1)
                xbmc.executebuiltin('Container.Refresh')
            return

        # Add Profiles
        if self._s.profiles and ('root' == path) and ('profiles' in self._catalog):
            activeProfile = self._catalog['profiles'][self._catalog['profiles']['active']]
            addDir(activeProfile['title'], 'True', 'pv/profiles/list', activeProfile['metadata']['artmeta'])

        if 1 > len(nodeKeys):
            node, breadcrumb = self._TraverseCatalog(path)
            if None is node:
                return

            # Populate children list with empty references
            nodeName = breadcrumb[-1]
            if (nodeName in self._videodata) and ('children' in self._videodata[nodeName]):
                for c in self._videodata[nodeName]['children']:
                    if c not in node:
                        node[c] = {}

            nodeKeys = sorted([k for k in node if k not in ['ref', 'verb', 'title', 'metadata', 'parent', 'siblings', 'children', 'pos']],
                              key=lambda x: (node[x].get('pos', 999) if isinstance(node[x], dict) else 999))
            # Move nextpage entry to end of list
            if 'nextPage' in nodeKeys:
                nodeKeys.pop(nodeKeys.index('nextPage'))
                nodeKeys.append('nextPage')

        ft_exp = (2, 0, 1, 3, 0, 2)
        folderType = 0 if 'root' == path else 1
        folderTypeList = []
        for key in nodeKeys:
            if key in self._videodata:
                entry = deepcopy(self._videodata[key])
            else:
                entry = node[key]
            title = entry.get('title', nodeName)
            itemPathURI = '{}{}{}'.format(path, self._separator, quote_plus(key.encode('utf-8')))
            ctxitems = []

            # Squash single season tv shows
            try:
                if 'tvshow' == entry['metadata']['videometa']['mediatype']:
                    if 1 == len(entry['children']):
                        childgti = entry['children'][0]
                        entry = deepcopy(self._videodata[childgti])
                        itemPathURI += '{}{}'.format(self._separator, quote_plus(childgti.encode('utf-8')))
            except: pass

            # Find out if item's a video leaf
            infoLabel = {'title': title}

            try: bIsVideo = entry['metadata']['videometa']['mediatype'] in ['episode', 'movie', 'video']
            except: bIsVideo = False

            # Can we refresh the cache on this/these item(s)?
            bCanRefresh = ('ref' in entry) or ('lazyLoadURL' in entry)
            if ('children' in entry) and (0 < len(entry['children'])):
                bCanRefresh |= (0 < len([k for k in entry['children'] if (k in self._videodata) and ('ref' in self._videodata[k])]))

            if bIsVideo:
                infoLabel['contentType'] = 'live' if entry.get('live', False) else entry['metadata']['videometa']['mediatype']
            elif 'verb' in entry:
                url = entry['verb']
                itemPathURI = ''
            else:
                url = 'pv/browse/' + itemPathURI
            # Log('Encoded PrimeVideo URL: {}'.format(url), Log.DEBUG)

            if bCanRefresh and (0 < len(itemPathURI)):
                # Log('Encoded PrimeVideo refresh URL: pv/refresh/{}'.format(itemPathURI), Log.DEBUG)
                ctxitems.append((getString(30268), 'RunPlugin({}pv/refresh/{})'.format(self._g.pluginid, itemPathURI)))

            # In case of tv shows find the oldest season and apply its art
            try:
                if ('tvshow' == entry['metadata']['videometa']['mediatype']) and (1 < len(entry['children'])):
                    sn = None
                    snid = None
                    for child in entry['children']:
                        try:
                            childsn = self._videodata[child]['metadata']['videometa']['season']
                            if (None is sn) or (sn > childsn):
                                sn = childsn
                                snid = child
                        except: pass
                    if snid:
                        entry['metadata']['artmeta'] = self._videodata[snid]['metadata']['artmeta']
                        entry['metadata']['videometa']['cast'] = self._videodata[snid]['metadata']['videometa'].get('cast', [])
                        entry['metadata']['videometa']['plot'] = '{}\n\n{}'.format(getString(30253).format(len(entry['children'])),
                                                                                   self._videodata[snid]['metadata']['videometa'].get('plot', ''))  # "# series" as plot/description
            except: pass

            folder = True
            if 'metadata' in entry:
                m = entry['metadata']
                if 'artmeta' in m:
                    try:
                        if self._s.removePosters and ('episode' == m['videometa']['mediatype']):
                            del m['artmeta']['poster']
                    except: pass
                    infoLabel.update(m['artmeta'])
                if 'videometa' in m:
                    # https://codedocs.xyz/xbmc/xbmc/group__python__xbmcgui__listitem.html#ga0b71166869bda87ad744942888fb5f14
                    infoLabel.update(m['videometa'])
                    if bIsVideo:
                        folder = False
                        if 'runtime' in m:
                            infoLabel['duration'] = m['runtime']
                    try:
                        folderType = {'video': 0, 'movie': 5, 'episode': 4, 'tvshow': 2, 'season': 3}[m['videometa']['mediatype']]
                    except:
                        folderType = 2  # Default to category
                    if folderType in [5, 3, 2, 0]:
                        gtis = ','.join(entry['children']) if 'children' in entry else entry['metadata']['compactGTI']
                        in_wl = 1 if path.split('/')[:3] == ['root', 'Watchlist', 'watchlist'] else 0
                        ctxitems.append((getString(30180 + in_wl) % getString(self._g.langID[m['videometa']['mediatype']]),
                                         'RunPlugin({}pv/wltoogle/{}/{}/{})'.format(self._g.pluginid, path, quote_plus(gtis), in_wl)))
                        ctxitems.append((getString(30185) % getString(self._g.langID[m['videometa']['mediatype']]),
                                         'RunPlugin({}pv/browse/{}/export={})'.format(self._g.pluginid, itemPathURI, ft_exp[folderType] + 10)))
                        ctxitems.append((getString(30186), 'UpdateLibrary(video)'))

                if 'schedule' in m:
                    ts = time.time()
                    from datetime import datetime as dt
                    for sh in m['schedule']:
                        us = sh.get('start') / 1000
                        ue = sh.get('end') / 1000
                        if us <= ts <= ue:
                            shm = sh['metadata']
                            infoLabel['plot'] = '{:%H:%M} - {:%H:%M}  {}\n\n{}'.format(dt.fromtimestamp(us), dt.fromtimestamp(ue),
                                                                                       shm.get('title', ''), shm.get('synopsis', ''))
            else:
                ctxitems.append((getString(30271), 'RunPlugin({}pv/sethome/{})'.format(self._g.pluginid, quote_plus(itemPathURI))))
                if itemPathURI.split(self._separator)[-3:] == ['root', 'Watchlist', 'watchlist']:
                    ctxitems.append((getString(30185) % 'Watchlist', 'RunPlugin({}pv/browse/{}/export={})'.format(self._g.pluginid, itemPathURI, 4)))
                    ctxitems.append((getString(30186), 'UpdateLibrary(video)'))

            folderTypeList.append(folderType)
            # If it's a video leaf without an actual video, something went wrong with Amazon servers, just hide it
            if ('nextPage' == key) or (not folder) or (4 > folderType):
                if export and 4 == folderType and bIsVideo:
                    if 'episode' not in infoLabel or 'season' not in infoLabel or 'tvshowtitle' not in infoLabel or 'trailer' in infoLabel['title']:
                        break
                addVideo(title, key, infoLabel, cm=ctxitems, export=export) if bIsVideo else addDir(title, str(folder), url, infoLabel, cm=ctxitems)
                if export and folder:
                    self.Browse(itemPathURI, export=ft_exp[folderType])

        if not export:
            # Set sort method and view
            # leave folderType if its a single content list or use the most common foldertype for mixed content, except episodes or seasons (it will break sorting)
            folderType = folderType if 2 > len(set(folderTypeList)) else \
            sorted([(folderTypeList.count(x), x) for x in set(folderTypeList) if x not in [3, 4]], reverse=True)[0][1]
            # https://codedocs.xyz/xbmc/xbmc/group__python__xbmcplugin.html#ga85b3bff796fd644fb28f87b136025f40
            xbmcplugin.addSortMethod(self._g.pluginhandle, [
                xbmcplugin.SORT_METHOD_NONE,  # Root
                xbmcplugin.SORT_METHOD_NONE,  # Category list
                xbmcplugin.SORT_METHOD_NONE,  # Category
                xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE,  # TV Show (Seasons list)
                xbmcplugin.SORT_METHOD_EPISODE,  # Season (Episodes list)
                xbmcplugin.SORT_METHOD_NONE,  # Movies list
            ][0 if bNoSort or ('nextPage' in node) else folderType])

            folderType = 0 if 2 > folderType else folderType
            setContentAndView([None, 'videos', 'series', 'season', 'episode', 'movie'][folderType])
            xbmcplugin.endOfDirectory(self._g.pluginhandle, succeeded=True, cacheToDisc=False)
        elif maincall:
            writeConfig('exporting', '')
            Log('Export finished')

    def Search(self, searchString=None):
        """ Provide search functionality for PrimeVideo """
        if searchString is None:
            searchString = self._g.dialog.input(getString(24121)).strip(' \t\n\r')
        if 0 == len(searchString):
            xbmcplugin.endOfDirectory(self._g.pluginhandle, succeeded=False)
            return
        Log('Searching "{}"…'.format(searchString), Log.INFO)
        self._catalog['search'] = OrderedDict([('lazyLoadURL', self._catalog['root']['Search']['endpoint'].format(searchString))])
        self.Browse('search', True)

    def Refresh(self, path, bRefreshVideodata=True, busy=True):
        """ Provides cache refresh functionality """

        refreshes = []
        node, breadcrumb = self._TraverseCatalog(path, True)
        if None is node:
            return

        # Only refresh if previously loaded. If not loaded, and specifically asked, perform a full (lazy) loading
        k = breadcrumb[-1]
        if (k not in node) and (k in self._videodata):
            node[k] = {}

        if ('lazyLoadURL' in node[k]) or ('lazyLoadData' in node[k]):
            refreshes.append((node[k], breadcrumb, False))
        else:
            bShow = False
            if 'ref' in node[k]:  # ref's in the cache already
                Log('Refreshing element in the cache: {}'.format(k), Log.DEBUG)
                targetURL = node[k]['ref']
            elif 'ref' in self._videodata[k]:  # Season
                Log('Refreshing season: {}'.format(k), Log.DEBUG)
                targetURL = self._videodata[k]['ref']
            else:  # TV Show
                Log('Refreshing Show: {}'.format(k), Log.DEBUG)
                bShow = True
                for season in [l for l in self._videodata[k]['children'] if (l in self._videodata) and ('ref' in self._videodata[l])]:
                    if (season in node[k]) and ('lazyLoadURL' in node[k][season]):
                        bRefresh = False
                    else:
                        bRefresh = bRefreshVideodata
                        node[k][season] = {'lazyLoadURL': self._videodata[season]['ref']}
                    refreshes.append((node[k][season], breadcrumb + [season], bRefresh))

            if not bShow:
                # Reset the basic metadata
                title = node[k]['title'] if 'title' in node[k] else None
                node[k] = {'lazyLoadURL': targetURL}
                if title:
                    node[k]['title'] = title
                refreshes.append((node[k], breadcrumb, bRefreshVideodata))

        from contextlib import contextmanager

        @contextmanager
        def _busy_dialog():
            if busy:
                xbmc.executebuiltin('ActivateWindow(busydialognocancel)')
            try:
                yield
            finally:
                xbmc.executebuiltin('Dialog.Close(busydialognocancel)')

        with _busy_dialog():
            for r in refreshes:
                Log('Refresh params: {}'.format(r))
                self._LazyLoad(r[0], r[1], r[2])

    def _LazyLoad(self, obj, breadcrumb=None, bCacheRefresh=False):
        """ Loader and parser of all the PrimeVideo.com queries """

        def MaxSize(imgUrl):
            """ Strip the dynamic resize triggers from the URL (and other effects, such as blur) """

            return re.sub(r'\._.*_\.', '.', imgUrl)

        def ExtractURN(url):
            """ Extract the unique resource name identifier """

            ret = self._reURN.search(url)
            return None if not ret else ret.group(1)

        def DelocalizeDate(lang, datestr):
            """ Convert language based timestamps into YYYY-MM-DD """

            if lang not in self._dateParserData:
                Log('Unable to decode date "{}": language "{}" not supported'.format(datestr, lang), Log.DEBUG)
                return datestr

            # Try to decode the date as localized format
            try:
                p = self._dateParserData[lang]['deconstruct'].search(datestr.lower())
            except: pass
            # Sometimes the date is returned with an american format and/or not localized
            if None is p:
                try:
                    p = self._dateParserData['generic'].search(datestr.lower())
                except: pass
                if (None is p) or ('en_US' == lang):
                    Log('Unable to parse date "{}" with language "{}": format changed?'.format(datestr, lang), Log.DEBUG)
                    return datestr

            # Get rid of the Match object
            p = {'d': p.group('d'), 'm': p.group('m'), 'y': p.group('y')}

            # Convert the month into an integer or die trying
            if p['m'].isdigit():
                p['m'] = int(p['m'])
            else:
                # Since they're inept, try with asiatic numeric months first
                try:
                    p['m'] = int(self._dateParserData['asianMonthExtractor'].match(p['m'])[1])
                except: pass

                def MonthToInt(langCode):
                    # Try the conversion against localized full month name
                    try:
                        p['m'] = self._dateParserData[langCode]['months'][p['m']]
                    except:
                        if 'months' in self._dateParserData[langCode]:
                            # Try to treat the month name as shortened
                            for monthName in self._dateParserData[langCode]['months']:
                                if monthName.startswith(p['m']):
                                    p['m'] = self._dateParserData[langCode]['months'][monthName]
                                    break

                # Delocalize date with the provided locale
                if not isinstance(p['m'], int):
                    MonthToInt(lang)

                # If all else failed, try en_US if applicable
                if (not isinstance(p['m'], int)) and ('en_US' != lang):
                    Log('Unable to parse month "{}" with language "{}": trying english'.format(datestr, lang), Log.DEBUG)
                    MonthToInt('en_US')

                # (╯°□°）╯︵ ┻━┻
                if not isinstance(p['m'], int):
                    Log('Unable to parse month "{}" with any known language combination'.format(datestr), Log.WARNING)
                    return datestr

            # Reassemble (YYYY-MM-DD)
            return '{0}-{1:0>2}-{2:0>2}'.format(p['y'], p['m'], p['d'])

        def NotifyUser(msg, bForceDisplay=False):
            """ Pop up messages while scraping to inform users of progress """

            if not hasattr(NotifyUser, 'lastNotification'):
                NotifyUser.lastNotification = 0
            if bForceDisplay or (NotifyUser.lastNotification < time.time()):
                # Only update once every other second, to avoid endless message queue
                NotifyUser.lastNotification = 1 + time.time()
                self._g.dialog.notification(self._g.addon.getAddonInfo('name'), msg, time=1000, sound=False)

        def AddLiveTV(o, item):
            """ Add a direct playable live TV channel to the list """
            if 'channelId' in item:
                chid = item['channelId']
                if chid in o:
                    return
                o[chid] = {'metadata': {'artmeta': {}, 'videometa': {'mediatype': 'video'}}, 'live': True, 'pos': len(o)}
                if 'station' in item:
                    title = item['station']['name']
                    o[chid]['metadata']['schedule'] = item['station'].get('schedule', {})
                elif 'playbackAction' in item:
                    title = item['playbackAction']['label']
                else:
                    title = item['title']

                o[chid]['title'] = title
                o[chid]['metadata']['videometa']['plot'] = title + ('\n\n' + item['synopsis'] if 'synopsis' in item else '')
                o[chid]['metadata']['artmeta']['poster'] = o[chid]['metadata']['artmeta']['thumb'] = MaxSize(item['image']['url'])
                o[chid]['metadata']['compactGTI'] = ExtractURN(item['playbackAction']['fallbackUrl']) if 'playbackAction' in item else chid

        def AddLiveEvent(o, item, url):
            urn = ExtractURN(url)
            """ Add a live event to the list """
            if urn in o:
                return
            title = return_value(item, 'title' if 'title' in item else 'heading', 'text')
            liveInfo = item.get('liveInfo', item.get('liveEvent', {}))
            liveStat = liveInfo.get('status', liveInfo.get('liveStateType', '')).lower() == 'live'
            liveTime = liveInfo.get('timeBadge', liveInfo.get('dateTime'))
            o[urn] = {'title': title, 'lazyLoadURL': url,
                      'metadata': {'artmeta': {}, 'videometa': {'mediatype': 'video'}}, 'live': liveStat, 'pos': len(o)}
            o[urn]['metadata']['compactGTI'] = ExtractURN(item['playbackAction']['fallbackUrl']) if 'playbackAction' in item else urn
            when = ''
            if liveTime or liveStat:
                when = 'Live' if not liveTime else liveTime
                if 'venue' in liveInfo:
                    when = '{} @ {}'.format(when, liveInfo['venue'])
                when += '\n\n'
            o[urn]['metadata']['videometa']['plot'] = when + return_value(item, 'synopsis', 'text')
            if 'imageSrc' in item:
                o[urn]['metadata']['artmeta']['thumb'] = MaxSize(item['imageSrc'])
            elif 'image' in item and 'url' in item['image']:
                o[urn]['metadata']['artmeta']['thumb'] = MaxSize(item['image']['url'])
            elif key_exists(item, 'packshot', 'image', 'src'):
                o[urn]['metadata']['artmeta']['thumb'] = MaxSize(item['packshot']['image']['src'])

        def AddSeason(oid, o, bCacheRefresh, url):
            """ Given a season, adds TV Shows to the catalog """
            urn = ExtractURN(url)
            parent = None
            season = {}
            bUpdatedVideoData = False
            if bCacheRefresh or (urn not in self._videodata['urn2gti']):
                # Find the show the season belongs to
                url += ('' if 'episodeListSize' in url else ('&' if '?' in url else '?') + 'episodeListSize=9999')
                bUpdatedVideoData |= ParseSinglePage(oid, season, bCacheRefresh, url=url)
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
                parent = self._videodata[self._videodata['urn2gti'][urn]].get('parent')
            bSeasonOnly = (not parent) or (oid == parent)
            if not bSeasonOnly:
                o[parent] = deepcopy(self._videodata[parent])
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
                        o[gti] = deepcopy(self._videodata[gti])
                        dest = o[gti]
                    else:
                        o = deepcopy(self._videodata[gti])
                        dest = o
                    # Add cached episodes
                    for c in dest['children']:
                        if c not in dest:
                            dest[c] = {}
                return False

            if url:
                url = FQify(url)
            if not data:
                if not url:
                    return False
                data = GrabJSON(url)
                if not data:
                    NotifyUser(getString(30256), True)
                    Log('Unable to fetch the url: {}'.format(url), Log.ERROR)
                    return False

            # Video/season/movie data are in the `state` field of the response
            if 'state' not in data:
                return False

            state = data['state']  # Video info
            GTIs = []  # List of inserted GTIs
            parents = {}  # Map of parents
            bUpdated = False  # Video data updated

            # Find out if it's a live event. Custom parsing rules apply
            if oid not in state['self']:
                res = [x for x in state['self'] if oid in (state['self'][x]['compactGTI'] if self._g.UsePrimeVideo else state['self'][x]['asins'])]
                if len(res) > 1:
                    oid = res[0]

            if ('self' in state) and (oid in state['self']) and ('event' == state['self'][oid]['titleType'].lower()):
                # List of video streams
                items = [oid]
                for i in state['collections'][oid]:
                    if i['collectionType'] not in ['schedule', 'highlights']:
                        continue
                    for id in i['titleIds']:
                        if id not in items:
                            items.append(id)
                items = {v: i for i, v in enumerate(items)}

                details = state['detail']
                if 'detail' in details:
                    details = details['detail']
                if 'headerDetail' in state['detail']:
                    details.update(state['detail']['headerDetail'])
                    del state['detail']['headerDetail']
                if 'btfMoreDetails' in state['detail']:
                    del state['detail']['btfMoreDetails']

                # Add video streams in order
                for vid, i in sorted(details.items(), key=lambda t: 9999 if t[0] not in items else items[t[0]]):
                    if (vid in o) or (vid not in items):
                        continue
                    if vid in state['buyboxTitleId']:
                        vid = state['buyboxTitleId'][vid]
                        if vid in o:
                            continue

                    o[vid] = {'title': i['title'], 'metadata': {'compactGTI': i.get('compactGti', i.get('catalogId', vid)),
                                                                'artmeta': {}, 'videometa': {'mediatype': 'video'}}}

                    if 'liveState' in i:
                        try:
                            mats = state['action']['atf'][oid]['playbackActions']['main']['children']
                            mats = [a['videoMaterialType'].lower() for a in mats if vid == a['playbackID']]
                            if 'live' in mats:
                                o[vid]['live'] = True
                        except: pass

                    # Date and synopsis as a unified synopsis
                    synopsis = None if 'synopsis' not in i else i['synopsis']
                    datetime = None if 'pageDateTimeBadge' not in i else i['pageDateTimeBadge']
                    if not datetime:
                        datetime = datetime if 'dateTimeBadge' not in i else i['dateTimeBadge']
                    if datetime:
                        synopsis = ('{0}\n{1}' if synopsis else '{0}').format(datetime, synopsis)
                    if synopsis:
                        o[vid]['metadata']['videometa']['plot'] = synopsis

                    # Images
                    if 'images' in i:
                        for k, v in {'thumb': 'packshot', 'poster': 'covershot', 'fanart': 'heroshot'}.items():
                            if v in i['images']:
                                o[vid]['metadata']['artmeta'][k] = i['images'][v]

                return False

            # Seasons (episodes are now listed in self too)
            # Only add seasons if we are not inside a season already
            if ('self' in state) and (oid not in state['self']):
                # "self": {"amzn1.dv.gti.[…]": {"gti": "amzn1.dv.gti.[…]", "link": "/detail/[…]"}}
                for gti in [k for k in state['self'] if 'season' == state['self'][k]['titleType'].lower()]:
                    s = state['self'][gti]
                    gti = s['gti'] if self._g.UsePrimeVideo else gti
                    if gti not in self._videodata:
                        o[gti] = {('ref' if state['pageTitleId'] == gti else 'lazyLoadURL'): s['link']}
                        self._videodata[gti] = {'ref': s['link'], 'children': [], 'siblings': []}
                        bUpdated = True
                    else:
                        # Season might be initialized with raw data first, make sure to add the necessary basics
                        for k, v in {'ref': s['link'], 'children': [], 'siblings': []}.items():
                            if k not in self._videodata[gti]:
                                self._videodata[gti][k] = v
                                bUpdated = True
                        o[gti] = deepcopy(self._videodata[gti])
                    GTIs.append(gti)
                    siblings = [k for k, ss in state['self'].items() if k != gti and ss['titleType'].lower() == s['titleType'].lower()]
                    if siblings != self._videodata[gti]['siblings']:
                        self._videodata[gti]['siblings'] = siblings
                        bUpdated = True

            # Episodes lists
            if 'collections' in state:
                # "collections": {"amzn1.dv.gti.[…]": [{"titleIds": ["amzn1.dv.gti.[…]", "amzn1.dv.gti.[…]"]}]}
                for gti, lc in state['collections'].items():
                    for le in lc:
                        for e in le['titleIds']:
                            GTIs.append(e)
                            # Save parent/children relationships
                            parents[e] = gti
                            if gti in self._videodata and e not in self._videodata[gti]['children']:
                                self._videodata[gti]['children'].append(e)
                                bUpdated = True

            # Video info
            if 'detail' not in state:
                return bUpdated

            if urn not in self._videodata['urn2gti']:
                self._videodata['urn2gti'][urn] = state['pageTitleId']

            # Both of these versions have been spotted in the wild
            # { "detail": { "headerDetail": {…}, "amzn1.dv.gti.[…]": {…} }
            # { "detail": { "detail": { "amzn1.dv.gti.[…]": {…} }, "headerDetail": {…} } }
            details = state['detail']
            if 'detail' in details:
                details = details['detail']
            # headerDetail contains sometimes gtis/asins, which are not included in details
            if 'headerDetail' in state['detail']:
                details.update(state['detail']['headerDetail'])
                del state['detail']['headerDetail']
            if 'btfMoreDetails' in state['detail']:
                del state['detail']['btfMoreDetails']

            # Get details, seasons first
            # WARNING: seasons may not have proper initialization at this stage
            for gti in sorted(details, key=lambda x: 'season' != details[x]['titleType'].lower()):
                # not inside a season/show: (oid not in details)
                #     not already appended: (gti not in GTIs)
                # part of the page details: ('self' in state) & (gti in state['self'])
                if (oid not in details) and (gti not in GTIs) and ('self' in state) and (gti in state['self']):
                    GTIs.append(gti)
                    o[gti] = {}
                if gti not in self._videodata:
                    self._videodata[gti] = {}
                vd = self._videodata[gti]

                # Meta prep
                if 'metadata' not in vd:
                    vd['metadata'] = {'compactGTI': urn, 'artmeta': {}, 'videometa': {}}
                    bUpdated = True
                if 'artmeta' not in vd['metadata']:
                    vd['metadata']['artmeta'] = {}
                    bUpdated = True
                if 'videometa' not in vd['metadata']:
                    vd['metadata']['videometa'] = {}
                    bUpdated = True

                # Parent
                if gti in parents:
                    vd['parent'] = parents[gti]
                    bUpdated = True

                item = details[gti]  # Shortcut

                # Title
                if bCacheRefresh or ('title' not in vd):
                    if item['titleType'].lower() == 'season' and 'seasonNumber' in item:
                        try:
                            vd['title'] = data['strings']['AVOD_DP_season_selector'].format(seasonNumber=item['seasonNumber'])
                        except:
                            vd['title'] = '{} {}'.format(getString(30167), item['seasonNumber'])
                    else:
                        vd['title'] = self._BeautifyText(item['title'])
                    bUpdated = True

                # Images
                for k, v in {'thumb': 'packshot', 'poster': 'titleshot', 'fanart': 'heroshot'}.items():
                    if (bCacheRefresh or (k not in vd['metadata']['artmeta'])) and \
                       ('images' in item) and (v in item['images']) and item['images'][v]:
                        vd['metadata']['artmeta'][k] = item['images'][v]
                        bUpdated = True

                # Mediatype
                if (bCacheRefresh or ('mediatype' not in vd['metadata']['videometa'])) and ('titleType' in item) and item['titleType']:
                    vd['metadata']['videometa']['mediatype'] = item['titleType'].lower()
                    bUpdated = True

                # Synopsis, media type, year, duration
                for k, v in {'plot': 'synopsis', 'year': 'releaseYear', 'duration': 'duration'}.items():
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
                    for k, v in OrderedDict([('directors', 'director'), ('starringActors', 'cast'), ('supportingActors', 'cast')]).items():
                        if k in item['contributors']:
                            for p in item['contributors'][k]:
                                if 'name' in p:
                                    try:
                                        if p['name'] not in vd['metadata']['videometa'][v]:
                                            vd['metadata']['videometa'][v].append(p['name'])
                                    except KeyError:
                                        vd['metadata']['videometa'][v] = [p['name']]
                                    bUpdated = True

                # Season, TV show title
                if ('seasonNumber' in item) and item['seasonNumber']:
                    if bCacheRefresh or ('season' not in vd['metadata']['videometa']):
                        vd['metadata']['videometa']['season'] = item['seasonNumber']
                        bUpdated = True
                    if bCacheRefresh or ('tvshowtitle' not in vd['metadata']['videometa']):
                        try:
                            vd['metadata']['videometa']['tvshowtitle'] = item['parentTitle']
                            bUpdated = True
                        except: pass

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
                            vd['metadata']['videometa']['tvshowtitle'] = self._videodata[vd['parent']]['metadata']['videometa']['tvshowtitle']
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

        if ('lazyLoadURL' not in obj) and ('lazyLoadData' not in obj):
            return
        requestURLs = [obj['lazyLoadURL'] if 'lazyLoadURL' in obj else None]

        try:
            from urllib.parse import urlencode
        except:
            from urllib import urlencode

        # Find the locale set in the cookies
        amzLang = None
        cj = MechanizeLogin()
        if cj:
            if self._g.UsePrimeVideo:
                amzLang = cj.get('lc-main-av', path='/')
            else:
                # after first language change lc-acb(de/uk) cookie gets stored
                cval = [v for k, v in cj.items() if 'lc-acb' in k]
                if cval:
                    amzLang = cval[0]
                else:
                    i18 = {'EUR': 'de_DE', 'GBP': 'en_GB', 'JPY': 'ja_JP', 'USD': 'en_US'}
                    pref = cj.get('i18n-prefs', path='/')
                    if pref:
                        amzLang = i18.get(pref)

        amzLang = amzLang if amzLang else 'en_US'

        bUpdatedVideoData = False  # Whether or not the pvData has been updated
        pageNumber = 1  # Page number

        while 0 < len(requestURLs):
            requestURL = requestURLs.pop(0)  # rURLs: FIFO stack
            o = obj

            # Too many instances to track, append the episode finder to about every query and cross fingers
            if requestURL is not None:
                requestURL += ('' if 'episodeListSize' in requestURL else ('&' if '?' in requestURL else '?') + 'episodeListSize=9999')

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
                        bUpdatedVideoData |= ParseSinglePage(breadcrumb[-1], o, bCacheRefresh, url=requestURL)
                        if 'lazyLoadURL' in o:
                            if 'ref' not in o:
                                o['ref'] = o['lazyLoadURL']
                            del o['lazyLoadURL']
                        continue
                    else:
                        cnt = GrabJSON(requestURL)

                # Don't switch direct action for reference until we have content to show for it
                if cnt and ('lazyLoadURL' in o):
                    if 'ref' not in o:
                        o['ref'] = o['lazyLoadURL']
                    del o['lazyLoadURL']
            except:
                bCouldNotParse = True
            if bCouldNotParse or (not cnt):
                self._g.dialog.notification(getString(30251), requestURL[:48], xbmcgui.NOTIFICATION_ERROR)
                Log('Unable to fetch the url: {}'.format(requestURL), Log.ERROR)
                continue

            # Submenus
            mmpos = [len(breadcrumb)-i for i, x in enumerate(breadcrumb) if 'mmlinks' in x]
            if len(mmpos) > 0 and (mmpos[0] == 1 or (mmpos[0] == 2 and 'genres' in breadcrumb[-1])):
                catid = ''
                for link in cnt['lists']['mainMenuLinks']:
                    for lk in link.get('links', []):
                        if 'heading' in lk.get('features', ''):
                            catid = lk['id']
                            if mmpos[0] == 1 and 'genres' in catid:
                                o[lk['id']] = \
                                    {'title': self._BeautifyText(lk['text']), 'lazyLoadURL': lk['href'], 'lazyLoadData': cnt, 'pos': len(o)}
                            continue
                        if (mmpos[0] == 2 and catid in breadcrumb[-1]) or (mmpos[0] == 1 and 'categories' in catid):
                            o[lk['id']] = {'title': self._BeautifyText(lk['text']), 'lazyLoadURL': lk['href'], 'pos': len(o)}
                cnt = ''
            # Categories
            elif 'collections' in cnt or 'containers' in cnt:
                var = 'collection' if len(cnt.get('collections', [])) > 0 else 'container'
                filtered_col = [x for x in cnt[var + 's'] if x[var + 'Type'].lower() not in ['chartscarousel', 'standardhero', 'textcontainer', 'superhero', 'tentpolehero']]
                if len(filtered_col) > 1:
                    for collection in filtered_col:
                        if 'text' in collection:
                            txt = collection['text']
                            if ('Channels' in breadcrumb[-1] or findKey("channelId", collection)) \
                                    and 'facet' in collection and collection['facet'].get('alternateText'):
                                txt = '{} - {}'.format(collection['facet']['alternateText'], txt)
                            id = txt
                            o[id] = {'title': self._BeautifyText(txt), 'pos': len(o)}
                            if 'seeMoreLink' in collection:
                                o[id]['lazyLoadURL'] = collection['seeMoreLink']['url']
                            elif 'paginationTargetId' in collection:
                                q = ['{}={}'.format(k.replace('paginationServiceToken', 'serviceToken'), ','.join(v) if isinstance(v, list) else quote_plus(v))
                                     for k, v in collection.items() if k in ['collectionType', 'paginationServiceToken', 'paginationTargetId', 'tags']]
                                q.append('startIndex=0&pageSize=20&pageType=home&pageId=home')
                                if 'collectionType' not in q:
                                    q.append('collectionType=Container')
                                if var == 'collection':
                                    q.append('&facetType=' + collection['facet']['facetType'])
                                o[id]['lazyLoadURL'] = '/gp/video/api/paginateCollection?' + '&'.join(q)
                            else:
                                o[id]['lazyLoadData'] = collection
                        elif 'items' in collection:
                            # LiveTV
                            for item in collection['items']:
                                AddLiveTV(o, item)
                elif len(filtered_col) == 1:
                    cnt = filtered_col[0]
            # MyStuff
            wl_lib = 'legacy-' + breadcrumb[2] if ['root', 'Watchlist'] == breadcrumb[:2] and len(breadcrumb) > 2 and not breadcrumb[2].startswith('ms_') else ''
            vo = ''
            if ['root', 'Watchlist'] == breadcrumb:
                if 'subNodes' in cnt:
                    for f in cnt['subNodes']:
                        id = f['id'].replace('pv-nav-my-stuff-', '').lower()
                        if 'all' not in id:
                            o[id] = {'title': f['label'], 'lazyLoadURL': f['url'], 'pos': len(o)}
                elif 'viewOutput' in cnt:
                    wl = return_item(cnt, 'viewOutput', 'features', 'view-filter')
                    for f in wl['filters']:
                        o[f['viewType']] = {'title': f['text'], 'lazyLoadURL': f['apiUrl' if 'apiUrl' in f else 'href'], 'pos': len(o)}
                        if f.get('active', False):
                            o[f['viewType']]['lazyLoadData'] = cnt
                else:
                    for f in cnt['content']['baseOutput']['containers']:
                        o['ms_{}'.format(len(o))] = {'title': f['text'], 'lazyLoadURL': f['seeMoreLink']['url'], 'pos': len(o)}
            # MyStuff categories
            elif len(wl_lib) > 0 and len(breadcrumb) == 3:
                if 'viewOutput' in cnt:
                    wl = return_item(cnt, 'viewOutput', 'features', wl_lib)
                else:
                    wl = {'filters': x['values'] for x in return_item(cnt, 'content', 'baseOutput', 'filters', 'items') if isinstance(x, dict) and 'OFFER_FILTER' in x['id']}
                for f in wl.get('filters', []):
                    id = f['id'].lower()
                    url = f.get('apiUrl', f.get('href'))
                    url = ('/' + id + '/').join(requestURL.rsplit('/', 1)) if url is None else url
                    o[id] = {'title': f['text'], 'lazyLoadURL': url, 'pos': len(o)}
                    if f.get('applied') or f.get('isCurrentlyApplied'):
                        o[id]['lazyLoadData'] = cnt
            else:
                vo = cnt['results'] if 'results' in cnt else return_item(cnt, 'viewOutput', 'features', wl_lib, 'content')
                vo = return_item(vo, 'content', 'baseOutput', 'containers')
                if isinstance(vo, list):
                    vo = vo[0]
                items = vo.get('entities', []) + vo.get('items', []) + vo.get('content', {}).get('items', [])
                for item in items:
                    tile = return_value(item, 'image', 'alternateText')
                    tile_cov = item.get('image', {})
                    if isinstance(tile, dict) and item.get('widgetType', '').lower() == 'imagetextlink':
                        tile = item.get('title', item.get('displayTitle'))
                        tile_cov = item.get('images', {})
                    else:
                        tile = None
                    if 'heading' in item or 'title' in item or tile:
                        oldk = list(o)
                        try:
                            iu = item['href'] if 'href' in item else item['link' if 'link' in item else 'title']['url']
                        except:
                            iu = None
                        try:
                            wl = 'watchlistAction' if 'watchlistAction' in item else 'watchlistButton'
                            t = item[wl]['endpoint']['query']['titleType'].lower()
                        except:
                            t = ''
                        if 'station' in item:
                            AddLiveTV(o, item)
                        elif tile and iu:
                            id = 'tile_{}'.format(len(o))
                            o[id] = {'title': tile, 'lazyLoadURL': iu, 'metadata': {'artmeta': {'thumb': findKey('url', tile_cov)}}}
                        elif ('liveInfo' in item) or ('event' == t):
                            AddLiveEvent(o, item, iu)
                        elif 'season' != t and 'season' not in item:
                            bUpdatedVideoData |= ParseSinglePage(breadcrumb[-1], o, bCacheRefresh, url=iu)
                        else:
                            bUpdatedVideoData |= AddSeason(breadcrumb[-1], o, bCacheRefresh, iu)

                        newitem = list(set(list(o)) - set(oldk))
                        if newitem:
                            o[newitem[0]]['pos'] = len(o)

                # Single page
                bSinglePage = False
                if 'state' in cnt:
                    bSinglePage = True
                    bUpdatedVideoData |= ParseSinglePage(breadcrumb[-1], o, bCacheRefresh, data=cnt, url=requestURL)
                # Pagination
                if ('pagination' in cnt) or (key_exists(cnt, 'viewOutput', 'features', wl_lib, 'content', 'seeMoreHref'))\
                        or ('hasMoreItems' in cnt) or ('paginationTargetId' in vo):
                    nextPage = None
                    try:
                        # Dynamic AJAX pagination
                        seeMore = cnt['viewOutput']['features'][wl_lib]['content']
                        if seeMore['nextPageStartIndex'] < seeMore['totalItems']:
                            nextPage = seeMore['seeMoreHref']
                    except:
                        # Classic numbered pagination
                        if 'pagination' in cnt:
                            if 'url' in cnt['pagination'] and cnt['pagination']['url'] != '':
                                nextPage = cnt['pagination']['url']  # + '&isCrow=0&isElcano=0&isCleanSlateActive=1&isLivePageActive=0&isDiscoverActive=1'
                            elif 'paginator' in cnt['pagination']:
                                nextPage = next((x['href'] for x in cnt['pagination']['paginator'] if
                                                 (('type' in x) and ('NextPage' == x['type'])) or
                                                 (('*className*' in x) and ('atv.wps.PaginatorNext' == x['*className*'])) or
                                                 (('__type' in x) and ('PaginatorNext' in x['__type']))), None)
                            elif 'queryParameters' in cnt['pagination']:
                                q = cnt['pagination']['queryParameters']
                                q = {k.replace('content', 'page').replace('targetId', 'paginationTargetId') if k in ['contentId', 'contentType', 'targetId']
                                     else k: v for k, v in q.items()}
                                if 'collectionType' not in q:
                                    q['collectionType'] = 'Container'
                                nextPage = '/gp/video/api/paginateCollection?' + urlencode(q)
                        elif cnt.get('hasMoreItems', False) and 'startIndex=' in requestURL:
                            idx = int(re.search(r'startIndex=(\d*)', requestURL).group(1))
                            nextPage = requestURL.replace('startIndex={}'.format(idx), 'startIndex={}'.format(idx+20))
                        elif 'paginationTargetId' in vo:
                            q = ['{}={}'.format(k.replace('paginationServiceToken', 'serviceToken').replace('paginationStartIndex', 'startIndex'), ','.join(v) if isinstance(v, list) else quote_plus(str(v)))
                                 for k, v in vo.items() if k in ['collectionType', 'paginationServiceToken', 'paginationTargetId', 'tags', 'paginationStartIndex']]
                            q.append('pageSize=20&pageType=browse&pageId=default')
                            if 'collectionType' not in q:
                                q.append('collectionType=Container')
                            nextPage = '/gp/video/api/paginateCollection?' + '&'.join(q)

                    if nextPage:
                        # Determine if we can auto page
                        p = self._s.pagination
                        bAutoPaginate = True
                        preloadPages = 2 if (p['all'] or p['collections']) else 10
                        # Always autoload episode list
                        if bSinglePage:
                            pass
                        # Auto pagination if not disabled for Search and Watchlist
                        elif 'search' == breadcrumb[0]:  # /search/*
                            bAutoPaginate = not (p['all'] or p['search'])
                        elif 'Watchlist' == breadcrumb[1]:  # /root/watchlist/*
                            bAutoPaginate = not (p['all'] or p['watchlist'])
                        # Always auto load category lists for pv, on tld load only 10 pages at most, then paginate if appropriate
                        elif (2 < len(breadcrumb) and (p['all'] or p['collections'])) if self._g.UsePrimeVideo else pageNumber >= preloadPages:
                            bAutoPaginate = False

                        if bAutoPaginate:
                            requestURLs.append(nextPage)
                        else:
                            # Insert pagination folder
                            o['nextPage'] = {'title': getString(30267), 'lazyLoadURL': nextPage, 'metadata': {'artmeta': {'thumb': self._s.NextIcon}}}

            # Notify new page
            if 0 < len(requestURLs):
                if (0 == (pageNumber % 5)) and bUpdatedVideoData:
                    self._Flush(bFlushCacheData=False, bFlushVideoData=True)
                    bUpdatedVideoData = False
                pageNumber += 1
                NotifyUser(getString(30252).format(pageNumber))

        # Flush catalog and data
        self._Flush(bFlushVideoData=bCacheRefresh or bUpdatedVideoData)