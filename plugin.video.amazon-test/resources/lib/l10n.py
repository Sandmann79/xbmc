#!/usr/bin/env python
# -*- coding: utf-8 -*-
import xbmc


def getString(string_id, addonInstance=None):
    from resources.lib.common import Globals
    if string_id < 30000:
        src = xbmc
    elif addonInstance is None:
        if not hasattr(getString, 'g'):
            getString.g = Globals()
        src = getString.g.addon
    else:
        src = addonInstance
    locString = src.getLocalizedString(string_id)
    return locString
