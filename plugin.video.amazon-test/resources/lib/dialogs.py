#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json

import pyxbmct

from .l10n import getString
from .configs import getConfig, writeConfig
from .common import Globals


class PV_ClearCache(pyxbmct.AddonDialogWindow):
    """ Cache deletion confirmation dialog """
    value = 0  # Contains the selected options bitmask

    def __init__(self, title=getString(30087), label=getString(30088)):
        """Class constructor"""
        # Call the base class' constructor.
        self._label = label
        super(PV_ClearCache, self).__init__(title)
        self.setGeometry(460, 280, 3, 2)
        self.set_controls()
        self.set_navigation()
        self.connect(pyxbmct.ACTION_NAV_BACK, self.close)
        self.doModal()

    def set_controls(self):
        """Set up UI controls"""
        # Text label
        label = pyxbmct.Label(self._label)
        self.placeControl(label, 0, 0, rowspan=1, columnspan=2)
        # None
        self.btnNone = pyxbmct.Button(getString(30089))
        self.placeControl(self.btnNone, 1, 0)
        self.connect(self.btnNone, self.close)
        # Catalog
        self.btnCatalog = pyxbmct.Button(getString(30090))
        self.placeControl(self.btnCatalog, 1, 1)
        self.connect(self.btnCatalog, lambda: self.clear(1))
        # Video
        self.btnVideo = pyxbmct.Button(getString(30091))
        self.placeControl(self.btnVideo, 2, 0)
        self.connect(self.btnVideo, lambda: self.clear(2))
        # Both
        self.btnBoth = pyxbmct.Button(getString(30092))
        self.placeControl(self.btnBoth, 2, 1)
        self.connect(self.btnBoth, lambda: self.clear(3))

    def set_navigation(self):
        """Set up keyboard/remote navigation between controls."""
        # None Catalog
        # Video   Both
        self.btnNone.controlRight(self.btnCatalog)
        self.btnNone.controlDown(self.btnVideo)
        self.btnCatalog.controlLeft(self.btnNone)
        self.btnCatalog.controlDown(self.btnBoth)
        self.btnVideo.controlUp(self.btnNone)
        self.btnVideo.controlRight(self.btnBoth)
        self.btnBoth.controlLeft(self.btnVideo)
        self.btnBoth.controlUp(self.btnCatalog)
        self.setFocus(self.btnNone)

    def clear(self, what):
        self.value = what
        self.close()


class SearchDialog(pyxbmct.AddonDialogWindow):

    def __init__(self, title=getString(30247)):
        super(SearchDialog, self).__init__(title)
        self._g = Globals()
        self.value = ''
        self.history = json.loads(getConfig('search_history', '[]'))
        self.setGeometry(500, 490, 9, 2)
        self.edit = pyxbmct.Edit('', _alignment=pyxbmct.ALIGN_CENTER_Y)
        self.label_hint = pyxbmct.Label(getString(24121).strip(' \t\n\r'), alignment=pyxbmct.ALIGN_CENTER_Y)
        self.label_hist = pyxbmct.Label(getString(30282), alignment=pyxbmct.ALIGN_CENTER_Y)
        self.list = pyxbmct.List(_itemTextXOffset=0, _itemHeight=35)
        self.btn_search = pyxbmct.Button(getString(30108))
        self.btn_cancel = pyxbmct.Button(getString(30123))
        self.set_controls()
        self.set_navigation()
        self.doModal()
        del self

    def set_controls(self):
        self.placeControl(self.label_hint, 0,0, columnspan=2)
        self.placeControl(self.edit, 1,0, columnspan=2)
        self.placeControl(self.label_hist, 2,0)
        self.placeControl(self.list, 3,0, rowspan=6, columnspan=2)
        self.placeControl(self.btn_search, 8 ,0)
        self.placeControl(self.btn_cancel, 8,1)
        self.connect(self.btn_search, self.search)
        self.connect(self.btn_cancel, self.close)
        self.connect(self.list, self.list_clicked)
        self.connect(pyxbmct.ACTION_NAV_BACK, self.close)
        self.connect(117, self.context_menu)  # context menu
        self.connect(101, self.context_menu)  # mouse right click
        self.list.addItems(self.history)

    def set_navigation(self):
        self.edit.setNavigation(self.btn_search, self.list, self.btn_search, self.btn_search)
        self.list.setNavigation(self.edit, self.btn_search, self.btn_search, self.btn_search)
        self.btn_search.setNavigation(self.list, self.edit, self.btn_cancel, self.btn_cancel)
        self.btn_cancel.setNavigation(self.list, self.edit, self.btn_search, self.btn_search)
        self.setFocus(self.edit)

    def list_clicked(self):
        pos = self.list.getSelectedPosition()
        self.edit.setText(self.history[pos])
        self.setFocus(self.btn_search)

    def context_menu(self):
        if self.getFocus() == self.list:
            pos = self.list.getSelectedPosition()
            ret = self._g.dialog.contextmenu([getString(30283), getString(30284)])
            if ret == 0:
                self.history.pop(pos)
                self.list.removeItem(pos)
            if ret == 1:
                self.history = []
                self.list.reset()

    def search(self):
        self.value = self.edit.getText().strip()
        if len(self.value) > 0:
            self.add_history()
        self.close()

    def add_history(self):
        self.history = [x for x in self.history if x.lower() != self.value.lower()]
        self.history.insert(0, self.value)
        if len(self.history) > 15:
            self.history = self.history[:15]
        writeConfig('search_history', json.dumps(self.history))
