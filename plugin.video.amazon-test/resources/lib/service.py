#!/usr/bin/env python
# -*- coding: utf-8 -*-
import threading

import xbmc
from xbmcaddon import Addon

from .logging import Log
from .configs import getConfig, writeConfig
from .common import Settings
from .proxy import ProxyTCPD


class BackgroundService(xbmc.Monitor):
    def __init__(self):
        super(BackgroundService, self).__init__()
        self._s = Settings()
        self.freqCheck = 60
        self.freqExport = 86400  # 24 * 60 * 60 seconds
        self.lastCheck = 0
        self.lastExport = float(getConfig('last_wl_export', '0'))
        self.wl_export = self._s.wl_export
        self.proxy = ProxyTCPD(self._s)
        writeConfig('loginlock', '')
        writeConfig('proxytoken', self.proxy.token)
        writeConfig('proxyaddress', f'127.0.0.1:{self.proxy.port}/{self.proxy.token}')
        Log(f'Service: Proxy bound to {self._s.proxyaddress}')
        self.proxy_thread = threading.Thread(target=self.proxy.serve_forever, daemon=True)

    def onSettingsChanged(self):
        xbmc.sleep(500)
        self._s._g._globals['addon'] = Addon()
        self.wl_export = self._s.wl_export

    def start(self):
        self.proxy_thread.start()
        Log('Service: Proxy server started')

        from time import time
        Log('Service started')

        while not self.abortRequested():
            ct = time()
            if (ct >= (self.lastCheck + self.freqCheck)) and self.wl_export:
                self.lastCheck = ct
                self.export_watchlist(ct)

            if self.waitForAbort(5):
                break

        Log('Service stopped')
        self.stop()

    def stop(self):
        self.proxy.shutdown()
        self.proxy.server_close()
        self.proxy_thread.join(timeout=5)
        for session in list(getattr(self.proxy.RequestHandlerClass, 'sessions', {}).values()):
            try:
                session.close()
            except Exception:
                pass
        getattr(self.proxy.RequestHandlerClass, 'sessions', {}).clear()
        Log('Service: Proxy server stopped')

    def export_watchlist(self, cur_time=0):
        """ Export the watchlist every self.freqExport seconds """
        if cur_time >= (self.freqExport + self.lastExport):
            Log('Service: Exporting the Watchlist')
            self.lastExport = cur_time
            xbmc.executebuiltin('RunPlugin(plugin://plugin.video.amazon-test/?mode=exportWatchlist)')
