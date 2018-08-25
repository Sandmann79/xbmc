from __future__ import unicode_literals
import xbmc
from resources.lib.common import Settings
from resources.lib.logging import Log
from resources.lib.configs import *

if __name__ == '__main__':
    _s = Settings()
    monitor = xbmc.Monitor()
    Log('Service: Start')
    check_freq = 60
    export_freq = 24 * 60 * 60

    if _s.wl_export:
        while not monitor.abortRequested():
            import time
            last_export = float(getConfig('last_wl_export', '0'))
            cur_time = time.time()
            if cur_time >= last_export + export_freq:
                Log('Service: Starting Export of Watchlist')
                writeConfig('last_wl_export', cur_time)
                xbmc.executebuiltin('XBMC.RunPlugin(plugin://plugin.video.amazon-test/?mode=getListMenu&url=watchlist&export=1)')
                #g.amz.getListMenu(g.watchlist, True)
            if monitor.waitForAbort(check_freq):
                break
    Log('Service: End')
