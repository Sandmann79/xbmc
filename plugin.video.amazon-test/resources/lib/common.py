#!/usr/bin/env python
# -*- coding: utf-8 -*-
from Singleton import Singleton
from PrimeVideo import PrimeVideo
import xbmcaddon

# Usage:
#   g = Globals()
#   v = g.attribute
#   v = g.attribute.AttributeMemberFunction()

class Globals(Singleton):
    """ A singleton instance of globals accessible through dot notation """
    _globals = {}

    ''' Allow the usage of dot notation for data inside the _globals dictionary, without explicit function call '''
    def __getattr__(self, name): return self._globals[name]
    #def __setattr__(self, name, value): self._globals[name] = value
    #def __delattr__(self, name): self._globals.pop(name, None)
    
    def __init__(self):
        self._globals['addon'] = xbmcaddon.Addon()
        self._globals['pv'] = PrimeVideo()
