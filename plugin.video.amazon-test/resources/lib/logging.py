#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from inspect import currentframe, getframeinfo
from os.path import join as OSPJoin, basename as opb
from sys import version_info
from kodi_six import xbmc, xbmcvfs
from kodi_six.utils import py2_encode
import xbmc
import xbmcvfs
from .common import Globals, Settings

g = Globals()
s = Settings()


def LogCaller():
    fi = getframeinfo(currentframe().f_back.f_back)
    msg = '[{}] Called from: {}:{}'.format(g.__plugin__, opb(fi.filename), fi.lineno)
    xbmc.log(py2_encode(msg), xbmc.LOGNOTICE)


def Log(msg, level=xbmc.LOGNOTICE):
    if level == xbmc.LOGDEBUG and s.verbLog:
        level = xbmc.LOGNOTICE
    fi = getframeinfo(currentframe().f_back)
    msg = '[{0}]{2} {1}'.format(g.__plugin__, msg, '' if not s.verbLog else ' {}:{}'.format(opb(fi.filename), fi.lineno))
    xbmc.log(py2_encode(msg), level)


def WriteLog(data, fn=''):
    if not s.verbLog:
        return

    fn = '-' + fn if fn else ''
    fn = 'avod{}.log'.format(fn)
    path = OSPJoin(g.HOME_PATH, fn)
    logfile = xbmcvfs.File(path, 'w')
    logfile.write(py2_encode(data))
    logfile.close()


def LogJSON(o, url):
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
