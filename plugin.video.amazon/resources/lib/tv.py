#!/usr/bin/env python
# !/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from .common import *
from service import updateRunning
import db
import appfeed

DialogPG = xbmcgui.DialogProgress()
MAX = 140


def loadTVShowdb(filterobj=None, value=None, sortcol=None):
    db.waitforDB(tvDB)
    c = tvDB.cursor()
    if filterobj:
        value = "%{0}%".format(value.decode('utf-8'))
        return db.cur_exec(c, 'select distinct * from shows where %s like (?)' % filterobj, (value,))
    elif sortcol:
        return db.cur_exec(c, 'select distinct * from shows where %s is not null order by %s asc' % (sortcol, sortcol))
    else:
        return db.cur_exec(c, 'select distinct * from shows order by seriestitle asc')


def loadTVSeasonsdb(seriesasin=None, sortcol=None, seasonasin=None):
    db.waitforDB(tvDB)
    c = tvDB.cursor()
    if seriesasin:
        return db.cur_exec(c, 'select distinct * from seasons where seriesasin = (?)', (seriesasin,))
    if seasonasin:
        seasonasin = '%' + seasonasin + '%'
        return db.cur_exec(c, 'select distinct * from seasons where asin like (?)', (seasonasin,))
    elif sortcol:
        return db.cur_exec(c, 'select distinct * from seasons where %s is not null order by %s asc' % (sortcol, sortcol))
    else:
        return db.cur_exec(c, 'select distinct * from seasons')


def loadTVEpisodesdb(seriestitle):
    db.waitforDB(tvDB)
    c = tvDB.cursor()
    return db.cur_exec(c, 'select distinct * from episodes where seasonasin = (?) order by episode', (seriestitle,))


def getShowTypes(col):
    db.waitforDB(tvDB)
    c = tvDB.cursor()
    items = db.cur_exec(c, 'select distinct %s from shows' % col)
    l = getTypes(items, col)
    c.close()
    return l


def getPoster(seriestitle):
    c = tvDB.cursor()
    data = db.cur_exec(c, 'select distinct poster from seasons where seriestitle = (?)', (seriestitle,)).fetchone()
    return data[0]


def fixHDshows():
    Log('fixing HD infos', xbmc.LOGDEBUG)
    c = tvDB.cursor()
    db.cur_exec(c, "update shows set isHD=?", (False,))
    HDseasons = db.cur_exec(c, 'select distinct seriestitle from seasons where isHD = (?)', (True,)).fetchall()
    for series in HDseasons:
        db.cur_exec(c, "update shows set isHD=? where seriestitle=?", (True, series[0]))


def fixGenres():
    Log('fixing genres', xbmc.LOGDEBUG)
    c = tvDB.cursor()
    seasons = db.cur_exec(c, 'select distinct seriestitle,genres from seasons where genres is not null').fetchall()
    for series, genres in seasons:
        db.cur_exec(c, "update seasons set genres=? where seriestitle=? and genres is null", (genres, series))
        db.cur_exec(c, "update shows set genres=? where seriestitle=? and genres is null", (genres, series))


def updateEpisodes():
    Log('updateing num of epsiodes', xbmc.LOGDEBUG)
    c = tvDB.cursor()
    shows = db.cur_exec(c, 'select distinct asin from shows where episodetotal = 0').fetchall()
    for asin in shows:
        asinn = asin[0]
        nums = 0
        for sasin in asinn.split(','):
            nums += int((db.cur_exec(c, "select count(*) from episodes where seriesasin like ?", (sasin,)).fetchone())[0])
        db.cur_exec(c, "update shows set episodetotal=? where asin=?", (nums, asinn))


def fixYears():
    Log('fixing years', xbmc.LOGDEBUG)
    c = tvDB.cursor()
    seasons = db.cur_exec(c, 'select seasonasin,year,season from episodes where year is not null order by year desc').fetchall()
    for asin, year, season in seasons:
        asin = '%' + asin + '%'
        db.cur_exec(c, "update seasons set year=? where season=? and asin like ?", (year, season, asin))
    seasons = db.cur_exec(c, 'select seriesasin,year from seasons where year is not null order by year desc').fetchall()
    for asin, year in seasons:
        asin = '%' + asin + '%'
        db.cur_exec(c, "update shows set year=? where asin like ?", (year, asin))


def fixDBLShows():
    Log('fixing double shows', xbmc.LOGDEBUG)
    c = tvDB.cursor()
    allseries = []
    for asin, seriestitle in db.cur_exec(c, 'select asin,seriestitle from shows').fetchall():
        flttitle = cleanTitle(seriestitle)
        addlist = True
        index = 0
        for asinlist, titlelist, fltlist in allseries:
            if flttitle == fltlist:
                allseries.pop(index)
                allseries.insert(index, [asinlist + ',' + asin, titlelist, fltlist])
                db.cur_exec(c, 'delete from shows where seriestitle = (?) and asin = (?)', (seriestitle, asin))
                addlist = False
            index += 1
        if addlist:
            allseries.append([asin, seriestitle, flttitle])

    for asinlist, titlelist, fltlist in allseries:
        db.cur_exec(c, "update shows set asin = (?) where seriestitle = (?)", (asinlist, titlelist))


def fixStars():
    Log('fixing stars', xbmc.LOGDEBUG)
    c = tvDB.cursor()
    series = db.cur_exec(c, 'select seriestitle from shows where votes = 0').fetchall()
    for title in series:
        title = title[0]
        stars = db.cur_exec(c, 'select avg(stars) from seasons where seriestitle like ? and votes != 0', (title,)).fetchone()[0]
        if stars:
            db.cur_exec(c, 'update shows set stars = (?) where seriestitle = (?)', (stars, title))


def fixTitles():
    Log('fixing titles', xbmc.LOGDEBUG)
    c = tvDB.cursor()
    for asins, title in db.cur_exec(c, 'select asin, seriestitle from shows').fetchall():
        for asin in asins.split(','):
            db.cur_exec(c, 'update seasons set seriestitle = (?) where seriesasin = (?)', (title, asin))
            db.cur_exec(c, 'update episodes set seriestitle = (?) where seriesasin = (?)', (title, asin))


def cleanTitle(content):
    Log('cleaning titlea', xbmc.LOGDEBUG)
    content = content.replace(' und ', '').lower()
    invalid_chars = "?!.:&,;' "
    return ''.join(c for c in content if c not in invalid_chars)


def addDB(table, data):
    c = tvDB.cursor()
    columns = {'shows': 22, 'seasons': 24, 'episodes': 23}
    query = '?,' * columns[table]
    num = db.cur_exec(c, 'insert ignore into %s values (%s)' % (table, query[0:-1]), data).rowcount

    if not num and table == 'seasons':
        oldepi = db.cur_exec(c, 'select episodetotal from seasons where asin=(?)', (data[0],)).fetchall()[0][0]
        Log('Updating show %s season %s (O:%s N:%s)' % (data[3], data[2], oldepi, data[13]), xbmc.LOGDEBUG)
        num = db.cur_exec(c, 'update seasons set episodetotal=(?) where asin=(?)', (data[13], data[0])).rowcount

    if num:
        tvDB.commit()
    c.close()
    return num


def lookupTVdb(value, rvalue='distinct *', tbl='episodes', name='asin', single=True, exact=False):
    db.waitforDB(tvDB)
    c = tvDB.cursor()
    value = value.decode('utf-8')
    if not db.cur_exec(c, 'counttables', (tbl,)).fetchone():
        return '' if single else []

    sqlstring = 'select %s from %s where %s ' % (rvalue, tbl, name)
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


def countDB(tbl):
    c = tvDB.cursor()
    return len(db.cur_exec(c, 'select * from %s' % tbl).fetchall())


def delfromTVdb():
    asins = var.args.get('asins')
    title = var.args.get('title')
    table = var.args.get('table')
    strid = 30167 if table == 'seasons' else 30166

    if Dialog.yesno(getString(30155) % getString(strid), getString(30156) % title.decode('utf-8')):
        delasins = []
        if table == 'seasons':
            delasins.append(asins)
        else:
            for asin in asins.split(','):
                for item in lookupTVdb(asin, rvalue='asin', tbl='seasons', name='seriesasin', single=False):
                    if item:
                        delasins += item

        UpdateDialog(0, 0, 0, *deleteremoved(delasins))


def deleteremoved(asins, refresh=True):
    Log('delete removed titles', xbmc.LOGDEBUG)
    c = tvDB.cursor()
    delShows = 0
    delSeasons = 0
    delEpisodes = 0
    Log('ASINS to Remove: ' + asins.__str__())
    for item in asins:
        for seasonasin in item.split(','):
            season, seriesasin = lookupTVdb(seasonasin, rvalue='season, seriesasin', tbl='seasons')
            if not seriesasin:
                season, seriesasin = lookupTVdb(seasonasin, rvalue='season, seriesasin', name='seasonasin', tbl='episodes')
            if seriesasin:
                asin = '%' + seasonasin + '%'
                delEpisodes += db.cur_exec(c, 'delete from episodes where season = (?) and seasonasin like (?)', (season, asin)).rowcount
                delSeasons += db.cur_exec(c, 'delete from seasons where season = (?) and asin like (?)', (season, asin)).rowcount
                if not lookupTVdb(seriesasin, rvalue='asin', tbl='seasons', name='seriesasin'):
                    delShows += db.cur_exec(c, 'delete from shows where asin like (?)', ('%'+seriesasin+'%',)).rowcount
    tvDB.commit()
    c.close()
    if refresh:
        xbmc.executebuiltin('Container.Refresh')

    return delShows, delSeasons, delEpisodes


def cleanDB():
    Log('cleaning db', xbmc.LOGDEBUG)
    removeAsins = []
    seasonasins = getTVdbAsins('seasons', 2, value='asin')
    for asin, pos in getTVdbAsins('episodes', 2, retlist=True, value='seasonasin'):
        if asin not in seasonasins:
            removeAsins.append(asin)

    if removeAsins:
        UpdateDialog(0, 0, 0, *deleteremoved(removeAsins, False))

    del seasonasins


def getTVdbAsins(table, isPrime=1, retlist=False, value='asin'):
    c = tvDB.cursor()
    content = [] if retlist else ''
    sqlstring = 'select %s from %s' % (value, table)

    if isPrime < 2:
        sqlstring += ' where isPrime = (%s)' % isPrime

    for item in db.cur_exec(c, sqlstring).fetchall():
        if str(item[0]) not in str(content):
            if retlist:
                content.append(list(item)+[0, ])
            else:
                content += ','.join(item) + ','

    return content


def addTVdb(full_update=True, libasins=None, cj=True):
    if isinstance(cj, bool):
        cj = MechanizeLogin()
        if not cj:
            return

    prime = True
    new_libasins = False
    endIndex = 0
    goAhead = 1
    SERIES_COUNT = 0
    SEASON_COUNT = 0
    EPISODE_COUNT = 0
    approx = 0
    retrycount = 0

    if full_update and not libasins:
        if updateRunning():
            return

        if not Dialog.yesno(getString(30136), getString(30137), getString(30138) % '30'):
            return
        DialogPG.create(getString(30130))
        DialogPG.update(0, getString(30131))
        db.createDatabase(tvDB, 'tv')
        ALL_SERIES_ASINS = ''
        ALL_SEASONS_ASINS = []
    else:
        cleanDB()
        ALL_SEASONS_ASINS = getTVdbAsins('seasons', retlist=True, value='asin,episodetotal')
        ALL_SERIES_ASINS = getTVdbAsins('shows')

    if libasins:
        prime = False
        ALL_SEASONS_ASINS = []
        new_libasins = checkLibraryAsins(libasins, cj)
        if not new_libasins:
            return
    else:
        while not approx:
            jsondata = appfeed.getList('TVEpisode&RollUpToSeason=T', randint(1, 20), NumberOfResults=1)
            approx = jsondata['message']['body'].get('approximateSize', 0)
            xbmc.sleep(randint(500, 1000))

    while goAhead == 1:
        jsondata = appfeed.getList('TVEpisode&RollUpToSeason=T', endIndex, isPrime=prime,
                                   OrderBy='Title', NumberOfResults=MAX, AsinList=new_libasins)
        if not jsondata:
            goAhead = -1
            break

        titles = jsondata['message']['body']['titles']
        endI = jsondata['message']['body']['endIndex']
        if endI:
            endIndex = endI
        else:
            endIndex += len(titles)
        del jsondata

        if titles:
            SERIES_ASINS = ''
            EPISODE_ASINS = []
            EPISODE_NUM = []
            for title in titles:
                if full_update and DialogPG.iscanceled():
                    goAhead = -1
                    break
                SEASONS_ASIN = title['titleId']

                if var.onlyGer and not libasins and re.compile(regex_ovf).search(title['title']):
                    Log('Season Ignored: %s' % title['title'], xbmc.LOGDEBUG)
                    found = True
                else:
                    season_size = int(title['childTitles'][0]['size'])
                    found, ALL_SEASONS_ASINS = compasin(ALL_SEASONS_ASINS, SEASONS_ASIN, season_size)

                if not found:
                    if ASIN_ADD([title]):
                        SEASON_COUNT += 1
                        if title['ancestorTitles']:
                            SERIES_KEY = title['ancestorTitles'][0]['titleId']
                        else:
                            SERIES_KEY = title['titleId']
                        if SERIES_KEY not in ALL_SERIES_ASINS and 'bbl test' not in title['title'].lower():
                            SERIES_COUNT += 1
                            SERIES_ASINS += SERIES_KEY + ','
                            ALL_SERIES_ASINS += SERIES_KEY + ','
                        if season_size < 1:
                            season_size = MAX
                        parsed = urlparse.urlparse(title['childTitles'][0]['feedUrl'])
                        EPISODE_ASINS.append(urlparse.parse_qs(parsed.query)['SeasonASIN'])
                        EPISODE_NUM.append(season_size)

            if (approx and endIndex + 1 >= approx) or (not approx and len(titles) < 1):
                goAhead = 0

            del titles

            if SERIES_ASINS:
                ASIN_ADD(0, asins=SERIES_ASINS)
            if full_update:
                DialogPG.update(int(SEASON_COUNT * 100.0 / approx), getString(30132) % SERIES_COUNT,
                                getString(30133) % SEASON_COUNT, getString(30134) % EPISODE_COUNT)
            episodes = 0
            AsinList = ''
            EPISODE_NUM.append(MAX + 1)
            for index, item in enumerate(EPISODE_ASINS):
                episodes += EPISODE_NUM[index]
                AsinList += ','.join(item) + ','
                if (episodes + EPISODE_NUM[index + 1]) > MAX:
                    jsondata = appfeed.getList('TVEpisode', 0, isPrime=prime, NumberOfResults=MAX, AsinList=AsinList)
                    titles = jsondata['message']['body']['titles']
                    if titles:
                        EPISODE_COUNT += ASIN_ADD(titles)
                    if full_update and DialogPG.iscanceled():
                        goAhead = -1
                        break
                    episodes = 0
                    AsinList = ''
                    if full_update:
                        DialogPG.update(int(SEASON_COUNT * 100.0 / approx), getString(30132) % SERIES_COUNT,
                                        getString(30133) % SEASON_COUNT, getString(30134) % EPISODE_COUNT)
                    del titles
        else:
            retrycount += 1

        if (approx and endIndex + 1 >= approx) or (not approx):
            goAhead = 0

        if retrycount > 3:
            Log('Waiting 5min')
            sleep(300)
            appfeed.getList('TVEpisode&RollUpToSeason=T', endIndex-randint(1, MAX-1), isPrime=prime,
                            NumberOfResults=randint(1, 10), AsinList=new_libasins)
            retrycount = 0

    if goAhead == 0:
        if not libasins:
            updatePop()
            delShows, delSeasons, delEpisodes = deleteremoved(getcompresult(ALL_SEASONS_ASINS))
            UpdateDialog(SERIES_COUNT, SEASON_COUNT, EPISODE_COUNT, delShows, delSeasons, delEpisodes)
            addTVdb(False, 'full', cj)

        fixDBLShows()
        fixYears()
        fixStars()
        fixHDshows()
        updateEpisodes()
        fixTitles()
        if full_update:
            setNewest()
            DialogPG.close()
            updateFanart()
        tvDB.commit()
        return True

    return False


def checkLibraryAsins(asinlist, cj):
    Log('updating titles in libary', xbmc.LOGDEBUG)
    asins = ''
    removed_seasons = []

    if asinlist == 'full':
        asinlist = SCRAP_ASINS(tvlib % lib, cj)
        ALL_SEASONS_ASINS = getTVdbAsins('seasons', 0, True)
        for asin in asinlist:
            found, ALL_SEASONS_ASINS = compasin(ALL_SEASONS_ASINS, asin)
            if not found:
                asins += asin + ','

        for item in ALL_SEASONS_ASINS:
            if item[1] == 0:
                removed_seasons.append(item[0])

        deleteremoved(removed_seasons)
    else:
        asins = ','.join(asinlist)

    if not asins:
        return False

    return asins


def updatePop():
    Log('updating popular titles', xbmc.LOGDEBUG)
    c = tvDB.cursor()
    db.cur_exec(c, "update shows set popularity=null")
    Index = 0
    maxIndex = MAX * 3

    while -1 < Index < maxIndex:
        jsondata = appfeed.getList('tvepisode,tvseason,tvseries&RollupToSeries=T', Index, NumberOfResults=MAX)
        titles = jsondata['message']['body']['titles']
        for title in titles:
            Index += 1
            asin = title['titleId']
            if asin:
                db.cur_exec(c, "update shows set popularity=? where asin like (?) and popularity is null",
                            (Index, '%' + asin + '%'))
        if len(titles) == 0:
            Index = -1


def UpdateDialog(SERIES_COUNT, SEASON_COUNT, EPISODE_COUNT, delShows, delSeasons, delEpisodes):
    line1 = ''
    line2 = ''
    line3 = ''
    if SERIES_COUNT:
        line1 += '%s %s' % (getString(30132) % SERIES_COUNT, getString(30124))
        if delShows:
            line1 += ', %s %s' % (delShows, getString(30125))

    if delShows and (not SERIES_COUNT):
        line1 += '%s %s' % (getString(30132) % delShows, getString(30125))
    if SEASON_COUNT:
        line2 += '%s %s' % (getString(30133) % SEASON_COUNT, getString(30124))
        if delSeasons:
            line2 += ', %s %s' % (delSeasons, getString(30125))

    if delSeasons and (not SEASON_COUNT):
        line2 += '%s %s' % (getString(30133) % delSeasons, getString(30125))
    if EPISODE_COUNT:
        line3 += '%s %s' % (getString(30134) % EPISODE_COUNT, getString(30124))
        if delEpisodes:
            line3 += ', %s %s' % (delEpisodes, getString(30125))

    if delEpisodes and (not EPISODE_COUNT):
        line3 += '%s %s' % (getString(30134) % delEpisodes, getString(30125))
    if line1 + line2 + line3 == '':
        line2 = getString(30127)

    Log('TV Shows Update:\n%s\n%s\n%s' % (line1, line2, line3))
    # Dialog.ok(getString(30126), line1, line2, line3)


def ASIN_ADD(titles, asins=None):
    count = 0
    if asins:
        titles = appfeed.ASIN_LOOKUP(asins)['message']['body']['titles']

    for title in titles:
        stars = votes = seriesasin = mpaa = premiered = year = genres = poster = None
        seasontotal = episodetotal = season = 0

        contentType = 'SERIES' if asins else title['contentType']
        asin, isHD, isPrime, audio = GET_ASINS(title)
        plot = title.get('synopsis')
        studio = title.get('studioOrNetwork')
        actors = title.get('starringCast')
        fanart = title.get('heroUrl')
        isAdult = 'ageVerificationRequired' in str(title.get('restrictions'))

        if 'images' in title['formats'][0].keys():
            try:
                thumbnailUrl = title['formats'][0]['images'][0]['uri']
                thumbnailFilename = thumbnailUrl.split('/')[-1]
                thumbnailBase = thumbnailUrl.replace(thumbnailFilename, '')
                poster = thumbnailBase + thumbnailFilename.split('.')[0] + '.jpg'
            except:
                pass

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
            votes = title['amazonRating']['count'] if 'count' in title['amazonRating'] else 0

        if contentType == 'SERIES':
            seriestitle = title['title']
            if 'childTitles' in title:
                seasontotal = title['childTitles'][0]['size']
            showdata = [cleanData(x) for x in
                        [asin, checkCase(seriestitle), plot, studio, mpaa, genres, actors, premiered, year,
                         stars, votes, seasontotal, 0, audio, isHD, isPrime, None, None, None, poster, None, fanart]]
            count += addDB('shows', showdata)
        elif contentType == 'SEASON':
            season = title['number']
            if title['ancestorTitles']:
                try:
                    seriestitle = title['ancestorTitles'][0]['title']
                    seriesasin = title['ancestorTitles'][0]['titleId']
                except:
                    pass
            else:
                seriesasin = asin.split(',')[0]
                seriestitle = title['title']
            if 'childTitles' in title:
                episodetotal = title['childTitles'][0]['size']
            imdburl = title.get('imdbUrl')
            seasondata = [cleanData(x) for x in
                          [asin, seriesasin, season, checkCase(seriestitle), plot, actors, studio, mpaa, genres,
                           premiered, year, stars, votes, episodetotal, audio, None, None, isHD, isPrime, imdburl,
                           poster, None, fanart, False]]
            count += addDB('seasons', seasondata)
        elif contentType == 'EPISODE':
            episodetitle = title['title']
            seasontitle = ''
            if 'ancestorTitles' in title:
                for content in title['ancestorTitles']:
                    if content['contentType'] == 'SERIES':
                        seriesasin = content.get('titleId')
                        seriestitle = content.get('title', '')
                    elif content['contentType'] == 'SEASON':
                        season = content.get('number')
                        seasonasin = content.get('titleId')
                        seasontitle = content.get('title', '')
                if not seriesasin:
                    seriesasin = seasonasin
                    seriestitle = seasontitle
            episode = title.get('number', 0)
            runtime = title['runtime']['valueMillis'] / 1000 if 'runtime' in title else None

            episodedata = [cleanData(x) for x in
                           [asin, seasonasin, seriesasin, checkCase(seriestitle), season, episode, poster, mpaa,
                            actors, genres, checkCase(episodetitle), studio, stars, votes, fanart, plot,
                            premiered, year, runtime, isHD, isPrime, isAdult, audio]]
            count += addDB('episodes', episodedata)
    return count


def updateFanart():
    if var.tvdb_art == '0':
        return

    seasons = False
    c = tvDB.cursor()
    sqlstring = "select asin, seriestitle, fanart, poster from shows where fanart is null"
    Log('TV Update: Updating Fanart')
    if var.tvdb_art == '2':
        sqlstring += " or fanart like '%images-amazon.com%'"
    if var.tvdb_art == '3':
        sqlstring += " or poster like '%images-amazon.com%'"
        seasons = True
    db.waitforDB(tvDB)
    for asin, title, oldfanart, oldposter in db.cur_exec(c, sqlstring).fetchall():
        title = title.lower().replace('[ov]', '').replace('[ultra hd]', '').replace('?', '') \
                .replace('omu', '').split('(')[0].strip()
        tvid, poster, fanart = appfeed.getTVDBImages(title, seasons=seasons)

        if not fanart:
            fanart = appfeed.getTMDBImages(title, content='tv')

        if oldfanart and not fanart:
            fanart = oldfanart

        if oldposter and not poster:
            poster = oldposter

        if tvid:
            if not fanart:
                fanart = na

            if not poster:
                fanart = na

        db.cur_exec(c, 'update shows set fanart=? where asin = (?)', (fanart, asin))
        if var.tvdb_art == '3':
            db.cur_exec(c, 'update shows set poster=? where asin = (?)', (poster, asin))
            if tvid:
                for season, url in tvid.items():
                    for singleasin in asin.split(','):
                        singleasin = '%' + singleasin + '%'
                        db.cur_exec(c, 'update seasons set poster=? where seriesasin like (?) and season = (?)',
                                    (url, singleasin, int(season)))
    tvDB.commit()
    Log('TV Update: Updating Fanart Finished')


def getIMDbID(asins, title):
    url = imdbid = None
    db.waitforDB(tvDB)
    c = tvDB.cursor()
    for asin in asins.split(','):
        asin = '%' + asin + '%'
        url = db.cur_exec(c, 'select imdburl from seasons where seriesasin like (?) and imdburl is not null',
                          (asin,)).fetchone()
        if url:
            url = url[0]
            break
    if not url:
        while not imdbid:
            data = getURL('http://www.omdbapi.com/?type=series&t=' + urllib.quote_plus(title.encode('utf-8')))
            if data['Response'] == 'True':
                imdbid = data['imdbID']
            else:
                oldtitle = title
                if title.count(' - '):
                    title = title.split(' - ')[0]
                elif title.count(': '):
                    title = title.split(': ')[0]
                elif title.count('?'):
                    title = title.replace('?', '')
                if title == oldtitle:
                    imdbid = na
    else:
        imdbid = re.compile('/title/(.+?)/', re.DOTALL).findall(url)
    Log(imdbid + asins.split(',')[0])
    return imdbid


def setNewest(compList=False):
    Log('updating new seasons', xbmc.LOGDEBUG)
    if not compList:
        compList = getCategories()
    catList = compList['tv_shows']
    db.waitforDB(tvDB)
    c = tvDB.cursor()
    db.cur_exec(c, 'drop table if exists categories')
    db.cur_exec(c, 'create table categories(title TEXT, asins TEXT)')
    db.cur_exec(c, 'update seasons set recent=null')
    count = 1
    for catid in catList:
        if catid == 'PrimeTVRecentlyAdded':
            for asin in catList[catid]:
                seasonasin = lookupTVdb(asin, rvalue='seasonasin')
                if not seasonasin:
                    seasonasin = asin

                db.cur_exec(c, "update seasons set recent=? where asin like (?)", (count, '%' + seasonasin + '%'))
                count += 1
        else:
            db.cur_exec(c, 'insert ignore into categories values (?,?)', [catid, catList[catid]])
    tvDB.commit()


tvDB = db.connSQL('tv')
