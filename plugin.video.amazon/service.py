from __future__ import unicode_literals
import xbmc
import xbmcaddon
import time
from resources.lib.common import getConfig, writeConfig, Log
monitor = xbmc.Monitor()


def strp(value, form):
    Log('strp value: %s' % value)
    Log('strp hasattr: %s' % hasattr(datetime, 'strptime'))
    def_value = datetime.utcfromtimestamp(0)
    try:
        return datetime.strptime(value, form)
    except TypeError:
        try:
            return datetime(*(time.strptime(value, form)[0:6]))
        except ValueError, e:
            Log('time.strp error: %s' % e, xbmc.LOGERROR)
            return def_value
    except Exception, e:
        Log('datetime.strp error: %s' % e, xbmc.LOGERROR)
        return def_value


def updateRunning():
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
    while True:
        try:
            from datetime import datetime, timedelta
            break
        except ImportError(datetime), e:
            Log('Importerror: %s' % e, xbmc.LOGERROR)
            if monitor.waitForAbort(1):
                exit()
    Log('AmazonDB: Service Start')
    addon = xbmcaddon.Addon()
    addonid = addon.getAddonInfo('id')
    datetime.today()
    strp('1970-01-01 00:00', '%Y-%m-%d %H:%M')
    timedelta()
    writeConfig('update_running', 'false')
    freq = int('0' + addon.getSetting('auto_update'))
    checkfreq = 60
    idleupdate = 300
    startidle = 0

    if freq:
        while not monitor.abortRequested():
            addon = xbmcaddon.Addon()
            today = datetime.today()
            freq = addon.getSetting('auto_update')
            time = addon.getSetting('update_time')
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
            if addon.getSetting('wait_idle') != 'true':
                idletime = idleupdate

            if dtlast + timedelta(days=freqdays) <= today and idletime >= idleupdate:
                if not update_run:
                    Log('AmazonDB: Starting DBUpdate (%s / %s)' % (dtlast, today))
                    xbmc.executebuiltin('XBMC.RunPlugin(plugin://%s/?mode=appfeed&sitemode=updateAll)' % addonid)

            if monitor.waitForAbort(checkfreq):
                break
    Log('AmazonDB: Service End')
