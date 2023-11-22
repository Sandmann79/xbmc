#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import json

from .common import Globals, Settings, get_user_lang
from .logging import Log, LogJSON
from .network import getURL
from .configs import getConfig, writeConfig

try:
    from urllib.parse import quote_plus
except ImportError:
    from urllib import quote_plus


class Artwork:
    def __init__(self):
        self._g = Globals()
        self._s = Settings()

    def getTVDBImages(self, title, year=None, tvdb_id=None):
        import time
        headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}
        art_ids = {1: 'banner', 2: 'poster', 3: 'fanart', 6: 'banner', 7: 'poster', 8: 'fanart'}
        artwork = data = {}
        season_ids = {-1: {}}

        def _gen_token():
            data = getURL('https://api4.thetvdb.com/v4/login', headers=headers, postdata=json.dumps({'apikey': self._g.tvdb}))
            if data['status'] == 'success':
                Log('TVDB Token updated successful')
                token = data['data']
                token['time'] = time.time() * 86400 * 30  # 30 days in the future
                writeConfig('tvdb_token', json.dumps(token))
                return token
            Log('TVDB Token update failed')
            return {}

        Log('searching fanart for %s at thetvdb.com' % title.upper())
        splitter = [' - ', ': ', ', ']

        token = json.loads(getConfig('tvdb_token', '{}'))
        if token.get('token') is None or token['time'] < time.time():
            token = _gen_token()
        if token.get('token') is None:
            return artwork
        headers.update({'Authorization': 'Bearer ' + token['token']})

        while not tvdb_id and title:
            str_year = '&year=' + str(year) if year else ''
            tv = quote_plus(title.encode('utf-8'))
            data = getURL('https://api4.thetvdb.com/v4/search?query={}{}&type=series'.format(tv, str_year), silent=True, headers=headers)['data']
            if len(data) == 0:
                if year:
                    year = 0
                else:
                    oldtitle = title
                    for splitchar in splitter:
                        if title.count(splitchar):
                            title = title.split(splitchar)[0]
                            break
                    if title == oldtitle:
                        break
            else:
                data = data[0]
                tvdb_id = data.get('tvdb_id')

        if not tvdb_id:
            return artwork

        result = getURL('https://api4.thetvdb.com/v4/series/{}/extended'.format(tvdb_id), silent=True, headers=headers)['data']
        if not result:
            return artwork

        languages = [get_user_lang(iso6392=True), 'eng', data.get('primary_language')]

        for season in result['seasons']:
            season_ids[season['id']] = season['number']

        for art in result['artworks']:
            if art.get('seasonId', -1) in season_ids and art['type'] in art_ids:
                s = season_ids[art['seasonId']] if art['type'] > 5 else -1
                if artwork.get(s) is None:
                    artwork[s] = {}
                if art['language'] in languages:
                    best = artwork[s].get(art_ids[art['type']], art)
                    idx = languages.index(art['language'])
                    if 'idx' in best:
                        if idx < best['idx'] or (art['height'] > best['height'] and idx == best['idx']) or (art['height'] == best['height'] and idx == best['idx'] and art['score'] > best['score']):
                            best = art
                    if not 'idx' in best:
                        best.update({'idx': idx})
                        artwork[s][art_ids[art['type']]] = best

        for s, v in artwork.items():
            for a in v:
                artwork[s][a] = artwork[s][a]['image']
        if 'overviews' in data:
            if not -1 in artwork:
                artwork[-1] = {}
            artwork[-1]['plot'] = data['overviews'][[l for l in languages if l in data['overviews']][0]]
        return artwork

    def getTMDBImages(self, title, content='movie', year=None, season=0):
        Log('searching fanart for %s at tmdb.com' % title.upper())
        tmdb_id = None
        splitter = [' - ', ': ', ', ']
        TMDB_URL = 'http://image.tmdb.org/t/p/original'
        titleorg = title
        headers = {'accept': 'application/json', 'Accept-Encoding': ''}
        lang = get_user_lang().replace('_', '-')
        artwork = {season: {}, -1: {}}

        while not tmdb_id and title:
            str_year = '&primary_release_year=' + str(year) if year else ''
            movie = quote_plus(title.encode('utf-8'))
            data = getURL('http://api.themoviedb.org/3/search/%s?api_key=%s&language=%s&query=%s%s' % (
                content, self._g.tmdb, lang, movie, str_year), silent=True, headers=headers)
            if not data:
                continue

            if data.get('total_results', 0) > 0:
                result = data['results'][0]
                tmdb_id = result.get('id')
                dic = season
                if result.get('backdrop_path'):
                    artwork[dic]['fanart'] = TMDB_URL + result['backdrop_path']
                if season > 0:
                    data = getURL('https://api.themoviedb.org/3/tv/{}/season/{}/images?api_key={}&include_image_language={}%2Cen'.format(
                        tmdb_id, season, self._g.tmdb, lang.split('-')[0]), silent=True, headers=headers)
                    pos = data.get('posters', [])
                    if len(pos) > 0:
                        f_lang = pos[0]['iso_639_1']
                        best = {}
                        for p in pos:
                            if p.get('height', 0) >= best.get('height', 0) and p.get('vote_average', 0) > best.get('vote_average', -1) and f_lang == p['iso_639_1']:
                                best = p
                        artwork[dic]['poster'] = TMDB_URL + best['file_path']
                        dic = -1
                if result.get('poster_path'):
                    artwork[dic]['poster'] = TMDB_URL + result['poster_path']
                if result.get('overview') and content == 'tv':
                    artwork['series']['plot'] = result['overview']
            else:
                oldtitle = title
                for splitchar in splitter:
                    if title.count(splitchar):
                        title = title.split(splitchar)[0]
                        break
                if title == oldtitle:
                    if year:
                        year = 0
                        title = titleorg
                    else:
                        break
        return artwork
