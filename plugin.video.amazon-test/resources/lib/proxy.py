#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Varstahl
# Module: CryptoProxy
# Created: 12/01/2019

from __future__ import unicode_literals
from kodi_six.utils import py2_decode
import base64
from resources.lib.logging import Log
from contextlib import contextmanager
try:
    from BaseHTTPServer import BaseHTTPRequestHandler  # Python2 HTTP Server
    from SocketServer import ThreadingTCPServer
except ImportError:
    from http.server import BaseHTTPRequestHandler  # Python3 HTTP Server
    from socketserver import ThreadingTCPServer


class ProxyHTTPD(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'  # Allow keep-alive
    server_version = 'AmazonVOD/0.1'
    sessions = {}  # Keep-Alive sessions
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

        try:
            from urllib.parse import unquote, urlparse, parse_qsl
        except ImportError:
            from urlparse import unquote, urlparse, parse_qsl

        path = py2_decode(urlparse(self.path).path[1:])  # Get URI without the trailing slash
        path = path.split('/')  # license/<asin>/<ATV endpoint>
        Log('[PS] Requested {} path {}'.format(method, path), Log.DEBUG)

        # Retrieve headers and data
        headers = {k: self.headers[k] for k in self.headers if k not in ['host', 'content-length']}
        data_length = self.headers.get('content-length')
        data = {k: v for k, v in parse_qsl(self.rfile.read(int(data_length)))} if data_length else None
        return (path, headers, data)

    def _ForwardRequest(self, method, endpoint, headers, data, stream=False):
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

        if 'Host' in headers: del headers['Host']  # Forcibly strip the host (py3 compliance)
        Log('[PS] Forwarding the {} request towards {}'.format(method.upper(), endpoint), Log.DEBUG)
        r = session.request(method, endpoint, data=data, headers=headers, cookies=cookie, stream=stream, verify=self.server._s.verifySsl)
        return (r.status_code, r.headers, r if stream else r.content.decode('utf-8'))

    def _gzip(self, data=None, stream=False):
        """Compress the output data"""

        from io import BytesIO
        from gzip import GzipFile
        out = BytesIO()
        f = GzipFile(fileobj=out, mode='w', compresslevel=5)
        if not stream:
            f.write(data)
            f.close()
            return out.getvalue()
        return (f, out)

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

        self._SendHeaders(code, headers)
        self.wfile.write(data)

    @contextmanager
    def _PrepareChunkedResponse(self, code, headers):
        """Prep the stream for gzipped chunked transfers"""

        Log('[PS] Chunked transfer: prepping', Log.DEBUG)
        headers = {k: headers[k] for k in headers if k not in self._purgeHeaders}
        headers['Connection'] = 'Keep-Alive'
        headers['Transfer-Encoding'] = 'chunked'
        headers['Content-Encoding'] = 'gzip'

        self._SendHeaders(code, headers)
        gzstream = self._gzip(stream=True)

        try:
            yield gzstream
        finally:
            gzstream[0].close()
            gzstream[1].close()

    def _SendChunk(self, gzstream, data=None):
        """Send a gzipped chunk"""

        # Log('[PS] Chunked transfer: sending chunk', Log.DEBUG)

        if None is not data:
            gzstream[0].write(data.encode('utf-8'))
            gzstream[0].flush()
        chunk = gzstream[1].getvalue()
        gzstream[1].seek(0)
        gzstream[1].truncate()

        if 0 == len(chunk):
            return

        data = b'%s\r\n%s\r\n' % (hex(len(chunk))[2:].upper().encode(), chunk)
        self.wfile.write(data)

    def _EndChunkedTransfer(self, gzstream):
        """Terminate the transfer"""

        Log('[PS] Chunked transfer: last chunks', Log.DEBUG)
        gzstream[0].flush()
        gzstream[0].close()
        self._SendChunk(gzstream)
        gzstream[1].close()

        self.wfile.write(b'0\r\n\r\n')

    def do_POST(self):
        """Respond to POST requests"""

        try:
            from urllib.parse import unquote
        except ImportError:
            from urlparse import unquote

        path, headers, data = self._ParseBaseRequest('POST')
        if None is path: return

        if ('gpr' == path[0]) and (2 == len(path)):
            self._AlterGPR(unquote(path[1]), headers, data)
        else:
            Log('[PS] Invalid request received', Log.DEBUG)
            self.send_error(501, 'Invalid request')

    def do_GET(self):
        """Respond to GET requests"""

        try:
            from urllib.parse import unquote
        except ImportError:
            from urlparse import unquote

        path, headers, data = self._ParseBaseRequest('GET')
        if None is path: return

        if ('mpd' == path[0]) and (2 == len(path)):
            self._AlterMPD(unquote(path[1]), headers, data)
        elif ('subtitles' == path[0]) and (3 == len(path)):
            self._TranscodeSubtitle(unquote(path[1]), headers, data, path[2])
        else:
            Log('[PS] Invalid request received', Log.DEBUG)
            self.send_error(501, 'Invalid request')

    def _AlterGPR(self, endpoint, headers, data):
        """ GPR data alteration for better language parsing and subtitles streaming instead of pre-caching """

        try:
            from urllib.parse import quote_plus
        except ImportError:
            from urllib import quote_plus
        import json
        from xbmc import convertLanguage, ENGLISH_NAME

        status_code, headers, content = self._ForwardRequest('get', endpoint, headers, data)

        # Grab the subtitle urls, merge them in a single list, append the locale codes to let Kodi figure
        # out which URL has which language, then sort them neatly in a human digestible order.
        content = json.loads(content)
        content['subtitles'] = []
        newsubs = []

        # Count the number of duplicates with the same ISO 639-1 codes
        langCount = {'forcedNarratives': {}, 'subtitleUrls': {}}
        for sub_type in list(langCount):  # list() instead of .keys() to avoid py3 iteration errors
            if sub_type in content:
                for i in range(0, len(content[sub_type])):
                    lang = content[sub_type][i]['languageCode'][0:2]
                    if lang not in langCount[sub_type]:
                        langCount[sub_type][lang] = 0
                    langCount[sub_type][lang] += 1

        # Merge the different subtitles lists in a single one, and append a spurious name file
        # to let Kodi figure out the locale, while at the same time enabling subtitles to be
        # proxied and transcoded on-the-fly.
        for sub_type in list(langCount):  # list() instead of .keys() to avoid py3 iteration errors
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
                    cl = py2_decode(convertLanguage(fn[0:2], ENGLISH_NAME))
                    newsubs.append((content[sub_type][i], cl, fn, variants, escapedurl))
                del content[sub_type]  # Reduce the data transfer by removing the lists we merged

        # Create the new merged subtitles list, and append time stretched variants.
        for sub in [x for x in sorted(newsubs, key=lambda sub: (sub[1], sub[2], sub[3]))]:
            content['subtitles'].append(sub[0])

        self._SendResponse(status_code, headers, json.dumps(content), True)

    def _AlterMPD(self, endpoint, headers, data):
        """ MPD alteration for better language parsing """

        try:
            from urllib.parse import urlparse
        except ImportError:
            from urlparse import urlparse
        import re

        # Extrapolate the base CDN url to avoid proxying data we don't need to
        url_parts = urlparse(endpoint)
        baseurl = url_parts.scheme + '://' + url_parts.netloc + re.sub(r'[^/]+$', '', url_parts.path)

        def _rebase(data):
            data = data.replace('<BaseURL>', '<BaseURL>' + baseurl)
            data = re.sub(r'(<SegmentTemplate\s+[^>]*?\s*media=")', r'\1' + baseurl, data)
            data = re.sub(r'(<SegmentTemplate\s+[^>]*?\s*initialization=")', r'\1' + baseurl, data)
            return data

        # Start the chunked reception
        status_code, headers, r = self._ForwardRequest('get', endpoint, headers, data, True)

        with self._PrepareChunkedResponse(status_code, headers) as gzstream:
            if r.encoding is None:
                r.encoding = 'utf-8'
            buffer = ''
            bPeriod = False
            Log('[PS] Loading MPD and rebasing as {}'.format(baseurl), Log.DEBUG)
            for chunk in r.iter_content(chunk_size=1048576, decode_unicode=True):
                buffer += py2_decode(chunk)

                # Flush everything up to audio AdaptationSets as fast as possible
                pos = re.search(r'(<AdaptationSet[^>]*contentType="video"[^>]*>.*?</AdaptationSet>\s*)' if bPeriod else r'(<Period[^>]*>\s*)', buffer, flags=re.DOTALL)
                if pos:
                    if 0 < pos.start(1):
                        self._SendChunk(gzstream, buffer[0:pos.start(1)])
                    if not bPeriod:
                        bPeriod = True
                        self._SendChunk(gzstream, buffer[pos.start(1):pos.end(1)])
                    else:
                        self._SendChunk(gzstream, _rebase(buffer[pos.start(1):pos.end(1)]))
                    buffer = buffer[pos.end(1):]

            # Count the number of duplicates with the same ISO 639-1 codes
            Log('[PS] Parsing languages', Log.DEBUG)
            languages = []
            langCount = {}
            for lang in re.findall(r'<AdaptationSet[^>]*audioTrackId="([^"]+)"[^>]*>', buffer):
                if lang not in languages:
                    languages.append(lang)
            for lang in languages:
                lang = lang[0:2]
                if lang not in langCount:
                    langCount[lang] = 0
                langCount[lang] += 1

            # Send corrected AdaptationSets, one at a time through chunked transfer
            Log('[PS] Altering <AdaptationSet>s', Log.DEBUG)
            while True:
                pos = re.search(r'(<AdaptationSet[^>]*>)(.*?</AdaptationSet>)', buffer, flags=re.DOTALL)
                if None is pos:
                    break
                # Log('[PS] AdaptationSet position: ([{}:{}], [{}:{}])'.format(pos.start(1), pos.end(1), pos.start(2), pos.end(2)))
                setTag = buffer[pos.start(1):pos.end(1)]
                try:
                    trackId = re.search(r'\s+audioTrackId="([a-z]{2})(-[a-z0-9]{2,})_(dialog|descriptive)', setTag).groups()
                    lang = re.search(r'\s+lang="([a-z]{2})"', setTag).group(1)

                    newLocale = self._AdjustLocale(trackId[0] + trackId[1], langCount[trackId[0]])
                    if 'descriptive' == trackId[2]:
                        newLocale += (' ' if '-' in newLocale else '-') + '[Audio Description]'
                    setTag = setTag.replace('lang="{}"'.format(lang), 'lang="{}"'.format(newLocale))
                except:
                    pass

                self._SendChunk(gzstream, setTag)
                self._SendChunk(gzstream, _rebase(buffer[pos.start(2):pos.end(2)]))
                buffer = buffer[pos.end(2):]

            # Send the rest and signal EOT
            if 0 < len(buffer):
                self._SendChunk(gzstream, buffer)
            self._EndChunkedTransfer(gzstream)

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
            if self.server._s.subtitleStretch:
                def _stretch(f):
                    millis = int(f.group('h')) * 3600000 + int(f.group('m')) * 60000 + int(f.group('s')) * 1000 + int(f.group('ms'))
                    h, m = divmod(millis * _stretch.factor, 3600000)
                    m, s = divmod(m, 60000)
                    s, ms = divmod(s, 1000)
                    # Truncate to the decimal of a ms (for lazyness)
                    return '%02d:%02d:%02d,%03d' % (h, m, s, int(ms))
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
                    text = re.sub(r'^(?!{}|{})'.format(lookup('RIGHT-TO-LEFT MARK'), lookup('RIGHT-TO-LEFT EMBEDDING')),
                                  lookup('RIGHT-TO-LEFT EMBEDDING'), text, flags=re.MULTILINE)
                    text = text.replace('?', '؟').replace(',', '،')

                for ec in [('&amp;', '&'), ('&quot;', '"'), ('&lt;', '<'), ('&gt;', '>'), ('&apos;', "'")]:
                    text = text.replace(ec[0], ec[1])
                num += 1
                srt += '%s\n%s --> %s\n%s\n\n' % (num, tt[0], tt[1], text)
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
