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


################################ Movie db

def createMoviedb():
    c = MovieDB.cursor()
    c.execute('''create table movies
                (asin UNIQUE,
                 HDasin UNIQUE,
                 movietitle TEXT,
                 url TEXT,
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
                 watched BOOLEAN,
                 favor BOOLEAN,
                 IMDB_ID TEXT,
                 PRIMARY KEY(movietitle,year,asin))''')
    MovieDB.commit()
    c.close()

def addMoviedb(moviedata):
    #print 'addMoviedb:'
    #print moviedata
    c = MovieDB.cursor()
    c.execute('insert or ignore into movies values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', moviedata)
    MovieDB.commit()
    c.close()

def lookupMoviedb(asin,isPrime):
    c = MovieDB.cursor()
    if c.execute('select distinct * from movies where asin = (?)', (asin,)).fetchone():
        return c.execute('select distinct * from movies where asin = (?)', (asin,))
    elif c.execute('select distinct * from movies where HDasin = (?)', (asin,)).fetchone():
        return c.execute('select distinct * from movies where HDasin = (?)', (asin,))
    else:
        p_asin,hd_asin = ASIN_ADD(asin,isPrime)
        if p_asin == asin:
            return c.execute('select distinct * from movies where asin = (?)', (asin,))
        elif hd_asin == asin:
            return c.execute('select distinct * from movies where HDasin = (?)', (asin,))
        else:
            c.execute("update movies set HDasin=? where asin=?", (asin,p_asin))
            MovieDB.commit()
            return c.execute('select distinct * from movies where HDasin = (?)', (asin,))

def deleteMoviedb(asin=False):
    if not asin:
        asin = common.args.url
    c = MovieDB.cursor()
    shownamedata = c.execute('delete from movies where asin = (?)', (asin,))
    
    c.close()

def watchMoviedb(asin=False):
    if not asin:
        asin = common.args.url
    c = MovieDB.cursor()
    c.execute("update movies set watched=? where asin=?", (True,asin))
    MovieDB.commit()
    c.close()
    
def unwatchMoviedb(asin=False):
    if not asin:
        asin = common.args.url
    c = MovieDB.cursor()
    c.execute("update movies set watched=? where asin=?", (False,asin))
    MovieDB.commit()
    c.close()

def favorMoviedb(asin=False):
    if not asin:
        asin = common.args.url
    c = MovieDB.cursor()
    c.execute("update movies set favor=? where asin=?", (True,asin))
    MovieDB.commit()
    c.close()
    
def unfavorMoviedb(asin=False):
    if not asin:
        asin = common.args.url
    c = MovieDB.cursor()
    c.execute("update movies set favor=? where asin=?", (False,asin))
    MovieDB.commit()
    c.close() 

def loadMoviedb(genrefilter=False,actorfilter=False,directorfilter=False,studiofilter=False,yearfilter=False,mpaafilter=False,watchedfilter=False,favorfilter=False,alphafilter=False,isprime=True):
    c = MovieDB.cursor()
    if genrefilter:
        genrefilter = '%'+genrefilter+'%'
        return c.execute('select distinct * from movies where isprime = (?) and genres like (?)', (isprime,genrefilter))
    elif mpaafilter:
        #mpaafilter = '%'+mpaafilter+'%'
        #return c.execute('select distinct * from movies where isprime = (?) and mpaa like (?)', (isprime,mpaafilter))
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
    elif watchedfilter:
        return c.execute('select distinct * from movies where isprime = (?) and watched = (?)', (isprime,watchedfilter))
    elif favorfilter:
        return c.execute('select distinct * from movies where isprime = (?) and favor = (?)', (isprime,favorfilter))
    elif alphafilter:
        return c.execute('select distinct * from movies where isprime = (?) and movietitle regexp (?)', (isprime,alphafilter+'*'))       
    else:
        return c.execute('select distinct * from movies where isprime = (?)', (isprime,))

def getMovieTypes(col):
    c = MovieDB.cursor()
    items = c.execute('select distinct %s from movies' % col)
    list = []
    for data in items:
        data = data[0]
        if type(data) == type(str()):
            if 'Rated' in data:
                item = data.split('for')[0]
                if item not in list and item <> '' and item <> 0 and item <> 'Inc.' and item <> 'LLC.':
                    list.append(item)
            else:
                data = data.decode('utf-8').encode('utf-8').split(',')
                for item in data:
                    item = item.replace('& ','').strip()
                    if item not in list and item <> '' and item <> 0 and item <> 'Inc.' and item <> 'LLC.':
                        list.append(item)
        elif data <> 0:
            if data is not None:
                list.append(str(data))
    c.close()
    return list

def addMoviesdb(isPrime=True):
    dialog = xbmcgui.DialogProgress()
    dialog.create('Building Prime Movie Database')
    dialog.update(0,'Initializing Movie Scan')
    page = 1
    goAhead = True
    endIndex=0
    while goAhead:
        page+=1
        json = appfeed.getList('Movie',endIndex)
        titles = json['message']['body']['titles']
        ASINLIST = ''
        for title in titles:
            ASINLIST += title['titleId']+','
        ASIN_ADD(ASINLIST)
        endIndex+=250
        #endIndex = json['message']['body']['endIndex']
        if (dialog.iscanceled()):
            goAhead = False
        elif endIndex > 14000:
            goAhead = False
        dialog.update(int(page*100.0/56),'Scanning Page %s' % str(page),'Scanned %s Movies' % str(endIndex) )

def ASIN_ADD(ASINLIST,isPrime=True):
    titles = appfeed.ASIN_LOOKUP(ASINLIST)['message']['body']['titles']
    for title in titles:
        asin = title['titleId']
        movietitle = title['title']
        url = common.BASE_URL+'/gp/product/'+asin
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
            mpaa = ''
        if title.has_key('starringCast'):
            actors = title['starringCast']
        else:
            actors = None
        if title.has_key('genres'):
            genres = ','.join(title['genres'])
        else:
            genres = ''
        if title.has_key('customerReviewCollection'):
            stars = float(title['customerReviewCollection']['customerReviewSummary']['averageOverallRating'])*2
            votes = str(title['customerReviewCollection']['customerReviewSummary']['totalReviewCount'])
        else:
            stars = None
            votes = None
        isHD = False
        hd_asin = None
        for format in title['formats']:
            if format['videoFormatType'] == 'HD':
                isHD = True
                for offer in format['offers']:
                    if offer['offerType'] == 'PURCHASE':
                        hd_asin = offer['asin']
                    elif offer['offerType'] == 'RENTAL':
                        hd_asin = offer['asin']
            #for offer in format['offers']:
            #    if offer['offerType'] == 'SUBSCRIPTION':
            #        isPrime = True
        #Add Movie
        moviedata = [asin,hd_asin,movietitle,url,poster,plot,director,None,runtime,year,premiered,studio,mpaa,actors,genres,stars,votes,None,None,None,isPrime,isHD,False,False,None]
        addMoviedb(moviedata)
    return [asin,hd_asin]

MovieDBfile = os.path.join(xbmc.translatePath('special://home/addons/script.module.amazon.database/lib/'),'movies.db')
if not os.path.exists(MovieDBfile):
    MovieDB = sqlite.connect(MovieDBfile)
    MovieDB.text_factory = str
    createMoviedb()
else:
    MovieDB = sqlite.connect(MovieDBfile)
    MovieDB.text_factory = str


#===============================================================================
# MovieDBdownload = os.path.join(xbmc.translatePath(common.pluginpath),'resources','cache','newmovies.db')
# MovieDBold = os.path.join(xbmc.translatePath('special://profile/addon_data/plugin.video.amazon/'),'movies.db')
# MovieDBfile = os.path.join(xbmc.translatePath('special://profile/addon_data/plugin.video.amazon/'),'movies0.db')
# MovieDBfile0 = os.path.join(xbmc.translatePath('special://profile/addon_data/plugin.video.amazon/'),'movies1.db')
# if not os.path.exists(MovieDBfile) and os.path.exists(MovieDBdownload):
#    import shutil
#    shutil.move(MovieDBdownload, MovieDBfile)
#    if os.path.exists(MovieDBfile0):
#        os.remove(MovieDBfile0)
#    if os.path.exists(MovieDBold): 
#        os.remove(MovieDBold)
# if not os.path.exists(MovieDBfile):
#    MovieDB = sqlite.connect(MovieDBfile)
#    MovieDB.text_factory = str
#    createMoviedb()
# else:
#    MovieDB = sqlite.connect(MovieDBfile)
#    MovieDB.text_factory = str
#===============================================================================

######### OLD HTML SCRAPING CODE
#MOVIE_URL = 'http://www.amazon.com/gp/search/ref=sr_st?qid=1314934213&rh=n%3A2625373011%2Cn%3A!2644981011%2Cn%3A!2644982011%2Cn%3A2858778011%2Cn%3A2858905011%2Cp_85%3A2470955011&sort=-releasedate'
#===============================================================================
# def addNewMoviesdbHTML():
#    addMoviesdb(MOVIE_URL,singlepage=True)
# 
# def addMoviesdbHTML(url=MOVIE_URL,isprime=True,singlepage=False):
#    dialog = xbmcgui.DialogProgress()
#    dialog.create('Refreshing Prime Movie Database')
#    dialog.update(0,'Initializing Movie Scan')
#    if not singlepage:
#        data = common.getURL(url)
#        tree = BeautifulSoup(data, convertEntities=BeautifulSoup.HTML_ENTITIES)
#        #total = int(tree.find('div',attrs={'id':'resultCount','class':'resultCount'}).span.string.replace(',','').split('of')[1].split('Results')[0].strip())
#        total = 1300
#        del tree; del data
#    else:
#        total=12
#    pages = (total/12)+1
#    increment = 100.0 / pages 
#    page = 1
#    percent = int(increment*page)
#    dialog.update(percent,'Scanning Page %s of %s' % (str(page),str(pages)),'Scanned %s of %s Movies' % (str((page-1)*12),str(total)))
#    pagenext = scrapeMoviesdb(url,isprime)
#    if not singlepage:
#        while pagenext:
#            page += 1
#            percent = int(increment*page)
#            dialog.update(percent,'Scanning Page %s of %s' % (str(page),str(pages)),'Scanned %s of %s Movies' % (str((page-1)*12),str(total)))
#            pagenext = scrapeMoviesdb(pagenext,isprime)
#            if (dialog.iscanceled()):
#                return False
# 
# def scrapeMoviesdbHTML(url,isprime=True):
#    data = common.getURL(url)
#    scripts = re.compile(r'<script.*?script>',re.DOTALL)
#    data = scripts.sub('', data)
#    style = re.compile(r'<style.*?style>',re.DOTALL)
#    data = style.sub('', data)
#    tree = BeautifulSoup(data, convertEntities=BeautifulSoup.HTML_ENTITIES)
#    atf = tree.find(attrs={'id':'atfResults'}).findAll('div',recursive=False,attrs={'name':True})
#    try:
#        btf = tree.find(attrs={'id':'btfResults'}).findAll('div',recursive=False,attrs={'name':True})
#        atf.extend(btf)
#        del btf
#    except:
#        print 'AMAZON: No btf found'
#    nextpage = tree.find(attrs={'title':'Next page','id':'pagnNextLink','class':'pagnNext'})
#    del tree
#    del data  
#    for movie in atf:
#        asin = movie['name']
#        movietitle = movie.find('a', attrs={'class':'title'}).string
#        poster = movie.find(attrs={'class':'image'}).find('img')['src'].replace('._AA160_','')
#        url = common.BASE_URL+'/gp/product/'+asin
#        print getMovieInfo(asin,movietitle,url,poster,isPrime=True)
#    del atf
#    if nextpage:
#        pagenext = common.BASE_URL + nextpage['href']
#        del nextpage
#        return pagenext
#    else:
#        return False
# 
# def getMovieInfoHTML(asin,movietitle,url,poster,isPrime=False):
#    c = MovieDB.cursor()
#    returndata = c.execute('select asin,movietitle,url,poster,plot,director,writer,runtime,year,premiered,studio,mpaa,actors,genres,stars,votes,TMDBbanner,TMDBposter,TMDBfanart,isprime,watched,favor from movies where asin = (?) and movietitle = (?)', (asin,movietitle)).fetchone()
#    c.close()
#    if returndata:
#        print 'AMAZON: Returning Cached Meta for ASIN: '+asin
#        return returndata
#    else:
#        plot,director,runtime,year,premiered,studio,mpaa,actors,genres,stars,votes = scrapeMovieInfo(asin)
#        moviedata = [asin,movietitle,url,poster,plot,director,None,runtime,year,premiered,studio,mpaa,actors,genres,stars,votes,None,None,None,isPrime,False,False,None]
#        addMoviedb(moviedata)
#        print 'AMAZON: Cached Meta for ASIN: '+asin
#        return moviedata
# 
# def scrapeMovieInfoHTML(asin):
#    url = common.BASE_URL+'/gp/product/'+asin
#    tags = re.compile(r'<.*?>')
#    scripts = re.compile(r'<script.*?script>',re.DOTALL)
#    spaces = re.compile(r'\s+')
#    data = common.getURL(url)
#    scripts = re.compile(r'<script.*?script>',re.DOTALL)
#    data = scripts.sub('', data)
#    style = re.compile(r'<style.*?style>',re.DOTALL)
#    data = style.sub('', data)
#    tree = BeautifulSoup(data, convertEntities=BeautifulSoup.HTML_ENTITIES)
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
#    try:
#        premieredpossible = tree.find('div', attrs={'class':'bucket','id':'stills'}).findAll('li')
#        for item in premieredpossible:
#            if item.contents[0].string == 'US Theatrical Release Date:':
#                premiered = item.contents[1].strip()
#                d = datetime.strptime(premiered, '%B %d, %Y')
#                premiered = d.strftime('%Y-%m-%d')
#        if not premiered:
#            premiered = None
#    except:
#        premiered = None
#    metadatas = tree.findAll('div', attrs={'style':'margin-top:7px;margin-bottom:7px;'})
#    del tree, data
#    metadict = {}
#    for metadata in metadatas:
#        mdata = metadata.renderContents()
#        mdata = scripts.sub('', mdata)
#        mdata = tags.sub('', mdata)
#        mdata = spaces.sub(' ', mdata).strip().split(':')
#        fd = ''
#        for md in mdata[1:]:
#            fd += ' '+md
#        metadict[mdata[0].strip()] = fd.strip()
#    try:plot = metadict['Synopsis']
#    except: plot = None
#    try:director = metadict['Directed by']
#    except:director = None
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
#    try: year = int(metadict['Release year'])
#    except: year = None
#    try: studio = metadict['Studio']
#    except: studio = None
#    try: mpaa = metadict['MPAA Rating']
#    except: mpaa = None
#    try: actors = metadict['Starring']+', '+metadict['Supporting actors']
#    except:
#        try: actors = metadict['Starring']
#        except: actors = None     
#    try: genres = metadict['Genre']
#    except: genres = None
#    return plot,director,runtime,year,premiered,studio,mpaa,actors,genres,stars,votes
#===============================================================================