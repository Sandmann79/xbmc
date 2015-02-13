import xbmc
import xbmcaddon
from datetime import datetime, timedelta

if __name__ == '__main__':
    print 'AmazonDB: Service Start'
    id = 'plugin.video.amazon'
    today = datetime.today().date()
    addon = xbmcaddon.Addon(id)
    freq = addon.getSetting('auto_update')
    last = addon.getSetting('last_update')
    if last == '':
        last = '1970-01-01'
    dtlast = datetime.strptime(last, '%Y-%m-%d').date()
    if (not freq == '') and (not freq == '0'):
        freqdays = [0, 1, 2, 5, 7][int(freq)]
        if (dtlast + timedelta(days=freqdays)) <= today:
            xbmc.executebuiltin('XBMC.RunPlugin(plugin://%s/?mode=<appfeed>&sitemode=<updateAll>)' % id)
    print 'AmazonDB: Service End'