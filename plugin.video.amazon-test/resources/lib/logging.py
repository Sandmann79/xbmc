#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from inspect import currentframe, getframeinfo
from os.path import join as OSPJoin, basename as opb

from kodi_six import xbmc, xbmcvfs
from kodi_six.utils import py2_encode

from .common import Globals, Settings

_g = Globals()
_s = Settings()

def_loglevel = 2 if _g.KodiVersion < 19 else 1


def Log(msg, level=def_loglevel):
    if level == xbmc.LOGDEBUG and _s.logging:
        level = def_loglevel
    fi = getframeinfo(currentframe().f_back)
    msg = '[{0}]{2} {1}'.format(_g.__plugin__, msg, '' if not _s.logging else ' {}:{}'.format(opb(fi.filename), fi.lineno))
    xbmc.log(py2_encode('msg: %s' % msg), level)


Log.DEBUG = xbmc.LOGDEBUG
Log.ERROR = xbmc.LOGERROR
Log.FATAL = xbmc.LOGFATAL
Log.INFO = def_loglevel
Log.WARNING = xbmc.LOGWARNING


def LogCaller():
    frame = currentframe().f_back
    fcaller = getframeinfo(frame.f_back)
    fcallee = getframeinfo(frame)
    msg = '[{}] {}:{} called from: {}:{}'.format(_g.__plugin__, opb(fcallee.filename), fcallee.lineno, opb(fcaller.filename), fcaller.lineno)
    xbmc.log(msg, Log.INFO)


def WriteLog(data, fn='avod', force=False, comment=None):
    if not _s.logging and not force:
        return

    cnt = 0
    while True:
        file = '{}{}.log'.format(fn, (cnt*-1 if cnt > 0 else ''))
        path = OSPJoin(_g.LOG_PATH, file)
        if not xbmcvfs.exists(path):
            break
        cnt += 1
    logfile = xbmcvfs.File(path, 'w')
    if comment:
        logfile.write(py2_encode(comment))
    logfile.write(py2_encode(data))
    logfile.close()
    Log('Saved Log with filename “{}”'.format(file), Log.DEBUG)


def LogJSON(o, comment=None, optionalName=None):
    from json import dump

    if (not o) or (not _s.json_dump):
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
    with co(OSPJoin(_g.LOG_PATH, fn), 'w+', 'utf-8') as f:
        if comment:
            f.write('/* %s */\n' % comment)
        dump(o, f, sort_keys=True, indent=4)
        Log('Saved JSON data with filename “{}”'.format(fn), Log.DEBUG)


def createZIP():
    from zipfile import ZipFile, ZIP_DEFLATED
    from datetime import datetime
    from .common import py2_decode, translatePath, getString

    kodilog = OSPJoin(py2_decode(translatePath('special://logpath')), 'kodi.log')
    arcfile = OSPJoin(_g.DATA_PATH, 'logfiles_{}.zip'.format(datetime.now().strftime('%Y%m%d-%H%M%S')))
    arccmp = {'compresslevel': 5} if _g.KodiVersion >= 19 else {}
    arc = ZipFile(arcfile, 'w', ZIP_DEFLATED, **arccmp)

    for fn in xbmcvfs.listdir(_g.LOG_PATH)[1]:
        arc.write(OSPJoin(_g.LOG_PATH, fn), arcname=(OSPJoin('log', fn)))
    arc.write(kodilog, arcname='kodi.log')
    arc.close()
    _g.dialog.notification(_g.__plugin__, getString(30281).format(arcfile))
    Log('Archive created at {}'.format(arcfile), Log.DEBUG)


def removeLogs():
    for fn in xbmcvfs.listdir(_g.LOG_PATH)[1]:
        xbmcvfs.delete(OSPJoin(_g.LOG_PATH, fn))
    Log('Logfiles removed', Log.DEBUG)
