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
import sys

try:
    from sqlite3 import dbapi2 as sqlite
except:
    from pysqlite2 import dbapi2 as sqlite
import xbmcaddon

################################ Movie db
MAX = int(common.addon.getSetting("mov_perpage"))
MOV_TOTAL = common.addon.getSetting("MoviesTotal")
if MOV_TOTAL == '' or MOV_TOTAL == '0': MOV_TOTAL = '2400'
MOV_TOTAL = int(MOV_TOTAL)
tmdb_art = common.addon.getSetting("tmdb_art")

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
                 fanart TEXT,
                 isprime BOOLEAN,
                 isHD BOOLEAN,
                 isAdult BOOLEAN,
                 popularity INTEGER,
                 recent INTEGER,
                 audio INTEGER,
                 PRIMARY KEY(movietitle,year,asin))''')
    MovieDB.commit()
    c.close()

def addMoviedb(moviedata):
    c = MovieDB.cursor()
    c.execute('insert or ignore into movies values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', moviedata)
    MovieDB.commit()
    c.close()

def lookupMoviedb(value, rvalue='distinct *', name='asin', single=True, exact=False):
    c = MovieDB.cursor()
    sqlstring = 'select %s from movies where %s ' % (rvalue, name)
    retlen = len(rvalue.split(','))
    if not exact:
        value = '%' + value + '%'
        sqlstring += 'like (?)'
    else:
        sqlstring += '= (?)'
    if c.execute(sqlstring, (value,)).fetchall():
        result = c.execute(sqlstring, (value,)).fetchall()
        if single:
            if len(result[0]) > 1:
                return result[0]
            return result[0][0]
        else:
            return result
    if (retlen < 2) and (single):
        return None
    return (None,) * retlen

def deleteMoviedb(asin=False):
    if not asin:
        asin = common.args.url
    asin = '%' + asin + '%'
    c = MovieDB.cursor()
    return c.execute('delete from movies where asin like (?)', (asin,)).rowcount

def updateMoviedb(asin, col, value):
    c = MovieDB.cursor()
    asin = '%' + asin + '%'
    sqlquery = 'update movies set %s=? where asin like (?)' % col
    result = c.execute(sqlquery, (value,asin)).rowcount
    MovieDB.commit()
    c.close()    
    return result
    
def loadMoviedb(genrefilter=False,actorfilter=False,directorfilter=False,studiofilter=False,yearfilter=False,mpaafilter=False,alphafilter=False,asinfilter=False,sortcol=False,isprime=True):
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
    elif sortcol:
        return c.execute('select distinct * from movies where %s is not null order by %s asc' % (sortcol,sortcol))
    elif asinfilter:
        asinfilter = '%' + asinfilter + '%'
        return c.execute('select distinct * from movies where isprime = (?) and asin like (?)', (isprime,asinfilter))        
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

def getMoviedbAsins(col=False,list=False):
    c = MovieDB.cursor()
    content = ''
    sqlstring = 'select asin from movies'
    if list:
        content = []
    if col:
         sqlstring += ' where %s = (1)' % col
    for item in c.execute(sqlstring).fetchall():
        if list:
            content.append(','.join(item))
        else:
            content += ','.join(item)
    return content
    
def addMoviesdb(full_update = True):
    try:
        if common.args.url == 'u':
            full_update = False
    except: pass
    dialog = xbmcgui.DialogProgress()
    c = MovieDB.cursor()
    if full_update:
        dialog.create(common.getString(30120))
        dialog.update(0,common.getString(30121))
        c.execute('drop table if exists movies')
        c.close()
        createMoviedb()
        MOVIE_ASINS = []
        full_update = True
    else:
        MOVIE_ASINS = getMoviedbAsins(list=True)
    page = 1
    goAhead = 1
    endIndex = 0
    new_mov = 0
    
    while goAhead == 1:
        page+=1
        json = appfeed.getList('Movie', endIndex, NumberOfResults=MAX)
        titles = json['message']['body']['titles']
        if titles:
            for title in titles:
                if full_update and dialog.iscanceled():
                    goAhead = -1
                    break
                if title.has_key('titleId'):
                    endIndex += 1
                    asin = title['titleId']
                    listpos = [i for i, j in enumerate(MOVIE_ASINS) if asin in j]
                    if listpos == []:
                        new_mov += ASIN_ADD(title)
                    else:
                        while listpos != []:
                            del MOVIE_ASINS[listpos[0]]
                            listpos = [i for i, j in enumerate(MOVIE_ASINS) if asin in j]
                    updateMoviedb(asin, 'popularity', endIndex)
        else:
            goAhead = 0
        if full_update: dialog.update(int((endIndex)*100.0/MOV_TOTAL), common.getString(30122) % page, common.getString(30123) % new_mov)
        if full_update and dialog.iscanceled(): goAhead = -1
    if full_update: 
        setNewest()
        dialog.close()
    print MOVIE_ASINS
    if goAhead == 0: 
        common.addon.setSetting("MoviesTotal",str(endIndex))
        print 'Amazon Movie Update: New %s Deleted %s Total %s' % (new_mov, deleteremoved(MOVIE_ASINS), endIndex)
        if tmdb_art == 'true':
            updateFanart()
        xbmc.executebuiltin("XBMC.Container.Refresh")

def setNewest(asins=False):
    if not asins:
        asins = common.getNewest()
    c = MovieDB.cursor()
    c.execute('update movies set recent=null')
    count = 1
    for asin in asins['movies']:
        updateMoviedb(asin, 'recent', count)
        count += 1
    
def updateFanart():
    asin = movie = year = None
    c = MovieDB.cursor()
    print "Amazon Movie Update: Updating Fanart"
    for asin, movie, year in c.execute("select asin, movietitle, year from movies where fanart is null"):
        movie = movie.replace('[OV]', '').replace('Omu', '').split('[')[0].split('(')[0].strip()
        result = appfeed.getTMDBImages(movie, year=year)
        if result == False:
            print "Amazon Movie Fanart: Pause 10 sec..."
            xbmc.sleep(10000)
            result = appfeed.getTMDBImages(movie, year=year)
        updateMoviedb(asin, 'fanart', result)
    print "Amazon Movie Update: Updating Fanart Finished"

       
def deleteremoved(asins):
    c = MovieDB.cursor()
    delMovies = 0
    for item in asins:
        for asin in item.split(','):
            delMovies += deleteMoviedb(asin)
    MovieDB.commit()
    c.close()
    return delMovies

def ASIN_ADD(title,isPrime=True):
    titelnum = 0
    isAdult = False
    stars = None
    votes = None
    trailer = False
    fanart = None
    poster = None
    asin, isHD, isPrime, audio = common.GET_ASINS(title)
    movietitle = title['title']
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
        if title['regulatoryRating'] == 'not_checked': mpaa = common.getString(30171)
        else: mpaa = common.getString(30170) + title['regulatoryRating']
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
    if title.has_key('restrictions'):
        for rest in title['restrictions']:
            if rest['action'] == 'playback':
                if rest['type'] == 'ageVerificationRequired': isAdult = True
    if title['formats'][0].has_key('images'):
        try:
            thumbnailUrl = title['formats'][0]['images'][0]['uri']
            thumbnailFilename = thumbnailUrl.split('/')[-1]
            thumbnailBase = thumbnailUrl.replace(thumbnailFilename,'')
            poster = thumbnailBase+thumbnailFilename.split('.')[0]+'.jpg'
        except: poster = None
    if title.has_key('heroUrl'):
        fanart = title['heroUrl']
    if 'bbl test' not in movietitle.lower():
        moviedata = [common.cleanData(x) for x in [asin,None,common.checkCase(movietitle),trailer,poster,plot,director,None,runtime,year,premiered,studio,mpaa,actors,genres,stars,votes,fanart,isPrime,isHD,isAdult,None,None,audio]]
        addMoviedb(moviedata)
        titelnum+=1
    return titelnum

MovieDBfile = os.path.join(common.dbpath, 'movies.db')
if not os.path.exists(MovieDBfile):
    MovieDB = sqlite.connect(MovieDBfile)
    MovieDB.text_factory = str
    createMoviedb()
else:
    MovieDB = sqlite.connect(MovieDBfile)
    MovieDB.text_factory = str