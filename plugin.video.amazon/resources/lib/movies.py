#!/usr/bin/env python
# -*- coding: utf-8 -*-
from common import *
from sqlite3 import dbapi2 as sqlite
import appfeed

MAX = 120
tmdb_art = addon.getSetting("tmdb_art")


def createMoviedb():
    c = MovieDB.cursor()
    c.execute('drop table if exists movies')
    c.execute('drop table if exists categories')
    c.execute('''create table movies
                (asin TEXT UNIQUE,
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
    PRIMARY KEY(movietitle,asin))''')
    MovieDB.commit()
    c.close()


def addMoviedb(moviedata):
    c = MovieDB.cursor()
    num = c.execute('insert or ignore into movies values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                    moviedata).rowcount
    if num:
        MovieDB.commit()
    return num


def lookupMoviedb(value, rvalue='distinct *', name='asin', single=True, exact=False, table='movies'):
    waitforDB('movie')
    c = MovieDB.cursor()
    if not c.execute('SELECT count(*) FROM sqlite_master WHERE type="table" AND name=(?)', (table,)).fetchone()[0]:
        return '' if single else []

    sqlstring = 'select %s from %s where %s ' % (rvalue, table, name)
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
    if (retlen < 2) and single:
        return None
    return (None,) * retlen


def deleteMoviedb(asin=False):
    movietitle = lookupMoviedb(asin, 'movietitle')
    num = 0
    if movietitle:
        c = MovieDB.cursor()
        num = c.execute('delete from movies where asin like (?)', ('%' + asin + '%',)).rowcount
        if num:
            MovieDB.commit()

    return num


def updateMoviedb(asin, col, value):
    waitforDB('movie')
    c = MovieDB.cursor()
    asin = '%' + asin + '%'
    sqlquery = 'update movies set %s=? where asin like (?)' % col
    result = c.execute(sqlquery, (value, asin)).rowcount
    return result


def loadMoviedb(filterobj=None, value=None, sortcol=False):
    waitforDB('movie')
    c = MovieDB.cursor()
    if filterobj:
        value = '%' + value + '%'
        return c.execute('select distinct * from movies where %s like (?)' % filterobj, (value,))
    elif sortcol:
        return c.execute('select distinct * from movies where %s is not null order by %s asc' % (sortcol, sortcol))
    else:
        return c.execute('select distinct * from movies')


def getMovieTypes(col):
    waitforDB('movie')
    c = MovieDB.cursor()
    items = c.execute('select distinct %s from movies' % col)
    l = getTypes(items, col)
    c.close()
    return l


def getMoviedbAsins(isPrime=1, retlist=False):
    waitforDB('movie')
    c = MovieDB.cursor()
    content = ''
    sqlstring = 'select asin from movies where isPrime = (%s)' % isPrime
    if retlist:
        content = []
    for item in c.execute(sqlstring).fetchall():
        if retlist:
            content.append([','.join(item), 0])
        else:
            content += ','.join(item)
    return content


def addMoviesdb(full_update=True, cj=True):
    MOV_TOTAL = int(getConfig('MoviesTotal', '0'))
    dialog = xbmcgui.DialogProgress()

    if isinstance(cj, bool):
        cj = mechanizeLogin()
        if not cj:
            return

    if full_update:
        if updateRunning():
            return

        dialog.create(getString(30120))
        dialog.update(0, getString(30121))
        createMoviedb()
        MOVIE_ASINS = []
    else:
        MOVIE_ASINS = getMoviedbAsins(retlist=True)

    page = 1
    goAhead = 1
    endIndex = 0
    new_mov = 0
    approx = 0

    while goAhead == 1:
        jsondata = appfeed.getList('Movie', endIndex, NumberOfResults=MAX, OrderBy='Title')
        if not jsondata:
            goAhead = -1
            break
        approx = jsondata['message']['body'].get('approximateSize', approx)
        titles = jsondata['message']['body']['titles']
        del jsondata

        if titles:
            for pos, title in enumerate(titles):

                if full_update and dialog.iscanceled():
                    goAhead = -1
                    break
                if 'titleId' in title.keys():
                    asin = title['titleId']
                    if '_duplicate_' not in title['title']:
                        if onlyGer and re.compile('(?i)\[(ov|omu)[(\W|omu|ov)]*\]').search(title['title']):
                            Log('Movie Out: %s' % title['title'])
                            found = True
                        else:
                            found, MOVIE_ASINS = compasin(MOVIE_ASINS, asin)
                        if not found:
                            new_mov += ASIN_ADD(title)

        endIndex += len(titles)

        if (approx and endIndex + 1 >= approx) or (not approx and len(titles) < 1):
            goAhead = 0

        page += 1
        if full_update:
            if approx:
                MOV_TOTAL = approx
            if not MOV_TOTAL:
                MOV_TOTAL = 6000
            dialog.update(int(endIndex * 100.0 / MOV_TOTAL), getString(30122) % page, getString(30123) % new_mov)
        if full_update and dialog.iscanceled():
            goAhead = -1

    if goAhead == 0:
        updateLibrary(cj=cj)
        updatePop()
        writeConfig("MoviesTotal", str(endIndex + 20))
        Log('Movie Update: New %s Deleted %s Total %s' % (new_mov, deleteremoved(MOVIE_ASINS), endIndex + 20))
        if full_update:
            setNewest()
            dialog.close()
            updateFanart()
        xbmc.executebuiltin("XBMC.Container.Refresh")
        MovieDB.commit()
        return True

    return False


def updatePop():
    waitforDB('movie')
    c = MovieDB.cursor()
    c.execute("update movies set popularity=null")
    Index = 0

    while -1 < Index < 240:
        jsondata = appfeed.getList('Movie', Index, NumberOfResults=MAX)
        titles = jsondata['message']['body']['titles']
        for title in titles:
            Index += 1
            asin = title['titleId']
            if asin:
                updateMoviedb(asin, 'popularity', Index)
        if len(titles) == 0:
            Index = -1


def updateLibrary(asinlist=None, cj=True):
    asins = ''
    if not asinlist:
        asinlist = SCRAP_ASINS(movielib % lib, cj)
        MOVIE_ASINS = getMoviedbAsins(0, True)
        for asin in asinlist:
            found, MOVIE_ASINS = compasin(MOVIE_ASINS, asin)
            if not found:
                asins += asin + ','

        deleteremoved(MOVIE_ASINS)
    else:
        asins = ','.join(asinlist)

    if not asins:
        return

    titles = appfeed.ASIN_LOOKUP(asins)['message']['body']['titles']
    for title in titles:
        ASIN_ADD(title)


def setNewest(compList=False):
    if not compList:
        compList = getCategories()
    catList = compList['movies']
    waitforDB('movie')
    c = MovieDB.cursor()
    c.execute('drop table if exists categories')
    c.execute('''create table categories(
                 title TEXT,
    asins TEXT);''')
    c.execute('update movies set recent=null')
    count = 1
    for catid in catList:
        if catid == 'PrimeMovieRecentlyAdded':
            for asin in catList[catid]:
                updateMoviedb(asin, 'recent', count)
                count += 1
        else:
            c.execute('insert or ignore into categories values (?,?)', [catid, catList[catid]])
    MovieDB.commit()


def updateFanart():
    if tmdb_art == '0':
        return

    sqlstring = 'select asin, movietitle, year, fanart from movies where fanart is null'
    c = MovieDB.cursor()
    Log('Movie Update: Updating Fanart')
    if tmdb_art == '2':
        sqlstring += ' or fanart like "%images-amazon.com%"'

    waitforDB('movie')
    for asin, movie, year, oldfanart in c.execute(sqlstring):
        movie = movie.lower().replace('[ov]', '').replace('omu', '').replace('[ultra hd]', '').split('(')[0].strip()
        result = appfeed.getTMDBImages(movie, year=year)
        if oldfanart:
            if result == na or not result:
                result = oldfanart
        updateMoviedb(asin, 'fanart', result)
    MovieDB.commit()
    Log('Movie Update: Updating Fanart Finished')


def deleteremoved(asins):
    delMovies = 0
    for item in asins:
        if item[1] == 0:
            for asin in item[0].split(','):
                delMovies += deleteMoviedb(asin)
    return delMovies


def ASIN_ADD(title):
    titelnum = 0
    stars = votes = mpaa = premiered = year = genres = poster = None
    asin, isHD, isPrime, audio = GET_ASINS(title)
    movietitle = title['title']
    plot = title.get('synopsis')
    director = title.get('director')
    studio = title.get('studioOrNetwork')
    actors = title.get('starringCast')
    runtime = title['runtime']['valueMillis'] / 1000 if 'runtime' in title else None
    trailer = title.get('trailerAvailable', False)
    fanart = title.get('heroUrl')
    isAdult = 'ageVerificationRequired' in str(title.get('restrictions'))

    if 'releaseOrFirstAiringDate' in title:
        premiered = title['releaseOrFirstAiringDate']['valueFormatted'].split('T')[0]
        year = int(premiered.split('-')[0])

    if 'regulatoryRating' in title:
        if title['regulatoryRating'] == 'not_checked':
            mpaa = getString(30171)
        else:
            mpaa = 'FSK ' + title['regulatoryRating']

    if 'genres' in title.keys():
        genres = ' / '.join(title['genres']).replace('_', ' & ').replace('Musikfilm & Tanz', 'Musikfilm, Tanz')

    if 'customerReviewCollection' in title:
        stars = float(title['customerReviewCollection']['customerReviewSummary']['averageOverallRating']) * 2
        votes = title['customerReviewCollection']['customerReviewSummary']['totalReviewCount']
    elif 'amazonRating' in title:
        stars = float(title['amazonRating']['rating']) * 2 if 'rating' in title['amazonRating'] else None
        votes = title['amazonRating']['count'] if 'count' in title['amazonRating'] else None

    if 'images' in title['formats'][0].keys():
        try:
            thumbnailUrl = title['formats'][0]['images'][0]['uri']
            thumbnailFilename = thumbnailUrl.split('/')[-1]
            thumbnailBase = thumbnailUrl.replace(thumbnailFilename, '')
            poster = thumbnailBase + thumbnailFilename.split('.')[0] + '.jpg'
        except:
            poster = None

    if 'bbl test' not in movietitle.lower() and 'test movie' not in movietitle.lower():
        moviedata = [cleanData(x) for x in
                     [asin, checkCase(movietitle), trailer, poster, plot, director, None, runtime, year,
                      premiered, studio, mpaa, actors, genres, stars, votes, fanart, isPrime, isHD, isAdult, None, None,
                      audio]]
        titelnum += addMoviedb(moviedata)
    return titelnum


MovieDBfile = getDBlocation('movie')
if not xbmcvfs.exists(MovieDBfile):
    MovieDB = sqlite.connect(MovieDBfile)
    MovieDB.text_factory = str
    createMoviedb()
else:
    MovieDB = sqlite.connect(MovieDBfile)
    MovieDB.text_factory = str
