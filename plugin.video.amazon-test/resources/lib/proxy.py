#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Varstahl
# Module: CryptoProxy
# Created: 12/01/2019

from __future__ import unicode_literals
import base64
from SocketServer import TCPServer
from resources.lib.logging import Log
try:
    from BaseHTTPServer import BaseHTTPRequestHandler  # Python2 HTTP Server
except ImportError:
    from http.server import BaseHTTPRequestHandler  # Python3 HTTP Server


class ProxyHTTPD(BaseHTTPRequestHandler):
    def log_message(self, *args):
        """Disable the BaseHTTPServer Log"""
        pass

    def _AdjustLocale(self, p1, p2):
        """Locale conversion helper"""
        localeConversionTable = {
            'ar-001': 'ar',
            'cmn-HANS': 'zh-HANS',
            'cmn-HANT': 'zh-HANT',
            'da-DK': 'da',
            'es-419': 'es-Latinoamerica',
            'ja-JP': 'ja',
            'ko-KR': 'ko',
            'nb-NO': 'nb',
            'sv-SE': 'sv',
            'pt-BR': 'pt-Brazil'
        }
        new_lang = p1 + ('' if p1 == p2 else '-' + p2.upper())
        if new_lang in localeConversionTable.keys():
            new_lang = localeConversionTable[new_lang]
        return new_lang

    def _ParseBaseRequest(self):
        """Return path, headers and post data commonly required by all methods"""
        from resources.lib.network import MechanizeLogin
        from urlparse import unquote, urlparse, parse_qsl

        path = urlparse(self.path).path[1:]  # Get URI without the trailing slash
        path = path.split('/')  # license/<asin>/<ATV endpoint>
        Log('[PS] Requested path {}'.format(path), Log.DEBUG)

        # Retrieve headers, data and set up cookies for the forward
        cookie = MechanizeLogin()
        if not cookie:
            Log('[PS] Not logged in', Log.DEBUG)
            self.send_response(400)
            return (None, None, None)
        headers = {k: self.headers[k] for k in self.headers if k not in ['host', 'content-length']}
        headers['cookie'] = ';'.join(['%s=%s' % (k, v) for k, v in cookie.items()])
        data_length = self.headers.get('content-length')
        data = None if None is data_length else {k: v for k, v in parse_qsl(self.rfile.read(int(data_length)))}
        return (path, headers, data)

    def _ForwardRequest(self, method, endpoint, headers, data=None):
        """Forwards the request to the proper target"""
        import requests
        r = requests.request(method, endpoint, data=data, headers=headers, verify=self.server._s.verifySsl)
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

        Log('[PS] Invalid request received', Log.DEBUG)
        self.send_response(501)
        return

    def do_GET(self):
        """Respond to GET requests"""
        from urlparse import unquote, urlparse
        import re

        path, headers, data = self._ParseBaseRequest()

        if None is path:
            return

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
                audioTrack = re.search(r' audioTrackId="([a-z]{2})-([a-z0-9]{2,})[^"]+[^>]+ lang="([a-z]{2})"', s[0])
                new_sets.append((s[0] if None is audioTrack else s[0].replace('lang="{}"'.format(audioTrack.group(3)), 'lang="{}"'.format(self._AdjustLocale(audioTrack.group(1), audioTrack.group(2))))) + s[1])

            content = header + ''.join(new_sets) + footer  # Reassemble the MPD
        else:
            Log('[PS] Invalid request received', Log.DEBUG)
            self.send_response(501)
            return

        self._SendResponse(status_code, headers, content)


class ProxyTCPD(TCPServer):
    def __init__(self, settings):
        """ Initialisation of the Proxy TCP server """
        self._s = settings  # Make settings available to the RequestHandler

        from socket import socket, AF_INET, SOCK_STREAM
        sock = socket(AF_INET, SOCK_STREAM)
        sock.bind(('127.0.0.1', 0))
        _, port = sock.getsockname()
        sock.close()
        self.port = port  # Save the current binded port

        TCPServer.__init__(self, ('127.0.0.1', port), ProxyHTTPD)
