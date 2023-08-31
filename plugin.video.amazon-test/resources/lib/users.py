#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import json

from kodi_six import xbmc, xbmcgui
from kodi_six.utils import py2_decode

from .common import Globals, Settings
from .configs import getConfig, writeConfig
from .l10n import getString

_g = Globals()
_s = Settings()
def_keys = {'name': '', 'atvurl': '', 'baseurl': '', 'pv': False, 'mid': '', 'cookie': '', 'token': '', 'deviceid': '', 'sidomain': '', 'lang': ''}


def loadUsers():
    users = json.loads(getConfig('accounts.lst', '[]'))
    if not users:
        _s.login_acc = ''
    return users


def loadUser(key='', empty=False, cachedUsers=None):
    cur_user = py2_decode(_s.login_acc)
    users = cachedUsers if cachedUsers else loadUsers()
    user = None if empty else [i for i in users if cur_user == i['name']]
    if user:
        user = user[0]
        if len([k for k in def_keys.keys() if k not in user]) > 0:
            from .login import getTerritory
            user = getTerritory(user)
            if False is user[1]:
                _g.dialog.notification(_g.__plugin__, getString(30219), xbmcgui.NOTIFICATION_ERROR)
            user = user[0]
            addUser(user)
        return user.get(key, user)
    else:
        return def_keys.get(key, def_keys)


def saveUsers(users):
    # remove redundant keys
    users = [{k: v for k, v in u.items() if k in def_keys} for u in users]
    writeConfig('accounts.lst', json.dumps(users, indent=2, separators=None, sort_keys=True))


def saveUserCookies(cookieJar, cachedUsers=None):
    if not cookieJar:
        return
    cur_user = py2_decode(_s.login_acc)
    users = cachedUsers if cachedUsers else loadUsers()
    user = [i for i in users if cur_user == i['name']]
    if not user:
        return
    user = user[0]
    user['cookie'] = cookieJar.get_dict()
    saveUsers(users)


def addUser(user):
    users = loadUsers() if _s.multiuser else []
    num = [n for n, i in enumerate(users) if user['name'] == i['name']]
    if num:
        users[num[0]] = user
    else:
        users.append(user)
    saveUsers(users)
    if xbmc.getInfoLabel('Container.FolderPath') == _g.pluginid:
        xbmc.executebuiltin('Container.Refresh')


def switchUser(sel=-1):
    users = loadUsers()
    cur_user = loadUser('name', cachedUsers=users)
    sel = _g.dialog.select(getString(30133), [i['name'] for i in users]) if sel < 0 else sel
    if sel > -1:
        if cur_user == users[sel]['name']:
            return False
        user = users[sel]
        _s.login_acc = user['name']
        if xbmc.getInfoLabel('Container.FolderPath') == _g.pluginid and _s.data_source != 0:
            # xbmc.executebuiltin('RunPlugin(%s)' % _g.pluginid)
            xbmc.executebuiltin('Container.Refresh')
    return -1 < sel


def removeUser():
    users = loadUsers()
    cur_user = loadUser('name', cachedUsers=users)
    sel = _g.dialog.select(getString(30133), [i['name'] for i in users])
    if sel > -1:
        user = users[sel]
        users.remove(user)
        saveUsers(users)
        if user['name'] == cur_user:
            _s.login_acc = ''
            if not switchUser():
                xbmc.executebuiltin('Container.Refresh')


def renameUser():
    users = loadUsers()
    cur_user = loadUser('name', cachedUsers=users)
    sel = _g.dialog.select(getString(30133), [i['name'] for i in users])
    if sel > -1:
        keyboard = xbmc.Keyboard(users[sel]['name'], getString(30135))
        keyboard.doModal()
        if keyboard.isConfirmed() and keyboard.getText():
            usr = keyboard.getText()
            if users[sel]['name'] == cur_user:
                _s.login_acc = usr
                xbmc.executebuiltin('Container.Refresh')
            users[sel]['name'] = usr
            saveUsers(users)


def updateUser(key, value):
    if key in def_keys:
        user = loadUser()
        user.update({key: value})
        addUser(user)
