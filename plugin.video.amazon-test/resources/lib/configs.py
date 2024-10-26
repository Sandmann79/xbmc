#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import time
from os.path import join as OSPJoin

from kodi_six import xbmcvfs


def getConfig(cfile, defvalue=''):
    cfgfile = OSPJoin(getConfig.configPath, cfile)

    value = ''
    if xbmcvfs.exists(cfgfile):
        f = xbmcvfs.File(cfgfile, 'r')
        value = f.read()
        f.close()

    return value if value else defvalue

def writeConfig(cfile, value):
    cfgfile = OSPJoin(writeConfig.configPath, cfile)
    cfglockfile = OSPJoin(writeConfig.configPath, cfile + '.lock')

    if not xbmcvfs.exists(writeConfig.configPath):
        xbmcvfs.mkdirs(writeConfig.configPath)

    while True:
        if not xbmcvfs.exists(cfglockfile):
            l = xbmcvfs.File(cfglockfile, 'w')
            l.write(str(time.time()))
            l.close()
            if value == '':
                xbmcvfs.delete(cfgfile)
            else:
                f = xbmcvfs.File(cfgfile, 'w')
                f.write(value.__str__())
                f.close()
            xbmcvfs.delete(cfglockfile)
            return True
        else:
            l = xbmcvfs.File(cfglockfile)
            modified = float('0'+l.read())
            l.close()
            if time.time() - modified > 0.1:
                xbmcvfs.delete(cfglockfile)

def langSettings(config_id):
    from .common import Globals
    _g = Globals()
    supported_langs = ['all', 'ar', 'bg', 'ca', 'cmn', 'cs', 'da', 'de', 'en', 'es', 'et', 'fi', 'fr', 'he', 'hi', 'hr', 'hu', 'is', 'it', 'ja',
                       'ko', 'lt', 'lv', 'nb', 'nl', 'pl', 'pt', 'ro', 'ru', 'sk', 'sl', 'sr', 'sv', 'ta', 'te', 'th', 'tr', 'uk', 'vi', 'yue']
    langs = getConfig(config_id, supported_langs[0])
    presel = [supported_langs.index(x) for x in langs.split(',') if x in supported_langs]
    sel = _g.dialog.multiselect('Languages', supported_langs, preselect=presel)

    if not sel is None:
        if len(sel) == 0:
            sel = supported_langs[0]
        elif 0 in sel and len(sel) > 1:
            sel.remove(0)
        langs = ','.join([supported_langs[x] for x in sel])
        writeConfig(config_id, langs)
        _g.addon.setSetting(config_id, langs)
