# -*- coding: utf-8 -*-
from inspect import currentframe, getframeinfo
from os.path import join as OSPJoin, basename as opb

import xbmc, xbmcvfs

from .common import Globals, Settings

_g = Globals()
_s = Settings()


def Log(msg, level=xbmc.LOGINFO):
    if level == xbmc.LOGDEBUG and _s.logging:
        level = xbmc.LOGINFO
    fi = getframeinfo(currentframe().f_back)
    msg = f"[{_g.__plugin__}]{('' if not _s.logging else f' {opb(fi.filename)}:{fi.lineno}')} {msg}"
    xbmc.log(msg, level)


Log.DEBUG = xbmc.LOGDEBUG
Log.ERROR = xbmc.LOGERROR
Log.FATAL = xbmc.LOGFATAL
Log.INFO = xbmc.LOGINFO
Log.WARNING = xbmc.LOGWARNING


def LogCaller():
    frame = currentframe().f_back
    fcaller = getframeinfo(frame.f_back)
    fcallee = getframeinfo(frame)
    msg = f'[{_g.__plugin__}] {opb(fcallee.filename)}:{fcallee.lineno} called from: {opb(fcaller.filename)}:{fcaller.lineno}'
    xbmc.log(msg, Log.INFO)


def WriteLog(data, fn='avod', force=False, comment=None):
    if not _s.logging and not force:
        return

    cnt = 0
    while True:
        file = f"{fn}{cnt * -1 if cnt > 0 else ''}.log"
        path = OSPJoin(_g.LOG_PATH, file)
        if not xbmcvfs.exists(path):
            break
        cnt += 1
    with xbmcvfs.File(path, 'w') as logfile:
        if comment:
            logfile.write(comment)
        logfile.write(data)
    Log(f'Saved Log with filename “{file}”', Log.DEBUG)


def LogJSON(o, comment=None, optionalName=None):
    from json import dumps

    if (not o) or (not _s.json_dump):
        return
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
    with xbmcvfs.File(OSPJoin(_g.LOG_PATH, fn), 'w') as f:
        if comment:
            f.write(f'/* {comment} */\n')
        f.write(dumps(o, sort_keys=True, indent=4))
        Log(f'Saved JSON data with filename “{fn}”', Log.DEBUG)


def createZIP():
    import io
    from zipfile import ZipFile, ZIP_DEFLATED
    from datetime import datetime
    from .common import translatePath, getString

    kodilog = OSPJoin(translatePath('special://logpath'), 'kodi.log')
    arcfile = OSPJoin(_g.DATA_PATH, f"logfiles_{datetime.now().strftime('%Y%m%d-%H%M%S')}.zip")
    arccmp = {'compresslevel': 5} if _g.KodiVersion >= 19 else {}
    buf = io.BytesIO()
    with ZipFile(buf, 'w', ZIP_DEFLATED, **arccmp) as arc:
        for fn in xbmcvfs.listdir(_g.LOG_PATH)[1]:
            fpath = OSPJoin(_g.LOG_PATH, fn)
            with xbmcvfs.File(fpath) as lf:
                arc.writestr(OSPJoin('log', fn), bytes(lf.readBytes()))
        if xbmcvfs.exists(kodilog):
            with xbmcvfs.File(kodilog) as kf:
                arc.writestr('kodi.log', bytes(kf.readBytes()))
    with xbmcvfs.File(arcfile, 'w') as zf:
        zf.write(bytearray(buf.getvalue()))
    _g.dialog.notification(_g.__plugin__, getString(30281).format(arcfile))
    Log(f'Archive created at {arcfile}', Log.DEBUG)


def removeLogs():
    for fn in xbmcvfs.listdir(_g.LOG_PATH)[1]:
        xbmcvfs.delete(OSPJoin(_g.LOG_PATH, fn))
    Log('Logfiles removed', Log.DEBUG)