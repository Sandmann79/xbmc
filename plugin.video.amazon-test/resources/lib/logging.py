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
def_loglevel = 2  # LOGNOTICE < Kodi Matrix => LOGINFO?


def Log(msg, level=def_loglevel):
    if level == xbmc.LOGDEBUG and s.verbLog:
        level = def_loglevel
    fi = getframeinfo(currentframe().f_back)
    msg = '[{0}]{2} {1}'.format(g.__plugin__, msg, '' if not s.verbLog else ' {}:{}'.format(opb(fi.filename), fi.lineno))
    xbmc.log(py2_encode(msg), level)


Log.DEBUG = xbmc.LOGDEBUG
Log.ERROR = xbmc.LOGERROR
Log.FATAL = xbmc.LOGFATAL
Log.INFO = def_loglevel
Log.WARNING = xbmc.LOGWARNING


def LogCaller():
    frame = currentframe().f_back
    fcaller = getframeinfo(frame.f_back)
    fcallee = getframeinfo(frame)
    msg = '[{}] {}:{} called from: {}:{}'.format(g.__plugin__, opb(fcallee.filename), fcallee.lineno, opb(fcaller.filename), fcaller.lineno)
    xbmc.log(msg, Log.INFO)


def WriteLog(data, fn=''):
    if not s.verbLog:
        return

    fn = '-' + fn if fn else ''
    fn = 'avod{}.log'.format(fn)
    path = OSPJoin(g.HOME_PATH, fn)
    logfile = xbmcvfs.File(path, 'w')
    logfile.write(py2_encode(data))
    logfile.close()


def LogJSON(o, url=None, optionalName=None):
    from json import dump

    if not o:
        return
    from codecs import open as co
    from datetime import datetime
    try:
        LogJSON.counter += 1
    except:
        LogJSON.counter = 0
    fn = '{}_{}{}.json'.format(
        datetime.now().strftime('%Y%m%d_%H%M%S%f'),
        LogJSON.counter,
        '_' + optionalName if optionalName else ''
    )
    with co(OSPJoin(g.DATA_PATH, fn), 'w+', 'utf-8') as f:
        if url:
            f.write('/* %s */\n' % url)
        dump(o, f, sort_keys=True, indent=4)
        Log('Saved JSON data with filename “{}”'.format(fn), Log.DEBUG)
