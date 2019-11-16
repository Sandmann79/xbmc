#!/usr/bin/env python
# -*- coding: utf-8 -*-
from kodi_six import xbmc


def getString(string_id, addonInstance=None):
    if string_id < 30000:
        src = xbmc
    elif addonInstance is None:
        from .common import Globals
        src = Globals().addon
    else:
        src = addonInstance
    locString = src.getLocalizedString(string_id)
    return locString
