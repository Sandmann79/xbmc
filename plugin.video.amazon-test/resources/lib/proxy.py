#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Varstahl
# Module: CryptoProxy
# Created: 12/01/2019
from http.server import BaseHTTPRequestHandler  # Python3 HTTP Server
import ipaddress
import re
import secrets
import socket
import threading
from socketserver import ThreadingTCPServer
from unicodedata import lookup as _uni_lookup
from urllib.parse import parse_qsl, unquote, urlparse

from resources.lib.logging import Log
from .configs import getConfig, writeConfig

MAX_CONTENT_LENGTH = 70 * 1024 * 1024  # 10 MB DoS limit

_ALLOWED_HOST_SUFFIXES = (
    '.amazon.com',
    '.amazon.de',
    '.amazon.co.uk',
    '.amazon.co.jp',
    '.amazon.ca',
    '.amazon.fr',
    '.amazon.es',
    '.amazon.it',
    '.amazon.com.au',
    '.amazon.com.br',
    '.amazon.com.mx',
    '.amazon.in',
    '.amazon.nl',
    '.amazon.pl',
    '.amazon.se',
    '.amazon.sg',
    '.amazon.ae',
    '.amazon.sa',
    '.amazon.com.tr',
    '.amazon.eg',
    '.primevideo.com',
    '.aiv-cdn.net',
    '.pv-cdn.net',
    '.cloudfront.net',
    '.akamaihd.net',
    '.akamaized.net',
    '.llnwd.net',
    '.footprint.net',
    '.level3.net',
    '.media-amazon.com',
)

# Pre-compiled regex patterns for TTMLv2 to SRT subtitle conversion (_CleanSubs) and MPD parsing
_RE_SUB_SPAN = re.compile(r'<(|/)span[^>]*>')
_RE_SUB_TIMESTAMP = re.compile(r'([0-9]{2}:[0-9]{2}:[0-9]{2})\.')
_RE_SUB_BR = re.compile(r'(?:\s*<(?:tt:)?br\s*/>\s*)+')
_RE_SUB_STRETCH = re.compile(r'(?P<h>\d+):(?P<m>\d+):(?P<s>\d+),(?P<ms>\d+)')
_RE_SUB_PARAGRAPH = re.compile(r'<(?:tt:)?p begin="([^"]+)"[^>]*end="([^"]+)"[^>]*>\s*(.*?)\s*</(?:tt:)?p>', re.DOTALL)
_RTL_MARK = _uni_lookup('RIGHT-TO-LEFT MARK')
_RTL_EMBEDDING = _uni_lookup('RIGHT-TO-LEFT EMBEDDING')
_RE_SUB_ARABIC_RTL = re.compile(rf'^(?!{_RTL_MARK}|{_RTL_EMBEDDING})', flags=re.MULTILINE)
_RE_MPD_PERIOD = re.compile(r'(<Period\b[^>]*>)(.*?)(</Period>)', flags=re.DOTALL)
_RE_MPD_ROLE_SELF = re.compile(r'<Role\b[^>]*/>')
_RE_MPD_ROLE_PAIR = re.compile(r'<Role\b[^>]*>.*?</Role>', flags=re.DOTALL)
_RE_MPD_SEG_MEDIA_REL = re.compile(r'(<SegmentTemplate\b[^>]*\bmedia=")(?![a-z]+:|//|/)')
_RE_MPD_SEG_INIT_REL = re.compile(r'(<SegmentTemplate\b[^>]*\binitialization=")(?![a-z]+:|//|/)')
_RE_MPD_SEG_MEDIA_ROOT = re.compile(r'(<SegmentTemplate\b[^>]*\bmedia=")/')
_RE_MPD_SEG_INIT_ROOT = re.compile(r'(<SegmentTemplate\b[^>]*\binitialization=")/')
_RE_MPD_BASEURL_ROOT = re.compile(r'<BaseURL>/([^<]*)</BaseURL>')


def _is_safe_upstream_url(endpoint):
    """SSRF-Schutz: Erlaubt nur http/https-URLs auf autorisierten Amazon-/CDN-Domains ohne private/Loopback-IPs."""
    if not endpoint:
        return False
    try:
        parsed = urlparse(endpoint)
        if parsed.scheme not in ('http', 'https'):
            return False
        host = (parsed.hostname or '').lower().rstrip('.')
        if not host or host == 'localhost':
            return False
        try:
            ip = ipaddress.ip_address(host)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified:
                return False
            return False
        except ValueError:
            pass
        return any(host == suffix[1:] or host.endswith(suffix) for suffix in _ALLOWED_HOST_SUFFIXES)
    except Exception:
        return False


class ProxyHTTPD(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    timeout = 10  # Prevent hung local Keep-Alive sockets from blocking handler threads forever
    server_version = 'AmazonVOD/0.1'
    sessions = {}  # Keep-Alive sessions
    _sessions_lock = threading.RLock()
    _refused_licenses = {}  # license URL -> Amazon's refusal, answered locally when inputstream.adaptive asks again
    _min_audio_keep_bitrate = 192000
    _log_audio_selection_details = False
    _host_re = re.compile(r'://([^/]+)/')
    _track_id_re = re.compile(r'([^_]+)_(.+?)(?:_\d+)?$')
    _tag_attr_re = re.compile(r'([^\s=/>]+)="([^"]*)"')
    _representation_re = re.compile(r'<Representation\b[^>]*>.*?</Representation>', flags=re.DOTALL)
    _atmos_re = re.compile(r'<SupplementalProperty\b[^>]*value="JOC"[^>]*>')
    _adaptation_set_re = re.compile(r'<AdaptationSet\b[^>]*>.*?</AdaptationSet>', flags=re.DOTALL)
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

    def handle_one_request(self):
        """Guard against socket timeouts or abrupt client disconnects during local Keep-Alive"""
        try:
            super().handle_one_request()
        except (socket.timeout, ConnectionError, OSError) as exc:
            Log(f'[PS] Local client connection closed or timed out: {exc}', Log.DEBUG)
            self.close_connection = True

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
        client_ip = self.client_address[0] if self.client_address else ''
        try:
            if not ipaddress.ip_address(client_ip).is_loopback:
                Log(f'[PS] Rejecting non-loopback client {client_ip}', Log.ERROR)
                self.send_error(403, 'Forbidden: local access only')
                return None, None, None
        except ValueError:
            self.send_error(403, 'Forbidden: invalid client address')
            return None, None, None

        parsed_url = urlparse(self.path)
        path = [p for p in parsed_url.path.lstrip('/').split('/') if p]
        expected_token = getattr(self.server, 'token', None) or getConfig('proxytoken')
        if expected_token:
            token_valid = False
            if path and secrets.compare_digest(path[0], expected_token):
                token_valid = True
                path = path[1:]
            else:
                hdr_token = self.headers.get('X-Proxy-Token', '')
                if hdr_token and secrets.compare_digest(hdr_token, expected_token):
                    token_valid = True
                else:
                    query_params = dict(parse_qsl(parsed_url.query))
                    q_token = query_params.get('token', '')
                    if q_token and secrets.compare_digest(q_token, expected_token):
                        token_valid = True
            if not token_valid:
                Log(f'[PS] Blocked unauthorized {method} request (invalid runtime token)', Log.ERROR)
                self.send_error(403, 'Forbidden: invalid proxy token')
                return None, None, None

        if not path:
            self.send_error(400, 'Empty request path')
            return None, None, None
        Log(f'[PS] Requested {method} path {path}', Log.DEBUG)

        # Retrieve headers and data
        headers = {k: self.headers[k] for k in self.headers if k.lower() not in ['host', 'content-length', 'x-proxy-token']}
        data_length = self.headers.get('content-length')
        if data_length:
            try:
                length = int(data_length)
            except ValueError:
                self.send_error(400, 'Invalid Content-Length')
                return None, None, None
            if length < 0 or length > MAX_CONTENT_LENGTH:
                Log(f'[PS] Rejecting request with excessive Content-Length: {length}', Log.ERROR)
                self.send_error(413, 'Payload Too Large')
                return None, None, None
            self.raw_data = self.rfile.read(length)
        else:
            self.raw_data = None
        data = {k: v for k, v in parse_qsl(self.raw_data)} if self.raw_data else None
        return path, headers, data

    def _ForwardRequest(self, method, endpoint, headers, data, stream=False, use_auth=True):
        """Forwards the request to the proper target"""
        import requests

        if not _is_safe_upstream_url(endpoint):
            Log(f'[PS] Blocked disallowed upstream URL (SSRF protection): {endpoint}', Log.ERROR)
            self.send_error(403, 'Forbidden upstream host')
            return (None, None, None)

        # Create sessions for keep-alives and connection pooling
        host = self._host_re.search(endpoint)  # Try to extract the host from the URL
        host_key = host.group(1) if host is not None else None
        with self._sessions_lock:
            session = self.sessions.setdefault(host_key, requests.Session()) if host_key else requests.Session()

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
        try:
            r = session.request(method, endpoint, data=data, headers=headers, cookies=cookie, stream=stream, verify=self.server._s.ssl_verif, timeout=(10, 20))
        except requests.exceptions.RequestException as exc:
            Log(f'[PS] Upstream request failed ({exc.__class__.__name__}): {exc}', Log.ERROR)
            if host_key:
                with self._sessions_lock:
                    old_sess = self.sessions.pop(host_key, None)
                if old_sess:
                    try:
                        old_sess.close()
                    except Exception:
                        pass
            self.send_error(502, 'Upstream request failed')
            return (None, None, None)
        if not stream and len(r.content) > MAX_CONTENT_LENGTH:
            Log(f'[PS] Upstream response exceeded MAX_CONTENT_LENGTH ({len(r.content)} bytes)', Log.ERROR)
            r.close()
            self.send_error(502, 'Upstream response too large')
            return (None, None, None)
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
        headers['Connection'] = 'close'
        self.close_connection = True
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
        path, headers, data = self._ParseBaseRequest('POST')
        if None is path: return

        if ('gpr' == path[0]) and (2 == len(path)):
            self._AlterGPR(unquote(path[1]), headers, data)
        elif ('lic' == path[0]) and (2 == len(path)):
            self._ForwardLicense(unquote(path[1]), headers)
        else:
            Log('[PS] Invalid request received', Log.DEBUG)
            self.send_error(501, 'Invalid request')

    def do_GET(self):
        """Respond to GET requests"""
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
        return self._ParseGPR(endpoint, headers, data)

    def _ParseGPR(self, endpoint, headers, data):
        """ GPR data alteration for better language parsing and subtitles streaming instead of pre-caching """
        import json
        from urllib.parse import quote_plus
        from xbmc import convertLanguage, ENGLISH_NAME

        if not _is_safe_upstream_url(endpoint):
            Log(f'[PS] Blocked disallowed GPR URL: {endpoint}', Log.ERROR)
            self.send_error(403, 'Forbidden upstream host')
            return

        status_code, headers, content = self._ForwardRequest('post', endpoint, headers, data)
        if status_code is None:
            return
        try:
            content = json.loads(content)
        except ValueError:
            Log(f'[PS] GetPlaybackResources returned HTTP {status_code} without JSON data', Log.ERROR)
            self._SendResponse(status_code, headers, json.dumps({'error': {'errorCode': f'HTTP{status_code}', 'message': f'HTTP Error {status_code}'}}))
            return

        # Grab the subtitle urls, merge them in a single list, append the locale codes to let Kodi figure
        # out which URL has which language, then sort them neatly in a human digestible order.
        chosen_langs = getConfig('sub_langs', 'all').split(',')
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
                        content[sub_type][i]['url'] = 'http://127.0.0.1:{}/{}/subtitles/{}/{}{}.srt'.format(
                            self.server.port,
                            getattr(self.server, 'token', ''),
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

    def _ForwardLicense(self, endpoint, headers):
        """ Pass the Widevine license request through unchanged, log why Amazon refused it """

        # The challenge is sent as is: parsing it as form data would turn the + of base64 into spaces
        # inputstream.adaptive asks again about 90 times after a refusal, answer them at once so that it
        # gives up quickly. Stopping the player from Python instead deadlocks Kodi: it waits for
        # inputstream.adaptive, which waits for this proxy.
        if not _is_safe_upstream_url(endpoint):
            Log(f'[PS] Blocked disallowed License URL: {endpoint}', Log.ERROR)
            self.send_error(403, 'Forbidden upstream host')
            return

        if endpoint in self._refused_licenses:
            self._SendResponse(200, {'Content-Type': 'application/json'}, self._refused_licenses[endpoint])
            return
        headers = {k: v for k, v in headers.items() if k.lower() != 'content-length'}
        status_code, headers, content = self._ForwardRequest('post', endpoint, headers, self.raw_data, use_auth=False)
        if status_code is None:
            return
        if 'widevine2License' not in content:
            Log(f'[PS] License request refused (HTTP {status_code}): {content[:2000]}', Log.ERROR)
            if 'HdContentNotAllowed' in content:
                self._refused_licenses[endpoint] = content
        self._SendResponse(status_code, headers, content)

    def _AlterMPD(self, endpoint, headers, data):
        """ MPD alteration for better language parsing """
        if not _is_safe_upstream_url(endpoint):
            Log(f'[PS] Blocked disallowed MPD URL: {endpoint}', Log.ERROR)
            self.send_error(403, 'Forbidden upstream host')
            return

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
            raw_mpd = r.content
            mpd = raw_mpd.decode(r.encoding, errors='replace')

            def _rebase(data):
                data = _RE_MPD_ROLE_SELF.sub('', data)
                data = _RE_MPD_ROLE_PAIR.sub('', data)
                data = data.replace('<BaseURL>', '<BaseURL>' + baseurl)
                data = _RE_MPD_SEG_MEDIA_REL.sub(r'\1' + baseurl, data)
                data = _RE_MPD_SEG_INIT_REL.sub(r'\1' + baseurl, data)
                data = _RE_MPD_SEG_MEDIA_ROOT.sub(r'\1' + rooturl + '/', data)
                data = _RE_MPD_SEG_INIT_ROOT.sub(r'\1' + rooturl + '/', data)
                data = _RE_MPD_BASEURL_ROOT.sub(rf'<BaseURL>{rooturl}/\1</BaseURL>', data)
                return data

            Log('[PS] Altering audio <AdaptationSet>s', Log.DEBUG)
            parts = []
            last = 0
            for period in _RE_MPD_PERIOD.finditer(mpd):
                parts.append(_rebase(mpd[last:period.start()]))
                period_open, period_body, period_close = period.groups()
                parts.append(_rebase(period_open + self._AlterPeriodAudio(period_body) + period_close))
                last = period.end()
            parts.append(_rebase(mpd[last:]))
            mpd = ''.join(parts)

            self._SendResponse(status_code or 200, headers, mpd, False)
        except Exception as e:
            Log(f'[PS] MPD rewrite failed, forwarding original document: {e}', Log.ERROR)
            if r.encoding is None:
                r.encoding = 'utf-8'
            self._SendResponse(status_code, headers, r.content.decode(r.encoding, errors='replace'), False)
        finally:
            r.close()

    def _CleanSubs(self, content, filename):
        """Vorab kompilierte TTMLv2-zu-SRT-Konvertierung."""
        if not content:
            return ''
        content = _RE_SUB_SPAN.sub(r'<\1i>', content)
        content = _RE_SUB_TIMESTAMP.sub(r'\1,', content)
        content = _RE_SUB_BR.sub('\n', content)

        if self.server._s.sub_stretch:
            factor = self.server._s.subtitleStretchFactor

            def _stretch(f):
                millis = int(f.group('h')) * 3600000 + int(f.group('m')) * 60000 + int(f.group('s')) * 1000 + int(f.group('ms'))
                h, m = divmod(int(millis * factor), 3600000)
                m, s = divmod(m, 60000)
                s, ms = divmod(s, 1000)
                return f'{h:02}:{m:02}:{s:02},{ms:03}'

            content = _RE_SUB_STRETCH.sub(_stretch, content)

        num = 0
        srt_parts = []
        is_es = filename.startswith('es')
        is_ar = filename.startswith('ar')
        for begin_ts, end_ts, text in _RE_SUB_PARAGRAPH.findall(content):
            if is_es:
                text = text.replace('\xA8', '¿').replace('\xAD', '¡').replace('ń', 'ñ')
            if is_ar:
                text = _RE_SUB_ARABIC_RTL.sub(_RTL_EMBEDDING, text).replace('?', '؟').replace(',', '،')
            for src_ent, dst_chr in (('&amp;', '&'), ('&quot;', '"'), ('&lt;', '<'), ('&gt;', '>'), ('&apos;', "'")):
                text = text.replace(src_ent, dst_chr)
            num += 1
            srt_parts.append(f'{num}\n{begin_ts} --> {end_ts}\n{text}\n\n')
        return ''.join(srt_parts)

    def _TranscodeSubtitle(self, endpoint, headers, data, filename):
        """ On-the-fly subtitle transcoding (TTMLv2 => SRT) """

        status_code, headers, content = self._ForwardRequest('get', endpoint, headers, data)
        if status_code is None:
            return
        if 0 < len(content):
            content = self._CleanSubs(content, filename)

        self._SendResponse(status_code, headers, content)  # Kodi doesn't quite like gzip'd subtitles


class ProxyTCPD(ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, settings):
        """ Initialisation of the Proxy TCP server """
        self._s = settings  # Make settings available to the RequestHandler
        self.token = secrets.token_urlsafe(32)
        writeConfig('proxytoken', self.token)

        # Let the OS pick a free port; retry a few times in case another process grabs it in between
        from socket import socket, AF_INET, SOCK_STREAM
        from time import sleep

        for attempt in range(10):
            sock = socket(AF_INET, SOCK_STREAM)
            try:
                sock.bind(('127.0.0.1', 0))
                _, port = sock.getsockname()
            finally:
                sock.close()
            try:
                ThreadingTCPServer.__init__(self, ('127.0.0.1', port), ProxyHTTPD)
                self.port = port  # Save the current binded port
                return
            except OSError as e:
                Log(f'[PS] Unable to bind port {port}: {e}', Log.WARNING)
                sleep(0.2)
        raise OSError('[PS] No free port for the proxy')
