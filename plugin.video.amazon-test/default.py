#!/usr/bin/env python
# -*- coding: utf-8 -*-
from sys import argv

from resources.lib.service import SettingsMonitor
from resources.lib.startup import EntryPoint

if __name__ == '__main__':
    EntryPoint(argv)
    SettingsMonitor().start()
