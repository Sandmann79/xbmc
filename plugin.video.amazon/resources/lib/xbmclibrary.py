#!/usr/bin/env python
# -*- coding: utf-8 -*-
import xbmcplugin
import xbmc
import xbmcgui
import os.path
import sys
import urllib
import string
import resources.lib.common as common

import movies as moviesDB
import tv as tvDB

from BeautifulSoup import BeautifulStoneSoup
from BeautifulSoup import BeautifulSoup , Tag, NavigableString

pluginhandle = common.pluginhandle

if (common.addon.getSetting('enablelibraryfolder') == 'true'):
    MOVIE_PATH = os.path.join(xbmc.translatePath('special://profile/addon_data/plugin.video.amazon/'),'Movies')
    TV_SHOWS_PATH = os.path.join(xbmc.translatePath('special://profile/addon_data/plugin.video.amazon/'),'TV')
elif (common.addon.getSetting('customlibraryfolder') <> ''):
    MOVIE_PATH = os.path.join(xbmc.translatePath(common.addon.getSetting('customlibraryfolder')),'Movies')
    TV_SHOWS_PATH = os.path.join(xbmc.translatePath(common.addon.getSetting('customlibraryfolder')),'TV') 

def UpdateLibrary():
    xbmc.executebuiltin("UpdateLibrary(video)") 
    
def SaveFile(filename, data, dir):
    path = os.path.join(dir, filename)
    file = open(path,'w')
    file.write(data)
    file.close()

def CreateDirectory(dir_path):
    dir_path = dir_path.strip()
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)

def cleanfilename(name):    
    valid_chars = "-_.() %s%s" % (string.ascii_letters, string.digits)
    return ''.join(c for c in name if c in valid_chars)    

def SetupLibrary():
    if (common.addon.getSetting('enablelibraryfolder') == 'true'):
        SetupAmazonLibrary()
    elif (common.addon.getSetting('customlibraryfolder') <> ''):
        CreateDirectory(MOVIE_PATH)
        CreateDirectory(TV_SHOWS_PATH) 

def streamDetails(duration, ishd, language='en', hasSubtitles=False):      
    fileinfo  = '<fileinfo>'
    fileinfo += '<streamdetails>'
    fileinfo += '<audio>'
    fileinfo += '<channels>2</channels>'
    fileinfo += '<codec>aac</codec>'
    fileinfo += '</audio>'
    fileinfo += '<video>'
    fileinfo += '<codec>h264</codec>'
    fileinfo += '<durationinseconds>'+duration+'</durationinseconds>'
    if ishd == True:
        fileinfo += '<aspect>1.778</aspect>'
        fileinfo += '<height>720</height>'
        fileinfo += '<width>1280</width>'
    else:
        fileinfo += '<height>400</height>'
        fileinfo += '<width>720</width>'        
    fileinfo += '<language>'+language+'</language>'
    #fileinfo += '<longlanguage>English</longlanguage>'
    fileinfo += '<scantype>Progressive</scantype>'
    fileinfo += '</video>'
    if hasSubtitles == True:
        fileinfo += '<subtitle>'
        fileinfo += '<language>eng</language>'
        fileinfo += '</subtitle>'
    fileinfo += '</streamdetails>'
    fileinfo += '</fileinfo>'
    return fileinfo

def EXPORT_MOVIE(asin=False,makeNFO=True):
    if not asin:
        asin=common.args.asin
    #SetupLibrary()
    movie = moviesDB.lookupMoviedb(asin,isPrime=True)
    for asin,hd_asin,movietitle,url,poster,plot,director,writer,runtime,year,premiered,studio,mpaa,actors,genres,stars,votes,TMDBbanner,TMDBposter,TMDBfanart,isprime,isHD,watched,favor,TMDB_ID in movie:       
        if year:
            filename = cleanfilename(movietitle+' ('+str(year)+')')
        else:
            filename = cleanfilename(movietitle)
 
        strm_file = filename + ".strm"
        u = 'plugin://plugin.video.amazon/'
        u += '?url="'+urllib.quote_plus(url)+'"'
        u += '&mode="play"'
        u += '&sitemode="PLAYVIDEO"'
        u += '&xbmclibrary=True'       
        SaveFile(strm_file, u, MOVIE_PATH)
        
        if makeNFO:
            nfo_file = filename + ".nfo"
            nfo = '<movie>'
            nfo+= '<title>'+movietitle+'</title>'
            if stars:
                nfo+= '<rating>'+str(stars)+'</rating>'
            if votes:
                nfo+= '<votes>'+votes+'</votes>'
            if year: 
                nfo+= '<year>'+str(year)+'</year>'
            if premiered:
                nfo+= '<premiered>'+premiered+'</premiered>'
            if plot:
                nfo+= '<outline>'+plot+'</outline>'
                nfo+= '<plot>'+plot+'</plot>'
            if runtime: 
                nfo+= '<runtime>'+runtime+'</runtime>' ##runtime in minutes
                nfo+= streamDetails(str(int(runtime)*60), isHD)
            else:
                nfo+= streamDetails('', isHD)
            if poster:
                nfo+= '<thumb>'+poster+'</thumb>'
            if mpaa:
                nfo+= '<mpaa>'+mpaa+'</mpaa>'
            if studio:
                nfo+= '<studio>'+studio+'</studio>'
            if watched:
                nfo+= '<watched>'+str(watched)+'</watched>'
            #nfo+= '<id>'tt0432337'</id>'
            u  = 'plugin://plugin.video.amazon/'
            u += '?url="'+urllib.quote_plus(url)+'"'
            u += '&mode="play"'
            u += '&name="'+urllib.quote_plus(movietitle)+'"'
            utrailer = u+'&sitemode="PLAYTRAILER"'
            nfo+= '<trailer>'+utrailer+'</trailer>'
            if genres:
                for genre in genres.split(','):
                    nfo+= '<genre>'+genre+'</genre>'
            if director:
                nfo+= '<director>'+director+'</director>'
            if actors:
                for actor in actors.split(','):
                    nfo+= '<actor>'
                    nfo+= '<name>'+actor+'</name>'
                    nfo+= '</actor>'
            nfo+= '</movie>'
            SaveFile(nfo_file, nfo, MOVIE_PATH)
            
def EXPORT_SHOW(asin=False):
    if not asin:
        asin=common.args.asin
    #SetupLibrary()
    show = tvDB.lookupShowsdb(asin)
    for asin,asin2,feed,seriestitle,poster,plot,network,mpaa,genres,actors,premiered,year,stars,votes,seasontotal,episodetotal,watched,unwatched,isHD,isprime,favor,TVDBbanner,TVDBposter,TVDBfanart,TVDBseriesid in show:
        directorname = os.path.join(TV_SHOWS_PATH,seriestitle.replace(':',''))
        CreateDirectory(directorname)
        seasons = tvDB.loadTVSeasonsdb(seriestitle=seriestitle,HDonly=False).fetchall()
        seasonTotal = len(seasons)
        for seasondata in seasons:
            EXPORT_SEASON(seasondata[0])
    
def EXPORT_SEASON(asin=False):
    if not asin:
        asin=common.args.asin
    #SetupLibrary()
    seasons = tvDB.lookupSeasondb(asin)
    for asin,seriesASIN,episodeFeed,poster,season,seriestitle,plot,actors,network,mpaa,genres,premiered,year,stars,votes,episodetotal,watched,unwatched,isHD,isprime in seasons:
        directorname = os.path.join(TV_SHOWS_PATH,seriestitle.replace(':',''))
        CreateDirectory(directorname)
        name = 'Season '+str(season)
        if isHD:
            name+=' HD'
        seasonpath = os.path.join(directorname,name)
        CreateDirectory(seasonpath)
        episodes = tvDB.loadTVEpisodesdb(seriestitle,season,isHD)
        for episodedata in episodes:
            EXPORT_EPISODE(episodedata[0],isHD=isHD)
    
def EXPORT_EPISODE(asin=False,makeNFO=True,isHD=False,isPrime=True):
    if not asin:
        asin=common.args.asin
    #SetupLibrary()
    episodes = tvDB.lookupEpisodedb(asin,isPrime=isPrime)
    for asin,seasonASIN,seriesASIN,seriestitle,season,episode,poster,mpaa,actors,genres,episodetitle,network,stars,votes,url,plot,airdate,year,runtime,isHD,isprime,watched in episodes:
        directorname = os.path.join(TV_SHOWS_PATH,seriestitle.replace(':',''))
        CreateDirectory(directorname)
        name = 'Season '+str(season)
        if isHD:
            name+=' HD'
        seasonpath = os.path.join(directorname,name)
        
        filename = 'S%sE%s - %s' % (season,episode,cleanfilename(episodetitle))
        if isHD:
            filename+=' (HD)'
        strm_file = filename + ".strm"
        u = 'plugin://plugin.video.amazon/'
        u += '?url="'+urllib.quote_plus(url)+'"'
        u += '&mode="play"'
        u += '&sitemode="PLAYVIDEO"'
        u += '&xbmclibrary=True'       
        SaveFile(strm_file, u, seasonpath)

        if makeNFO:
            nfo_file = filename + ".nfo"
            nfo = '<episodedetails>'
            nfo+= '<title>'+episodetitle+'</title>'
            if season:
                nfo+= '<season>'+str(season)+'</season>'
            if episode:
                nfo+= '<episode>'+str(episode)+'</episode>'
            if stars:
                nfo+= '<rating>'+str(stars)+'</rating>'
            if votes:
                nfo+= '<votes>'+votes+'</votes>'
            if year: 
                nfo+= '<year>'+str(year)+'</year>'
            if airdate:
                nfo+= '<aired>'+airdate+'</aired>'
                nfo+= '<premiered>'+airdate+'</premiered>'
            if plot:
                nfo+= '<plot>'+plot+'</plot>'
            if runtime: 
                nfo+= '<runtime>'+runtime+'</runtime>' ##runtime in minutes
                nfo+= streamDetails(str(int(runtime)*60), isHD)
            else:
                nfo+= streamDetails('', isHD)
            if poster:
                nfo+= '<thumb>'+poster+'</thumb>'
            if mpaa:
                nfo+= '<mpaa>'+mpaa+'</mpaa>'
            if network:
                nfo+= '<studio>'+network+'</studio>'
            if watched:
                nfo+= '<watched>'+str(watched)+'</watched>'
            #nfo+= '<id>'tt0432337'</id>'
            u  = 'plugin://plugin.video.amazon/'
            u += '?url="'+urllib.quote_plus(url)+'"'
            u += '&mode="play"'
            u += '&name="'+urllib.quote_plus(episodetitle)+'"'
            utrailer = u+'&sitemode="PLAYTRAILER"'
            nfo+= '<trailer>'+utrailer+'</trailer>'
            if genres:
                for genre in genres.split(','):
                    nfo+= '<genre>'+genre+'</genre>'
            if actors:
                for actor in actors.split(','):
                    nfo+= '<actor>'
                    nfo+= '<name>'+actor+'</name>'
                    nfo+= '</actor>'
            nfo+= '</episodedetails>'
            SaveFile(nfo_file, nfo, seasonpath)

def SetupAmazonLibrary():
    print "Trying to add Amazon source paths..."
    source_path = os.path.join(xbmc.translatePath('special://profile/'), 'sources.xml')
    dialog = xbmcgui.Dialog()
    
    CreateDirectory(MOVIE_PATH)
    CreateDirectory(TV_SHOWS_PATH)
    
    try:
        file = open(source_path, 'r')
        contents=file.read()
        file.close()
    except:
        dialog.ok("Error","Could not read from sources.xml, does it really exist?")
        file = open(source_path, 'w')
        content = "<sources>\n"
        content += "    <programs>"
        content += "        <default pathversion=\"1\"></default>"
        content += "    </programs>"
        content += "    <video>"
        content += "        <default pathversion=\"1\"></default>"
        content += "    </video>"
        content += "    <music>"
        content += "        <default pathversion=\"1\"></default>"
        content += "    </music>"
        content += "    <pictures>"
        content += "        <default pathversion=\"1\"></default>"
        content += "    </pictures>"
        content += "    <files>"
        content += "        <default pathversion=\"1\"></default>"
        content += "    </files>"
        content += "</sources>"
        file.close()

    soup = BeautifulSoup(contents)  
    video = soup.find("video")      
        
    if len(soup.findAll(text="Amazon Movies")) < 1:
        movie_source_tag = Tag(soup, "source")
        movie_name_tag = Tag(soup, "name")
        movie_name_tag.insert(0, "Amazon Movies")
        movie_path_tag = Tag(soup, "path")
        movie_path_tag['pathversion'] = 1
        movie_path_tag.insert(0, MOVIE_PATH)
        movie_source_tag.insert(0, movie_name_tag)
        movie_source_tag.insert(1, movie_path_tag)
        video.insert(2, movie_source_tag)

    if len(soup.findAll(text="Amazon TV")) < 1: 
        tvshow_source_tag = Tag(soup, "source")
        tvshow_name_tag = Tag(soup, "name")
        tvshow_name_tag.insert(0, "Amazon TV")
        tvshow_path_tag = Tag(soup, "path")
        tvshow_path_tag['pathversion'] = 1
        tvshow_path_tag.insert(0, TV_SHOWS_PATH)
        tvshow_source_tag.insert(0, tvshow_name_tag)
        tvshow_source_tag.insert(1, tvshow_path_tag)
        video.insert(2, tvshow_source_tag)
    
    
    string = ""
    for i in soup:
        string = string + str(i)
    
    file = open(source_path, 'w')
    file.write(str(soup))
    file.close()
    print "Source paths added!"
    
    #dialog = xbmcgui.Dialog()
    #dialog.ok("Source folders added", "To complete the setup:", " 1) Restart XBMC.", " 2) Set the content type of added folders.")
    #Appearently this restarted everything and not just XBMC... :(
    #if dialog.yesno("Restart now?", "Do you want to restart XBMC now?"):
    #   xbmc.restart()
