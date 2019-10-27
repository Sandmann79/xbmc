#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from os.path import join as OSPJoin
import xbmc
import xbmcvfs
from .common import Globals, Settings

g = Globals()
s = Settings()


def Log(msg, level=xbmc.LOGNOTICE):
    if level == xbmc.LOGDEBUG and s.verbLog:
        level = xbmc.LOGNOTICE
    msg = '[{}] {}'.format(g.__plugin__, msg)
    msg = msg if isinstance(u'', str) else msg.encode('utf-8')
    xbmc.log(msg, level)


def WriteLog(data, fn=''):
    if not s.verbLog:
        return

    fn = '-' + fn if fn else ''
    fn = 'avod{}.log'.format(fn)
    path = OSPJoin(g.HOME_PATH, fn)
    try:
        data = data.encode('utf-8')
    except:
        pass
    logfile = xbmcvfs.File(path, 'w')
    logfile.write(data.__str__())
    logfile.close()


def LogJSON(o, url):
    from os.path import join as OSPJoin
    from json import dump

    if not o:
        return
    from codecs import open as co
    from datetime import datetime
    try:
        LogJSON.counter += 1
    except:
        LogJSON.counter = 0
    with co(OSPJoin(g.DATA_PATH, '{}_{}.json'.format(datetime.now().strftime('%Y%m%d_%H%M%S%f'), LogJSON.counter)), 'w+', 'utf-8') as f:
        f.write('/* %s */\n' % url)
        dump(o, f, sort_keys=True, indent=4)


Log.DEBUG = xbmc.LOGDEBUG
Log.ERROR = xbmc.LOGERROR
# Log.FATAL = xbmc.LOGFATAL
Log.INFO = xbmc.LOGINFO
# Log.NOTICE = xbmc.LOGNOTICE
# Log.SEVERE = xbmc.LOGSEVERE
Log.WARNING = xbmc.LOGWARNING
