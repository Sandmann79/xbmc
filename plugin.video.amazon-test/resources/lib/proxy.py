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

    def _AdjustLocale(self, langCode, separator='-'):
        """Locale conversion helper"""
        try:
            p1, p2 = langCode.split('-')
        except:
            p1 = langCode
            p2 = langCode
        localeConversionTable = {
            'ar' + separator + '001': 'ar',
            'cmn' + separator + 'HANS': 'zh' + separator + 'HANS',
            'cmn' + separator + 'HANT': 'zh' + separator + 'HANT',
            'da' + separator + 'DK': 'da',
            'es' + separator + '419': 'es' + separator + 'Latinoamerica',
            'ja' + separator + 'JP': 'ja',
            'ko' + separator + 'KR': 'ko',
            'nb' + separator + 'NO': 'nb',
            'sv' + separator + 'SE': 'sv',
            'pt' + separator + 'BR': 'pt' + separator + 'Brazil'
        }
        new_lang = p1 + ('' if p1 == p2 else separator + p2.upper())
        new_lang = new_lang if new_lang not in localeConversionTable.keys() else localeConversionTable[new_lang]
        return new_lang

    def _ParseBaseRequest(self, method):
        """Return path, headers and post data commonly required by all methods"""
        from resources.lib.network import MechanizeLogin
        from urlparse import unquote, urlparse, parse_qsl

        path = urlparse(self.path).path[1:]  # Get URI without the trailing slash
        path = path.split('/')  # license/<asin>/<ATV endpoint>
        Log('[PS] Requested {} path {}'.format(method, path), Log.DEBUG)

        # Retrieve headers, data and set up cookies for the forward
        cookie = MechanizeLogin()
        if not cookie:
            Log('[PS] Not logged in', Log.DEBUG)
            self.send_error(440)
            return (None, None, None)
        headers = {k: self.headers[k] for k in self.headers if k not in ['host', 'content-length']}
        headers['cookie'] = ';'.join(['%s=%s' % (k, v) for k, v in cookie.items()])
        data_length = self.headers.get('content-length')
        data = None if None is data_length else {k: v for k, v in parse_qsl(self.rfile.read(int(data_length)))}
        return (path, headers, data)

    def _ForwardRequest(self, method, endpoint, headers, data=None):
        """Forwards the request to the proper target"""
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

        r = session.request(method, endpoint, data=data, headers=headers, verify=self.server._s.verifySsl)
        return (r.status_code, r.headers, r.content)

    def _SendResponse(self, code, headers, content):
        """Send a response to the caller"""
        # We don't use chunked or gunzipped transfers locally, so we removed the relative headers and
        # attach the contact length, before returning the response
        headers = {k: headers[k] for k in headers if k not in ['Transfer-Encoding', 'Content-Encoding']}
        headers['Content-Length'] = len(content)

        # Build the response
        self.send_response(code)
        for k in headers:
            self.send_header(k, headers[k])
        self.end_headers()
        self.wfile.write(content)

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
            status_code, headers, content = self._ForwardRequest('get', endpoint, headers)

            # Grab the subtitle urls, merge them in a single list, append the locale codes to let Kodi figure
            # out which URL has which language, then sort them neatly in a human digestible order.
            content = json.loads(content)
            content['subtitles'] = []
            for sub_type in ['forcedNarratives', 'subtitleUrls']:
                if sub_type in content:
                    for i in range(0, len(content[sub_type])):
                        fn = self._AdjustLocale(content[sub_type][i]['languageCode'], ' ')
                        variants = '{}{}'.format(
                            ' [CC]' if 'sdh' == content[sub_type][i]['type'] else '',
                            '.Forced' if 'forcedNarratives' == sub_type else ''
                        )
                        # Proxify the URLs, with a make believe Kodi-friendly file name
                        content[sub_type][i]['url'] = 'http://127.0.0.1:{}/subtitles/{}/{}.srt'.format(
                            self.server.port,
                            quote_plus(content[sub_type][i]['url']),
                            '{}{}'.format(fn, variants)
                        )
                        content['subtitles'].append((content[sub_type][i], xbmc.convertLanguage(fn[0:2], xbmc.ENGLISH_NAME).decode('utf-8') + fn, variants))
                del content[sub_type]  # Reduce the data transfer by removing the lists we merged
            content['subtitles'] = [x[0] for x in sorted(content['subtitles'], key=lambda sub: (sub[1], sub[2]))]
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
            status_code, headers, content = self._ForwardRequest('get', endpoint, headers)  # Call the destination server

            content = re.sub(r'(<BaseURL>)', r'\1{}'.format(baseurl), content)  # Rebase CDN URLs
            header, sets, footer = re.search(r'^(.*<Period [^>]*>\s*)(.*)(\s*</Period>.*)$', content, flags=re.DOTALL).groups()  # Extract <AdaptationSet>s

            # Alter the <AdaptationSet>s for our linguistic needs
            new_sets = []
            for s in re.findall(r'(<AdaptationSet\s+[^>]*>)(.*?</AdaptationSet>)', content, flags=re.DOTALL):
                audioTrack = re.search(r' audioTrackId="([a-z]{2}-[a-z0-9]{2,})[^"]+[^>]+ lang="([a-z]{2})"', s[0])
                new_sets.append((s[0] if None is audioTrack else s[0].replace('lang="%s"' % audioTrack.group(2), 'lang="%s"' % self._AdjustLocale(audioTrack.group(1)))) + s[1])

            content = header + ''.join(new_sets) + footer  # Reassemble the MPD
        elif ('subtitles' == path[0]) and (3 == len(path)):
            # On-the-fly subtitle transcoding (TTMLv2 => SRT)
            status_code, headers, content = self._ForwardRequest('get', unquote(path[1]), headers)
            if 0 < len(content):
                # Apply a bunch of regex to the content instead of line-by-line to save computation time
                content = re.sub(r'<(|/)span[^>]*>', r'<\1i>', content.decode('utf-8'))  # Using (|<search>) instead of ()? to avoid py2.7 empty matching error
                content = re.sub(r'([0-9]{2}:[0-9]{2}:[0-9]{2})\.', r'\1,', content)  # SRT-like timestamps
                content = re.sub(r'\s*<(?:tt:)?br\s*/>\s*', '\n', content)  # Replace <br/> with actual new lines

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
                content = srt.encode('utf-8')
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
        sock.bind(('127.0.0.1', 0))
        _, port = sock.getsockname()
        sock.close()
        self.port = port  # Save the current binded port

        ThreadingTCPServer.__init__(self, ('127.0.0.1', port), ProxyHTTPD)
