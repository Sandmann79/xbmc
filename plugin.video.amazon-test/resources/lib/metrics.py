#!/usr/bin/env python
# -*- coding: utf-8 -*-
from functools import wraps
from timeit import default_timer as timer

from .logging import Log

networkTime = 0


def addNetTime(t):
    global networkTime
    networkTime += t


def measure(func):
    """ Timing wrapper for speed performance benchmark, while removing the time spent retrieving network data """
    @wraps(func)
    def _time_it(*args, **kwargs):
        global networkTime
        start = timer()
        try:
            networkTime = 0
            return func(*args, **kwargs)
        finally:
            end_ = timer() - start - networkTime
            Log("Execution time: {} ms{}".format(
                round(end_ * 1000, 2),
                '' if 0 == networkTime else ", network: {} ms".format(round(networkTime * 1000, 2))
            ), Log.DEBUG)
    return _time_it
