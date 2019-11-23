#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from . import db
from . import appfeed
from .common import *
from service import updateRunning

MAX_RES = 140
max_wt = 10800  # 3hrs


def addMoviedb(moviedata):
    c = MovieDB.cursor()
    num = db.cur_exec(c, 'insert ignore into movies values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                      moviedata).rowcount

    # if num:
        # MovieDB.commit()
    return num


def lookupMoviedb(value, rvalue='distinct *', name='asin', single=True, exact=False, table='movies'):
    c = MovieDB.cursor()
    value = py2_decode(value)
    if not db.cur_exec(c, 'counttables', (table,)).fetchone():
        return '' if single else []

    sqlstring = 'select {} from {} where {} '.format(rvalue, table, name)
    retlen = len(rvalue.split(','))
    if not exact:
        value = "%{0}%".format(value)
        sqlstring += 'like (?)'
    else:
        sqlstring += '= (?)'
    if db.cur_exec(c, sqlstring, (value,)).fetchall():
        result = db.cur_exec(c, sqlstring, (value,)).fetchall()
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
        num = db.cur_exec(c, 'delete from movies where asin like (?)', ('%' + asin + '%',)).rowcount
        # if num:
            # MovieDB.commit()

    return num


def updateMoviedb(asin, col, value):
    c = MovieDB.cursor()
    asin = '%' + asin + '%'
    sqlquery = 'update movies set {}=? where asin like (?)'.format(col)
    result = db.cur_exec(c, sqlquery, (value, asin)).rowcount
    return result


def loadMoviedb(filterobj=None, value=None, sortcol=False):
    c = MovieDB.cursor()
    if filterobj:
        value = "%{0}%".format(py2_decode(value))
        return db.cur_exec(c, 'select distinct * from movies where {} like (?)'.format(filterobj), (value,))
    elif sortcol:
        return db.cur_exec(c, 'select distinct * from movies where {} is not null order by {} asc'.format(sortcol, sortcol))
    else:
        return db.cur_exec(c, 'select distinct * from movies order by movietitle asc')


def getMovieTypes(col):
    c = MovieDB.cursor()
    items = db.cur_exec(c, 'select distinct {} from movies'.format(col))
    l = getTypes(items, col)
    c.close()
    return l


def getMoviedbAsins(isPrime=1, retlist=False):
    c = MovieDB.cursor()
    content = ''
    sqlstring = 'select asin from movies where isPrime = ({})'.format(isPrime)
    if retlist:
        content = []
    for item in db.cur_exec(c, sqlstring).fetchall():
        if retlist:
            content.append([','.join(item), 0])
        else:
            content += ','.join(item)
    return content


def addMoviesdb(full_update=True, cj=True):
    MOV_TOTAL = int(getConfig('MoviesTotal', '6000'))
    dialog = xbmcgui.DialogProgress()

    if isinstance(cj, bool):
        cj = MechanizeLogin()
        if not cj:
            return

    if full_update:
        if updateRunning():
            return

        dialog.create(getString(30120))
        dialog.update(0, getString(30121))
        db.createDatabase(MovieDB, 'movie')
        MOVIE_ASINS = []
    else:
        MOVIE_ASINS = getMoviedbAsins(retlist=True)

    page = 1
    goAhead = 1
    endIndex = 0
    new_mov = 0
    retrycount = 0
    approx = 0

    while not approx:
        jsondata = appfeed.getList('Movie', randint(1, 20), NumberOfResults=1)
        approx = jsondata['message']['body'].get('approximateSize', 0)
        xbmc.sleep(randint(500, 1000))

    while goAhead == 1:
        MAX = randint(5, MAX_RES)
        jsondata = appfeed.getList('Movie', endIndex, NumberOfResults=MAX, OrderBy='Title')
        if not jsondata:
            goAhead = -1
            break

        titles = jsondata['message']['body']['titles']
        del jsondata

        if titles:
            for title in titles:
                retrycount = 0
                if full_update and dialog.iscanceled():
                    goAhead = -1
                    break
                if 'titleId' in title.keys():
                    asin = title['titleId']
                    if '_duplicate_' not in title['title']:
                        if var.onlyGer and re.compile(regex_ovf).search(title['title']):
                            Log('Movie Ignored: {}'.format(title['title']), xbmc.LOGDEBUG)
                            found = True
                        else:
                            found, MOVIE_ASINS = compasin(MOVIE_ASINS, asin)

                        if not found:
                            new_mov += ASIN_ADD(title)
        else:
            retrycount += 1
            endIndex += 1

        if retrycount > 2:
            wait_time = 3  # randint(180, 420)
            Log('Getting {} times a empty response. Waiting {} sec'.format(retrycount, wait_time))
            sleep(wait_time)
            retrycount = 0

        endIndex += len(titles)
        if (approx and endIndex + 1 >= approx) or (not approx and len(titles) == 10):
            goAhead = 0

        page += 1
        if full_update:
            if approx:
                MOV_TOTAL = approx
            dialog.update(int(endIndex * 100.0 / MOV_TOTAL), getString(30122).format(page), getString(30123).format(new_mov))
        if full_update and dialog.iscanceled():
            goAhead = -1

        if len(titles) > 9:
            endIndex -= 10

    if goAhead == 0:
        endIndex += 10
        updateLibrary(cj=cj)
        updatePop()
        writeConfig("MoviesTotal", endIndex)
        Log('Movie Update: New {} Deleted {} Total {}'.format(new_mov, deleteremoved(MOVIE_ASINS), endIndex))
        if full_update:
            setNewest()
            dialog.close()
            updateFanart()
        xbmc.executebuiltin("XBMC.Container.Refresh")
        # MovieDB.commit()
        return True

    return False


def updatePop():
    c = MovieDB.cursor()
    db.cur_exec(c, "update movies set popularity=null")
    Index = 0
    maxIndex = MAX_RES * 3

    while -1 < Index < maxIndex:
        MAX = randint(5, MAX_RES)
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
        asinlist = SCRAP_ASINS(movielib.format(lib), cj)
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
    c = MovieDB.cursor()
    db.cur_exec(c, 'drop table if exists categories')
    db.cur_exec(c, '''create table categories(
                 title TEXT,
    asins TEXT);''')
    db.cur_exec(c, 'update movies set recent=null')
    count = 1
    for catid in catList:
        if catid == 'PrimeMovieRecentlyAdded':
            for asin in catList[catid]:
                updateMoviedb(asin, 'recent', count)
                count += 1
        else:
            db.cur_exec(c, 'insert ignore into categories values (?,?)', [catid, catList[catid]])
    # MovieDB.commit()


def updateFanart():
    if var.tmdb_art == '0':
        return

    sqlstring = "select asin, movietitle, year, fanart from movies where fanart is null"
    c = MovieDB.cursor()
    Log('Movie Update: Updating Fanart')
    if var.tmdb_art == '2':
        sqlstring += " or fanart like '%images-amazon.com%'"

    for asin, movie, year, oldfanart in db.cur_exec(c, sqlstring):
        movie = movie.lower().replace('[ov]', '').replace('omu', '').replace('[ultra hd]', '').split('(')[0].strip()
        result = appfeed.getTMDBImages(movie, year=year)
        if oldfanart:
            if result == na or not result:
                result = oldfanart
        updateMoviedb(asin, 'fanart', result)
    # MovieDB.commit()
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


MovieDB = db.connSQL('movie')
