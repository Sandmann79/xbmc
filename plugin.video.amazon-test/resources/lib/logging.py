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
    msg = '[%s] %s' % (g.__plugin__, msg)
    xbmc.log(msg.encode('utf-8'), level)


def WriteLog(data, fn=''):
    if not s.verbLog:
        return

    fn = '-' + fn if fn else ''
    fn = 'avod%s.log' % fn
    path = OSPJoin(g.HOME_PATH, fn)
    if isinstance(data, unicode):
        data = data.encode('utf-8')
    logfile = xbmcvfs.File(path, 'w')
    logfile.write(data.__str__())
    logfile.close()


Log.DEBUG = xbmc.LOGDEBUG
Log.ERROR = xbmc.LOGERROR
# Log.FATAL = xbmc.LOGFATAL
Log.INFO = xbmc.LOGINFO
# Log.NOTICE = xbmc.LOGNOTICE
# Log.SEVERE = xbmc.LOGSEVERE
Log.WARNING = xbmc.LOGWARNING
