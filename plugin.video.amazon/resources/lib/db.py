#!/usr/bin/env python
# -*- coding: utf-8 -*-
from common import xbmc, addon, xbmcvfs, xbmcgui, os, Dialog, Log, getString, getConfig, writeConfig, homepath, pluginname
from BeautifulSoup import BeautifulSoup

usesqlite = addon.getSetting('dbsystem') == '0'
dbplugin = 'script.module.amazon.database'
dbpath = os.path.join(homepath, 'addons', dbplugin, 'lib')


def waitforDB(cnx):
    if not usesqlite:
        return

    c = cnx.cursor()
    error = True

    while error:
        error = False
        try:
            c.execute('SELECT name FROM sqlite_master WHERE type="table"').fetchone()
        except:
            error = True
            xbmc.sleep(1000)
            Log('Database locked')
    c.close()


def getDBlocation(retvar):
    custdb = addon.getSetting('customdbfolder') == 'true'
    old_dbpath = xbmc.translatePath(getConfig('old_dbfolder')).decode('utf-8')
    cur_dbpath = dbpath

    if not old_dbpath:
        old_dbpath = cur_dbpath
    if custdb:
        cur_dbpath = xbmc.translatePath(addon.getSetting('dbfolder')).decode('utf-8')
    else:
        addon.setSetting('dbfolder', dbpath)

    orgDBfile = {'tv': os.path.join(dbpath, 'tv.db'), 'movie': os.path.join(dbpath, 'movies.db')}
    oldDBfile = {'tv': os.path.join(old_dbpath, 'tv.db'), 'movie': os.path.join(old_dbpath, 'movies.db')}
    DBfile = {'tv': os.path.join(cur_dbpath, 'tv.db'), 'movie': os.path.join(cur_dbpath, 'movies.db')}

    if old_dbpath != cur_dbpath:
        Log('DBPath changed')
        if xbmcvfs.exists(oldDBfile['tv']) and xbmcvfs.exists(oldDBfile['movie']):
            if not xbmcvfs.exists(cur_dbpath):
                xbmcvfs.mkdir(cur_dbpath)
            if not xbmcvfs.exists(DBfile['tv']) or not xbmcvfs.exists(DBfile['movie']):
                copyDB(oldDBfile, DBfile)
        writeConfig('old_dbfolder', cur_dbpath)

    if custdb:
        org_fileacc = int(xbmcvfs.Stat(orgDBfile['tv']).st_mtime() + xbmcvfs.Stat(orgDBfile['movie']).st_mtime())
        cur_fileacc = int(xbmcvfs.Stat(DBfile['tv']).st_mtime() + xbmcvfs.Stat(DBfile['movie']).st_mtime())
        if org_fileacc > cur_fileacc:
            copyDB(orgDBfile, DBfile, True)

    return DBfile[retvar]


def cur_exec(cur, query, param=None):
    syntax = {True: {'counttables': 'SELECT count(*) FROM sqlite_master WHERE type="table" AND name=(?)',
                     'insert ignore': 'insert or ignore'},
              False:{'counttables': 'show tables like ?',
                     "?": "%s"}}

    for k, v in syntax[usesqlite].items():
        query = query.replace(k, v)

    param = '' if not param and usesqlite else param
    res = cur.execute(query, param)

    return res if usesqlite else cur


def copyDB(source, dest, ask=False):
    import shutil
    if ask:
        if not Dialog.yesno(getString(30193), getString(30194)):
            shutil.copystat(source['tv'], dest['tv'])
            shutil.copystat(source['movie'], dest['movie'])
            return
    shutil.copy2(source['tv'], dest['tv'])
    shutil.copy2(source['movie'], dest['movie'])


def connSQL(dbname):
    cnx = None
    if usesqlite:
        from sqlite3 import dbapi2
        DBfile = getDBlocation(dbname)
        if not xbmcvfs.exists(DBfile):
            cnx = dbapi2.connect(DBfile)
            cnx.text_factory = str
            createDatabase(cnx, dbname)
        else:
            cnx = dbapi2.connect(DBfile)
            cnx.text_factory = str
    else:
        import mysql.connector
        from mysql.connector import errorcode
        dbname = 'amazon_' + dbname
        mysql_config = {
            'host': addon.getSetting('dbhost'),
            'port': addon.getSetting('dbport'),
            'user': addon.getSetting('dbuser'),
            'password': addon.getSetting('dbpass'),
            'database': dbname,
            'use_unicode': False,
            'get_warnings': True,
            'buffered': True
        }
        try:
            cnx = mysql.connector.connect(**mysql_config)
        except mysql.connector.Error as err:
            if err.errno == errorcode.CR_CONN_HOST_ERROR:
                Dialog.notification('MySQL/MariaDB', getString(30224), xbmcgui.NOTIFICATION_ERROR)
            elif err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
                Dialog.notification('MySQL/MariaDB', getString(30225), xbmcgui.NOTIFICATION_ERROR)
            elif err.errno == errorcode.ER_BAD_DB_ERROR:
                mysql_config['database'] = None
                cnx = mysql.connector.connect(**mysql_config)
                c = cnx.cursor()
                cur_exec(c, 'CREATE DATABASE %s CHARACTER SET utf8 COLLATE utf8_general_ci;' % dbname)
                cnx.database = dbname
                createDatabase(cnx, dbname)
            else:
                Log(err)

    if not cnx:
        exit()
    return cnx


def loadSQLconfig():
    keys = 'host port user pass'
    userdata = xbmc.translatePath('special://userdata').decode('utf-8')
    asfile = os.path.join(userdata, 'advancedsettings.xml')
    if xbmcvfs.exists(asfile):
        f = xbmcvfs.File(asfile, 'r')
        soup = BeautifulSoup(f.read(), convertEntities=BeautifulSoup.XML_ENTITIES)
        videodb = soup.advancedsettings.videodatabase
        if videodb:
            for tag in videodb.findAll():
                if tag.name in keys:
                    addon.setSetting('db'+tag.name, tag.string)
        else:
            Dialog.notification(pluginname, getString(30226))
    else:
        Dialog.notification(pluginname, getString(30226))


def createDatabase(cnx, dbname):
    c = cnx.cursor()
    cur_exec(c, 'drop table if exists categories')
    Log('Creating %s database' % dbname.upper())

    if 'movie' in dbname:
        cur_exec(c, 'drop table if exists movies')
        cur_exec(c, '''create table movies(
                     asin VARCHAR(144) UNIQUE,
                     movietitle TEXT,
                     trailer BOOLEAN,
                     poster TEXT,
                     plot TEXT,
                     director TEXT,
                     writer TEXT,
                     runtime INTEGER,
                     year INTEGER,
                     premiered TEXT,
                     studio TEXT,
                     mpaa TEXT,
                     actors TEXT,
                     genres TEXT,
                     stars FLOAT,
                     votes INTEGER,
                     fanart TEXT,
                     isprime BOOLEAN,
                     isHD BOOLEAN,
                     isAdult BOOLEAN,
                     popularity INTEGER,
                     recent INTEGER,
                     audio INTEGER,
                     PRIMARY KEY(asin))''')
    else:
        cur_exec(c, 'drop table if exists shows')
        cur_exec(c, 'drop table if exists seasons')
        cur_exec(c, 'drop table if exists episodes')
        cur_exec(c, '''CREATE TABLE shows(
                     asin VARCHAR(144) UNIQUE,
                     seriestitle TEXT,
                     plot TEXT,
                     network TEXT,
                     mpaa TEXT,
                     genres TEXT,
                     actors TEXT,
                     airdate TEXT,
                     year INTEGER,
                     stars float,
                     votes INTEGER,
                     seasontotal INTEGER,
                     episodetotal INTEGER,
                     audio INTEGER,
                     isHD BOOLEAN,
                     isprime BOOLEAN,
                     popularity INTEGER,
                     recent INTEGER,
                     imdb TEXT,
                     poster TEXT,
                     banner TEXT,
                     fanart TEXT,
                     PRIMARY KEY(asin));''')
        cur_exec(c, '''CREATE TABLE seasons(
                     asin VARCHAR(144) UNIQUE,
                     seriesasin TEXT,
                     season INTEGER,
                     seriestitle TEXT,
                     plot TEXT,
                     actors TEXT,
                     network TEXT,
                     mpaa TEXT,
                     genres TEXT,
                     airdate TEXT,
                     year INTEGER,
                     stars float,
                     votes INTEGER,
                     episodetotal INTEGER,
                     audio INTEGER,
                     popularity INTEGER,
                     recent INTEGER,
                     isHD BOOLEAN,
                     isprime BOOLEAN,
                     imdburl TEXT,
                     poster TEXT,
                     banner TEXT,
                     fanart TEXT,
                     forceupdate BOOLEAN,
                     PRIMARY KEY(asin));''')
        cur_exec(c, '''create table episodes(
                     asin VARCHAR(144) UNIQUE,
                     seasonasin TEXT,
                     seriesasin TEXT,
                     seriestitle TEXT,
                     season INTEGER,
                     episode INTEGER,
                     poster TEXT,
                     mpaa TEXT,
                     actors TEXT,
                     genres TEXT,
                     episodetitle TEXT,
                     studio TEXT,
                     stars float,
                     votes INTEGER,
                     fanart TEXT,
                     plot TEXT,
                     airdate TEXT,
                     year INTEGER,
                     runtime INTEGER,
                     isHD BOOLEAN,
                     isprime BOOLEAN,
                     isAdult BOOLEAN,
                     audio INTEGER,
                     PRIMARY KEY(asin));''')
    cnx.commit()
    c.close()
