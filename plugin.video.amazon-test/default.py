#!/usr/bin/env python
# -*- coding: utf-8 -*-
from resources.lib.startup import EntryPoint
from resources.lib.service import SettingsMonitor

if __name__ == '__main__':
    EntryPoint()
    SettingsMonitor().start()
