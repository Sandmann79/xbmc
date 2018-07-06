#!/usr/bin/env python
# -*- coding: utf-8 -*-
import xbmcvfs
from os.path import join as OSPJoin

def getConfig(cfile, defvalue='', configPath = None):
    if (not hasattr(getConfig, 'configPath')) and (None is not configPath):
        getConfig.configPath = configPath
    cfgfile = OSPJoin(getConfig.configPath, cfile)

    value = ''
    if xbmcvfs.exists(cfgfile):
        f = xbmcvfs.File(cfgfile, 'r')
        value = f.read()
        f.close()

    return value if value else defvalue


def writeConfig(cfile, value, configPath = None):
    if (not hasattr(getConfig, 'configPath')) and (None is not configPath):
        writeConfig.configPath = configPath
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
