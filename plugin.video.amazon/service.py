import xbmc
import xbmcaddon
from resources.lib.common import getConfig, writeConfig, import_dt, updateRunning, Log

datetime, timedelta = import_dt()

if __name__ == '__main__':
    Log('AmazonDB: Service Start')
    addon = xbmcaddon.Addon()
    writeConfig('update_running', 'false')
    freq = int('0' + addon.getSetting('auto_update'))
    addonid = addon.getAddonInfo('id')
    checkfreq = 60
    idleupdate = 300
    startidle = 0
    monitor = xbmc.Monitor()

    if freq:
        while not monitor.abortRequested():
            today = datetime.today()
            freq = addon.getSetting('auto_update')
            time = addon.getSetting('update_time')
            time = '00:00' if time == '' else time
            last = getConfig('last_update', '1970-01-01')
            update = updateRunning()

            if freq == '0':
                break
            dt = last + ' ' + time
            dtlast = datetime.strptime(dt, '%Y-%m-%d %H:%M')
            freqdays = [0, 1, 2, 5, 7][int(freq)]
            lastidle = xbmc.getGlobalIdleTime()
            if xbmc.Player().isPlaying():
                startidle = lastidle
            if lastidle < startidle:
                startidle = 0
            idletime = lastidle - startidle
            if addon.getSetting('wait_idle') != 'true':
                idletime = idleupdate

            if dtlast + timedelta(days=freqdays) <= today and idletime >= idleupdate:
                if not update:
                    Log('AmazonDB: Starting DBUpdate (%s / %s)' % (dtlast, today))
                    xbmc.executebuiltin('XBMC.RunPlugin(plugin://%s/?mode=appfeed&sitemode=updateAll)' % addonid)

            if monitor.waitForAbort(checkfreq):
                break
    xbmc.log('AmazonDB: Service End')
