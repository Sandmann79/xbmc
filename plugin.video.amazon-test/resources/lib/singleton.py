#!/usr/bin/env python
# -*- coding: utf-8 -*-

# A singleton instancing metaclass compatible with both Python 2 & 3.
# The __init__ of each class is only called once.


class _Singleton(type):
    """ A metaclass that creates a Singleton base class when called. """
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(_Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class Singleton(_Singleton('SingletonMeta', (object,), {})):
    pass
