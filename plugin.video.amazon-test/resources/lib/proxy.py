#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Varstahl
# Module: CryptoProxy
# Created: 12/01/2019
from http.server import BaseHTTPRequestHandler  # Python3 HTTP Server
from socketserver import ThreadingTCPServer

from resources.lib.logging import Log
from .configs import getConfig


class ProxyHTTPD(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'  # Allow keep-alive
    server_version = 'AmazonVOD/0.1'
    sessions = {}  # Keep-Alive sessions
    _min_audio_keep_bitrate = 192000
    _log_audio_selection_details = False
    _host_re = None
    _track_id_re = None
    _tag_attr_re = None
    _representation_re = None
    _atmos_re = None
    _adaptation_set_re = None
    _purgeHeaders = [  # List of headers not to forward to the client
        'Transfer-Encoding',
        'Content-Encoding',
        'Content-Length',
        'Server',
        'Date'
    ]

    def log_message(self, *args):
        """Disable the BaseHTTPServer Log"""
        pass

    def _AdjustLocale(self, langCode, count=2, separator='-'):
        """Locale conversion helper"""
        p1, p2 = langCode.split('-') if '-' in langCode else [langCode, langCode]
        if 1 == count and p1 not in ['yue', 'cmn']:
            return p1.lower()
        localeConversionTable = {
            'ar' + separator + '001': 'ar',
            'cmn' + separator + 'HANS': 'zh' + separator + 'HANS',
            'cmn' + separator + 'HANT': 'zh' + separator + 'HANT',
            'fr' + separator + 'CA': 'fr' + separator + 'Canada',
            'da' + separator + 'DK': 'da',
            'en' + separator + 'GB': 'en',
            'es' + separator + '419': 'es' + separator + 'Latinoamerica',
            'ja' + separator + 'JP': 'ja',
            'ko' + separator + 'KR': 'ko',
            'nb' + separator + 'NO': 'nb',
            'sv' + separator + 'SE': 'sv',
            'pt' + separator + 'BR': 'pt' + separator + 'Brazil',
            'yue': 'zh' + separator + 'Cantonese',
            'cmn' + separator + 'CN': 'zh' + separator + 'CN',
            'cmn' + separator + 'TW': 'zh' + separator + 'TW'
        }
        new_lang = p1.lower() + ('' if p1 == p2 else separator + p2.upper())
        return localeConversionTable.get(new_lang, new_lang)

    def _ParseBaseRequest(self, method):
        """Return path, headers and post data commonly required by all methods"""
        from urllib.parse import urlparse, parse_qsl

        path = urlparse(self.path).path[1:]  # Get URI without the trailing slash
        path = path.split('/')  # license/<asin>/<ATV endpoint>
        Log(f'[PS] Requested {method} path {path}', Log.DEBUG)

        # Retrieve headers and data
        headers = {k: self.headers[k] for k in self.headers if k not in ['host', 'content-length']}
        data_length = self.headers.get('content-length')
        data = {k: v for k, v in parse_qsl(self.rfile.read(int(data_length)))} if data_length else None
        return path, headers, data

    def _ForwardRequest(self, method, endpoint, headers, data, stream=False, use_auth=True):
        """Forwards the request to the proper target"""

        import re
        import requests

        if self._host_re is None:
            self.__class__._host_re = re.compile('://([^/]+)/')

        # Create sessions for keep-alives and connection pooling
        host = self._host_re.search(endpoint)  # Try to extract the host from the URL
        if None is not host:
            host = host.group(1)
            if host not in self.sessions:
                self.sessions[host] = requests.Session()
            session = self.sessions[host]
        else:
            session = requests.Session()

        cookie = None
        if use_auth:
            from resources.lib.common import MechanizeLogin
            cookie = MechanizeLogin(preferToken=True)
            if not cookie:
                Log('[PS] Not logged in', Log.DEBUG)
                self.send_error(440)
                return (None, None, None)
            if isinstance(cookie, dict):
                headers.update(cookie)
                cookie = None

        if 'Host' in headers: del headers['Host']  # Forcibly strip the host (py3 compliance)
        Log(f'[PS] Forwarding the {method.upper()} request towards {endpoint}', Log.DEBUG)
        r = session.request(method, endpoint, data=data, headers=headers, cookies=cookie, stream=stream, verify=self.server._s.ssl_verif)
        return r.status_code, r.headers, r if stream else r.content.decode('utf-8')

    @staticmethod
    def _gzip(data):
        """Compress the output data"""

        from io import BytesIO
        from gzip import GzipFile
        out = BytesIO()
        f = GzipFile(fileobj=out, mode='w', compresslevel=5)
        f.write(data)
        f.close()
        return out.getvalue()

    def _SendHeaders(self, code, headers):
        self.send_response(code)
        for k in headers:
            self.send_header(k, headers[k])
        self.end_headers()

    def _SendResponse(self, code, headers, data, gzip=False):
        """Send a response to the caller"""

        # We don't use chunked or gunzipped transfers locally, so we removed the relative headers and
        # attach the contact length, before returning the response
        headers = {k: headers[k] for k in headers if k not in self._purgeHeaders}
        headers['Connection'] = 'Keep-Alive'
        data = data.encode('utf-8') if data else b''
        if gzip:
            data = self._gzip(data)
            headers['Content-Encoding'] = 'gzip'
        headers['Content-Length'] = len(data)

        try:
            self._SendHeaders(code, headers)
            self.wfile.write(data)
        except OSError as exc:
            Log(f'[PS] Client disconnected while sending response: {exc}', Log.DEBUG)

    def do_POST(self):
        """Respond to POST requests"""
        from urllib.parse import unquote

        path, headers, data = self._ParseBaseRequest('POST')
        if None is path: return

        if ('gpr' == path[0]) and (2 == len(path)):
            self._AlterGPR(unquote(path[1]), headers, data)
        else:
            Log('[PS] Invalid request received', Log.DEBUG)
            self.send_error(501, 'Invalid request')

    def do_GET(self):
        """Respond to GET requests"""
        from urllib.parse import unquote

        path, headers, data = self._ParseBaseRequest('GET')
        if None is path: return

        if ('mpd' == path[0]) and (2 == len(path)):
            self._AlterMPD(unquote(path[1]), headers, data)
        elif ('subtitles' == path[0]) and (3 == len(path)):
            self._TranscodeSubtitle(unquote(path[1]), headers, data, path[2])
        else:
            Log('[PS] Invalid request received', Log.DEBUG)
            self.send_error(501, 'Invalid request')

    @staticmethod
    def split_lang(lng):
        return lng.split('-' if '-' in lng else '_')[0]

    def _ParseAudioTrackInfo(self, track_id, lang=None, track_subtype=None):
        import re

        if self._track_id_re is None:
            self.__class__._track_id_re = re.compile(r'([^_]+)_(.+?)(?:_\d+)?$')
        if track_id:
            match = self._track_id_re.match(track_id)
            if match:
                return match.group(1) or lang, match.group(2)
            parts = track_id.split('_')
            if len(parts) > 1:
                return parts[0] or lang, parts[1] or track_subtype or ''
            if lang or track_subtype:
                return lang or track_id, track_subtype or ''
        if lang:
            return lang, track_subtype or ''
        return None, None

    @staticmethod
    def _ParseTagAttributes(tag):
        import re

        if ProxyHTTPD._tag_attr_re is None:
            ProxyHTTPD._tag_attr_re = re.compile(r'([^\s=/>]+)="([^"]*)"')
        return {k: v for k, v in ProxyHTTPD._tag_attr_re.findall(tag)}

    @staticmethod
    def _EscapeAttr(value):
        return str(value).replace('&', '&amp;').replace('"', '&quot;')

    def _UpdateTagAttributes(self, tag, updates=None, removals=None):
        import re

        updates = updates or {}
        removals = removals or []
        for attr in removals:
            tag = re.sub(rf'\s+{re.escape(attr)}="[^"]*"', '', tag)
        for attr, value in updates.items():
            value = self._EscapeAttr(value)
            pattern = rf'(\s+{re.escape(attr)}=")[^"]*(")'
            if re.search(pattern, tag):
                tag = re.sub(pattern, rf'\g<1>{value}\2', tag)
            else:
                tag = f'{tag[:-1]} {attr}="{value}">'
        return tag

    @staticmethod
    def _IsAudioAdaptationSetTag(attrs):
        mime_type = attrs.get('mimeType', '')
        return attrs.get('contentType') == 'audio' or mime_type.startswith('audio/') or 'audioTrackId' in attrs

    def _SelectAudioRepresentationsText(self, adaptation_tag, adaptation_body):
        if self._representation_re is None:
            import re
            self.__class__._representation_re = re.compile(r'<Representation\b[^>]*>.*?</Representation>', flags=re.DOTALL)
            self.__class__._atmos_re = re.compile(r'<SupplementalProperty\b[^>]*value="JOC"[^>]*>')
        representations = list(self._representation_re.finditer(adaptation_body))
        if not representations:
            return [], 0, 0, False, 0, adaptation_body

        prefer_atmos = self.server._s.enable_atmos is not False
        candidates = []
        found_atmos = False
        set_codecs = self._ParseTagAttributes(adaptation_tag).get('codecs', '').lower()

        for match in representations:
            rep = match.group(0)
            attrs = self._ParseTagAttributes(rep[:rep.find('>') + 1])
            bitrate = int(attrs.get('bandwidth', '0') or 0)
            atmos = self._atmos_re.search(rep) is not None
            codecs = (attrs.get('codecs', '') or set_codecs).lower()
            codec_rank = 2 if 'ec-3' in codecs else 1 if 'ac-3' in codecs else 0

            if atmos and prefer_atmos and not found_atmos:
                found_atmos = True
                candidates = []

            if prefer_atmos and found_atmos and not atmos:
                continue

            candidates.append({
                'match': match,
                'bitrate': bitrate,
                'atmos': atmos,
                'codec_rank': codec_rank,
            })

        if not candidates:
            return [], 0, 0, False, 0, adaptation_body

        kept = [item for item in candidates if item['bitrate'] >= self._min_audio_keep_bitrate]
        if not kept:
            kept = [max(candidates, key=lambda item: (item['codec_rank'], item['bitrate']))]

        kept.sort(key=lambda item: item['match'].start())
        bitrates = [item['bitrate'] for item in kept]
        best_codec_rank = max(item['codec_rank'] for item in kept)
        kept_ranges = {(item['match'].start(), item['match'].end()) for item in kept}
        body_parts = []
        body_last = 0
        for rep_match in representations:
            body_parts.append(adaptation_body[body_last:rep_match.start()])
            if (rep_match.start(), rep_match.end()) in kept_ranges:
                body_parts.append(rep_match.group(0))
            body_last = rep_match.end()
        body_parts.append(adaptation_body[body_last:])
        filtered_body = ''.join(body_parts)
        return kept, min(bitrates), max(bitrates), any(item['atmos'] for item in kept), best_codec_rank, filtered_body

    def _AudioSetScore(self, max_bitrate, atmos, codec_rank):
        prefer_atmos = self.server._s.enable_atmos is not False
        return (1 if prefer_atmos and atmos else 0, codec_rank, max_bitrate)

    def _AlterPeriodAudio(self, period_data):
        import re

        if self._adaptation_set_re is None:
            self.__class__._adaptation_set_re = re.compile(r'<AdaptationSet\b[^>]*>.*?</AdaptationSet>', flags=re.DOTALL)
        chosen_langs = {
            lang.strip()
            for lang in getConfig('audio_langs', 'all').split(',')
            if lang.strip()
        }
        allow_all = not chosen_langs or 'all' in chosen_langs
        matches = list(self._adaptation_set_re.finditer(period_data))
        all_infos = []
        infos = []

        for index, match in enumerate(matches):
            full = match.group(0)
            tag_end = full.find('>') + 1
            if tag_end <= 0:
                continue
            set_tag = full[:tag_end]
            set_body = full[tag_end:-16]  # len('</AdaptationSet>') == 16
            attrs = self._ParseTagAttributes(set_tag)
            if not self._IsAudioAdaptationSetTag(attrs):
                continue

            track_lang, track_kind = self._ParseAudioTrackInfo(
                attrs.get('audioTrackId', ''),
                attrs.get('lang'),
                attrs.get('audioTrackSubtype', '')
            )
            if not track_lang:
                continue

            base_lang = self.split_lang(track_lang)
            kept_representations, min_bitrate, max_bitrate, best_atmos, codec_rank, filtered_body = self._SelectAudioRepresentationsText(set_tag, set_body)
            if not kept_representations:
                continue

            info = {
                'index': index,
                'match': match,
                'tag': set_tag,
                'attrs': attrs,
                'track_id': attrs.get('audioTrackId', track_lang),
                'track_lang': track_lang,
                'track_kind': track_kind,
                'base_lang': base_lang,
                'kept_representations': kept_representations,
                'min_bitrate': min_bitrate,
                'max_bitrate': max_bitrate,
                'best_atmos': best_atmos,
                'codec_rank': codec_rank,
                'filtered_body': filtered_body,
            }
            all_infos.append(info)

            if not allow_all and base_lang not in chosen_langs:
                continue

            infos.append(info)

        if not infos and not allow_all:
            infos = list(all_infos)

        grouped = {}
        for info in infos:
            grouped.setdefault(info['track_id'], []).append(info)

        selected_infos = []
        for track_infos in grouped.values():
            keep_high = [info for info in track_infos if info['max_bitrate'] >= self._min_audio_keep_bitrate]
            if keep_high:
                selected_infos.extend(keep_high)
                continue

            best_info = max(
                track_infos,
                key=lambda item: self._AudioSetScore(item['max_bitrate'], item['best_atmos'], item['codec_rank'])
            )
            selected_infos.append(best_info)

        Log(
            f'[PS] Selected {len(selected_infos)} audio AdaptationSets from {len(all_infos)} candidates',
            Log.DEBUG
        )

        lang_count = {}
        for info in selected_infos:
            lang_count[info['base_lang']] = lang_count.get(info['base_lang'], 0) + 1

        selected_indexes = {info['index']: info for info in selected_infos}
        audio_indexes = {info['index'] for info in all_infos}
        result = []
        last = 0
        for index, match in enumerate(matches):
            result.append(period_data[last:match.start()])
            info = selected_indexes.get(index)
            if info is not None:
                new_lang = self._AdjustLocale(info['track_lang'], lang_count[info['base_lang']])
                suffix = ''
                if info['best_atmos'] and self.server._s._g.KodiVersion < 21:
                    suffix = ' (Atmos)'
                elif 'boosted' in info['track_kind']:
                    suffix = f" (Dialog Boost: {info['track_kind'].replace('boosteddialog', '').capitalize()})"

                updates = {
                    'lang': new_lang,
                    'name': f'{int(info["max_bitrate"] / 1000)} kbps{suffix}',
                    'minBandwidth': str(info['min_bitrate']),
                    'maxBandwidth': str(info['max_bitrate']),
                }
                removals = ['impaired']
                if info['track_kind'] == 'descriptive':
                    updates['impaired'] = 'true'

                set_tag = self._UpdateTagAttributes(info['tag'], updates, removals)
                if self._log_audio_selection_details:
                    Log(f'[PS] Audio AdaptationSet attrs: {self._ParseTagAttributes(set_tag)}', Log.DEBUG)
                result.append(f'{set_tag}{info["filtered_body"]}</AdaptationSet>')
            elif index not in audio_indexes:
                result.append(match.group(0))
            last = match.end()

        result.append(period_data[last:])
        return ''.join(result)

    def _AlterGPR(self, endpoint, headers, data):
        """ GPR data alteration for better language parsing and subtitles streaming instead of pre-caching """

        import json
        from urllib.parse import quote_plus
        from xbmc import convertLanguage, ENGLISH_NAME

        status_code, headers, content = self._ForwardRequest('post', endpoint, headers, data)

        # Grab the subtitle urls, merge them in a single list, append the locale codes to let Kodi figure
        # out which URL has which language, then sort them neatly in a human digestible order.
        chosen_langs = getConfig('sub_langs', 'all').split(',')
        content = json.loads(content)
        content['subtitles'] = []
        newsubs = []
        chosen_found = 0

        # Count the number of duplicates with the same ISO 639-1 codes
        langCount = {'forcedNarratives': {}, 'subtitleUrls': {}}
        for sub_type in list(langCount):  # list() instead of .keys() to avoid py3 iteration errors
            if sub_type in content:
                for i in range(0, len(content[sub_type])):
                    lang = self.split_lang(content[sub_type][i]['languageCode'])
                    if lang not in langCount[sub_type]:
                        if lang in chosen_langs or chosen_langs == 'all':
                            chosen_found += 1
                        langCount[sub_type][lang] = 0
                    langCount[sub_type][lang] += 1
        if chosen_found == 0:
            chosen_langs = 'all'

        # Merge the different subtitles lists in a single one, and append a spurious name file
        # to let Kodi figure out the locale, while at the same time enabling subtitles to be
        # proxied and transcoded on-the-fly.
        for sub_type in list(langCount):  # list() instead of .keys() to avoid py3 iteration errors
            if sub_type in content:
                for i in range(0, len(content[sub_type])):
                    fn = self._AdjustLocale(content[sub_type][i]['languageCode'], langCount[sub_type][self.split_lang(content[sub_type][i]['languageCode'])])
                    ic = self.split_lang(fn)
                    if ic in chosen_langs or chosen_langs == 'all':
                        variants = '{}{}'.format(
                            '-[CC]' if 'sdh' == content[sub_type][i]['type'] else '',
                            '.Forced' if 'forcedNarratives' == sub_type else ''
                        )
                        # Proxify the URLs, with a make believe Kodi-friendly file name
                        escapedurl = quote_plus(content[sub_type][i]['url'])
                        content[sub_type][i]['url'] = 'http://127.0.0.1:{}/subtitles/{}/{}{}.srt'.format(
                            self.server.port,
                            escapedurl,
                            fn,
                            variants
                        )
                        cl = convertLanguage(ic, ENGLISH_NAME)
                        newsubs.append((content[sub_type][i], cl, fn, variants, escapedurl))
                del content[sub_type]  # Reduce the data transfer by removing the lists we merged

        # Create the new merged subtitles list, and append time stretched variants.
        for sub in [x for x in sorted(newsubs, key=lambda sub: (sub[1], sub[2], sub[3]))]:
            content['subtitles'].append(sub[0])

        self._SendResponse(status_code, headers, json.dumps(content), True)

    def _AlterMPD(self, endpoint, headers, data):
        """ MPD alteration for better language parsing """
        import re
        from urllib.parse import urlparse

        # Extrapolate the base CDN url to avoid proxying data we don't need to
        url_parts = urlparse(endpoint)
        baseurl = endpoint.rsplit('/', 1)[0] + '/'
        rooturl = url_parts.scheme + '://' + url_parts.netloc

        # Start the chunked reception
        status_code, headers, r = self._ForwardRequest('get', endpoint, headers, data, True, use_auth=False)
        if r is None:
            return

        Log(f'[PS] Loading MPD and rebasing as {baseurl} (upstream {status_code})', Log.DEBUG)
        try:
            if r.encoding is None:
                r.encoding = 'utf-8'
            mpd = r.content.decode(r.encoding, errors='replace')

            def _rebase(data):
                data = re.sub(r'<Role\b[^>]*/>', '', data)
                data = re.sub(r'<Role\b[^>]*>.*?</Role>', '', data, flags=re.DOTALL)
                data = data.replace('<BaseURL>', '<BaseURL>' + baseurl)
                data = re.sub(r'(<SegmentTemplate\b[^>]*\bmedia=")(?![a-z]+:|//|/)', r'\1' + baseurl, data)
                data = re.sub(r'(<SegmentTemplate\b[^>]*\binitialization=")(?![a-z]+:|//|/)', r'\1' + baseurl, data)
                data = re.sub(r'(<SegmentTemplate\b[^>]*\bmedia=")/', r'\1' + rooturl + '/', data)
                data = re.sub(r'(<SegmentTemplate\b[^>]*\binitialization=")/', r'\1' + rooturl + '/', data)
                data = re.sub(r'<BaseURL>/([^<]*)</BaseURL>', rf'<BaseURL>{rooturl}/\1</BaseURL>', data)
                return data

            Log('[PS] Altering audio <AdaptationSet>s', Log.DEBUG)
            parts = []
            last = 0
            period_pattern = re.compile(r'(<Period\b[^>]*>)(.*?)(</Period>)', flags=re.DOTALL)
            for period in period_pattern.finditer(mpd):
                parts.append(_rebase(mpd[last:period.start()]))
                period_open, period_body, period_close = period.groups()
                parts.append(_rebase(period_open + self._AlterPeriodAudio(period_body) + period_close))
                last = period.end()
            parts.append(_rebase(mpd[last:]))
            mpd = ''.join(parts)

            self._SendResponse(200 if status_code and int(status_code) >= 400 else status_code, headers, mpd, False)
        except Exception as e:
            Log(f'[PS] MPD rewrite failed, forwarding original document: {e}', Log.ERROR)
            if r.encoding is None:
                r.encoding = 'utf-8'
            self._SendResponse(status_code, headers, r.content.decode(r.encoding, errors='replace'), False)

    def _TranscodeSubtitle(self, endpoint, headers, data, filename):
        """ On-the-fly subtitle transcoding (TTMLv2 => SRT) """

        import re

        status_code, headers, content = self._ForwardRequest('get', endpoint, headers, data)
        if 0 < len(content):
            # Apply a bunch of regex to the content instead of line-by-line to save computation time
            content = re.sub(r'<(|/)span[^>]*>', r'<\1i>', content)  # Using (|<search>) instead of ()? to avoid py2.7 empty matching error
            content = re.sub(r'([0-9]{2}:[0-9]{2}:[0-9]{2})\.', r'\1,', content)  # SRT-like timestamps
            content = re.sub(r'(?:\s*<(?:tt:)?br\s*/>\s*)+', '\n', content)  # Replace <br/> with actual new lines

            # Subtitle timing stretch
            if self.server._s.sub_stretch:
                def _stretch(f):
                    millis = int(f.group('h')) * 3600000 + int(f.group('m')) * 60000 + int(f.group('s')) * 1000 + int(f.group('ms'))
                    h, m = divmod(millis * _stretch.factor, 3600000)
                    m, s = divmod(m, 60000)
                    s, ms = divmod(s, 1000)
                    # Truncate to the decimal of a ms (for lazyness)
                    return '{h:02}:{m:02}:{s:02},{ms:03}'
                _stretch.factor = self.server._s.subtitleStretchFactor
                content = re.sub(r'(?P<h>\d+):(?P<m>\d+):(?P<s>\d+),(?P<ms>\d+)', _stretch, content)

            # Convert dfxp or ttml2 to srt
            num = 0
            srt = ''
            for tt in re.compile(r'<(?:tt:)?p begin="([^"]+)"[^>]*end="([^"]+)"[^>]*>\s*(.*?)\s*</(?:tt:)?p>', re.DOTALL).findall(content):
                text = tt[2]

                # Fix Spanish characters
                if filename.startswith("es"):
                    text = text.replace('\xA8', u'¿')
                    text = text.replace('\xAD', u'¡')
                    text = text.replace(u'ń', u'ñ')

                # Embed RTL and change the punctuation where needed
                if filename.startswith("ar"):
                    from unicodedata import lookup
                    text = re.sub(rf"^(?!{lookup('RIGHT-TO-LEFT MARK')}|{lookup('RIGHT-TO-LEFT EMBEDDING')})",
                                  lookup('RIGHT-TO-LEFT EMBEDDING'), text, flags=re.MULTILINE)
                    text = text.replace('?', '؟').replace(',', '،')

                for ec in [('&amp;', '&'), ('&quot;', '"'), ('&lt;', '<'), ('&gt;', '>'), ('&apos;', "'")]:
                    text = text.replace(ec[0], ec[1])
                num += 1
                srt += f'{num}\n{tt[0]} --> {tt[1]}\n{text}\n\n'
            content = srt

        self._SendResponse(status_code, headers, content)  # Kodi doesn't quite like gzip'd subtitles


class ProxyTCPD(ThreadingTCPServer):
    def __init__(self, settings):
        """ Initialisation of the Proxy TCP server """
        self._s = settings  # Make settings available to the RequestHandler

        from socket import socket, AF_INET, SOCK_STREAM
        sock = socket(AF_INET, SOCK_STREAM)

        while True:
            try:
                sock.bind(('127.0.0.1', 0))
                _, port = sock.getsockname()
                sock.close()
                ThreadingTCPServer.__init__(self, ('127.0.0.1', port), ProxyHTTPD)
                self.port = port  # Save the current binded port
                break
            except:
                pass
