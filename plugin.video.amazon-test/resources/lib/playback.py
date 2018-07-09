#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from os.path import join as OSPJoin
from urllib import quote_plus
import time
import xbmc
import xbmcgui
import xbmcplugin
from inputstreamhelper import Helper
from resources.lib.l10n import *
from resources.lib.logging import Log
from resources.lib.network import *
from common import Globals, Settings, jsonRPC, sleep

def _getListItem(li):
    return xbmc.getInfoLabel('ListItem.%s' % li).decode('utf-8')

def ParseStreams(suc, data, retmpd=False):
    g = Globals()
    s = Settings()

    def _ParseSubs(data):
        bForcedOnly = False  # Whether or not we should only download forced subtitles
        down_lang = int('0' + g.addon.getSetting('sub_lang'))
        if 0 == down_lang:
            return []  # Return if the sub_lang is set to None
        lang_main = jsonRPC('Settings.GetSettingValue', param={'setting': 'locale.subtitlelanguage'})
        lang_main = lang_main['value'] if 'value' in lang_main else ''
        
        # Locale.SubtitleLanguage (and .AudioLanguage) can either return a language or:
        # [ S] none: no subtitles
        # [ S] forced_only: forced subtitles only
        # [AS] original: the stream's original language
        # [AS] default: Kodi's UI
        #
        # For simplicity's sake (and temporarily) we will treat original as AudioLanguage, and
        # AudioLanguage 'original' as 'default'
        if lang_main not in ['none', 'forced_only', 'original', 'default']:
            lang_main = xbmc.convertLanguage(lang_main, xbmc.ISO_639_1)
        if 'none' == lang_main:
            return []
        if 'forced_only' == lang_main:
            bForcedOnly = True
        if ('forced_only' == lang_main) or ('original' == lang_main):
            lang_main = jsonRPC('Settings.GetSettingValue', param={'setting': 'locale.audiolanguage'})
            lang_main = lang_main['value'] if 'value' in lang_main else ''
            if lang_main not in ['original', 'default']:
                lang_main = xbmc.convertLanguage(lang_main, xbmc.ISO_639_1)
            if lang_main == 'original':
                lang_main = 'default'
        if 'default' == lang_main:
            lang_main = xbmc.getLanguage(xbmc.ISO_639_1, False)

        # At this point we should have the user's selected language or a valid fallback, although
        # we further sanitize for safety
        lang_main = lang_main if lang_main else xbmc.getLanguage(xbmc.ISO_639_1, False)
        lang_main = lang_main if lang_main else 'en'

        # down_lang: None | All | From Kodi player language settings | From settings, fallback to english | From settings, fallback to all
        lang_main = '' if 1 == down_lang else lang_main
        lang_fallback = None if 3 > down_lang else ('' if 4 == down_lang else 'en')

        localeConversion = {
            'ar-001':'ar',
            'cmn-hans':'zh HANS',
            'cmn-hant':'zh HANT',
            'da-dk':'da',
            'es-419':'es LA',
            'ja-jp':'ja',
            'ko-kr':'ko',
            'nb-no':'nb',
            'sv-se':'sv',
        } # Clean up language and locale information where needed
        subs = []
        if (not down_lang) or (('subtitleUrls' not in data) and ('forcedNarratives' not in data)):
            return subs

        def_subs = []
        fb_subs = []

        for sub in data['subtitleUrls'] + data['forcedNarratives']:
            lang = sub['languageCode'].strip()
            if lang in localeConversion:
                lang = localeConversion[lang]
            # Clean up where needed
            if '-' in lang:
                p1 = re.split('-', lang)[0]
                p2 = re.split('-', lang)[1]
                if (p1 == p2): # Remove redundant locale information when not useful
                    lang = p1
                else:
                    lang = '%s %s' % (p1, p2.upper())
            # Amazon's en defaults to en_US, not en_UK
            if 'en' == lang:
                lang = 'en US'
            # Read close-caption information where needed
            if '[' in sub['displayName']:
                cc = re.search(r'(\[[^\]]+\])', sub['displayName'])
                if None is not cc:
                    lang = lang + (' %s' % cc.group(1))
            # Add forced subs information
            if ' forced ' in sub['displayName']:
                lang = lang + '.Forced'
            if (' forced ' in sub['displayName']) or (False is bForcedOnly):
                sub['languageCode'] = lang
                if lang_main in lang:
                    def_subs.append(sub)
                if (None is not lang_fallback) and (lang_fallback in lang):
                    fb_subs.append(sub)

        if not def_subs:
            def_subs = fb_subs

        import codecs
        for sub in def_subs:
            escape_chars = [('&amp;', '&'), ('&quot;', '"'), ('&lt;', '<'), ('&gt;', '>'), ('&apos;', "'")]
            srtfile = xbmc.translatePath('special://temp/%s.srt' % sub['languageCode']).decode('utf-8')
            subDisplayLang = '“%s” subtitle (%s)' % (sub['displayName'].strip(), sub['languageCode'])
            content = ''
            with codecs.open(srtfile, 'w', encoding='utf-8') as srt:
                num = 0
                # Since .srt are available on amazon's servers, we strip the default extension and try downloading it just once
                subUrl = re.search(r'^(.*?\.)[^.]{1,}$', sub['url'])
                content = '' if None is subUrl else getURL(subUrl.group(1) + 'srt', rjson=False, attempt=777)
                if 0 < len(content):
                    Log('Downloaded %s' % subDisplayLang)
                    srt.write(content)
                else:
                    content = getURL(sub['url'], rjson=False, attempt=3)
                    if 0 < len(content):
                        Log('Converting %s' % subDisplayLang)
                        for tt in re.compile('<tt:p(.*)').findall(content):
                            tt = re.sub('<tt:br[^>]*>', '\n', tt)
                            tt = re.search(r'begin="([^"]*).*end="([^"]*).*>([^<]*).', tt)
                            subtext = tt.group(3)
                            for ec in escape_chars:
                                subtext = subtext.replace(ec[0], ec[1])
                            if tt:
                                num += 1
                                srt.write('%s\n%s --> %s\n%s\n\n' % (num, tt.group(1), tt.group(2), subtext))
            if 0 == len(content):
                Log('Unable to download %s' % subDisplayLang)
            else:
                subs.append(srtfile)
        return subs

    HostSet = g.addon.getSetting("pref_host")
    subUrls = []

    if not suc:
        return False, data

    if retmpd:
        subUrls = _ParseSubs(data)

    if 'audioVideoUrls' in data.keys():
        hosts = data['audioVideoUrls']['avCdnUrlSets']
    elif 'playbackUrls' in data.keys():
        defid = data['playbackUrls']['defaultUrlSetId']
        h_dict = data['playbackUrls']['urlSets']
        '''
        failover = h_dict[defid]['failover']
        defid_dis = [failover[k]['urlSetId'] for k in failover if failover[k]['mode'] == 'discontinuous']
        defid = defid_dis[0] if defid_dis else defid
        '''
        hosts = [h_dict[k] for k in h_dict]
        hosts.insert(0, h_dict[defid])

    while hosts:
        for cdn in hosts:
            prefHost = False if HostSet not in str(hosts) or HostSet == 'Auto' else HostSet
            cdn_item = cdn

            if 'urls' in cdn:
                cdn = cdn['urls']['manifest']
            if prefHost and prefHost not in cdn['cdn']:
                continue
            Log('Using Host: ' + cdn['cdn'])

            urlset = cdn['avUrlInfoList'][0] if 'avUrlInfoList' in cdn else cdn

            data = getURL(urlset['url'], rjson=False, check=retmpd)
            if not data:
                hosts.remove(cdn_item)
                Log('Host not reachable: ' + cdn['cdn'])
                continue

            return (urlset['url'], subUrls) if retmpd else (True, extrFr(data))

    return False, getString(30217)


def PlayVideo(name, asin, adultstr, trailer, forcefb=0):
    from common import Globals, Settings
    g = Globals()
    s = Settings()

    def _playDummyVid():
        dummy_video = OSPJoin(g.PLUGIN_PATH, 'resources', 'dummy.avi')
        xbmcplugin.setResolvedUrl(g.pluginhandle, True, xbmcgui.ListItem(path=dummy_video))
        Log('Playing Dummy Video', Log.DEBUG)
        xbmc.Player().stop()
        return

    def _ExtPlayback(videoUrl, asin, isAdult, method, fr):
        waitsec = int(g.addon.getSetting("clickwait")) * 1000
        waitprepin = int(g.addon.getSetting("waitprepin")) * 1000
        pin = g.addon.getSetting("pin")
        waitpin = int(g.addon.getSetting("waitpin")) * 1000
        pininput = g.addon.getSetting("pininput") == 'true'
        fullscr = g.addon.getSetting("fullscreen") == 'true'
        videoUrl += '&playerDebug=true' if s.verbLog else ''

        xbmc.Player().stop()
        xbmc.executebuiltin('ActivateWindow(busydialog)')

        suc, url = getCmdLine(videoUrl, asin, method, fr)
        if not suc:
            g.dialog.notification(getString(30203), url, xbmcgui.NOTIFICATION_ERROR)
            return

        Log('Executing: %s' % url)
        if g.platform & g.OS_WINDOWS:
            process = subprocess.Popen(url, startupinfo=getStartupInfo())
        else:
            args = shlex.split(url)
            process = subprocess.Popen(args)
            if g.platform & g.OS_LE:
                result = 1
                while result != 0:
                    p = subprocess.Popen('pgrep chrome > /dev/null', shell=True)
                    p.wait()
                    result = p.returncode

        if isAdult and pininput:
            if fullscr:
                waitsec *= 0.75
            else:
                waitsec = waitprepin
            xbmc.sleep(int(waitsec))
            Input(keys=pin)
            waitsec = waitpin

        if fullscr:
            xbmc.sleep(int(waitsec))
            if s.browser != 0:
                Input(keys='f')
            else:
                Input(mousex=-1, mousey=350, click=2)
                xbmc.sleep(500)
                Input(mousex=9999, mousey=350)

        Input(mousex=9999, mousey=-1)

        xbmc.executebuiltin('Dialog.Close(busydialog)')
        if hasExtRC:
            return

        myWindow = window(process, asin)
        myWindow.wait()

    def _AndroidPlayback(asin, trailer):
        manu = ''
        if os.access('/system/bin/getprop', os.X_OK):
            manu = check_output(['getprop', 'ro.product.manufacturer'])

        if manu == 'Amazon':
            pkg = 'com.fivecent.amazonvideowrapper'
            act = ''
            url = asin
        else:
            pkg = 'com.amazon.avod.thirdpartyclient'
            act = 'android.intent.action.VIEW'
            url = g.BaseUrl + '/piv-apk-play?asin=' + asin
            url += '&playTrailer=T' if trailer == 1 else ''

        subprocess.Popen(['log', '-p', 'v', '-t', 'Kodi-Amazon', 'Manufacturer: ' + manu])
        subprocess.Popen(['log', '-p', 'v', '-t', 'Kodi-Amazon', 'Starting App: %s Video: %s' % (pkg, url)])
        Log('Manufacturer: %s' % manu)
        Log('Starting App: %s Video: %s' % (pkg, url))

        if s.verbLog:
            if os.access('/system/xbin/su', os.X_OK) or os.access('/system/bin/su', os.X_OK):
                Log('Logcat:\n' + check_output(['su', '-c', 'logcat -d | grep -i com.amazon.avod']))
            Log('Properties:\n' + check_output(['sh', '-c', 'getprop | grep -iE "(ro.product|ro.build|google)"']))

        xbmc.executebuiltin('StartAndroidActivity("%s", "%s", "", "%s")' % (pkg, act, url))

    def _IStreamPlayback(asin, name, trailer, isAdult, extern):
        from resources.lib.ages import AgeRestrictions
        vMT = ['Feature', 'Trailer', 'LiveStreaming'][trailer]
        dRes = 'PlaybackUrls' if trailer == 2 else 'PlaybackUrls,SubtitleUrls,ForcedNarratives'
        mpaa_str = AgeRestrictions().GetRestrictedAges() + getString(30171)
        drm_check = g.addon.getSetting("drm_check") == 'true'
        inputstream_helper = Helper('mpd', drm='com.widevine.alpha')

        if not inputstream_helper.check_inputstream():
            Log('No Inputstream Addon found or activated')
            _playDummyVid()
            return True

        cookie = MechanizeLogin()
        if not cookie:
            g.dialog.notification(getString(30203), getString(30200), xbmcgui.NOTIFICATION_ERROR)
            Log('Login error at playback')
            _playDummyVid()
            return True

        mpd, subs = ParseStreams(*getURLData('catalog/GetPlaybackResources', asin, extra=True, vMT=vMT, dRes=dRes, useCookie=cookie), retmpd=True)

        cj_str = ';'.join(['%s=%s' % (k, v) for k, v in cookie.items()])
        opt = '|Content-Type=application%2Fx-www-form-urlencoded&Cookie=' + quote_plus(cj_str)
        opt += '|widevine2Challenge=B{SSM}&includeHdcpTestKeyInLicense=true'
        opt += '|JBlicense;hdcpEnforcementResolutionPixels'
        licURL = getURLData('catalog/GetPlaybackResources', asin, opt=opt, extra=True, vMT=vMT, dRes='Widevine2License', retURL=True)

        if not mpd:
            g.dialog.notification(getString(30203), subs, xbmcgui.NOTIFICATION_ERROR)
            _playDummyVid()
            return True

        from xbmcaddon import Addon as KodiAddon
        is_version = KodiAddon(g.is_addon).getAddonInfo('version') if g.is_addon else '0'
        is_binary = xbmc.getCondVisibility('System.HasAddon(kodi.binary.instance.inputstream)')

        if trailer != 2:
            mpd = re.sub(r'~', '', mpd)

        if drm_check and (not g.platform & g.OS_ANDROID) and (not is_binary):
            mpdcontent = getURL(mpd, useCookie=cookie, rjson=False)
            if 'avc1.4D00' in mpdcontent:
                xbmc.executebuiltin('ActivateWindow(busydialog)')
                return extrFr(mpdcontent)

        Log(mpd, Log.DEBUG)

        if (not extern) or g.UsePrimeVideo:
            mpaa_check = _getListItem('MPAA') in mpaa_str or isAdult
            title = _getListItem('Label')
            thumb = _getListItem('Art(season.poster)')
            if not thumb:
                thumb = _getListItem('Art(tvshow.poster)')
                if not thumb:
                    thumb = _getListItem('Art(thumb)')
        else:
            content = getATVData('GetASINDetails', 'ASINList=' + asin)['titles'][0]
            ct, Info = getInfos(content, False)
            title = Info['DisplayTitle']
            thumb = Info.get('Poster', Info['Thumb'])
            mpaa_check = str(Info.get('MPAA', mpaa_str)) in mpaa_str or isAdult

        if trailer == 1:
            title += ' (Trailer)'
            Info = {'Plot': _getListItem('Plot')}
        if not title:
            title = name

        if mpaa_check and not RequestPin():
            return True

        listitem = xbmcgui.ListItem(label=title, path=mpd)

        if extern or trailer == 1:
            listitem.setInfo('video', getInfolabels(Info))

        if 'adaptive' in g.is_addon:
            listitem.setProperty('inputstream.adaptive.manifest_type', 'mpd')

        Log('Using %s Version: %s' % (g.is_addon, is_version))
        listitem.setArt({'thumb': thumb})
        listitem.setSubtitles(subs)
        listitem.setProperty('%s.license_type' % g.is_addon, 'com.widevine.alpha')
        listitem.setProperty('%s.license_key' % g.is_addon, licURL)
        listitem.setProperty('%s.stream_headers' % g.is_addon, 'user-agent=' + getConfig('UserAgent'))
        listitem.setProperty('inputstreamaddon', g.is_addon)
        listitem.setMimeType('application/dash+xml')
        listitem.setContentLookup(False)
        xbmc.executebuiltin('Dialog.Close(busydialog)')
        player = _AmazonPlayer()
        player.extern = extern
        player.asin = asin
        player.url = mpd
        player.cookie = cookie
        player.resolve(listitem)
        starttime = time.time()

        while not xbmc.abortRequested and player.running:
            if player.isPlayingVideo():
                player.video_lastpos = player.getTime()
                if time.time() > starttime + player.interval:
                    starttime = time.time()
                    player.updateStream('PLAY')
            sleep(1)

        del player
        return True

    isAdult = adultstr == '1'
    amazonUrl = g.BaseUrl + "/dp/" + (name if g.UsePrimeVideo else asin)
    playable = False
    fallback = int(g.addon.getSetting("fallback_method"))
    methodOW = fallback - 1 if forcefb and fallback else s.playMethod
    videoUrl = "%s/?autoplay=%s" % (amazonUrl, ('trailer' if trailer == 1 else '1'))
    extern = not xbmc.getInfoLabel('Container.PluginName').startswith('plugin.video.amazon')
    fr = ''

    if extern:
        Log('External Call', Log.DEBUG)

    while not playable:
        playable = True

        if methodOW == 2 and g.platform & g.OS_ANDROID:
            _AndroidPlayback(asin, trailer)
        elif methodOW == 3:
            playable = _IStreamPlayback(asin, name, trailer, isAdult, extern)
        elif not g.platform & g.OS_ANDROID:
            _ExtPlayback(videoUrl, asin, isAdult, methodOW, fr)

        if not playable or isinstance(playable, unicode):
            if fallback:
                methodOW = fallback - 1
                if isinstance(playable, unicode):
                    fr = playable
                    playable = False
            else:
                xbmc.sleep(500)
                g.dialog.ok(getString(30203), getString(30218))
                playable = True

    if methodOW != 3:
        _playDummyVid()


class _AmazonPlayer(xbmc.Player):
    def __init__(self):
        super(_AmazonPlayer, self).__init__()
        self._g = Globals()
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
            xbmcplugin.setResolvedUrl(self._g.pluginhandle, True, xbmcgui.ListItem())
            xbmc.executebuiltin('Container.Refresh')
            return
        self.running = True
        xbmcplugin.setResolvedUrl(self._g.pluginhandle, True, li)
        self.PlayerInfo('Starting Playback')
        if self.seek:
            self.seekTime(self.seek)
            self.PlayerInfo('Resuming Playback')

        self.updateStream('START')
        Log('Video ContentType Movie? %s' % xbmc.getCondVisibility('VideoPlayer.Content(movies)'), Log.DEBUG)
        Log('Video ContentType Episode? %s' % xbmc.getCondVisibility('VideoPlayer.Content(episodes)'), Log.DEBUG)

    def checkResume(self):
        self.dbid = int('0' + _getListItem('DBID'))
        Log(self.dbid, Log.DEBUG)
        if not self.dbid:
            return True
        dbtype = _getListItem('DBTYPE')
        result = jsonRPC('VideoLibrary.Get%sDetails' % dbtype, 'resume,playcount', {'%sid' % dbtype: self.dbid})
        position = int(result['episodedetails']['resume']['position'])
        playcount = int(result['episodedetails']['playcount'])
        Log(result, Log.DEBUG)

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
        suc, msg = getURLData('usage/UpdateStream', self.asin, useCookie=self.cookie, opt='&event=%s&timecode=%s' % (event, self.video_lastpos))
        if suc and 'statusCallbackIntervalSeconds' in str(msg):
            self.interval = msg['message']['body']['statusCallbackIntervalSeconds']

    def finished(self):
        self.updateStream('STOP')
        if self.extern:
            playcount = 1 if (self.video_lastpos * 100) / self.video_totaltime >= 90 else 0
            watched = _getListItem('PlayCount')
            if self.dbid:
                dbtype = _getListItem('DBTYPE')
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
