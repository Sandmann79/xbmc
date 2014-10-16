#!/usr/bin/env python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
from BeautifulSoup import BeautifulStoneSoup
from BeautifulSoup import BeautifulSoup
import os.path
import re
import urllib
import xbmcplugin
import xbmc
import xbmcgui
import resources.lib.common as common
import appfeed
import urlparse
import string
try:
    from sqlite3 import dbapi2 as sqlite
except:
    from pysqlite2 import dbapi2 as sqlite
import xbmcaddon
xmlstring = xbmcaddon.Addon().getLocalizedString

################################ TV db
MAX = int(common.addon.getSetting("tv_perpage"))
MAX_MOV = int(common.addon.getSetting("mov_perpage"))
EPI_TOTAL = common.addon.getSetting("EpisodesTotal")
if EPI_TOTAL == '': EPI_TOTAL = '14000'
EPI_TOTAL = int(EPI_TOTAL)

def createTVdb():
    c = tvDB.cursor()
    c.execute('''CREATE TABLE shows(
                 asin TEXT UNIQUE,
                 asin2 TEXT UNIQUE,
                 feed TEXT,
                 seriestitle TEXT,
                 poster TEXT,
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
                 watched INTEGER,
                 unwatched INTEGER,
                 isHD BOOLEAN,
                 isprime BOOLEAN,
                 favor BOOLEAN,
                 TVDBbanner TEXT,
                 TVDBposter TEXT,
                 TVDBfanart TEXT,
                 TVDB_ID TEXT,
                 PRIMARY KEY(asin,seriestitle)
                 );''')
    c.execute('''CREATE TABLE seasons(
                 asin TEXT UNIQUE,
                 seriesasin TEXT,
                 feed TEXT,
                 poster TEXT,
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
                 watched INTEGER,
                 unwatched INTEGER,
                 isHD BOOLEAN,
                 isprime BOOLEAN,
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
                 url TEXT,
                 plot TEXT,
                 airdate TEXT,
                 year INTEGER,
                 runtime TEXT,
                 isHD BOOLEAN,
                 isprime BOOLEAN,
                 isAdult BOOLEAN,
                 watched BOOLEAN,
                 PRIMARY KEY(asin,seriestitle,season,episode,episodetitle,isHD),
                 FOREIGN KEY(seriestitle,season) REFERENCES seasons(seriestitle,season)
                 );''')
    tvDB.commit()
    c.close()

def loadTVShowdb(HDonly=False,mpaafilter=False,genrefilter=False,creatorfilter=False,networkfilter=False,yearfilter=False,watchedfilter=False,favorfilter=False,alphafilter=False,isprime=True):
    c = tvDB.cursor()
    if HDonly:
        return c.execute('select distinct * from shows where isprime = (?) and isHD = (?)', (isprime,HDonly))
    elif genrefilter:
        genrefilter = '%'+genrefilter+'%'
        return c.execute('select distinct * from shows where isprime = (?) and genres like (?)', (isprime,genrefilter))
    elif mpaafilter:
        return c.execute('select distinct * from shows where isprime = (?) and mpaa = (?)', (isprime,mpaafilter))
    elif creatorfilter:
        return c.execute('select distinct * from shows where isprime = (?) and creator = (?)', (isprime,creatorfilter))
    elif networkfilter:
        return c.execute('select distinct * from shows where isprime = (?) and network = (?)', (isprime,networkfilter))
    elif yearfilter:    
        return c.execute('select distinct * from shows where isprime = (?) and year = (?)', (isprime,int(yearfilter)))
    elif favorfilter:
        return c.execute('select distinct * from shows where isprime = (?) and favor = (?)', (isprime,favorfilter)) 
    elif alphafilter:
        return c.execute('select distinct * from shows where isprime = (?) and seriestitle like (?)', (isprime,alphafilter)) 
    else:
        return c.execute('select distinct * from shows where isprime = (?)', (isprime,))

def loadTVSeasonsdb(seriestitle,HDonly=False,isprime=True):
    c = tvDB.cursor()
    return c.execute('select distinct * from seasons where isprime = (?) and seriesasin = (?)', (isprime,seriestitle))

def loadTVEpisodesdb(seriestitle,HDonly=False,isprime=True):
    c = tvDB.cursor()
    return c.execute('select distinct * from episodes where isprime = (?) and seasonasin = (?) order by episode', (isprime,seriestitle))

def getShowTypes(col):
    c = tvDB.cursor()
    items = c.execute('select distinct %s from shows' % col)
    list = []
    for data in items:
        if data and data[0] <> None:
            data = data[0]
            if type(data) == type(str()):
                if 'genres' in col: data = data.decode('utf-8').encode('utf-8').split('/')
                else: data = data.decode('utf-8').encode('utf-8').split(',')
                for item in data:
                    item = item.strip()
                    if item not in list and item <> ' Inc':
                        if item <> '':
                            list.append(item)
            else:
                list.append(str(data))
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
    tvDB.commit()
    c.close()
    
def fixGenres():
    c = tvDB.cursor()
    seasons = c.execute('select distinct seriestitle,genres from seasons where genres is not null').fetchall()
    for series,genres in seasons:
        c.execute("update seasons set genres=? where seriestitle=? and genres is null", (genres,series))
        c.execute("update shows set genres=? where seriestitle=? and genres is null", (genres,series))
    tvDB.commit()
    c.close()

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
    tvDB.commit()
    c.close()
    
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
    tvDB.commit()
    c.close()
    
def fixStars():
    c = tvDB.cursor()
    series = c.execute('select seriestitle from shows where votes is 0').fetchall()
    for title in series:
        title = title[0]
        stars = c.execute('select avg(stars) from seasons where seriestitle like ? and votes is not 0', (title,)).fetchone()[0]
        print title,stars
        if stars: c.execute('update shows set stars = (?) where seriestitle = (?)', (stars, title))
    tvDB.commit()
    c.close()
    
def cleanTitle(content):
    content = content.replace(' und ','').lower()
    invalid_chars = "?!.:&,;' "
    return ''.join(c for c in content if c not in invalid_chars)

def deleteShowdb(seriestitle=False):
    if not seriestitle:
        seriestitle = common.args.title
    dialog = xbmcgui.Dialog()
    ret = dialog.yesno('Delete Season', 'Delete %s ?' % (seriestitle))
    if ret:
        c = tvDB.cursor()
        c.execute('delete from shows where seriestitle = (?)', (seriestitle,))
        c.execute('delete from seasons where seriestitle = (?)', (seriestitle,))
        tvDB.commit()
        c.close()

def renameShowdb(seriestitle=False,asin=False):
    if not seriestitle:
        seriestitle = common.args.title
    if not asin:
        asin = common.args.asin
    keyb = xbmc.Keyboard(seriestitle, 'Show Rename')
    keyb.doModal()
    if (keyb.isConfirmed()):
            newname = keyb.getText()
            c = tvDB.cursor()
            c.execute("update or replace shows set seriestitle=? where seriestitle=? and asin=?", (newname,seriestitle,asin))
            c.execute("update seasons set seriestitle=? where seriestitle=?", (newname,seriestitle))
            c.execute("update episodes set seriestitle=? where seriestitle=?", (newname,seriestitle))
            tvDB.commit()
            c.close()

def deleteSeasondb(seriestitle=False,season=False,asin=False):
    if not seriestitle and not season:
        seriestitle = common.args.title
        season = int(common.args.season)
    if not asin:
        asin = common.args.asin
    dialog = xbmcgui.Dialog()
    ret = dialog.yesno('Delete Season', 'Delete %s Season %s?' % (seriestitle,season))
    if ret:
        c = tvDB.cursor()
        c.execute('delete from seasons where seriestitle = (?) and season = (?) and asin=(?)', (seriestitle,season,asin))
        c.execute('delete from episodes where seriestitle = (?) and season = (?)', (seriestitle,season))
        tvDB.commit()
        c.close()

def renameSeasondb(seriestitle=False,season=False,asin=False):
    if not seriestitle and not season:
        seriestitle = common.args.title
        season = int(common.args.season)
    if not asin:
        asin = common.args.asin
    keyb = xbmc.Keyboard(seriestitle, 'Season Rename')
    keyb.doModal()
    if (keyb.isConfirmed()):
            newname = keyb.getText()
            c = tvDB.cursor()
            c.execute("update or ignore seasons set seriestitle=? where seriestitle=? and season = ? and asin=?", (newname,seriestitle,season,asin))
            c.execute("update or ignore episodes set seriestitle=? where seriestitle=? and season = ?", (newname,seriestitle,season))
            tvDB.commit()
            c.close()

def favorShowdb(seriestitle=False):
    if not seriestitle:
        seriestitle = common.args.title
    c = tvDB.cursor()
    c.execute("update shows set favor=? where seriestitle=?", (True,seriestitle))
    tvDB.commit()
    c.close()
    
def unfavorShowdb(seriestitle=False):
    if not seriestitle:
        seriestitle = common.args.title
    c = tvDB.cursor()
    c.execute("update shows set favor=? where seriestitle=?", (False,seriestitle))
    tvDB.commit()
    c.close()
    
def watchEpisodedb(asin=False):
    if not asin:
        asin = common.args.url
    c = tvDB.cursor()
    c.execute("update episodes set watched=? where asin=?", (True,asin))
    tvDB.commit()
    c.close()
    
def unwatchEpisodedb(asin=False):
    if not asin:
        asin = common.args.url
    c = tvDB.cursor()
    c.execute("update episodes set watched=? where asin=?", (False,asin))
    tvDB.commit()
    c.close()

def addEpisodedb(episodedata):
    #print 'AMAZON: addEpisodedb'
    #print episodedata
    c = tvDB.cursor()
    c.execute('insert or ignore into episodes values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', episodedata)
    tvDB.commit()
    c.close()
    
def addSeasondb(seasondata):
    #print 'AMAZON: addSeasondb'
    #print seasondata
    c = tvDB.cursor()
    c.execute('insert or ignore into seasons values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', seasondata)
    tvDB.commit()
    c.close()

def addShowdb(showdata):
    #print 'AMAZON: addShowdb'
    #print showdata
    c = tvDB.cursor()
    c.execute('insert or ignore into shows values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', showdata)
    tvDB.commit()
    c.close()

def lookupShowsdb(asin,isPrime=True):
    c = tvDB.cursor()
    if c.execute('select distinct * from shows where asin = (?)', (asin,)).fetchone():
        return c.execute('select distinct * from shows where asin = (?)', (asin,))
    elif c.execute('select distinct * from shows where asin2 = (?)', (asin,)).fetchone():
        return c.execute('select distinct * from shows where asin2 = (?)', (asin,))
    else:
        asin1,asin2 = ASIN_ADD(0,asins=asin,isPrime=isPrime,single=True)
        if asin1 == asin2:
            return c.execute('select distinct * from shows where asin = (?)', (asin1,))
        elif asin1 <> asin2:
            c.execute("update shows set asin2=? where asin=?", (asin2,asin1))
            tvDB.commit()
            return c.execute('select distinct * from shows where asin = (?)', (asin1,))

def lookupSeasondb(asin,isPrime=True,addSeries=False):
    c = tvDB.cursor()
    if c.execute('select distinct * from seasons where asin = (?)', (asin,)).fetchone():
        return c.execute('select distinct * from seasons where asin = (?)', (asin,))
    else:
        ASIN_ADD(0,asins=asin,isPrime=isPrime,addSeries=addSeries)
        return c.execute('select distinct * from seasons where asin = (?)', (asin,))

def lookupEpisodedb(asin,isPrime=True):
    c = tvDB.cursor()
    if c.execute('select distinct * from episodes where asin = (?)', (asin,)).fetchone():
        return c.execute('select distinct * from episodes where asin = (?)', (asin,))
    else:
        ASIN_ADD(0,asins=asin,isPrime=isPrime)
        return c.execute('select distinct * from episodes where asin = (?)', (asin,))
        
def rebuildTVdb():
    c = tvDB.cursor()
    c.execute('drop table if exists shows')
    c.execute('drop table if exists seasons')
    c.execute('drop table if exists episodes')
    c.close()
    createTVdb()

def getTVdbAsins(table,col):
    c = tvDB.cursor()
    content = ''
    for item in c.execute('select asin from %s where %s = (1)' % (table, col)).fetchall():
        content += ','.join(item)
    return content
    
def addTVdb():
    global EpWatched, SesWatched, ShowWatched, ShowFav
    dialog = xbmcgui.DialogProgress()
    dialog.create(xmlstring(30130))
    dialog.update(0,xmlstring(30131))
    EpWatched = getTVdbAsins('episodes', 'watched')
    SesWatched = getTVdbAsins('seasons', 'watched')
    ShowWatched = getTVdbAsins('shows', 'watched')
    ShowFav = getTVdbAsins('shows', 'favor')
    rebuildTVdb()
    page = 1
    endIndex = 0
    goAhead = 1
    SERIES_COUNT = 0
    SEASON_COUNT = 0
    EPISODE_COUNT = 0
    ALL_SERIES_ASINS = ''
    while goAhead == 1:
        json = appfeed.getList('TVSeason', endIndex, NumberOfResults=MAX)
        titles = json['message']['body']['titles']
        if titles:
            SERIES_ASINS = ''
            EPISODE_ASINS = []
            EPISODE_NUM = []
            for title in titles:
                if (dialog.iscanceled()):
                    goAhead = -1
                    break
                if title['ancestorTitles']:
                    SERIES_KEY = title['ancestorTitles'][0]['titleId']
                else:
                    SERIES_KEY = title['titleId']
                if SERIES_KEY not in ALL_SERIES_ASINS:
                    SERIES_COUNT += 1
                    SERIES_ASINS += SERIES_KEY+','
                    ALL_SERIES_ASINS += SERIES_KEY+','
                season_size = int(title['childTitles'][0]['size'])
                if season_size < 1:
                    season_size = MAX_MOV
                parsed = urlparse.urlparse(title['childTitles'][0]['feedUrl'])
                EPISODE_ASINS.append(urlparse.parse_qs(parsed.query)['SeasonASIN'])
                EPISODE_NUM.append(season_size)
            result = ASIN_ADD(titles)
            SEASON_COUNT += result
            del titles
            if SERIES_ASINS <> '':
                ASIN_ADD(0, asins=SERIES_ASINS)
            dialog.update(int(EPISODE_COUNT*100.0/EPI_TOTAL), xmlstring(30132).replace("%s",str(SERIES_COUNT)), xmlstring(30133).replace("%s",str(SEASON_COUNT)),xmlstring(30134).replace("%s",str(EPISODE_COUNT)) )
            goAheadepi = 1
            episodes = 0
            AsinList = ''
            EPISODE_NUM.append(MAX_MOV+1)
            for index, item in enumerate(EPISODE_ASINS):
                episodes += EPISODE_NUM[index]
                AsinList += ','.join(item) + ','
                if (episodes + EPISODE_NUM[index+1]) > MAX_MOV:
                    json = appfeed.getList('TVEpisode', 0, NumberOfResults=MAX_MOV, AsinList=AsinList)
                    titles = json['message']['body']['titles']
                    if titles:
                        EPISODE_COUNT += ASIN_ADD(titles)
                    else:
                        goAheadepi = -1
                    if (dialog.iscanceled()):
                        goAheadepi = -1
                        goAhead = -1
                        break
                    episodes = 0
                    AsinList = ''
                    dialog.update(int(EPISODE_COUNT*100.0/EPI_TOTAL), xmlstring(30132).replace("%s",str(SERIES_COUNT)), xmlstring(30133).replace("%s",str(SEASON_COUNT)),xmlstring(30134).replace("%s",str(EPISODE_COUNT)) )
                    del titles
            endIndex+=result
        else:
            goAhead = 0
        page+=1
    print 'TOTALS'
    print SERIES_COUNT
    print SEASON_COUNT
    print EPISODE_COUNT
    if goAhead == 0: common.addon.setSetting("EpisodesTotal",str(EPISODE_COUNT))
    fixDBLShows()
    fixYears()
    fixStars()

def ASIN_FEED(url):
    titles = appfeed.URL_LOOKUP(url)['message']['body']['titles']
    EPISODE_ASINS=''
    for title in titles:
        EPISODE_ASINS += title['titleId']+','
    if EPISODE_ASINS <> '':
        ASIN_ADD(0,asins=EPISODE_ASINS)

def ASIN_ADD(titles,asins=False,url=False,isPrime=True,isHD=False,single=False,addSeries=False):
    if asins:
        titles = appfeed.ASIN_LOOKUP(asins)['message']['body']['titles']
    count = 0
    for title in titles:
        if asins:
            contentType = 'SERIES'
        else:
            contentType = title['contentType']
        count+=1
        isHD=False
        isPrime=True
        isWatched=False
        isFav=False
        if contentType == 'SERIES':
            asin, isHD, isPrime = GET_ASINS(title)
            seriestitle = title['title']
            if title['formats'][0].has_key('images'):
                try:
                    thumbnailUrl = title['formats'][0]['images'][0]['uri']
                    thumbnailFilename = thumbnailUrl.split('/')[-1]
                    thumbnailBase = thumbnailUrl.replace(thumbnailFilename,'')
                    poster = thumbnailBase+thumbnailFilename.split('.')[0]+'.jpg'
                except: poster = None
            else:
                poster = None
            if title.has_key('synopsis'):
                plot = title['synopsis']
            else:
                plot = None
            if title.has_key('childTitles'):
                seasontotal = title['childTitles'][0]['size']
                seasonFeed = title['childTitles'][0]['feedUrl']
            else:
                seasontotal = 0
                seasonFeed = None
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
                mpaa = None
            if title.has_key('starringCast'):
                actors = title['starringCast']
            else:
                actors = None
            if title.has_key('genres'):
                genres = ' / '.join(title['genres']).replace('_', ' & ').replace('Musikfilm & Tanz', 'Musikfilm, Tanz')
            else:
                genres = None
            if title.has_key('amazonRating'):
                stars = float(title['amazonRating']['rating'])*2
                votes = str(title['amazonRating']['count'])
            else:
                stars = None
                votes = None
            if asin.split(',')[0] in ShowWatched: isWatched = True
            if asin.split(',')[0] in ShowFav: isFav = True
            addShowdb([asin,None,seasonFeed,seriestitle,poster,plot,studio,mpaa,genres,actors,premiered,year,stars,votes,seasontotal,0,isWatched,0,isHD,isPrime,isFav,None,None,None,None])
            if single:
                return asin,ASINLIST
        elif contentType == 'SEASON':
            asin, isHD, isPrime = GET_ASINS(title)
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
            if addSeries:
                ASIN_ADD(0,asins=seriesasin)
            if title['formats'][0].has_key('images'):
                try:
                    thumbnailUrl = title['formats'][0]['images'][0]['uri']
                    thumbnailFilename = thumbnailUrl.split('/')[-1]
                    thumbnailBase = thumbnailUrl.replace(thumbnailFilename,'')
                    poster = thumbnailBase+thumbnailFilename.split('.')[0]+'.jpg'
                except: poster = None
            else:
                poster = None
            if title.has_key('synopsis'):
                plot = title['synopsis']
            else:
                plot = None
            if title.has_key('childTitles'):
                episodetotal = title['childTitles'][0]['size']
                episodeFeed = title['childTitles'][0]['feedUrl']
            else:
                episodetotal = 0
                episodeFeed = None
            if title.has_key('releaseOrFirstAiringDate'):
                premiered = title['releaseOrFirstAiringDate']['valueFormatted'].split('T')[0]
                year = int(premiered.split('-')[0])
            else:
                premiered = None
                year = None
            if title.has_key('starringCast'):
                actors = title['starringCast']
            else:
                actors = None
            if title.has_key('studioOrNetwork'):
                studio = title['studioOrNetwork']
            else:
                studio = None
            if title.has_key('regulatoryRating'):
                if title['regulatoryRating'] == 'not_checked': mpaa = xmlstring(30171)
                else: mpaa = xmlstring(30170) + title['regulatoryRating']
            else:
                mpaa = None
            if title.has_key('genres'):
                genres = ' / '.join(title['genres']).replace('_', ' & ').replace('Musikfilm & Tanz', 'Musikfilm, Tanz')
            else:
                genres = None
            if title.has_key('amazonRating'):
                stars = float(title['amazonRating']['rating'])*2
                votes = str(title['amazonRating']['count'])
            else:
                stars = None
                votes = None
            if asin.split(',')[0] in SesWatched: isWatched = True
            addSeasondb([asin,seriesasin,episodeFeed,poster,season,seriestitle,plot,actors,studio,mpaa,genres,premiered,year,stars,votes,episodetotal,isWatched,episodetotal,isHD,isPrime])
        elif contentType == 'EPISODE':
            seriesasin = ''
            asin, isHD, isPrime = GET_ASINS(title)
            isAdult = False
            stars = None
            votes = None
            asin = asin.split(',')[0]
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
                if seriesasin == '':
                    seriesasin = seasonasin
                    seriestitle = seasontitle                        
            if title.has_key('number'):
                episode = title['number']
            else:
                episode = 0
            url = common.BASE_URL+'/dp/'+asin+'/ref=vod_0_wnzw'
            if title['formats'][0].has_key('images'):
                try:
                    thumbnailUrl = title['formats'][0]['images'][0]['uri']
                    thumbnailFilename = thumbnailUrl.split('/')[-1]
                    thumbnailBase = thumbnailUrl.replace(thumbnailFilename,'')
                    poster = thumbnailBase+thumbnailFilename.split('.')[0]+'.jpg'
                except: poster = None
            else:
                poster = None
            if title.has_key('synopsis'):
                plot = title['synopsis']
            else:
                plot = None
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
                mpaa = None
            if title.has_key('starringCast'):
                actors = title['starringCast']
            else:
                actors = None
            if title.has_key('genres'):
                genres = ' / '.join(title['genres']).replace('_', ' & ').replace('Musikfilm & Tanz', 'Musikfilm, Tanz')
            else:
                genres = None
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
            if asin in EpWatched: isWatched = True
            addEpisodedb([asin,seasonasin,seriesasin,seriestitle,season,episode,poster,mpaa,actors,genres,episodetitle,studio,stars,votes,url,plot,premiered,year,runtime,isHD,isPrime,isAdult,isWatched])
    return count
    
def GET_ASINS(content):
    asins = ''
    hd_key = False
    prime_key = True
    if content.has_key('titleId'): asins += content['titleId']
    for format in content['formats']:
        if format['videoFormatType'] == 'HD': hd_key = True
        for offer in format['offers']:
            if offer['offerType'] == 'SUBSCRIPTION': 
                prime_key = True
            elif offer.has_key('asin'):
                if offer['asin'] not in asins:
                    asins += ',' + offer['asin']
    del content
    return asins, hd_key, prime_key

tvDBfile = os.path.join(xbmc.translatePath('special://home/addons/script.module.amazon.database/lib/'),'tv.db')
if not os.path.exists(tvDBfile):
    tvDB = sqlite.connect(tvDBfile)
    tvDB.text_factory = str
    createTVdb()
else:
    tvDB = sqlite.connect(tvDBfile)
    tvDB.text_factory = str
    
def scanTVDBshows():
    c = tvDB.cursor()
    shows = c.execute('select distinct seriestitle,year from shows order by seriestitle').fetchall()
    dialog = xbmcgui.DialogProgress()
    dialog.create('Refreshing Prime TV Database')
    dialog.update(0,'Scanning TVDB Data')
    for seriestitle,year in shows:
        TVDBbanner,TVDBposter,TVDBfanart,year2,seriesid = tv_db_series_lookup(seriestitle)
        if not year:
            try:
                year = int(year2.split('-')[0])
            except:
                year = None
        c.execute("update shows set TVDBbanner=?,TVDBposter=?,TVDBfanart=?,TVDB_ID=?,year=? where seriestitle=?", (TVDBbanner,TVDBposter,TVDBfanart,seriesid,year,seriestitle))
        tvDB.commit()
        if (dialog.iscanceled()):
            return False
    c.close()
 
 
def tv_db_series_lookup(seriesname,manualsearch=False):
    tv_api_key = '03B8C17597ECBD64'
    mirror = 'http://thetvdb.com'
    banners = 'http://thetvdb.com/banners/'
    try:
        print 'intial search'
        series_lookup = 'http://www.thetvdb.com/api/GetSeries.php?seriesname='+urllib.quote_plus(seriesname)
        seriesid = common.getURL(series_lookup)
        seriesid = get_series_id(seriesid,seriesname)
    except:
        try:
            print 'strip search'
            series_lookup = 'http://www.thetvdb.com/api/GetSeries.php?seriesname='+urllib.quote_plus(seriesname.split('(')[0].split(':')[0].strip())
            seriesid = common.getURL(series_lookup)
            seriesid = get_series_id(seriesid,seriesname)
        except:
            if manualsearch:
                print 'manual search'
                keyb = xbmc.Keyboard(seriesname, 'Manual Search')
                keyb.doModal()
                if (keyb.isConfirmed()):
                    try:
                        series_lookup = 'http://www.thetvdb.com/api/GetSeries.php?seriesname='+urllib.quote_plus(keyb.getText())
                        seriesid = common.getURL(series_lookup)
                        seriesid = get_series_id(seriesid,seriesname)
                    except:
                        print 'manual search failed'
                        return None,None,None,None,None
            else:
                return None,None,None,None,None
    if seriesid:
        return tv_db_id_lookup(seriesid,seriesname)
    else:
        return None,None,None,None,None
  
def tv_db_id_lookup(seriesid,seriesname):
    tv_api_key = '03B8C17597ECBD64'
    mirror = 'http://thetvdb.com'
    banners = 'http://thetvdb.com/banners/'
    if seriesid:
        series_xml = mirror+('/api/%s/series/%s/de.xml' % (tv_api_key, seriesid))
        series_xml = common.getURL(series_xml)
        tree = BeautifulStoneSoup(series_xml, convertEntities=BeautifulStoneSoup.HTML_ENTITIES)
        try: aired = tree.find('firstaired').string
        except:
            print '%s - Air Date Failed' % seriesname
            aired = None
        try: banner = banners + tree.find('banner').string
        except:
            print '%s - Banner Failed' % seriesname
            banner = None
        try: fanart = banners + tree.find('fanart').string
        except:
            print '%s - Fanart Failed' % seriesname
            fanart = None
        try: poster = banners + tree.find('poster').string
        except:
            print '%s - Poster Failed' % seriesname
            poster = None
        return banner, poster, fanart, aired, seriesid
    else:
        return None,None,None,None,None
 
def get_series_id(seriesid,seriesname):
    shows = BeautifulStoneSoup(seriesid, convertEntities=BeautifulStoneSoup.HTML_ENTITIES).findAll('series')
    names = list(BeautifulStoneSoup(seriesid, convertEntities=BeautifulStoneSoup.HTML_ENTITIES).findAll('seriesname'))
    if len(names) > 1:
        select = xbmcgui.Dialog()
        ret = select.select(seriesname, [name.string for name in names])
        if ret <> -1:
            seriesid = shows[ret].find('seriesid').string
        else:
            seriesid = False
    else:
        seriesid = shows[0].find('seriesid').string
    return seriesid