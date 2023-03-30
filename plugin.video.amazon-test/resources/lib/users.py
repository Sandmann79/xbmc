#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from kodi_six import xbmcgui
from kodi_six.utils import py2_decode
import json
from .configs import *
from .common import Globals, Settings
from .l10n import *

g = Globals()
def_keys = {'name': '', 'atvurl': '', 'baseurl': '', 'pv': False, 'mid': '', 'cookie': '', 'token': '', 'deviceid': '', 'sidomain': ''}


def loadUsers():
    users = json.loads(getConfig('accounts.lst', '[]'))
    if not users:
        g.addon.setSetting('login_acc', '')
    return users


def loadUser(key='', empty=False, cachedUsers=None):
    cur_user = py2_decode(g.addon.getSetting('login_acc'))
    users = cachedUsers if cachedUsers else loadUsers()
    user = None if empty else [i for i in users if cur_user == i['name']]
    if user:
        user = user[0]
        if len([k for k in def_keys.keys() if k not in user]) > 0:
            from .network import getTerritory
            user = getTerritory(user)
            if False is user[1]:
                g.dialog.notification(g.__plugin__, getString(30219), xbmcgui.NOTIFICATION_ERROR)
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
    cur_user = py2_decode(g.addon.getSetting('login_acc'))
    users = cachedUsers if cachedUsers else loadUsers()
    user = [i for i in users if cur_user == i['name']]
    if not user:
        return
    user = user[0]
    from requests.utils import dict_from_cookiejar as dfcj
    user['cookie'] = dfcj(cookieJar)
    saveUsers(users)


def addUser(user):
    s = Settings()
    users = loadUsers() if s.multiuser else []
    num = [n for n, i in enumerate(users) if user['name'] == i['name']]
    if num:
        users[num[0]] = user
    else:
        users.append(user)
    saveUsers(users)
    if xbmc.getInfoLabel('Container.FolderPath') == g.pluginid:
        xbmc.executebuiltin('Container.Refresh')


def switchUser(sel=-1):
    users = loadUsers()
    cur_user = loadUser('name', cachedUsers=users)
    sel = g.dialog.select(getString(30133), [i['name'] for i in users]) if sel < 0 else sel
    if sel > -1:
        if cur_user == users[sel]['name']:
            return False
        user = users[sel]
        g.addon.setSetting('login_acc', user['name'])
        if xbmc.getInfoLabel('Container.FolderPath') == g.pluginid:
            xbmc.executebuiltin('RunPlugin(%s)' % g.pluginid)
            xbmc.executebuiltin('Container.Refresh')
    return -1 < sel


def removeUser():
    users = loadUsers()
    cur_user = loadUser('name', cachedUsers=users)
    sel = g.dialog.select(getString(30133), [i['name'] for i in users])
    if sel > -1:
        user = users[sel]
        users.remove(user)
        saveUsers(users)
        if user['name'] == cur_user:
            g.addon.setSetting('login_acc', '')
            if not switchUser():
                xbmc.executebuiltin('Container.Refresh')


def renameUser():
    users = loadUsers()
    cur_user = loadUser('name', cachedUsers=users)
    sel = g.dialog.select(getString(30133), [i['name'] for i in users])
    if sel > -1:
        keyboard = xbmc.Keyboard(users[sel]['name'], getString(30135))
        keyboard.doModal()
        if keyboard.isConfirmed() and keyboard.getText():
            usr = keyboard.getText()
            if users[sel]['name'] == cur_user:
                g.addon.setSetting('login_acc', usr)
                xbmc.executebuiltin('Container.Refresh')
            users[sel]['name'] = usr
            saveUsers(users)
