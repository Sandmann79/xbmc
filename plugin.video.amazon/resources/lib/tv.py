#!/usr/bin/env python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
from BeautifulSoup import BeautifulStoneSoup
from BeautifulSoup import BeautifulSoup
import common
import appfeed

try:
    from sqlite3 import dbapi2 as sqlite
except:
    from pysqlite2 import dbapi2 as sqlite

xbmc = common.xbmc
urllib = common.urllib
xbmcgui = common.xbmcgui
re = common.re
json = common.json
os = common.os
urlparse = common.urlparse

################################ TV db
MAX = int(common.addon.getSetting("mov_perpage"))
EPI_TOTAL = common.addon.getSetting("EpisodesTotal")
if EPI_TOTAL == '': EPI_TOTAL = '17000'
EPI_TOTAL = int(EPI_TOTAL)
tvdb_art = common.addon.getSetting("tvdb_art")

Dialog = xbmcgui.Dialog()
DialogPG = xbmcgui.DialogProgress()

def createTVdb():
    c = tvDB.cursor()
    c.execute('drop table if exists shows')
    c.execute('drop table if exists seasons')
    c.execute('drop table if exists episodes')
    c.execute('drop table if exists categories')
    c.execute('''CREATE TABLE shows(
                 asin TEXT UNIQUE,
                 seriestitle TEXT,
                 plot TEXT,
                 network TEXT,
                 mpaa TEXT,
                 genres TEXT,
                 actors TEXT,
                 airdate TEXT,
                 year INTEGER,
                 stars float,
                 votes TEXT,
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
                 PRIMARY KEY(asin,seriestitle)
                 );''')
    c.execute('''CREATE TABLE seasons(
                 asin TEXT UNIQUE,
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
                 votes TEXT,
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
                 PRIMARY KEY(asin,seriestitle,season,isHD),
                 FOREIGN KEY(seriestitle) REFERENCES shows(seriestitle)
                 );''')
    c.execute('''create table episodes(
                 asin TEXT UNIQUE,
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
                 votes TEXT,
                 fanart TEXT,
                 plot TEXT,
                 airdate TEXT,
                 year INTEGER,
                 runtime TEXT,
                 isHD BOOLEAN,
                 isprime BOOLEAN,
                 isAdult BOOLEAN,
                 audio INTEGER,
                 PRIMARY KEY(asin,seriestitle,season,episode,episodetitle,isHD),
                 FOREIGN KEY(seriestitle,season) REFERENCES seasons(seriestitle,season)
                 );''')
    tvDB.commit()
    c.close()

def loadTVShowdb(filter=False,value=False,sortcol=False):
    common.waitforDB('tv')
    c = tvDB.cursor()
    if filter:
        value = '%' + value + '%'
        return c.execute('select distinct * from shows where %s like (?)' % filter, (value,))
    elif sortcol:
        return c.execute('select distinct * from shows where %s is not null order by %s asc' % (sortcol,sortcol))
    else:
        return c.execute('select distinct * from shows')

def loadTVSeasonsdb(seriesasin=False,sortcol=False,seasonasin=False):
    common.waitforDB('tv')
    c = tvDB.cursor()
    if seriesasin:
        return c.execute('select distinct * from seasons where seriesasin = (?)', (seriesasin,))
    if seasonasin:
        seasonasin = '%' + seasonasin + '%'
        return c.execute('select distinct * from seasons where asin like (?)', (seasonasin,))
    elif sortcol:
        return c.execute('select distinct * from seasons where %s is not null order by %s asc' % (sortcol,sortcol))
    else:
        return c.execute('select distinct * from seasons')

def loadTVEpisodesdb(seriestitle):
    common.waitforDB('tv')
    c = tvDB.cursor()
    return c.execute('select distinct * from episodes where seasonasin = (?) order by episode', (seriestitle,))

def getShowTypes(col):
    common.waitforDB('tv')
    c = tvDB.cursor()
    items = c.execute('select distinct %s from shows' % col)
    list = common.getTypes(items, col)
    c.close()
    return list

def getPoster(seriestitle):
    c = tvDB.cursor()
    data = c.execute('select distinct poster from seasons where seriestitle = (?)', (seriestitle,)).fetchone()
    return data[0]

def fixHDshows():
    c = tvDB.cursor()
    c.execute("update shows set isHD=?", (False,))
    HDseasons = c.execute('select distinct seriestitle from seasons where isHD = (?)', (True,)).fetchall()
    for series in HDseasons:
        c.execute("update shows set isHD=? where seriestitle=?", (True,series[0]))
    
def fixGenres():
    c = tvDB.cursor()
    seasons = c.execute('select distinct seriestitle,genres from seasons where genres is not null').fetchall()
    for series,genres in seasons:
        c.execute("update seasons set genres=? where seriestitle=? and genres is null", (genres,series))
        c.execute("update shows set genres=? where seriestitle=? and genres is null", (genres,series))

def updateEpisodes():
    c = tvDB.cursor()
    shows = c.execute('select distinct asin from shows where episodetotal is 0').fetchall()
    for asin in shows:
        asinn = asin[0]
        nums = 0
        for sasin in asinn.split(','):
            nums += int((c.execute("select count(*) from episodes where seriesasin like ?", (sasin,)).fetchone())[0])
        c.execute("update shows set episodetotal=? where asin=?", (nums,asinn))
    
def fixYears():
    c = tvDB.cursor()
    seasons = c.execute('select seasonasin,year,season from episodes where year is not null order by year desc').fetchall()
    for asin,year,season in seasons:
        asin = '%' + asin + '%'
        c.execute("update seasons set year=? where season=? and asin like ?", (year,season,asin))
    seasons = c.execute('select seriesasin,year from seasons where year is not null order by year desc').fetchall()
    for asin,year in seasons:
        asin = '%' + asin + '%'
        c.execute("update shows set year=? where asin like ?", (year,asin))
    
def fixDBLShows():
    c = tvDB.cursor()
    allseries = []
    for asin,seriestitle in c.execute('select asin,seriestitle from shows').fetchall():
        flttitle = cleanTitle(seriestitle)
        addlist = True
        index = 0
        for asinlist,titlelist,fltlist in allseries:
            if flttitle == fltlist:
                allseries.pop(index)
                allseries.insert(index, [asinlist + ',' + asin,titlelist,fltlist])
                c.execute('delete from shows where seriestitle = (?) and asin = (?)', (seriestitle,asin))
                addlist = False
            index += 1
        if addlist: allseries.append([asin,seriestitle,flttitle])
    for asinlist,titlelist,fltlist in allseries: 
        c.execute("update shows set asin = (?) where seriestitle = (?)", (asinlist, titlelist))
    
def fixStars():
    c = tvDB.cursor()
    series = c.execute('select seriestitle from shows where votes is 0').fetchall()
    for title in series:
        title = title[0]
        stars = c.execute('select avg(stars) from seasons where seriestitle like ? and votes is not 0', (title,)).fetchone()[0]
        if stars: c.execute('update shows set stars = (?) where seriestitle = (?)', (stars, title))
    
def fixTitles():
    c = tvDB.cursor()
    for asins, title in c.execute('select asin, seriestitle from shows').fetchall():
        for asin in asins.split(','):
            c.execute('update seasons set seriestitle = (?) where seriesasin = (?)', (title, asin))
            c.execute('update episodes set seriestitle = (?) where seriesasin = (?)', (title, asin))
    
def cleanTitle(content):
    content = content.replace(' und ','').lower()
    invalid_chars = "?!.:&,;' "
    return ''.join(c for c in content if c not in invalid_chars)

def addDB(table, data):
    if table == 'shows': columns = 22
    elif table == 'seasons': columns = 23
    elif table == 'episodes': columns = 23
    else: return
    query = '?,' * columns
    c = tvDB.cursor()
    num = c.execute('insert or ignore into %s values (%s)' % (table, query[0:-1]), data).rowcount
    if num: 
        tvDB.commit()
    c.close()
    return num
    
def lookupTVdb(value, rvalue='distinct *', tbl='episodes', name='asin', single=True, exact=False):
    common.waitforDB('tv')
    c = tvDB.cursor()
    if not c.execute('SELECT count(*) FROM sqlite_master WHERE type="table" AND name=(?)', (tbl,)).fetchone()[0]: return ''
    sqlstring = 'select %s from %s where %s ' % (rvalue, tbl, name)
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

def countDB(tbl):
    c = tvDB.cursor()
    return len(c.execute('select * from %s' % tbl).fetchall())
    
def delfromTVdb():
    asins = common.args.asins
    title = common.args.title
    table = common.args.table
    id = 30166
    if table == 'seasons': id = 30167

    if Dialog.yesno(common.getString(30155) % common.getString(id), common.getString(30156) % title.decode('utf-8')):
        delasins = []
        if table == 'seasons':
            delasins.append(asins)
        else:
            for asin in asins.split(','):
                for item in lookupTVdb(asin, rvalue='asin', tbl='seasons', name='seriesasin'):
                    if item: delasins += (item)
        UpdateDialog(0, 0, 0, *deleteremoved(delasins))
        
def deleteremoved(asins, refresh=True):
    c = tvDB.cursor()
    delShows = 0
    delSeasons = 0
    delEpisodes = 0
    common.Log('ASINS to Remove: ' + asins.__str__())
    for item in asins:
        for seasonasin in item.split(','):
            title, season = lookupTVdb(seasonasin, rvalue='seriestitle, season', tbl='seasons', name='asin')
            if title and season:
                asin = '%' + seasonasin + '%'
                delEpisodes += c.execute('delete from episodes where seriestitle = (?) and season = (?) and seasonasin like (?)', (title, season, asin)).rowcount
                delSeasons += c.execute('delete from seasons where seriestitle = (?) and season = (?) and asin like (?)', (title, season, asin)).rowcount
                if not lookupTVdb(title, rvalue='asin', tbl='seasons', name='seriestitle'):
                    delShows += c.execute('delete from shows where seriestitle = (?)', (title,)).rowcount
    tvDB.commit()
    c.close()
    if refresh: xbmc.executebuiltin('Container.Refresh')
    return delShows, delSeasons, delEpisodes
    
def cleanDB():
    c = tvDB.cursor()
    episodeasins = getTVdbAsins('episodes', 2, value='seasonasin')
    removeAsins = []
    for asins, season in lookupTVdb('', rvalue='asin, season', tbl='seasons', name='asin', single=False):
        foundSeason = False
        for asin in asins.split(','):
            if asin in episodeasins: foundSeason = True
        if not foundSeason: removeAsins.append(asins)
    if len(removeAsins): UpdateDialog(0, 0, 0, *deleteremoved(removeAsins, False))
    del episodeasins#,seasonasins

def getTVdbAsins(table, isPrime=1, list=False, value='asin'):
    c = tvDB.cursor()
    content = ''
    if list:
        content = []
    sqlstring = 'select %s from %s' % (value,table)
    if isPrime < 2: sqlstring += ' where isPrime = (%s)' % isPrime
    for item in c.execute(sqlstring).fetchall():
        if list:
            content.append([','.join(item), 0])
        else:
            content += ','.join(item) + ','
    return content
    
def addTVdb(full_update = True, libasins = False):
    prime = True
    new_libasins = False
    try:
        if common.args.url == 'u':
            full_update = False
    except: pass
    endIndex = 0
    goAhead = 1
    SERIES_COUNT = 0
    SEASON_COUNT = 0
    EPISODE_COUNT = 0
    POP_ASINS = []
    
    if full_update and not libasins:
        if common.updateRunning(): return
        if not Dialog.yesno(common.getString(30136), common.getString(30137), common.getString(30138) % '30'):
            return
        DialogPG.create(common.getString(30130))
        DialogPG.update(0,common.getString(30131))
        createTVdb()
        ALL_SERIES_ASINS = ''
        ALL_SEASONS_ASINS = []
    else:
        cleanDB()
        ALL_SEASONS_ASINS = getTVdbAsins('seasons', list=True)
        ALL_SERIES_ASINS = getTVdbAsins('shows')
        
    if libasins:
        prime = False
        ALL_SEASONS_ASINS = []
        new_libasins = checkLibraryAsins(libasins)
        if not new_libasins: return
            
    while goAhead == 1:
        json = appfeed.getList('tvepisode,tvseason,tvseries&RollupToSeason=T', endIndex, isPrime=prime, OrderBy='Title', NumberOfResults=MAX, AsinList=new_libasins)
        titles = json['message']['body']['titles']
        if titles:
            SERIES_ASINS = ''
            EPISODE_ASINS = []
            EPISODE_NUM = []
            for title in titles:
                if full_update and DialogPG.iscanceled():
                    goAhead = -1
                    break
                SEASONS_ASIN = title['titleId']
                endIndex += 1
                found, ALL_SEASONS_ASINS = common.compasin(ALL_SEASONS_ASINS, SEASONS_ASIN)
                if not found:
                    if ASIN_ADD([title]):
                        SEASON_COUNT += 1
                        if title['ancestorTitles']:
                            SERIES_KEY = title['ancestorTitles'][0]['titleId']
                        else:
                            SERIES_KEY = title['titleId']
                        if SERIES_KEY not in ALL_SERIES_ASINS and 'bbl test' not in title['title'].lower():
                            SERIES_COUNT += 1
                            SERIES_ASINS += SERIES_KEY+','
                            ALL_SERIES_ASINS += SERIES_KEY+','
                        season_size = int(title['childTitles'][0]['size'])
                        if season_size < 1:
                            season_size = MAX
                        parsed = urlparse.urlparse(title['childTitles'][0]['feedUrl'])
                        EPISODE_ASINS.append(urlparse.parse_qs(parsed.query)['SeasonASIN'])
                        EPISODE_NUM.append(season_size)
            if len(titles) < MAX: goAhead = 0
            del titles
            if SERIES_ASINS:
                ASIN_ADD(0, asins=SERIES_ASINS)
            if full_update:
                DialogPG.update(int(EPISODE_COUNT*100.0/EPI_TOTAL), common.getString(30132) % SERIES_COUNT, common.getString(30133) % SEASON_COUNT,common.getString(30134) % EPISODE_COUNT)
            goAheadepi = 1
            episodes = 0
            AsinList = ''
            EPISODE_NUM.append(MAX + 1)
            for index, item in enumerate(EPISODE_ASINS):
                episodes += EPISODE_NUM[index]
                AsinList += ','.join(item) + ','
                if (episodes + EPISODE_NUM[index+1]) > MAX:
                    json = appfeed.getList('TVEpisode', 0, isPrime=prime, NumberOfResults=MAX, AsinList=AsinList)
                    titles = json['message']['body']['titles']
                    if titles:
                        EPISODE_COUNT += ASIN_ADD(titles)
                    else:
                        goAheadepi = -1
                    if full_update and DialogPG.iscanceled():
                        goAheadepi = -1
                        goAhead = -1
                        break
                    episodes = 0
                    AsinList = ''
                    if full_update:
                        DialogPG.update(int(EPISODE_COUNT*100.0/EPI_TOTAL), common.getString(30132) % SERIES_COUNT, common.getString(30133) % SEASON_COUNT,common.getString(30134) % EPISODE_COUNT)
                    del titles
        else:
            goAhead = 0
            
    if goAhead == 0:
        if not libasins: 
            updatePop()
            removed_seasons = []
            for item in ALL_SEASONS_ASINS:
                if item[1] == 0: removed_seasons.append(item[0])
            delShows, delSeasons, delEpisodes = deleteremoved(removed_seasons)
            UpdateDialog(SERIES_COUNT, SEASON_COUNT, EPISODE_COUNT, delShows, delSeasons, delEpisodes)
            addTVdb(False, 'full')
            
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
        common.addon.setSetting("EpisodesTotal",str(countDB('episodes')))

def checkLibraryAsins(asinlist):
    asins = ''
    removed_seasons = []
    
    if asinlist == 'full':
        asinlist = common.SCRAP_ASINS(common.tvlib % common.lib)
        ALL_SEASONS_ASINS = getTVdbAsins('seasons', 0, True)
        for asin in asinlist:
            found, ALL_SEASONS_ASINS = common.compasin(ALL_SEASONS_ASINS, asin)
            if not found: asins += asin + ','
        for item in ALL_SEASONS_ASINS:
            if item[1] == 0: removed_seasons.append(item[0])
        deleteremoved(removed_seasons)
    else: asins = ','.join(asinlist)

    if not asins: return False
    return asins

def updatePop():
    c = tvDB.cursor()
    c.execute("update shows set popularity=null")
    Index = 0
    
    while Index != -1:
        json = appfeed.getList('tvepisode,tvseason,tvseries&RollupToSeries=T', Index, NumberOfResults=MAX)
        titles = json['message']['body']['titles']
        for title in titles:
            Index += 1
            asin = title['titleId']
            if asin: c.execute("update shows set popularity=? where asin like (?) and popularity is null", (Index, '%' + asin + '%'))
        if len(titles) == 0: Index = -1
        
def UpdateDialog(SERIES_COUNT, SEASON_COUNT, EPISODE_COUNT, delShows, delSeasons, delEpisodes):
    line1 = ''
    line2 = ''
    line3 = ''
    if SERIES_COUNT:
        line1 += '%s %s' % (common.getString(30132) % SERIES_COUNT, common.getString(30124))
        if delShows: line1 += ', %s %s' % (delShows, common.getString(30125))
    if (delShows) and (not SERIES_COUNT):
        line1 += '%s %s' % (common.getString(30132) % delShows, common.getString(30125))
    if SEASON_COUNT:
        line2 += '%s %s' % (common.getString(30133) % SEASON_COUNT, common.getString(30124))
        if delSeasons: line2 += ', %s %s' % (delSeasons, common.getString(30125))
    if (delSeasons) and (not SEASON_COUNT):
        line2 += '%s %s' % (common.getString(30133) % delSeasons, common.getString(30125))
    if EPISODE_COUNT:
        line3 += '%s %s' % (common.getString(30134) % EPISODE_COUNT, common.getString(30124))
        if delEpisodes: line3 += ', %s %s' % (delEpisodes, common.getString(30125))
    if (delEpisodes) and (not EPISODE_COUNT):
        line3 += '%s %s' % (common.getString(30134) % delEpisodes, common.getString(30125))
    if line1 + line2 + line3 == '': line2 = common.getString(30127)
    common.Log('TV Shows Update:\n%s\n%s\n%s' % (line1,line2,line3))
    #Dialog.ok(common.getString(30126), line1, line2, line3)
    
def ASIN_ADD(titles,asins=False,url=False,single=False):
    if asins:
        titles = appfeed.ASIN_LOOKUP(asins)['message']['body']['titles']
    count = 0
    for title in titles:
        poster = plot = premiered = year = studio = mpaa = fanart = imdburl = None
        actors = genres = stars = votes = seriesasin = runtime = banner = None
        seasontotal = episodetotal = episode = 0
        isAdult = False
        if asins:
            contentType = 'SERIES'
        else:
            contentType = title['contentType']

        asin, isHD, isPrime, audio = common.GET_ASINS(title)
        if title['formats'][0].has_key('images'):
            try:
                thumbnailUrl = title['formats'][0]['images'][0]['uri']
                thumbnailFilename = thumbnailUrl.split('/')[-1]
                thumbnailBase = thumbnailUrl.replace(thumbnailFilename,'')
                poster = thumbnailBase+thumbnailFilename.split('.')[0]+'.jpg'
            except: pass
        if title.has_key('synopsis'):
            plot = title['synopsis']
        if title.has_key('releaseOrFirstAiringDate'):
            premiered = title['releaseOrFirstAiringDate']['valueFormatted'].split('T')[0]
            year = int(premiered.split('-')[0])
        if title.has_key('studioOrNetwork'):
            studio = title['studioOrNetwork']
        if title.has_key('regulatoryRating'):
            if title['regulatoryRating'] == 'not_checked': mpaa = common.getString(30171)
            else: mpaa = common.getString(30170) + title['regulatoryRating']
        if title.has_key('starringCast'):
            actors = title['starringCast']
        if title.has_key('genres'):
            genres = ' / '.join(title['genres']).replace('_', ' & ').replace('Musikfilm & Tanz', 'Musikfilm, Tanz')
        if title.has_key('customerReviewCollection'):
            stars = float(title['customerReviewCollection']['customerReviewSummary']['averageOverallRating'])*2
            votes = str(title['customerReviewCollection']['customerReviewSummary']['totalReviewCount'])
        elif title.has_key('amazonRating'):
            if title['amazonRating'].has_key('rating'): stars = float(title['amazonRating']['rating'])*2
            if title['amazonRating'].has_key('count'): votes = str(title['amazonRating']['count'])                
        if title.has_key('heroUrl'):
            fanart = title['heroUrl']
            
        if contentType == 'SERIES':
            seriestitle = title['title']
            if title.has_key('childTitles'):
                seasontotal = title['childTitles'][0]['size']
            showdata = [common.cleanData(x) for x in [asin,common.checkCase(seriestitle),plot,studio,mpaa,genres,actors,premiered,year,stars,votes,seasontotal,0,audio,isHD,isPrime,None,None,None,poster,None,fanart]]
            count += addDB('shows', showdata)
            if single:
                return asin,ASINLIST
        elif contentType == 'SEASON':
            season = title['number']
            if title['ancestorTitles']:
                try:
                    seriestitle = title['ancestorTitles'][0]['title']
                    seriesasin = title['ancestorTitles'][0]['titleId']
                except: pass
            else:
                seriesasin = asin.split(',')[0]
                seriestitle = title['title']
            if title.has_key('childTitles'):
                episodetotal = title['childTitles'][0]['size']
            #if title.has_key('drakeUrl'):
            #    imdburl = title['drakeUrl']
            if title.has_key('imdbUrl'):
                imdburl = title['imdbUrl']
            seasondata = [common.cleanData(x) for x in [asin,seriesasin,season,common.checkCase(seriestitle),plot,actors,studio,mpaa,genres,premiered,year,stars,votes,episodetotal,audio,None,None,isHD,isPrime,imdburl,poster,None,fanart]]
            count += addDB('seasons', seasondata)
        elif contentType == 'EPISODE':
            episodetitle = title['title']
            if title.has_key('ancestorTitles'):
                for content in title['ancestorTitles']:
                    if content['contentType'] == 'SERIES':
                        if content.has_key('titleId'): seriesasin = content['titleId']
                        if content.has_key('title'): seriestitle = content['title']
                    elif content['contentType'] == 'SEASON':
                        if content.has_key('number'): season = content['number']
                        if content.has_key('titleId'): seasonasin = content['titleId']
                        if content.has_key('title'): seasontitle = content['title']
                if not seriesasin:
                    seriesasin = seasonasin
                    seriestitle = seasontitle                        
            if title.has_key('number'):
                episode = title['number']
            if title.has_key('runtime'):
                runtime = str(title['runtime']['valueMillis']/60000)
            if title.has_key('restrictions'):
                for rest in title['restrictions']:
                    if rest['action'] == 'playback':
                        if rest['type'] == 'ageVerificationRequired': isAdult = True
            episodedata = [common.cleanData(x) for x in [asin,seasonasin,seriesasin,common.checkCase(seriestitle),season,episode,poster,mpaa,actors,genres,common.checkCase(episodetitle),studio,stars,votes,fanart,plot,premiered,year,runtime,isHD,isPrime,isAdult,audio]]
            count += addDB('episodes', episodedata)
    return count

def updateFanart():
    if tvdb_art == '0': return
    asin = title = year = None
    seasons = False
    c = tvDB.cursor()
    sqlstring = 'select asin, seriestitle, fanart, poster from shows where fanart is null'
    common.Log('TV Update: Updating Fanart')
    if tvdb_art == '2':
        sqlstring += ' or fanart like "%images-amazon.com%"'
    if tvdb_art == '3':
        sqlstring += ' or poster like "%images-amazon.com%"'
        seasons = True
    for asin, title, oldfanart, oldposter in c.execute(sqlstring).fetchall():
        title = title.lower().replace('[ov]', '').replace('[ultra hd]', '').replace('?', '').replace('omu', '').split('(')[0].strip()
        tvid, poster, fanart = appfeed.getTVDBImages(title, seasons=seasons)
        if not fanart: fanart = appfeed.getTMDBImages(title, content='tv')
        if oldfanart and not fanart: fanart = oldfanart
        if oldposter and not poster: poster = oldposter
        if tvid:
            if not fanart: fanart = common.na
            if not poster: fanart = common.na
        c.execute("update shows set fanart=? where asin = (?)", (fanart, asin))
        if tvdb_art == '3':
            c.execute("update shows set poster=? where asin = (?)", (poster, asin))
            if tvid:
                for season, url in tvid.items():
                    for singleasin in asin.split(','):
                        singleasin = '%' + singleasin + '%'
                        c.execute("update seasons set poster=? where seriesasin like (?) and season = (?)", (url, singleasin, season))
    tvDB.commit()
    common.Log('TV Update: Updating Fanart Finished')
    
def getIMDbID(asins,title):
    url = id = None
    c = tvDB.cursor()
    for asin in asins.split(','):
        asin = '%' + asin + '%'
        url = c.execute('select imdburl from seasons where seriesasin like (?) and imdburl is not null', (asin,)).fetchone()
        if url:
            url = url[0]
            break
    if not url:
        while not id:
            response = common.getURL('http://www.omdbapi.com/?type=series&t=' + urllib.quote_plus(title))
            data = json.loads(response)
            if data['Response'] == 'True':
                id = data['imdbID']
            else:
                oldtitle = title
                if title.count(' - '):
                    title = title.split(' - ')[0]
                elif title.count(': '):
                    title = title.split(': ')[0]
                elif title.count('?'):
                    title = title.replace('?', '')
                if title == oldtitle:
                    id = common.na
    else:
        id = re.compile('/title/(.+?)/', re.DOTALL).findall(url)
    common.Log(id + asins.split(',')[0])
    return id
    
def setNewest(compList=False):
    if not compList:
        compList = common.getCategories()
    catList = compList['tv_shows']
    c = tvDB.cursor()
    c.execute('drop table if exists categories')
    c.execute('''create table categories(
                 title TEXT,
                 asins TEXT);''')
    c.execute('update seasons set recent=null')
    count = 1
    for id in catList:
        if id == 'PrimeTVRecentlyAdded':
            for asin in catList[id]:
                seasonasin = lookupTVdb(asin, rvalue='seasonasin')
                if not seasonasin: seasonasin = asin
                c.execute("update seasons set recent=? where asin like (?)", (count, '%'+seasonasin+'%'))
                count += 1
        else:
            c.execute('insert or ignore into categories values (?,?)', [id, catList[id]])
    tvDB.commit()
        
if not os.path.exists(common.tvDBfile):
    tvDB = sqlite.connect(common.tvDBfile)
    tvDB.text_factory = str
    createTVdb()
else:
    tvDB = sqlite.connect(common.tvDBfile)
    tvDB.text_factory = str
