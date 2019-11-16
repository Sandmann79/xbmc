#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from kodi_six import xbmcvfs
import time
from os.path import join as OSPJoin


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
            modified = float(l.read())
            l.close()
            if time.time() - modified > 0.1:
                xbmcvfs.delete(cfglockfile)
