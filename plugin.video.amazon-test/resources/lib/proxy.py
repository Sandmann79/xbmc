#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Varstahl
# Module: CryptoProxy
# Created: 12/01/2019

from __future__ import unicode_literals
import base64
from SocketServer import ThreadingTCPServer
from resources.lib.logging import Log
try:
    from BaseHTTPServer import BaseHTTPRequestHandler  # Python2 HTTP Server
except ImportError:
    from http.server import BaseHTTPRequestHandler  # Python3 HTTP Server


class ProxyHTTPD(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'  # Allow keep-alive
    server_version = 'AmazonVOD/0.1'
    sessions = {}  # Keep-Alive sessions

    def log_message(self, *args):
        """Disable the BaseHTTPServer Log"""
        pass

    def _AdjustLocale(self, langCode, count=2, separator='-'):
        """Locale conversion helper"""
        try:
            p1, p2 = langCode.split('-')
        except:
            p1 = langCode
            p2 = langCode
        if 1 == count:
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
            'pt' + separator + 'BR': 'pt' + separator + 'Brazil'
        }
        new_lang = p1.lower() + ('' if p1 == p2 else separator + p2.upper())
        new_lang = new_lang if new_lang not in localeConversionTable.keys() else localeConversionTable[new_lang]
        return new_lang

    def _ParseBaseRequest(self, method):
        """Return path, headers and post data commonly required by all methods"""
        from urlparse import unquote, urlparse, parse_qsl

        path = urlparse(self.path).path[1:]  # Get URI without the trailing slash
        path = path.decode('utf-8').split('/')  # license/<asin>/<ATV endpoint>
        Log('[PS] Requested {} path {}'.format(method, path), Log.DEBUG)

        # Retrieve headers and data
        headers = {k: self.headers[k] for k in self.headers if k not in ['host', 'content-length']}
        data_length = self.headers.get('content-length')
        data = {k: v for k, v in parse_qsl(self.rfile.read(int(data_length)))} if data_length else None
        return (path, headers, data)

    def _ForwardRequest(self, method, endpoint, headers, data):
        """Forwards the request to the proper target"""
        from resources.lib.network import MechanizeLogin
        import re
        import requests

        # Create sessions for keep-alives and connection pooling
        host = re.search('://([^/]+)/', endpoint)  # Try to extract the host from the URL
        if None is not host:
            host = host.group(1)
            if host not in self.sessions:
                self.sessions[host] = requests.Session()
            session = self.sessions[host]
        else:
            session = requests.Session()

        cookie = MechanizeLogin()
        if not cookie:
            Log('[PS] Not logged in', Log.DEBUG)
            self.send_error(440)
            return (None, None, None)

        Log('[PS] Forwarding the {} request towards {}'.format(method, endpoint), Log.DEBUG)
        r = session.request(method, endpoint, data=data, headers=headers, cookies=cookie, verify=self.server._s.verifySsl)
        return (r.status_code, r.headers, r.content.decode('utf-8'))

    def _gzip(self, data):
        """Compress the output data"""
        from StringIO import StringIO
        from gzip import GzipFile
        out = StringIO()
        with GzipFile(fileobj=out, mode='w', compresslevel=5) as f:
            f.write(data)
        return out.getvalue()

    def _SendResponse(self, code, headers, data, gzip=False):
        """Send a response to the caller"""
        # We don't use chunked or gunzipped transfers locally, so we removed the relative headers and
        # attach the contact length, before returning the response
        headers = {k: headers[k] for k in headers if k not in ['Transfer-Encoding', 'Content-Encoding', 'Content-Length', 'Server', 'Date']}
        data = data.encode('utf-8') if data else b''
        if gzip:
            data = self._gzip(data)
            headers['Content-Encoding'] = 'gzip'
        headers['Content-Length'] = len(data)

        # Build the response
        self.send_response(code)
        for k in headers:
            self.send_header(k, headers[k])
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        """Respond to POST requests"""
        from urlparse import unquote

        path, headers, data = self._ParseBaseRequest('POST')
        if None is path: return

        if ('gpr' == path[0]) and (2 == len(path)):
            # Alter the GetPlaybackResources manifest
            from urllib import quote_plus
            import json
            import xbmc
            endpoint = unquote(path[1])  # MPD stream
            status_code, headers, content = self._ForwardRequest('get', endpoint, headers, data)

            # Grab the subtitle urls, merge them in a single list, append the locale codes to let Kodi figure
            # out which URL has which language, then sort them neatly in a human digestible order.
            content = json.loads(content)
            content['subtitles'] = []
            newsubs = []
            langCount = {'forcedNarratives': {}, 'subtitleUrls': {}}
            # Count the number of duplicates with the same ISO 639-1 codes
            for sub_type in langCount.keys():
                if sub_type in content:
                    for i in range(0, len(content[sub_type])):
                        lang = content[sub_type][i]['languageCode'][0:2]
                        if lang not in langCount[sub_type]:
                            langCount[sub_type][lang] = 0
                        langCount[sub_type][lang] += 1
            for sub_type in langCount.keys():
                if sub_type in content:
                    for i in range(0, len(content[sub_type])):
                        fn = self._AdjustLocale(content[sub_type][i]['languageCode'], langCount[sub_type][content[sub_type][i]['languageCode'][0:2]])
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
                        newsubs.append((content[sub_type][i], xbmc.convertLanguage(fn[0:2], xbmc.ENGLISH_NAME).decode('utf-8'), fn, variants, escapedurl))
                    del content[sub_type]  # Reduce the data transfer by removing the lists we merged
            for sub in [x for x in sorted(newsubs, key=lambda sub: (sub[1], sub[2], sub[3]))]:
                content['subtitles'].append(sub[0])
                # Add multiple options for time stretching
                if self.server._s.subtitleStretch:
                    from copy import deepcopy
                    cnts = deepcopy(sub[0])
                    urls = 'http://127.0.0.1:{}/subtitles/{}/{}-{{}}{}.srt'.format(
                        self.server.port,
                        sub[4],
                        sub[2],
                        sub[3]
                    )
                    # Loop-ready for multiple stretches
                    cnts['url'] = urls.format('[–1]')
                    content['subtitles'].append(cnts)
            content = json.dumps(content)
        else:
            Log('[PS] Invalid request received', Log.DEBUG)
            self.send_error(501, 'Invalid request')
            return

        self._SendResponse(status_code, headers, content)

    def do_GET(self):
        """Respond to GET requests"""
        from urlparse import unquote, urlparse
        import re

        path, headers, data = self._ParseBaseRequest('GET')
        if None is path: return

        if ('mpd' == path[0]) and (2 == len(path)):
            endpoint = unquote(path[1])  # MPD stream

            # Extrapolate the base CDN url to avoid proxying data we don't need to
            url_parts = urlparse(endpoint)
            baseurl = url_parts.scheme + '://' + url_parts.netloc + re.sub(r'[^/]+$', '', url_parts.path)
            status_code, headers, content = self._ForwardRequest('get', endpoint, headers, data)  # Call the destination server

            content = re.sub(r'(<BaseURL>)', r'\1{}'.format(baseurl), content)  # Rebase CDN URLs
            header, sets, footer = re.search(r'^(.*<Period [^>]*>\s*)(.*)(\s*</Period>.*)$', content, flags=re.DOTALL).groups()  # Extract <AdaptationSet>s

            # Count the number of duplicates with the same ISO 639-1 codes
            languages = []
            langCount = {}
            for lang in re.findall(r'<AdaptationSet[^>]*audioTrackId="([^"]+)"[^>]*>', content):
                if lang not in languages:
                    languages.append(lang)
            for lang in languages:
                lang = lang[0:2]
                if lang not in langCount:
                    langCount[lang] = 0
                langCount[lang] += 1
            # Alter the <AdaptationSet>s for our linguistic needs
            new_sets = []
            for s in re.findall(r'(<AdaptationSet\s+[^>]*>)(.*?</AdaptationSet>)', content, flags=re.DOTALL):
                s = list(s)
                audioTrack = re.search(r' audioTrackId="([a-z]{2})(-[a-z0-9]{2,})[^"]+[^>]+ lang="([a-z]{2})"', s[0])
                if None is not audioTrack:
                    audioTrack = audioTrack.groups()
                    s[0] = s[0].replace('lang="%s"' % audioTrack[2], 'lang="%s"' % self._AdjustLocale(audioTrack[0] + audioTrack[1], langCount[audioTrack[0]]))
                new_sets.append(s[0] + s[1])

            content = header + ''.join(new_sets) + footer  # Reassemble the MPD
        elif ('subtitles' == path[0]) and (3 == len(path)):
            # On-the-fly subtitle transcoding (TTMLv2 => SRT)
            status_code, headers, content = self._ForwardRequest('get', unquote(path[1]), headers, data)
            if 0 < len(content):
                # Apply a bunch of regex to the content instead of line-by-line to save computation time
                content = re.sub(r'<(|/)span[^>]*>', r'<\1i>', content)  # Using (|<search>) instead of ()? to avoid py2.7 empty matching error
                content = re.sub(r'([0-9]{2}:[0-9]{2}:[0-9]{2})\.', r'\1,', content)  # SRT-like timestamps
                content = re.sub(r'\s*<(?:tt:)?br\s*/>\s*', '\n', content)  # Replace <br/> with actual new lines
                # Subtitle timing stretching
                if ('[–1]' in path[2]):
                    def _stretch(f):
                        millis = int(f.group('h')) * 3600000 + int(f.group('m')) * 60000 + int(f.group('s')) * 1000 + int(f.group('ms'))
                        h, m = divmod(millis * _stretch.factor, 3600000)
                        m, s = divmod(m, 60000)
                        s, ms = divmod(s, 1000)
                        # Truncate to the decimal of a ms (for lazyness)
                        return '%02d:%02d:%02d,%03d' % (h, m, s, int(ms))
                    _stretch.factor = 24 / 23.976
                    content = re.sub(r'(?P<h>\d+):(?P<m>\d+):(?P<s>\d+),(?P<ms>\d+)', _stretch, content)

                # Convert dfxp or ttml2 to srt
                num = 0
                srt = ''
                for tt in re.compile(r'<(?:tt:)?p begin="([^"]+)"[^>]*end="([^"]+)"[^>]*>\s*(.*?)\s*</(?:tt:)?p>', re.DOTALL).findall(content):
                    text = tt[2]

                    # Embed RTL and change the punctuation where needed
                    if path[2].startswith("ar"):
                        from unicodedata import lookup
                        text = re.sub('^', lookup('RIGHT-TO-LEFT EMBEDDING'), text, flags=re.MULTILINE)
                        text = text.replace('?', '؟').replace(',', '،')

                    for ec in [('&amp;', '&'), ('&quot;', '"'), ('&lt;', '<'), ('&gt;', '>'), ('&apos;', "'")]:
                        text = text.replace(ec[0], ec[1])
                    num += 1
                    srt += '%s\n%s --> %s\n%s\n\n' % (num, tt[0], tt[1], text)
                content = srt
        else:
            Log('[PS] Invalid request received', Log.DEBUG)
            self.send_error(501, 'Invalid request')
            return

        self._SendResponse(status_code, headers, content)


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
