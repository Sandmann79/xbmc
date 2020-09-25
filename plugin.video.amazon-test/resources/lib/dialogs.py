#!/usr/bin/env python
# -*- coding: utf-8 -*-import pyxbmct
import pyxbmct
from .l10n import getString


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
