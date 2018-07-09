#!/usr/bin/env python
# -*- coding: utf-8 -*-
import requests
import re
import json
from resources.lib.network import MechanizeLogin
from resources.lib.configs import *
from resources.lib.common import Globals


def loadUsers():
    if not hasattr(loadUsers, 'g'):
        loadUsers.g = Globals()
    users = json.loads(getConfig('accounts.lst', '[]'))
    if not users:
        loadUsers.g.addon.setSetting('login_acc', '')
    return users


def loadUser(key='', empty=False, cachedUsers=None):
    if not hasattr(loadUser, 'g'):
        loadUser.g = Globals()
    def_keys = {'email': '', 'password': '', 'name': '', 'save': '', 'atvurl': '', 'baseurl': '', 'pv': False, 'mid': '', 'cookie': ''}
    cur_user = loadUser.g.addon.getSetting('login_acc').decode('utf-8')
    users = cachedUsers if cachedUsers else loadUsers()
    user = None if empty else [i for i in users if cur_user == i['name']]
    if user:
        user = user[0]
        if key and key not in user.keys():
            user = getTerritory(user)
            if False is user[1]:
                loadUser.g.dialog.notification(loadUser.g.__plugin__, getString(30219), xbmcgui.NOTIFICATION_ERROR)
            user = user[0]
            addUser(user)
        return user.get(key, user)
    else:
        return def_keys.get(key, def_keys)


def addUser(user):
    if not hasattr(addUser, 'g'):
        addUser.g = Globals()
    addUser.user['save'] = g.addon.getSetting('save_login')
    users = loadUsers() if multiuser else []
    num = [n for n, i in enumerate(users) if user['name'] == i['name']]
    if num:
        users[num[0]] = user
    else:
        users.append(user)
    writeConfig('accounts.lst', json.dumps(users))
    if xbmc.getInfoLabel('Container.FolderPath') == sys.argv[0]:
        xbmc.executebuiltin('Container.Refresh')


def switchUser(sel=-1):
    if not hasattr(switchUser, 'g'):
        switchUser.g = Globals()
    users = loadUsers()
    sel = switchUser.g.dialog.select(getString(30133), [i['name'] for i in users]) if sel < 0 else sel
    if sel > -1:
        if loadUser('name') == users[sel]['name']:
            return False
        user = users[sel]
        switchUser.g.addon.setSetting('save_login', user['save'])
        switchUser.g.addon.setSetting('login_acc', user['name'])
        xbmc.executebuiltin('Container.Refresh')
    return -1 < sel


def removeUser():
    if not hasattr(removeUser, 'g'):
        removeUser.g = Globals()
    cur_user = loadUser('name')
    users = loadUsers()
    sel = removeUser.g.dialog.select(getString(30133), [i['name'] for i in users])
    if sel > -1:
        user = users[sel]
        users.remove(user)
        writeConfig('accounts.lst', json.dumps(users))
        if user['name'] == cur_user:
            removeUser.g.addon.setSetting('login_acc', '')
            if not switchUser():
                xbmc.executebuiltin('Container.Refresh')


def renameUser():
    if not hasattr(renameUser, 'g'):
        renameUser.g = Globals()
    cur_user = loadUser('name')
    users = loadUsers()
    sel = renameUser.g.dialog.select(getString(30133), [i['name'] for i in users])
    if sel > -1:
        keyboard = xbmc.Keyboard(users[sel]['name'], getString(30135))
        keyboard.doModal()
        if keyboard.isConfirmed() and keyboard.getText():
            usr = keyboard.getText()
            if users[sel]['name'] == cur_user:
                renameUser.g.addon.setSetting('login_acc', usr)
                xbmc.executebuiltin('Container.Refresh')
            users[sel]['name'] = usr
            writeConfig('accounts.lst', json.dumps(users))
