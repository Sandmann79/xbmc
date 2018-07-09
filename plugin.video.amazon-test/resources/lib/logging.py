#!/usr/bin/env python
# -*- coding: utf-8 -*-
from os.path import join as OSPJoin
import xbmc
import xbmcvfs
from resources.lib.common import Globals, Settings


def Log(msg, level=xbmc.LOGNOTICE):
    if not hasattr(Log, '_s'):
        Log._s = Settings()
    if not hasattr(Log, '_g'):
        Log._g = Globals()
    if level == xbmc.LOGDEBUG and Log._s.verbLog:
        level = xbmc.LOGNOTICE
    msg = '[%s] %s' % (Log._g.__plugin__, msg)
    xbmc.log(msg.encode('utf-8'), level)
Log.DEBUG = xbmc.LOGDEBUG
Log.ERROR = xbmc.LOGERROR
# Log.FATAL = xbmc.LOGFATAL
Log.INFO = xbmc.LOGINFO
# Log.NOTICE = xbmc.LOGNOTICE
# Log.SEVERE = xbmc.LOGSEVERE
Log.WARNING = xbmc.LOGWARNING


def WriteLog(data, fn=''):
    if not s.verbLog:
        return

    fn = '-' + fn if fn else ''
    fn = 'avod%s.log' % fn
    path = os.path.join(g.HOME_PATH, fn)
    if isinstance(data, unicode):
        data = data.encode('utf-8')
    logfile = xbmcvfs.File(path, 'w')
    logfile.write(data.__str__())
    logfile.close()
