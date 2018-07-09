#!/usr/bin/env python
# -*- coding: utf-8 -*-
import pyxbmct
import xbmcgui
from resources.lib.configs import *
from resources.lib.l10n import *


class AgeRestrictions:
    class _AgeSettings(pyxbmct.AddonDialogWindow):
        def __init__(self, title=''):
            super(AgeSettings, self).__init__(title)
            self.age_list = [age[0] for age in Ages]
            self.pin_req = int(getConfig('pin_req', '0'))
            self.pin = pyxbmct.Edit('', _alignment=pyxbmct.ALIGN_CENTER)
            self.btn_ages = pyxbmct.Button(self.age_list[self.pin_req])
            self.btn_save = pyxbmct.Button(getString(30122))
            self.btn_close = pyxbmct.Button(getString(30123))
            self.setGeometry(500, 300, 5, 2)
            self.set_controls()
            self.set_navigation()

        def set_controls(self):
            self.placeControl(pyxbmct.Label(getString(30120), alignment=pyxbmct.ALIGN_CENTER_Y), 1, 0)
            self.placeControl(self.pin, 1, 1)
            self.placeControl(pyxbmct.Label(getString(30121), alignment=pyxbmct.ALIGN_CENTER_Y), 2, 0)
            self.placeControl(self.btn_ages, 2, 1)
            self.placeControl(self.btn_save, 4, 0)
            self.placeControl(self.btn_close, 4, 1)
            self.connect(self.btn_close, self.close)
            self.connect(self.btn_ages, self.select_age)
            self.connect(self.btn_save, self.save_settings)
            self.connect(pyxbmct.ACTION_NAV_BACK, self.close)
            self.pin.setText(AgePin)

        def set_navigation(self):
            self.pin.controlUp(self.btn_save)
            self.pin.controlDown(self.btn_ages)
            self.btn_save.setNavigation(self.btn_ages, self.pin, self.btn_close, self.btn_close)
            self.btn_close.setNavigation(self.btn_ages, self.pin, self.btn_save, self.btn_save)
            self.btn_ages.setNavigation(self.pin, self.btn_save, self.btn_save, self.btn_close)
            self.setFocus(self.pin)

        def save_settings(self):
            writeConfig('age_pin', self.pin.getText().strip())
            writeConfig('pin_req', self.pin_req)
            self.close()

        def select_age(self):
            sel = g.dialog.select(getString(30121), self.age_list)
            if sel > -1:
                self.pin_req = sel
                self.btn_ages.setLabel(self.age_list[self.pin_req])

    def __init__(self):
        from resources.lib.common import Globals
        self._g = Globals()
        AgesCfg = {
            'A1PA6795UKMFR9': ['FSK', ('FSK 0', 'FSK 0'), ('FSK 6', 'FSK 6'), ('FSK 12', 'FSK 12'), ('FSK 16', 'FSK 16'), ('FSK 18', 'FSK 18')],
            'A1F83G8C2ARO7P': ['', ('Universal', 'U'), ('Parental Guidance', 'PG'), ('12 and older', '12,12A'), ('15 and older', '15'), ('18 and older', '18')],
            'ATVPDKIKX0DER': ['', ('General Audiences', 'G,TV-G,TV-Y'), ('Family', 'PG,NR,TV-Y7,TV-Y7-FV,TV-PG'), ('Teen', 'PG-13,TV-14'),
                              ('Mature', 'R,NC-17,TV-MA,Unrated,Not rated')],
            'A1VC38T7YXB528': ['', ('全ての観客', 'g'), ('親の指導・助言', 'pg12'), ('R-15指定', 'r15+'), ('成人映画', 'r18+,nr')]
        }
        PinReq = int(getConfig('pin_req', '0'))
        Ages = ['', ''] if self._g.MarketID not in AgesCfg.keys() else AgesCfg[g.MarketID]
        self._AgeRating = Ages[0]
        Ages = Ages[1:]
        self._RestrAges = ','.join(a[1] for a in Ages[PinReq:]) if getConfig('age_pin') else ''

    def RequestPin(self):
        AgePin = getConfig('age_pin')
        if AgePin:
            pin = self._g.dialog.input('PIN', type=xbmcgui.INPUT_ALPHANUM, option=xbmcgui.ALPHANUM_HIDE_INPUT)
            return True if pin == AgePin else False
        return True

    def GetRestrictedAges(self):
        return self._RestrAges

    def GetAgeRating(self):
        return self._AgeRating

    def Settings(self):
        if RequestPin():
            _AgeSettings(getString(30018).split('…')[0]).doModal()