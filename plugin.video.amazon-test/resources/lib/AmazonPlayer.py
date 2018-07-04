#!/usr/bin/env python
# -*- coding: utf-8 -*-
import xbmc
import xbmcplugin

class AmazonPlayer(xbmc.Player):
    def __init__(self):
        super(AmazonPlayer, self).__init__()
        self.sleeptm = 0.2
        self.video_lastpos = 0
        self.video_totaltime = 0
        self.dbid = 0
        self.seek = 0
        self.url = ''
        self.extern = ''
        self.asin = ''
        self.cookie = None
        self.interval = 180
        self.running = False

    def resolve(self, li):
        if not self.checkResume():
            xbmcplugin.setResolvedUrl(pluginhandle, True, xbmcgui.ListItem())
            xbmc.executebuiltin('Container.Refresh')
            return
        self.running = True
        xbmcplugin.setResolvedUrl(pluginhandle, True, li)
        self.PlayerInfo('Starting Playback')
        if self.seek:
            self.seekTime(self.seek)
            self.PlayerInfo('Resuming Playback')

        self.updateStream('START')
        Log('Video ContentType Movie? %s' % xbmc.getCondVisibility('VideoPlayer.Content(movies)'), xbmc.LOGDEBUG)
        Log('Video ContentType Episode? %s' % xbmc.getCondVisibility('VideoPlayer.Content(episodes)'), xbmc.LOGDEBUG)

    def checkResume(self):
        self.dbid = int('0' + getListItem('DBID'))
        Log(self.dbid, xbmc.LOGDEBUG)
        if not self.dbid:
            return True
        dbtype = getListItem('DBTYPE')
        result = jsonRPC('VideoLibrary.Get%sDetails' % dbtype, 'resume,playcount', {'%sid' % dbtype: self.dbid})
        position = int(result['episodedetails']['resume']['position'])
        playcount = int(result['episodedetails']['playcount'])
        Log(result, xbmc.LOGDEBUG)

        if playcount:
            return True
        if position > 180:
            sel = Dialog.contextmenu([getString(12022).format(time.strftime("%H:%M:%S", time.gmtime(position))), getString(12021)])
            if sel > -1:
                self.seek = position if sel == 0 else 0
            else:
                return False
        return True

    def onPlayBackEnded(self):
        self.finished()

    def onPlayBackStopped(self):
        self.finished()

    def updateStream(self, event):
        suc, msg = getUrldata('usage/UpdateStream', self.asin, useCookie=self.cookie, opt='&event=%s&timecode=%s' % (event, self.video_lastpos))
        if suc and 'statusCallbackIntervalSeconds' in str(msg):
            self.interval = msg['message']['body']['statusCallbackIntervalSeconds']

    def finished(self):
        self.updateStream('STOP')
        if self.extern:
            playcount = 1 if (self.video_lastpos * 100) / self.video_totaltime >= 90 else 0
            watched = getListItem('PlayCount')
            if self.dbid:
                dbtype = getListItem('DBTYPE')
                params = {'%sid' % dbtype: self.dbid,
                          'resume': {'position': 0 if playcount else self.video_lastpos,
                                     'total': self.video_totaltime},
                          'playcount': playcount}
                res = '' if 'OK' in jsonRPC('VideoLibrary.Set%sDetails' % dbtype, '', params) else 'NOT '
                Log('%sUpdated %sid(%s) with: pos(%s) total(%s) playcount(%s)' % (res, dbtype, self.dbid, self.video_lastpos, self.video_totaltime, playcount))
            else:
                Log('No DBID returned')
                if playcount and not watched:
                    xbmc.executebuiltin("Action(ToggleWatched)")

        xbmc.executebuiltin('Container.Refresh')
        self.running = False

    def PlayerInfo(self, msg):
        while not self.isPlayingVideo():
            sleep(self.sleeptm)
        while self.isPlayingVideo() and (0 > self.getTime() >= self.getTotalTime()):
            sleep(self.sleeptm)
        if self.isPlayingVideo():
            self.video_totaltime = self.getTotalTime()
            self.video_lastpos = self.getTime()
            Log('%s: %s/%s' % (msg, self.video_lastpos, self.video_totaltime))
