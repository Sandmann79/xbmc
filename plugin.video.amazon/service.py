from __future__ import unicode_literals
import xbmc
import xbmcaddon
from resources.lib.common import getConfig, writeConfig, Log, var
var.__init__()


def strp(value, form):
    from time import strptime
    from datetime import datetime
    def_value = datetime.utcfromtimestamp(0)
    try:
        return datetime.strptime(value, form)
    except TypeError:
        try:
            return datetime(*(strptime(value, form)[0:6]))
        except ValueError as e:
            Log('time.strp error: {}'.format(e), xbmc.LOGERROR)
            return def_value
    except Exception as e:
        Log('datetime.strp error: {}'.format(e), xbmc.LOGERROR)
        return def_value


def updateRunning():
    from datetime import datetime, timedelta
    update = getConfig('update_running', 'false')
    if update != 'false':
        starttime = strp(update, '%Y-%m-%d %H:%M')
        if (starttime + timedelta(hours=6)) <= datetime.today():
            writeConfig('update_running', 'false')
            Log('DB Cancel update - duration > 6 hours')
        else:
            Log('DB Update already running', xbmc.LOGDEBUG)
            return True
    return False


if __name__ == '__main__':
    addon = xbmcaddon.Addon()
    monitor = xbmc.Monitor()
    Log('AmazonDB: Service Start')
    writeConfig('update_running', 'false')
    freq = int('0' + var.addon.getSetting('auto_update'))
    checkfreq = 60
    idleupdate = 300
    startidle = 0

    if freq:
        while not monitor.abortRequested():
            from datetime import datetime, timedelta
            today = datetime.today()
            freq = var.addon.getSetting('auto_update')
            time = var.addon.getSetting('update_time')
            time = '00:00' if time == '' else time
            last = getConfig('last_update', '1970-01-01')
            update_run = updateRunning()

            if freq == '0':
                break
            dt = last + ' ' + time[0:5]
            dtlast = strp(dt, '%Y-%m-%d %H:%M')
            freqdays = [0, 1, 2, 5, 7][int(freq)]
            lastidle = xbmc.getGlobalIdleTime()
            if xbmc.Player().isPlaying():
                startidle = lastidle
            if lastidle < startidle:
                startidle = 0
            idletime = lastidle - startidle
            if var.addon.getSetting('wait_idle') != 'true':
                idletime = idleupdate

            if dtlast + timedelta(days=freqdays) <= today and idletime >= idleupdate:
                if not update_run:
                    Log('AmazonDB: Starting DBUpdate ({} / {})'.format(dtlast, today))
                    xbmc.executebuiltin('XBMC.RunPlugin(plugin://{}/?mode=appfeed&sitemode=updateAll)'.format(var.addon.getAddonInfo('id')))

            if monitor.waitForAbort(checkfreq):
                break
    Log('AmazonDB: Service End')
