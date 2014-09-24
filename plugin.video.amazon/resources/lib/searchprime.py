#!/usr/bin/env python
# -*- coding: utf-8 -*-
from BeautifulSoup import BeautifulSoup
import xbmcplugin
import xbmc
import urllib
import resources.lib.common as common
import re

pluginhandle = common.pluginhandle

# 501-POSTER WRAP 503-MLIST3 504=MLIST2 508-FANARTPOSTER 
confluence_views = [500,501,502,503,504,508]


def SEARCH_PRIME():
    keyboard = xbmc.Keyboard('')#Put amazon prime video link here.')
    keyboard.doModal()
    q = keyboard.getText()
    if (keyboard.isConfirmed()):
        xbmcplugin.setContent(0, 'Movies')#int(sys.argv[1])
        url = common.args.url + ( urllib.quote_plus(keyboard.getText())) + "%2Cp_85%3A2470955011&page=1"
        data = common.getURL(url,useCookie=False)
        tree = BeautifulSoup(data, convertEntities=BeautifulSoup.HTML_ENTITIES)
        #videos = tree.findAll('div',attrs={'class':re.compile("^result.+product$"),'name':True}) 
        atf = tree.find(attrs={'id':'atfResults'}).findAll('div',recursive=False,attrs={'name':True})
        try:
            btf = tree.find(attrs={'id':'btfResults'}).findAll('div',recursive=False,attrs={'name':True})
            atf.extend(btf)
            del btf
        except:
            print 'AMAZON: No btf found'
        del tree
        del data
        #nextpage = tree.find(attrs={'title':'Next page','id':'pagnNextLink','class':'pagnNext'})
        totalItems = len(atf)
        print totalItems
        for video in atf:
            #price = video.find('span',attrs={'class':'price'})
            #print price
            #if (price != None and price.string != None and price.string.strip() == '$0.00'):
            asin = video['name']
            movietitle = video.find('',attrs={'class':'data'}).a.string
            url = video.find('div',attrs={'class':'data'}).a['href'] # 
            thumb = video.find('img')['src'].replace('._AA160_','') # was SS160 for purchased tv/movies, regular search is just this
            fanart = thumb      
            infoLabels = { 'Title':movietitle}
            prices = video.findAll(attrs={'class':'priceInfo'})
            episodes = False
            for price in prices:
                if 'episode' in price.renderContents():
                    episodes = True
            if episodes:
                common.addDir(movietitle,'library','LIST_EPISODES', url,thumb,fanart,infoLabels)
            else:
                fanart = fanart.replace('.jpg','._BO354,0,0,0_CR177,354,708,500_.jpg') 
                common.addVideo(movietitle,url,thumb,fanart,infoLabels=infoLabels,totalItems=totalItems)
        #viewenable=common.addon.getSetting("viewenable")
        #if viewenable == 'true':
        #    view=int(xbmcplugin.getSetting(pluginhandle,"movieview"))
        #    xbmc.executebuiltin("Container.SetViewMode("+str(confluence_views[view])+")")
        xbmcplugin.endOfDirectory(pluginhandle)




