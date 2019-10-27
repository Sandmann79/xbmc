#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import unicode_literals
import xbmc
import threading
from resources.lib.logging import Log
from resources.lib.configs import *


class BackgroundService():
    freqCheck = 60
    freqExport = 86400  # 24 * 60 * 60 seconds
    lastCheck = 0

    def __init__(self):
        from resources.lib.common import Settings
        from resources.lib.proxy import ProxyTCPD
        from resources.lib.configs import writeConfig
        self._s = Settings()
        self.lastExport = float(getConfig('last_wl_export', '0'))
        self.proxy = ProxyTCPD(self._s)
        writeConfig('proxyaddress', '127.0.0.1:{}'.format(self.proxy.port))
        Log('Service: Proxy bound to {}'.format(self._s.proxyaddress))
        self.proxy_thread = threading.Thread(target=self.proxy.serve_forever)

    def run(self):

        def _start_servers():
            self.proxy.server_activate()
            self.proxy.timeout = 1
            self.proxy_thread.start()
            Log('Service: Proxy server started')

        def _stop_servers():
            self.proxy.server_close()
            self.proxy.shutdown()
            self.proxy_thread.join()
            Log('Service: Proxy server stopped')

        from time import time
        monitor = xbmc.Monitor()

        _start_servers()
        Log('Service started')

        while not monitor.abortRequested():
            ct = time()
            if (ct >= (self.lastCheck + self.freqCheck)) and self._s.wl_export:
                self.lastCheck = ct
                self.export_watchlist(ct)

            if monitor.waitForAbort(1):
                break

        _stop_servers()
        Log('Service stopped')

    def export_watchlist(self, cur_time=0, override=False):
        """ Export the watchlist every self.freqExport seconds or when triggered by override """
        if override or (cur_time >= (self.freqExport + self.lastExport)):
            Log('Service: Exporting the Watchlist')
            self.lastExport = cur_time
            writeConfig('last_wl_export', cur_time)
            xbmc.executebuiltin('XBMC.RunPlugin(plugin://plugin.video.amazon-test/?mode=getListMenu&url=watchlist&export=2)')


if __name__ == '__main__':
    BackgroundService().run()
