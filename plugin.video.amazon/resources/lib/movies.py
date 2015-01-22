#!/usr/bin/env python
# -*- coding: utf-8 -*-
from BeautifulSoup import BeautifulStoneSoup
from BeautifulSoup import BeautifulSoup
import os.path
import re
import xbmcplugin
import xbmc
import xbmcgui
import shutil
import appfeed
import resources.lib.common as common

try:
    from sqlite3 import dbapi2 as sqlite
except:
    from pysqlite2 import dbapi2 as sqlite
import xbmcaddon
xmlstring = xbmcaddon.Addon().getLocalizedString

################################ Movie db
MAX = int(common.addon.getSetting("mov_perpage"))
MOV_TOTAL = common.addon.getSetting("MoviesTotal")
if MOV_TOTAL == '': MOV_TOTAL = '2400'
MOV_TOTAL = int(MOV_TOTAL)

def createMoviedb():
    c = MovieDB.cursor()
    c.execute('''create table movies
                (asin UNIQUE,
                 HDasin UNIQUE,
                 movietitle TEXT,
                 trailer BOOLEAN,
                 poster TEXT,
                 plot TEXT,
                 director TEXT,
                 writer TEXT,
                 runtime TEXT,
                 year INTEGER,
                 premiered TEXT,
                 studio TEXT,
                 mpaa TEXT,
                 actors TEXT,
                 genres TEXT,
                 stars FLOAT,
                 votes TEXT,
                 externalBanner TEXT,
                 externalPoster TEXT,
                 externalFanart TEXT,
                 isprime BOOLEAN,
                 isHD BOOLEAN,
                 isAdult BOOLEAN,
                 watched BOOLEAN,
                 audio INTEGER,
                 IMDB_ID TEXT,
                 PRIMARY KEY(movietitle,year,asin))''')
    MovieDB.commit()
    c.close()

def addMoviedb(moviedata):
    c = MovieDB.cursor()
    c.execute('insert or ignore into movies values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', moviedata)
    MovieDB.commit()
    c.close()

def lookupMoviedb(asin):
    c = MovieDB.cursor()
    if c.execute('select distinct * from movies where asin = (?)', (asin,)).fetchone():
        result = c.execute('select distinct * from movies where asin = (?)', (asin,))
        for moviedata in result:
            return moviedata
    else:
        return False

def deleteMoviedb(asin=False):
    if not asin:
        asin = common.args.url
    c = MovieDB.cursor()
    shownamedata = c.execute('delete from movies where asin = (?)', (asin,))
    
    c.close()

def loadMoviedb(genrefilter=False,actorfilter=False,directorfilter=False,studiofilter=False,yearfilter=False,mpaafilter=False,alphafilter=False,isprime=True):
    c = MovieDB.cursor()
    if genrefilter:
        genrefilter = '%'+genrefilter+'%'
        return c.execute('select distinct * from movies where isprime = (?) and genres like (?)', (isprime,genrefilter))
    elif mpaafilter:
        return c.execute('select distinct * from movies where isprime = (?) and mpaa = (?)', (isprime,mpaafilter))
    elif actorfilter:
        actorfilter = '%'+actorfilter+'%'
        return c.execute('select distinct * from movies where isprime = (?) and actors like (?)', (isprime,actorfilter))
    elif directorfilter:
        return c.execute('select distinct * from movies where isprime = (?) and director like (?)', (isprime,directorfilter))
    elif studiofilter:
        return c.execute('select distinct * from movies where isprime = (?) and studio = (?)', (isprime,studiofilter))
    elif yearfilter:    
        return c.execute('select distinct * from movies where isprime = (?) and year = (?)', (isprime,int(yearfilter)))
    elif alphafilter:
        return c.execute('select distinct * from movies where isprime = (?) and movietitle like (?)', (isprime,alphafilter))       
    else:
        return c.execute('select distinct * from movies where isprime = (?)', (isprime,))

def getMovieTypes(col):
    c = MovieDB.cursor()
    items = c.execute('select distinct %s from movies' % col)
    list = []
    lowlist = []
    for data in items:
        data = data[0]
        if type(data) == type(str()):
            if 'Rated' in data:
                item = data.split('for')[0]
                if item not in list and item <> '' and item <> 0 and item <> 'Inc.' and item <> 'LLC.':
                    list.append(item)
            else:
                if 'genres' in col: data = data.decode('utf-8').encode('utf-8').split('/')
                else: data = data.decode('utf-8').encode('utf-8').split(',')
                for item in data:
                    item = item.strip()
                    if item.lower() not in lowlist and item <> '' and item <> 0 and item <> 'Inc.' and item <> 'LLC.':
                        list.append(item)
                        lowlist.append(item.lower())
        elif data <> 0:
            if data is not None:
                list.append(str(data))
    c.close()
    return list

def getMoviedbAsins(table,col):
    c = MovieDB.cursor()
    content = ''
    for item in c.execute('select asin from %s where %s = (1)' % (table, col)).fetchall():
        content += ','.join(item)
    return content
    
def addMoviesdb(isPrime=True):
    dialog = xbmcgui.DialogProgress()
    dialog.create(xmlstring(30120))
    dialog.update(0,xmlstring(30121))
    c = MovieDB.cursor()
    c.execute('drop table if exists movies')
    c.close()
    createMoviedb()
    page = 1
    goAhead = 1
    endIndex=0
    while goAhead == 1:
        page+=1
        json = appfeed.getList('Movie', endIndex, NumberOfResults=MAX)
        titles = json['message']['body']['titles']
        if titles:
            endIndex += ASIN_ADD(titles)
        else:
            goAhead = 0
        if (dialog.iscanceled()): goAhead = -1
        dialog.update(int((endIndex)*100.0/MOV_TOTAL), xmlstring(30122).replace("%s",str(page)), xmlstring(30123).replace("%s", str(endIndex) ))
    if goAhead == 0: common.addon.setSetting("MoviesTotal",str(endIndex))
    dialog.close()

def ASIN_ADD(titles,isPrime=True):
    titelnum = 0
    for title in titles:
        isWatched=False
        isFav=False
        isHD = False
        isAdult = False
        stars = None
        votes = None
        trailer = False
        audio = 1
        #isPrime = False
        asin = title['titleId']
        movietitle = title['title']
        if title['formats'][0].has_key('images'):
            try:
                thumbnailUrl = title['formats'][0]['images'][0]['uri']
                thumbnailFilename = thumbnailUrl.split('/')[-1]
                thumbnailBase = thumbnailUrl.replace(thumbnailFilename,'')
                poster = thumbnailBase+thumbnailFilename.split('.')[0]+'.jpg'
            except: poster = None
        if title.has_key('synopsis'):
            plot = title['synopsis']
        else:
            plot = None
        if title.has_key('director'):
            director = title['director']
        else:
            director = None
        if title.has_key('runtime'):
            runtime = str(title['runtime']['valueMillis']/60000)
        else:
            runtime = None
        if title.has_key('releaseOrFirstAiringDate'):
            premiered = title['releaseOrFirstAiringDate']['valueFormatted'].split('T')[0]
            year = int(premiered.split('-')[0])
        else:
            premiered = None
            year = None
        if title.has_key('studioOrNetwork'):
            studio = title['studioOrNetwork']
        else:
            studio = None
        if title.has_key('regulatoryRating'):
            if title['regulatoryRating'] == 'not_checked': mpaa = xmlstring(30171)
            else: mpaa = xmlstring(30170) + title['regulatoryRating']
        else:
            mpaa = ''
        if title.has_key('starringCast'):
            actors = title['starringCast']
        else:
            actors = None
        if title.has_key('genres'):
            genres = ' / '.join(title['genres']).replace('_', ' & ').replace('Musikfilm & Tanz', 'Musikfilm, Tanz')
        else:
            genres = ''
        if title.has_key('trailerAvailable'): trailer = title['trailerAvailable']
        if title.has_key('customerReviewCollection'):
            stars = float(title['customerReviewCollection']['customerReviewSummary']['averageOverallRating'])*2
            votes = str(title['customerReviewCollection']['customerReviewSummary']['totalReviewCount'])
        elif title.has_key('amazonRating'):
            if title['amazonRating'].has_key('rating'): stars = float(title['amazonRating']['rating'])*2
            if title['amazonRating'].has_key('count'): votes = str(title['amazonRating']['count'])
        for format in title['formats']:
            if format['videoFormatType'] == 'HD':
                for offer in format['offers']:
                    if offer['offerType'] == 'SUBSCRIPTION':
                        isHD = True
                        isPrime = True
            for offer in format['offers']:
                if offer['offerType'] == 'SUBSCRIPTION': isPrime = True
            if 'STEREO' in format['audioFormatTypes']: audio = 2
            if 'AC_3_5_1' in format['audioFormatTypes']: audio = 6
        if title.has_key('restrictions'):
            for rest in title['restrictions']:
                if rest['action'] == 'playback':
                    if rest['type'] == 'ageVerificationRequired': isAdult = True
        titelnum+=1
        if 'bbl test' not in movietitle.lower():
            moviedata = [common.cleanData(x) for x in [asin,None,movietitle,trailer,poster,plot,director,None,runtime,year,premiered,studio,mpaa,actors,genres,stars,votes,None,None,None,isPrime,isHD,isAdult,isWatched,audio,None]]
            addMoviedb(moviedata)
    return titelnum

MovieDBfile = os.path.join(common.dbpath, 'movies.db')
if not os.path.exists(MovieDBfile):
    MovieDB = sqlite.connect(MovieDBfile)
    MovieDB.text_factory = str
    createMoviedb()
else:
    MovieDB = sqlite.connect(MovieDBfile)
    MovieDB.text_factory = str