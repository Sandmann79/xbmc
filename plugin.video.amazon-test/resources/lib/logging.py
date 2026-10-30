# -*- coding: utf-8 -*-
from inspect import currentframe
from os.path import join as OSPJoin, basename as opb
import re

import xbmc, xbmcvfs

from .common import Globals, Settings

_g = Globals()
_s = Settings()

_RE_SENSITIVE = re.compile(
    r'(?i)((?:access_token|refresh_token|source_token|password|guess|otpCode|pin|authorization|cookie|x-amzn-sessionid|ubid-\w+|at-\w+|sess-at-\w+|session-token)["\'\s:=]+)([^"\'&\s,;}{]+)'
)


def _sanitize(text):
    """Maskiert sensible Tokens, Passwörter und Session-Cookies vor dem Schreiben ins Log."""
    if not text:
        return ''
    return _RE_SENSITIVE.sub(r'\1***REDACTED***', str(text))


def Log(msg, level=xbmc.LOGINFO):
    if level == xbmc.LOGDEBUG and _s.logging:
        level = xbmc.LOGINFO
    loc = ''
    if _s.logging:
        frame = currentframe().f_back
        if frame is not None:
            loc = f' {opb(frame.f_code.co_filename)}:{frame.f_lineno}'
    msg = f'[{_g.__plugin__}]{loc} {_sanitize(msg)}'
    xbmc.log(msg, level)


Log.DEBUG = xbmc.LOGDEBUG
Log.ERROR = xbmc.LOGERROR
Log.FATAL = xbmc.LOGFATAL
Log.INFO = xbmc.LOGINFO
Log.WARNING = xbmc.LOGWARNING


def LogCaller():
    frame = currentframe().f_back
    fcaller = frame.f_back if frame else None
    if frame and fcaller:
        msg = f'[{_g.__plugin__}] {opb(frame.f_code.co_filename)}:{frame.f_lineno} called from: {opb(fcaller.f_code.co_filename)}:{fcaller.f_lineno}'
        xbmc.log(msg, Log.INFO)
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
            logfile.write(_sanitize(comment))
        logfile.write(_sanitize(data))
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
            f.write(f'/* {_sanitize(comment)} */\n')
        f.write(_sanitize(dumps(o, sort_keys=True, indent=4)))
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