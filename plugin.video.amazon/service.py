import xbmc
import xbmcaddon
import time
from resources.lib.common import getConfig, writeConfig, Log
monitor = xbmc.Monitor()


def strp(value, form):
    while True:
        try:
            return datetime(*(time.strptime(value, form)[0:6]))
        except AttributeError:
            return datetime.strptime(value, form)
        except:
            if monitor.waitForAbort(1):
                exit()


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


while True:
    try:
        from datetime import datetime, timedelta
        datetime.today()
        strp('1970-01-01 00:00', '%Y-%m-%d %H:%M')
        timedelta()
        break
    except ImportError(datetime), e:
        Log('Importerror: %s' % e, xbmc.LOGERROR)
        if monitor.waitForAbort(1):
            exit()


if __name__ == '__main__':
    Log('AmazonDB: Service Start')
    addon = xbmcaddon.Addon()
    writeConfig('update_running', 'false')
    freq = int('0' + addon.getSetting('auto_update'))
    addonid = addon.getAddonInfo('id')
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
            dt = last + ' ' + time
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
    xbmc.log('AmazonDB: Service End')
