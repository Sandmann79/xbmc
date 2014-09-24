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
try:
    from sqlite3 import dbapi2 as sqlite
except:
    from pysqlite2 import dbapi2 as sqlite

################################ TV db

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
    #             asin,seriestitle,season,episode,poster,mpaa,actors,genres,episodetitle,studio,stars,votes,url,plot,airdate,runtime,isHD,isprime,watched
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
                 watched BOOLEAN,
                 PRIMARY KEY(asin,seriestitle,season,episode,episodetitle,isHD),
                 FOREIGN KEY(seriestitle,season) REFERENCES seasons(seriestitle,season)
                 );''')
    tvDB.commit()
    c.close()

def loadTVShowdb(HDonly=False,mpaafilter=False,genrefilter=False,creatorfilter=False,networkfilter=False,yearfilter=False,watchedfilter=False,favorfilter=False,isprime=True):
    c = tvDB.cursor()
    if HDonly:
        return c.execute('select distinct * from shows where isprime = (?) and isHD = (?)', (isprime,HDonly))
    elif genrefilter:
        genrefilter = '%'+genrefilter+'%'
        return c.execute('select distinct * from shows where isprime = (?) and genres like (?)', (isprime,genrefilter))
    elif mpaafilter:
        #mpaafilter = '%'+mpaafilter+'%'
        #return c.execute('select distinct * from shows where isprime = (?) and mpaa like (?)', (isprime,mpaafilter))
        return c.execute('select distinct * from shows where isprime = (?) and mpaa = (?)', (isprime,mpaafilter))
    elif creatorfilter:
        return c.execute('select distinct * from shows where isprime = (?) and creator = (?)', (isprime,creatorfilter))
    elif networkfilter:
        return c.execute('select distinct * from shows where isprime = (?) and network = (?)', (isprime,networkfilter))
    elif yearfilter:    
        return c.execute('select distinct * from shows where isprime = (?) and year = (?)', (isprime,int(yearfilter)))
    elif favorfilter:
        return c.execute('select distinct * from shows where isprime = (?) and favor = (?)', (isprime,favorfilter)) 
    else:
        return c.execute('select distinct * from shows where isprime = (?)', (isprime,))

def loadTVSeasonsdb(seriestitle,HDonly=False,isprime=True):
    c = tvDB.cursor()
    if HDonly:
        return c.execute('select distinct * from seasons where isprime = (?) and (seriestitle = (?) and isHD = (?))', (isprime,seriestitle,HDonly))
    else:
        return c.execute('select distinct * from seasons where isprime = (?) and seriestitle = (?)', (isprime,seriestitle))

def loadTVEpisodesdb(seriestitle,season,HDonly=False,isprime=True):
    c = tvDB.cursor()
    if HDonly:
        return c.execute('select distinct * from episodes where isprime = (?) and (seriestitle = (?) and season = (?) and isHD = (?)) order by episode', (isprime,seriestitle,season,HDonly))
    else:
        return c.execute('select distinct * from episodes where isprime = (?) and (seriestitle = (?) and season = (?) and isHD = (?)) order by episode', (isprime,seriestitle,season,HDonly))

def getShowTypes(col):
    c = tvDB.cursor()
    items = c.execute('select distinct %s from shows' % col)
    list = []
    for data in items:
        if data and data[0] <> None:
            data = data[0]
            if type(data) == type(str()):
                data = data.decode('utf-8').encode('utf-8').split(',')
                for item in data:
                    item = item.replace('& ','').strip()
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
    seasons = c.execute('select seriestitle,year from seasons where year is not null order by year desc').fetchall()
    for series,year in seasons:
        c.execute("update shows set year=? where seriestitle=?", (year,series))
    tvDB.commit()
    c.close()
    
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
    print 'AMAZON: addEpisodedb'
    print episodedata
    c = tvDB.cursor()
    c.execute('insert or ignore into episodes values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', episodedata)
    tvDB.commit()
    c.close()
    
def addSeasondb(seasondata):
    print 'AMAZON: addSeasondb'
    print seasondata
    c = tvDB.cursor()
    c.execute('insert or ignore into seasons values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', seasondata)
    tvDB.commit()
    c.close()

def addShowdb(showdata):
    print 'AMAZON: addShowdb'
    print showdata
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
        asin1,asin2 = ASIN_ADD(asin,isPrime=isPrime,single=True)
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
        ASIN_ADD(asin,isPrime=isPrime,addSeries=addSeries)
        return c.execute('select distinct * from seasons where asin = (?)', (asin,))

def lookupEpisodedb(asin,isPrime=True):
    c = tvDB.cursor()
    if c.execute('select distinct * from episodes where asin = (?)', (asin,)).fetchone():
        return c.execute('select distinct * from episodes where asin = (?)', (asin,))
    else:
        ASIN_ADD(asin,isPrime=isPrime)
        return c.execute('select distinct * from episodes where asin = (?)', (asin,))

def addTVdb():
    dialog = xbmcgui.DialogProgress()
    dialog.create('Building Prime Television Database')
    dialog.update(0,'Initializing Television Scan')
    page = 1
    endIndex = 0
    goAhead = True    
    SERIES_COUNT = 0
    SEASON_COUNT = 0
    EPISODE_COUNT = 0
    ALL_SERIES_ASINS = ''
    while goAhead:
        #json = appfeed.getList('TVSeries',0)
        json = appfeed.getList('TVSeason',endIndex)
        titles = json['message']['body']['titles']
        SERIES_ASINS = ''
        SEASONS_ASINS = ''
        EPISODE_FEEDS = []
        for title in titles:
            SEASON_COUNT += 1
            asin=title['titleId']
            hdasin=False
            SEASONS_ASINS += title['titleId']+','
            for format in title['formats']:
                if format['videoFormatType'] == 'HD':
                    for offer in format['offers']:
                        if offer['offerType'] == 'SEASON_PURCHASE':
                            hdasin=offer['asin']
                            SEASONS_ASINS.replace(asin,hdasin)            
            if title['ancestorTitles'][0]['titleId'] not in ALL_SERIES_ASINS:
                SERIES_COUNT += 1
                SERIES_ASINS += title['ancestorTitles'][0]['titleId']+','
                ALL_SERIES_ASINS += title['ancestorTitles'][0]['titleId']+','
            EPISODE_FEEDS.append(title['childTitles'][0]['feedUrl']+'&NumberOfResults=400')
            if hdasin:
                EPISODE_FEEDS.append(title['childTitles'][0]['feedUrl'].replace(asin,hdasin)+'&NumberOfResults=400')
        del titles
        ASIN_ADD(SERIES_ASINS)
        dialog.update(int(page*100.0/9),'%s Shows' % str(SERIES_COUNT),'%s Seasons' % str(SEASON_COUNT),'%s Episodes' % str(EPISODE_COUNT) )
        ASIN_ADD(SEASONS_ASINS)
        dialog.update(int(page*100.0/9),'%s Shows' % str(SERIES_COUNT),'%s Seasons' % str(SEASON_COUNT),'%s Episodes' % str(EPISODE_COUNT) )
        for url in EPISODE_FEEDS:
            titles = appfeed.URL_LOOKUP(url)['message']['body']['titles']
            EPISODE_ASINS=''
            for title in titles:
                EPISODE_COUNT += 1
                EPISODE_ASINS += title['titleId']+','
                for format in title['formats']:
                    if format['videoFormatType'] == 'HD':
                        for offer in format['offers']:
                            if offer['offerType'] == 'PURCHASE':
                                EPISODE_ASINS += offer['asin']+','
            if EPISODE_ASINS <> '':
                ASIN_ADD(EPISODE_ASINS)
            dialog.update(int(page*100.0/9),'%s Shows' % str(SERIES_COUNT),'%s Seasons' % str(SEASON_COUNT),'%s Episodes' % str(EPISODE_COUNT) )
        #endIndex = json['message']['body']['endIndex']
        endIndex+=250
        if (dialog.iscanceled()):
            goAhead = False
        elif endIndex > 2500:
            goAhead = False
        dialog.update(int(page*100.0/9),'Scanning Page %s' % str(page),'Scanned %s Seasons' % str(endIndex) )
        page+=1
    print 'TOTALS'
    print SERIES_COUNT
    print SEASON_COUNT
    print EPISODE_COUNT
    fixHDshows()

def ASIN_FEED(url):
    titles = appfeed.URL_LOOKUP(url)['message']['body']['titles']
    EPISODE_ASINS=''
    for title in titles:
        EPISODE_ASINS += title['titleId']+','
    if EPISODE_ASINS <> '':
        ASIN_ADD(EPISODE_ASINS)

def ASIN_ADD(ASINLIST,url=False,isPrime=True,isHD=False,single=False,addSeries=False):
    if url:
        titles = appfeed.URL_LOOKUP(url)['message']['body']['titles']
    else:
        titles = appfeed.ASIN_LOOKUP(ASINLIST)['message']['body']['titles']
    for title in titles:
        isHD=False
        isPrime=True
        if title['contentType'] == 'SERIES':
            asin = title['titleId']
            seriestitle = title['title']
            for format in title['formats']:
                if format['videoFormatType'] == 'HD':
                    isHD = True
                for offer in format['offers']:
                    if offer['offerType'] == 'SUBSCRIPTION':
                        isPrime = True
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
                mpaa = title['regulatoryRating']
            else:
                mpaa = None
            if title.has_key('starringCast'):
                actors = title['starringCast']
            else:
                actors = None
            if title.has_key('genres'):
                genres = ','.join(title['genres'])
            else:
                genres = None
            if title.has_key('amazonRating'):
                stars = float(title['amazonRating']['rating'])*2
                votes = str(title['amazonRating']['count'])
            else:
                stars = None
                votes = None
            #          asin,feed      ,seriestitle,poster,plot,studio,mpaa,genres,actors,premiered,year,stars,votes,seasontotal,episodetotal,watched,unwatched,isHD,isprime,favor,TVDBbanner,TVDBposter,TVDBfanart
            addShowdb([asin,None,seasonFeed,seriestitle,poster,plot,studio,mpaa,genres,actors,premiered,year,stars,votes,seasontotal,0,0,0,isHD,isPrime,False,None,None,None,None])
            if single:
                return asin,ASINLIST
        elif title['contentType'] == 'SEASON':
            asin = title['titleId']
            season = title['number']
            if title.has_key('ancestorTitles'):
                if len(title['ancestorTitles']) > 0:
                    try:
                        seriestitle = title['ancestorTitles'][0]['title']
                        seriesasin = title['ancestorTitles'][0]['titleId']
                    except:
                        pass
            if addSeries:
                ASIN_ADD(seriesasin)
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
                mpaa = title['regulatoryRating']
            else:
                mpaa = None
            if title.has_key('genres'):
                genres = ','.join(title['genres'])
            else:
                genres = None
            if title.has_key('amazonRating'):
                stars = float(title['amazonRating']['rating'])*2
                votes = str(title['amazonRating']['count'])
            else:
                stars = None
                votes = None
            for format in title['formats']:
                if format['videoFormatType'] == 'HD':
                    for offer in format['offers']:
                        if offer['offerType'] == 'SUBSCRIPTION':
                            isPrime = True
                    isHD = True
                    for offer in format['offers']:
                        if offer['offerType'] == 'SEASON_PURCHASE' or offer['offerType'] == 'TV_PASS':
                            hd_asin = offer['asin']
                            addSeasondb([hd_asin,seriesasin,episodeFeed,poster,season,seriestitle,plot,actors,studio,mpaa,genres,premiered,year,stars,votes,episodetotal,0,episodetotal,isHD,isPrime])
                            #if hd_asin not in episodeFeed:
                            #    ASIN_FEED(episodeFeed.replace(asin,hd_asin))
                if format['videoFormatType'] == 'SD':
                    for offer in format['offers']:
                        if offer['offerType'] == 'SUBSCRIPTION':
                            isPrime = True
                    isHD = False
                    for offer in format['offers']:
                        if offer['offerType'] == 'SEASON_PURCHASE' or offer['offerType'] == 'TV_PASS':
                            sd_asin = offer['asin']
                            addSeasondb([sd_asin,seriesasin,episodeFeed,poster,season,seriestitle,plot,actors,studio,mpaa,genres,premiered,year,stars,votes,episodetotal,0,episodetotal,isHD,isPrime])
            #            asin,episodeFeed,poster,season,seriestitle,plot,actors,studio,mpaa,genres,premiered,year,stars,votes,episodetotal,watched,unwatched,isHD,isprime
        elif title['contentType'] == 'EPISODE':
            asin = title['titleId']
            episodetitle = title['title']
            if title.has_key('ancestorTitles'):
                if len(title['ancestorTitles']) > 0:
                    seriestitle = title['ancestorTitles'][0]['title']
                    seriesasin = title['ancestorTitles'][0]['titleId']
                    seasonasin = title['ancestorTitles'][1]['titleId']
                    season = title['ancestorTitles'][1]['number']
            if title.has_key('number'):
                episode = title['number']
            else:
                episode = 0
            url = common.BASE_URL+'/gp/product/'+asin
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
                runtime = str(title['runtime']['valueMillis']/1000)
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
                mpaa = title['regulatoryRating']
            else:
                mpaa = None
            if title.has_key('starringCast'):
                actors = title['starringCast']
            else:
                actors = None
            if title.has_key('genres'):
                genres = ','.join(title['genres'])
            else:
                genres = None
            if title.has_key('customerReviewCollection'):
                stars = float(title['customerReviewCollection']['customerReviewSummary']['averageOverallRating'])*2
                votes = str(title['customerReviewCollection']['customerReviewSummary']['totalReviewCount'])
            else:
                stars = None
                votes = None
            for format in title['formats']:
                if format['videoFormatType'] == 'HD':
                    for offer in format['offers']:
                        if offer['offerType'] == 'PURCHASE':
                            isHD = True
                            hd_asin = offer['asin']
                            hd_url = common.BASE_URL+'/gp/product/'+hd_asin
                for offer in format['offers']:
                    if offer['offerType'] == 'SUBSCRIPTION':
                        isPrime = True
            #             asin,seriestitle,season,episode,poster,mpaa,actors,genres,episodetitle,studio,stars,votes,url,plot,airdate,year,runtime,isHD,isprime,watched
            if isHD:
                addEpisodedb([hd_asin,seasonasin,seriesasin,seriestitle,season,episode,poster,mpaa,actors,genres,episodetitle,studio,stars,votes,hd_url,plot,premiered,year,runtime,isHD,isPrime,False])
                addEpisodedb([asin,seasonasin,seriesasin,seriestitle,season,episode,poster,mpaa,actors,genres,episodetitle,studio,stars,votes,url,plot,premiered,year,runtime,False,isPrime,False])
            else:
                addEpisodedb([asin,seasonasin,seriesasin,seriestitle,season,episode,poster,mpaa,actors,genres,episodetitle,studio,stars,votes,url,plot,premiered,year,runtime,isHD,isPrime,False])

tvDBfile = os.path.join(xbmc.translatePath('special://home/addons/script.module.amazon.database/lib/'),'tv.db')
if not os.path.exists(tvDBfile):
    tvDB = sqlite.connect(tvDBfile)
    tvDB.text_factory = str
    createTVdb()
else:
    tvDB = sqlite.connect(tvDBfile)
    tvDB.text_factory = str

#tvDBdownload = os.path.join(xbmc.translatePath(common.pluginpath),'resources','cache','newtv.db')
#tvDBold = os.path.join(xbmc.translatePath('special://profile/addon_data/plugin.video.amazon/'),'tv.db')
#tvDBfile = os.path.join(xbmc.translatePath('special://profile/addon_data/plugin.video.amazon/'),'tv0.db')
#tvDBfile0 = os.path.join(xbmc.translatePath('special://profile/addon_data/plugin.video.amazon/'),'tv1.db')
#if not os.path.exists(tvDBfile) and os.path.exists(tvDBdownload):
#    import shutil
#    shutil.move(tvDBdownload, tvDBfile)
#    if os.path.exists(tvDBfile0):
#        os.remove(tvDBfile0)
#    if os.path.exists(tvDBold):
#        os.remove(tvDBold)
#if not os.path.exists(tvDBfile):
#    tvDB = sqlite.connect(tvDBfile)
#    tvDB.text_factory = str
#    createTVdb()
#else:
#    tvDB = sqlite.connect(tvDBfile)
#    tvDB.text_factory = str

#===============================================================================
# TV_URL = 'http://www.amazon.com/gp/search/ref=sr_st?qid=1314982661&rh=n%3A2625373011%2Cn%3A!2644981011%2Cn%3A!2644982011%2Cn%3A2858778011%2Cn%3A2864549011%2Cp_85%3A2470955011&sort=-releasedate'
# def addTVdb(url=TV_URL,isprime=True):
#    dialog = xbmcgui.DialogProgress()
#    dialog.create('Building Prime TV Database')
#    dialog.update(0,'Initializing TV Scan')
#    url = 'http://www.amazon.com/s/ref=sr_pg_89?rh=n%3A2625373011%2Cn%3A%212644981011%2Cn%3A%212644982011%2Cn%3A2858778011%2Cn%3A2864549011%2Cp_85%3A2470955011&page=92&sort=-releasedate&ie=UTF8&qid=1332473294'
#    data = common.getURL(url)
#    try:
#        tree = BeautifulSoup(data, convertEntities=BeautifulSoup.HTML_ENTITIES)
#        total = int(tree.find('div',attrs={'id':'resultCount','class':'resultCount'}).span.string.replace(',','').split('of')[1].split('Results')[0].strip())
#    except:
#        total=12
#    del tree; del data
#    pages = (total/12)+1
#    increment = 100.0 / pages 
#    page = 1
#    percent = int(increment*page)
#    dialog.update(percent,'Scanning Page %s of %s' % (str(page),str(pages)),'Added %s Episodes' % str(0))
#    pagenext,episodetotal = scrapeTVdb(url,isprime)
#    while pagenext:
#        page += 1
#        percent = int(increment*page)
#        dialog.update(percent,'Scanning Page %s of %s' % (str(page),str(pages)),'Added %s Episodes' % str(episodetotal))
#        pagenext,nextotal = scrapeTVdb(pagenext,isprime)
#        episodetotal += nextotal
#        if (dialog.iscanceled()):
#            return False
#        xbmc.sleep(2000)
#    fixHDshows()
#    fixGenres()
#    fixYears()
#    
# def getTVTree(url): 
#    data = common.getURL(url)
#    scripts = re.compile(r'<script.*?script>',re.DOTALL)
#    data = scripts.sub('', data)
#    style = re.compile(r'<style.*?style>',re.DOTALL)
#    data = style.sub('', data)
#    tree = BeautifulSoup(data, convertEntities=BeautifulSoup.HTML_ENTITIES)
#    atf = tree.find(attrs={'id':'atfResults'})
#    if atf == None:
#        print tree.prettify()
#        return False
#    atf = tree.find(attrs={'id':'atfResults'}).findAll('div',recursive=False,attrs={'name':True})
#    try:
#        btf = tree.find(attrs={'id':'btfResults'}).findAll('div',recursive=False,attrs={'name':True})
#        atf.extend(btf)
#        del btf
#    except:
#        print 'AMAZON: No btf found'
#    nextpage = tree.find(attrs={'title':'Next page','id':'pagnNextLink','class':'pagnNext'})
#    del data
#    return atf, nextpage
# 
#    
# def scrapeTVdb(url,isprime):
#    stop = False
#    while stop == False:
#        #try:
#        atf,nextpage = getTVTree(url)
#        stop = True
#        #except:
#        #    xbmc.sleep(15000)
#    returnTotal = 0
#    failedshows = []
#    for show in atf:
#        showasin = show['name']
#        url = common.BASE_URL+'/gp/product/'+showasin
#        seasondata = checkURLInfo(url)
#        if seasondata:
#            print 'AMAZON: Returning Cached Meta for URL: '+url
#            print seasondata
#            continue
#        try:
#            name = show.find('a', attrs={'class':'title'}).string.strip()
#        except:
#            print show.prettify()
#        poster = show.find(attrs={'class':'image'}).find('img')['src'].replace('._AA160_','')
#        if '[HD]' in name: isHD = True
#        else: isHD = False
#        seriestitle = name.split('Season ')[0].split('season ')[0].split('Volume ')[0].split('Series ')[0].split('Year ')[0].split(' The Complete')[0].replace('[HD]','').strip().strip('-').strip(',').strip(':').strip()
#        if seriestitle.endswith('-') or seriestitle.endswith(',') or seriestitle.endswith(':'):
#            seriestitle = name[:-1].strip()
#        #try:
#        showdata, episodes = scrapeShowInfo(url,owned=False)
#        #except: continue
#        season,episodetotal,plot,creator,runtime,year,network,actors,genres,stars,votes = showdata
#        strseason = str(season)
#        if len(strseason)>2 and strseason in name:
#            seriestitle = seriestitle.replace(strseason,'').strip()
#        seasondata = checkSeasonInfo(seriestitle,season,isHD)
#        if seasondata:
#            print 'AMAZON: Returning Cached Meta for SEASON: '+str(season)+' SERIES: '+seriestitle
#            print seasondata
#            continue
#        if episodetotal:
#            returnTotal += episodetotal
#        #          seriestitle,plot,creator,network,genres,actors,year,stars,votes,episodetotal,watched,unwatched,isHD,isprime,favor,TVDBbanner,TVDBposter,TVDBfanart
#        addShowdb([seriestitle,plot,creator,network,genres,actors,year,stars,votes,episodetotal,0,episodetotal,isHD,isprime,False,None,None,None,None])
#        for episodeASIN,Eseason,episodeNum,episodetitle,eurl,eplot,eairDate,eisHD in episodes:
#            #                    asin,seriestitle,season,episode,episodetitle,url,plot,airdate,runtime,isHD,isprime,watched
#            addEpisodedb([episodeASIN,seriestitle,Eseason,episodeNum,episodetitle,eurl,eplot,eairDate,runtime,eisHD,isprime,False])
#        #            url,poster,season,seriestitle,plot,creator,network,genres,actors,year,stars,votes,episodetotal,watched,unwatched,isHD,isprime
#        addSeasondb([url,poster,season,seriestitle,plot,creator,network,genres,actors,year,stars,votes,episodetotal,0,episodetotal,isHD,isprime])
#    del atf
#    if nextpage:
#        pagenext = common.BASE_URL + nextpage['href']
#        del nextpage
#        return pagenext,returnTotal
#    else:
#        return False,returnTotal
# 
# def checkSeasonInfo(seriestitle,season,isHD):
#    c = tvDB.cursor()
#    metadata = c.execute('select * from seasons where seriestitle = (?) and season = (?) and isHD = (?)', (seriestitle,season,isHD))
#    returndata = metadata.fetchone()
#    c.close()
#    return returndata
# 
# def checkURLInfo(url):
#    c = tvDB.cursor()
#    metadata = c.execute('select * from seasons where url = (?)', (url,))
#    returndata = metadata.fetchone()
#    c.close()
#    return returndata
# 
# def scrapeShowInfo(url,owned=False):
#    tags = re.compile(r'<.*?>')
#    scripts = re.compile(r'<script.*?script>',re.DOTALL)
#    spaces = re.compile(r'\s+')
#    odata = common.getURL(url)
#    data = scripts.sub('', odata)
#    style = re.compile(r'<style.*?style>',re.DOTALL)
#    data = style.sub('', data)
#    tree = BeautifulSoup(data, convertEntities=BeautifulSoup.HTML_ENTITIES)
#    print tree.find('td',attrs={'class':'description'}).string.strip().split(' ')[-1].strip()
#    try:season = int(tree.find('td',attrs={'class':'description'}).string.strip().split(' ')[-1].strip())
#    except:
#        try:season = int(tree.find('div',attrs={'class':'unbox_season_selected'}).string)
#        except:season = int(re.compile('''class="unbox_season_selected">(.*?)</div>''').findall(odata)[0].strip())
#        #    try:season = int(tree.find('div',attrs={'style':'font-size: 120%;font-weight:bold; margin-top:15px;margin-bottom:10px;'}).contents[0].split('Season')[1].strip())
#        #    except:print 'no season'
#    episodes = []
#    episodebox = tree.find('div',attrs={'id':'avod-ep-list-rows'})
#    if episodebox == None:
#        print tree.pretiffy()
#        episodecount = None
#    else:
#        episodebox = tree.find('div',attrs={'id':'avod-ep-list-rows'}).findAll('tr',attrs={'asin':True})
#        episodecount = len(episodebox)
#        for episode in episodebox:
#            if owned:
#                purchasecheckbox = episode.find('input',attrs={'type':'checkbox'})
#                if purchasecheckbox:
#                    continue
#            episodeASIN = episode['asin']
#            episodetitle = episode.find(attrs={'title':True})['title'].encode('utf-8')
#            if '[HD]' in episodetitle:
#                episodetitle.replace('[HD]','').strip()
#                isHD = True
#            else:
#                isHD = False
#            airDate = episode.find(attrs={'style':'width: 150px; overflow: hidden'}).string.strip()
#            try: plot =  episode.findAll('div')[1].string.strip()
#            except: plot = ''
#            try:episodeNum = int(episode.find('div',attrs={'style':'width: 185px;'}).string.split('.')[0].strip())
#            except:episodeNum = int(episode.find('div',attrs={'style':'width: 185px;'}).contents[0].split('.')[0].strip())
#            url = common.BASE_URL+'/gp/product/'+episodeASIN
#            episodedata = [episodeASIN,season,episodeNum,episodetitle,url,plot,airDate,isHD]
#            episodes.append(episodedata)
#        del episodebox
#    try:
#        stardata = tree.find('span',attrs={'class':'crAvgStars'}).renderContents()
#        stardata = scripts.sub('', stardata)
#        stardata = tags.sub('', stardata)
#        stardata = spaces.sub(' ', stardata).strip().split('out of ')
#        stars = float(stardata[0])*2
#        votes = stardata[1].split('customer reviews')[0].split('See all reviews')[1].replace('(','').strip()
#    except:
#        stars = None
#        votes = None
#    metadatas = tree.findAll('div', attrs={'style':'margin-top:7px;margin-bottom:7px;'})
#    del tree, data
#    metadict = {}
#    for metadata in metadatas:
#        mdata = metadata.renderContents()
#        mdata = scripts.sub('', mdata)
#        mdata = tags.sub('', mdata)
#        mdata = spaces.sub(' ', mdata).strip().split(': ')
#        fd = ''
#        for md in mdata[1:]:
#            fd += md+' '
#        metadict[mdata[0].strip()] = fd.strip()
#    try:plot = metadict['Synopsis']
#    except: plot = None
#    try:creator = metadict['Creator']
#    except:creator = None
#    try:
#        runtime = metadict['Runtime']
#        if 'hours' in runtime:
#            split = 'hours'
#        elif 'hour' in runtime:
#            split = 'hour'
#        if 'minutes' in runtime:
#            replace = 'minutes'
#        elif 'minute' in runtime:
#            replace = 'minute'
#        if 'hour' not in runtime:
#            runtime = runtime.replace(replace,'')
#            minutes = int(runtime.strip())
#        elif 'minute' not in runtime:
#            runtime = runtime.replace(split,'')
#            minutes = (int(runtime.strip())*60)     
#        else:
#            runtime = runtime.replace(replace,'').split(split)
#            try:
#                minutes = (int(runtime[0].strip())*60)+int(runtime[1].strip())
#            except:
#                minutes = (int(runtime[0].strip())*60)
#        runtime = str(minutes)
#    except: runtime = None
#    try: year = int(metadict['Season year'])
#    except: year = None
#    try: network = metadict['Network']
#    except: network = None
#    try: actors = metadict['Starring']+', '+metadict['Supporting actors']
#    except:
#        try: actors = metadict['Starring']
#        except: actors = None     
#    try: genres = metadict['Genre']
#    except: genres = None
#    print metadict
#    showdata = [season,episodecount,plot,creator,runtime,year,network,actors,genres,stars,votes]
#    return showdata, episodes
# 
# 
# def refreshTVDBshow(seriestitle=False):
#    if not seriestitle:
#        seriestitle = common.args.title
#    c = tvDB.cursor()
#    seriestitle,genre,year,TVDB_ID = c.execute('select distinct seriestitle,genres,year,TVDB_ID from shows where seriestitle = ?', (seriestitle,)).fetchone()
#    #for seriestitle,genre,year,TVDB_ID in show:
#    TVDBbanner,TVDBposter,TVDBfanart,genre2,year2,seriesid = tv_db_id_lookup(TVDB_ID,seriestitle)
#    if not genre:
#        genre = genre2
#    if not year:
#        try:
#            year = int(year2.split('-')[0])
#        except:
#            year = None
#    c.execute("update shows set TVDBbanner=?,TVDBposter=?,TVDBfanart=?,TVDB_ID=?,genres=?,year=? where seriestitle=?", (TVDBbanner,TVDBposter,TVDBfanart,seriesid,genre,year,seriestitle))
#    tvDB.commit()
#    
# def deleteUserDatabase():
#    dialog = xbmcgui.Dialog()
#    ret = dialog.yesno('Delete User Database', 'Delete User Television Database?')
#    if ret:
#        os.remove(tvDByourfile)
#        
# def deleteBackupDatabase():
#    dialog = xbmcgui.Dialog()
#    ret = dialog.yesno('Delete Backuo Database', 'Delete Backup Television Database?')
#    if ret:
#        os.remove(tvDBfile)
# 
# def scanTVDBshow(seriestitle=False):
#    if not seriestitle:
#        seriestitle = common.args.title
#    c = tvDB.cursor()
#    seriestitle,genre,year,TVDB_ID = c.execute('select distinct seriestitle,genres,year,TVDB_ID from shows where seriestitle = ?', (seriestitle,)).fetchone()
#    #for seriestitle,genre,year,TVDB_ID in show:
#    TVDBbanner,TVDBposter,TVDBfanart,genre2,year2,seriesid = tv_db_series_lookup(seriestitle,manualsearch=True)
#    if not genre:
#        genre = genre2
#    if not year:
#        try:
#            year = int(year2.split('-')[0])
#        except:
#            year = None
#    c.execute("update shows set TVDBbanner=?,TVDBposter=?,TVDBfanart=?,TVDB_ID=?,genres=?,year=? where seriestitle=?", (TVDBbanner,TVDBposter,TVDBfanart,seriesid,genre,year,seriestitle))
#    tvDB.commit()
# 
# def scanTVDBshows():
#    c = tvDB.cursor()
#    shows = c.execute('select distinct seriestitle,genres,year from shows order by seriestitle').fetchall()
#    dialog = xbmcgui.DialogProgress()
#    dialog.create('Refreshing Prime TV Database')
#    dialog.update(0,'Scanning TVDB Data')
#    #len(shows)
#    for seriestitle,genre,year in shows:
#        TVDBbanner,TVDBposter,TVDBfanart,genre2,year2,seriesid = tv_db_series_lookup(seriestitle)
#        if not genre:
#            genre = genre2
#        if not year:
#            try:
#                year = int(year2.split('-')[0])
#            except:
#                year = None
#        c.execute("update shows set TVDBbanner=?,TVDBposter=?,TVDBfanart=?,TVDB_ID=?,genres=?,year=? where seriestitle=?", (TVDBbanner,TVDBposter,TVDBfanart,seriesid,genre,year,seriestitle))
#        tvDB.commit()
#        if (dialog.iscanceled()):
#            return False
#    c.close()
# 
# 
# def tv_db_series_lookup(seriesname,manualsearch=False):
#    tv_api_key = '03B8C17597ECBD64'
#    mirror = 'http://thetvdb.com'
#    banners = 'http://thetvdb.com/banners/'
#    try:
#        print 'intial search'
#        series_lookup = 'http://www.thetvdb.com/api/GetSeries.php?seriesname='+urllib.quote_plus(seriesname)
#        seriesid = common.getURL(series_lookup)
#        seriesid = get_series_id(seriesid,seriesname)
#    except:
#        try:
#            print 'strip search'
#            series_lookup = 'http://www.thetvdb.com/api/GetSeries.php?seriesname='+urllib.quote_plus(seriesname.split('(')[0].split(':')[0].strip())
#            seriesid = common.getURL(series_lookup)
#            seriesid = get_series_id(seriesid,seriesname)
#        except:
#            if manualsearch:
#                print 'manual search'
#                keyb = xbmc.Keyboard(seriesname, 'Manual Search')
#                keyb.doModal()
#                if (keyb.isConfirmed()):
#                    try:
#                        series_lookup = 'http://www.thetvdb.com/api/GetSeries.php?seriesname='+urllib.quote_plus(keyb.getText())
#                        seriesid = common.getURL(series_lookup)
#                        seriesid = get_series_id(seriesid,seriesname)
#                    except:
#                        print 'manual search failed'
#                        return None,None,None,None,None,None
#            else:
#                return None,None,None,None,None,None
#    if seriesid:
#        return tv_db_id_lookup(seriesid,seriesname)
#    else:
#        return None,None,None,None,None,None
#  
# def tv_db_id_lookup(seriesid,seriesname):
#    tv_api_key = '03B8C17597ECBD64'
#    mirror = 'http://thetvdb.com'
#    banners = 'http://thetvdb.com/banners/'
#    if seriesid:
#        series_xml = mirror+('/api/%s/series/%s/en.xml' % (tv_api_key, seriesid))
#        series_xml = common.getURL(series_xml)
#        tree = BeautifulStoneSoup(series_xml, convertEntities=BeautifulStoneSoup.HTML_ENTITIES)
#        try:
#            genre = tree.find('genre').string
#            genre = genre.replace("|",",")
#            genre = genre.strip(",")
#        except:
#            print '%s - Genre Failed' % seriesname
#            genre = None
#        try: aired = tree.find('firstaired').string
#        except:
#            print '%s - Air Date Failed' % seriesname
#            aired = None
#        try: banner = banners + tree.find('banner').string
#        except:
#            print '%s - Banner Failed' % seriesname
#            banner = None
#        try: fanart = banners + tree.find('fanart').string
#        except:
#            print '%s - Fanart Failed' % seriesname
#            fanart = None
#        try: poster = banners + tree.find('poster').string
#        except:
#            print '%s - Poster Failed' % seriesname
#            poster = None
#        return banner, poster, fanart, genre, aired, seriesid
#    else:
#        return None,None,None,None,None,None
# 
# def get_series_id(seriesid,seriesname):
#    shows = BeautifulStoneSoup(seriesid, convertEntities=BeautifulStoneSoup.HTML_ENTITIES).findAll('series')
#    names = list(BeautifulStoneSoup(seriesid, convertEntities=BeautifulStoneSoup.HTML_ENTITIES).findAll('seriesname'))
#    if len(names) > 1:
#        select = xbmcgui.Dialog()
#        ret = select.select(seriesname, [name.string for name in names])
#        if ret <> -1:
#            seriesid = shows[ret].find('seriesid').string
#        else:
#            seriesid = False
#    else:
#        seriesid = shows[0].find('seriesid').string
#    return seriesid
#===============================================================================