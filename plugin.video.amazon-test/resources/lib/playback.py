#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from kodi_six import xbmcplugin
from kodi_six.utils import py2_decode
import os
import shlex
import subprocess
import threading
from inputstreamhelper import Helper
from .network import *
from .common import Globals, Settings, jsonRPC, sleep
from .itemlisting import getInfolabels
try:
    from urllib.parse import quote_plus
except:
    from urllib import quote_plus


def _getListItem(li):
    return py2_decode(xbmc.getInfoLabel('ListItem.%s' % li))


def _Input(mousex=0, mousey=0, click=0, keys=None, delay='0.2'):
    import pyautogui
    '''Control the user's mouse and/or keyboard.
       Arguments:
         mousex, mousey - x, y co-ordinates from top left of screen
         keys - list of keys to press or single key
    '''
    g = Globals()
    screenWidth, screenHeight = pyautogui.size()
    mousex = int(screenWidth / 2) if mousex == -1 else mousex
    mousey = int(screenHeight / 2) if mousey == -1 else mousey
    exit_cmd = [('alt', 'f4'), ('ctrl', 'shift', 'q'), ('command', 'q')][(g.platform & -g.platform).bit_length() - 1]

    if keys:
        if '{EX}' in keys:
            pyautogui.hotkey(*exit_cmd)
        else:
            pyautogui.press(keys, interval=delay)
    else:
        pyautogui.moveTo(mousex, mousey)
        if click:
            pyautogui.click(clicks=click)

    Log('Input command: Mouse(x={}, y={}, click={}), Keyboard({})'.format(mousex, mousey, click, keys))


def PlayVideo(name, asin, adultstr, streamtype, forcefb=0):
    g = Globals()
    s = Settings()

    def _check_output(*popenargs, **kwargs):
        p = subprocess.Popen(stdout=subprocess.PIPE, stderr=subprocess.STDOUT, *popenargs, **kwargs)
        out, err = p.communicate()
        retcode = p.poll()
        if retcode != 0:
            c = kwargs.get("args")
            if c is None:
                c = popenargs[0]
                e = subprocess.CalledProcessError(retcode, c)
                e.output = str(out) + str(err)
                Log(e, Log.ERROR)
        return out.strip()

    def _playDummyVid():
        dummy_video = OSPJoin(g.PLUGIN_PATH, 'resources', 'art', 'dummy.avi')
        xbmcplugin.setResolvedUrl(g.pluginhandle, True, xbmcgui.ListItem(path=dummy_video))
        Log('Playing Dummy Video', Log.DEBUG)
        xbmc.Player().stop()
        return

    def _extrFr(data):
        fps_string = re.compile('frameRate="([^"]*)').findall(data)[0]
        fr = round(eval(fps_string + '.0'), 3)
        return str(fr).replace('.0', '')

    def _ParseStreams(suc, data, retmpd=False, bypassproxy=False):
        g = Globals()
        s = Settings()

        HostSet = g.addon.getSetting("pref_host")
        subUrls = []

        if not suc:
            return False, data, None

        timecodes = data.get('transitionTimecodes', {})

        if retmpd and ('subtitles' in data):
            subUrls = [sub['url'] for sub in data['subtitles'] if 'url' in sub.keys()]

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

                returl = urlset['url'] if bypassproxy else 'http://{}/mpd/{}'.format(s.proxyaddress, quote_plus(urlset['url']))
                return (returl, subUrls, timecodes) if retmpd else (True, _extrFr(data), None)

        return False, getString(30217), None

    def _getCmdLine(videoUrl, asin, method, fr):
        scr_path = g.addon.getSetting("scr_path")
        br_path = g.addon.getSetting("br_path").strip()
        scr_param = g.addon.getSetting("scr_param").strip()
        kiosk = g.addon.getSetting("kiosk") == 'true'
        appdata = g.addon.getSetting("ownappdata") == 'true'
        cust_br = g.addon.getSetting("cust_path") == 'true'
        nobr_str = getString(30198)
        frdetect = g.addon.getSetting("framerate") == 'true'

        if method == 1:
            if not xbmcvfs.exists(scr_path):
                return False, nobr_str

            if frdetect:
                suc, fr = _ParseStreams(*getURLData('catalog/GetPlaybackResources', asin, extra=True, useCookie=True))[:2] if not fr else (True, fr)
                if not suc:
                    return False, fr
            else:
                fr = ''

            return True, scr_path + ' ' + scr_param.replace('{f}', fr).replace('{u}', videoUrl)

        br_platform = (g.platform & -g.platform).bit_length()
        os_paths = [None, ('C:\\Program Files\\', 'C:\\Program Files (x86)\\'), ('/usr/bin/', '/usr/local/bin/'), 'open -a '][br_platform]

        # path(0,win,lin,osx), kiosk, profile, args
        br_config = [[(None, ['Internet Explorer\\iexplore.exe'], '', ''), '-k ', '', ''],
                     [(None, ['Google\\Chrome\\Application\\chrome.exe'],
                       ['google-chrome', 'google-chrome-stable', 'google-chrome-beta', 'chromium-browser'], '"/Applications/Google Chrome.app"'),
                      '--kiosk ', '--user-data-dir=',
                      '--start-maximized --disable-translate --disable-new-tab-first-run --no-default-browser-check --no-first-run '],
                     [(None, ['Mozilla Firefox\\firefox.exe'], ['firefox'], 'firefox'), '', '-profile ', ''],
                     [(None, ['Safari\\Safari.exe'], '', 'safari'), '', '', '']]

        if not cust_br:
            br_path = ''

        if (not g.platform & g.OS_OSX) and (not cust_br):
            for path in os_paths:
                for exe_file in br_config[s.browser][0][br_platform]:
                    if xbmcvfs.exists(OSPJoin(path, exe_file)):
                        br_path = path + exe_file
                        break
                    else:
                        Log('Browser %s not found' % (path + exe_file), Log.DEBUG)
                if br_path:
                    break

        if (not xbmcvfs.exists(br_path)) and (not g.platform & g.OS_OSX):
            return False, nobr_str

        br_args = br_config[s.browser][3]
        if kiosk:
            br_args += br_config[s.browser][1]
        if appdata and br_config[s.browser][2]:
            br_args += br_config[s.browser][2] + '"' + OSPJoin(g.DATA_PATH, str(s.browser)) + '" '

        if g.platform & g.OS_OSX:
            if not cust_br:
                br_path = os_paths + br_config[s.browser][0][3]
            if br_args.strip():
                br_args = '--args ' + br_args

        br_path += ' %s"%s"' % (br_args, videoUrl)

        return True, br_path

    def _getStartupInfo():
        si = subprocess.STARTUPINFO()
        si.dwFlags = subprocess.STARTF_USESHOWWINDOW
        return si

    def _ExtPlayback(videoUrl, asin, isAdult, method, fr):
        waitsec = int(g.addon.getSetting("clickwait"))
        waitprepin = int(g.addon.getSetting("waitprepin"))
        pin = g.addon.getSetting("pin")
        waitpin = int(g.addon.getSetting("waitpin"))
        pininput = g.addon.getSetting("pininput") == 'true'
        fullscr = g.addon.getSetting("fullscreen") == 'true'
        videoUrl += '&playerDebug=true' if s.verbLog else ''

        xbmc.Player().stop()
        # xbmc.executebuiltin('ActivateWindow(busydialog)')

        suc, url = _getCmdLine(videoUrl, asin, method, fr)
        if not suc:
            g.dialog.notification(getString(30203), url, xbmcgui.NOTIFICATION_ERROR)
            return

        Log('Executing: %s' % url)
        if g.platform & g.OS_WINDOWS:
            process = subprocess.Popen(url, startupinfo=_getStartupInfo())
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
            sleep(waitsec)
            _Input(keys=list(pin))
            waitsec = waitpin

        if fullscr:
            sleep(waitsec)
            if s.browser != 0:
                _Input(keys='f')
            else:
                _Input(mousex=-1, mousey=350, click=2)
                xbmc.sleep(500)

        _Input(mousex=9999, mousey=-1)

        # xbmc.executebuiltin('Dialog.Close(busydialog)')
        if s.hasExtRC:
            return

        myWindow = _window(process, asin)
        myWindow.wait()

    def _AndroidPlayback(asin, streamtype):
        manu = avodapp = ''
        if os.access('/system/bin/getprop', os.X_OK):
            manu = _check_output(['getprop', 'ro.product.manufacturer']).lower()
            avodapp = _check_output(['cmd', 'package', 'list', 'packages', 'com.amazon.avod.thirdpartyclient'])

        if manu == 'amazon':
            pkg = 'com.fivecent.amazonvideowrapper'
            act = ''
            url = asin
        else:
            burl = g.BaseUrl.replace('www', 'app' if g.UsePrimeVideo else 'watch')
            gti = 'gti' if g.UsePrimeVideo else 'asin'
            pkg = 'com.amazon.avod.thirdpartyclient' if avodapp else 'com.amazon.amazonvideo.livingroom'
            act = 'android.intent.action.VIEW'
            url = '{}/watch?{}={}'.format(burl, gti, asin)
            if not g.UsePrimeVideo and avodapp:
                url = g.BaseUrl + '/piv-apk-play?asin=' + asin
                url += '&playTrailer=T' if streamtype == 1 else ''

        subprocess.Popen(['log', '-p', 'v', '-t', 'Kodi-Amazon', 'Manufacturer: ' + manu])
        subprocess.Popen(['log', '-p', 'v', '-t', 'Kodi-Amazon', 'Starting App: %s Video: %s' % (pkg, url)])
        Log('Manufacturer: %s' % manu)
        Log('Starting App: %s Video: %s' % (pkg, url))

        if s.verbLog:
            if os.access('/system/xbin/su', os.X_OK) or os.access('/system/bin/su', os.X_OK):
                Log('Logcat:\n' + _check_output(['su', '-c', 'logcat -d | grep -iE "(avod|amazonvideo)']))
            Log('Properties:\n' + _check_output(['sh', '-c', 'getprop | grep -iE "(ro.product|ro.build|google)"']))
            Log('Installed Amazon Packages:\n' + _check_output(['sh', '-c', 'cmd package list packages | grep -i amazon']))

        xbmc.executebuiltin('StartAndroidActivity("%s", "%s", "", "%s")' % (pkg, act, url))

    def _IStreamPlayback(asin, name, streamtype, isAdult, extern):
        from .ages import AgeRestrictions
        vMT = ['Feature', 'Trailer', 'LiveStreaming'][streamtype]
        dRes = 'PlaybackUrls' if streamtype == 2 else 'PlaybackUrls,SubtitleUrls,ForcedNarratives,TransitionTimecodes'
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

        mpd, subs, timecodes = _ParseStreams(*getURLData('catalog/GetPlaybackResources', asin, extra=True, vMT=vMT, dRes=dRes, useCookie=cookie,
                                                         proxyEndpoint='gpr'), retmpd=True, bypassproxy=s.bypassProxy or (streamtype == 2))

        if not mpd:
            g.dialog.notification(getString(30203), subs, xbmcgui.NOTIFICATION_ERROR)
            _playDummyVid()
            return True

        skip = timecodes.get('skipElements')
        Log(skip, Log.DEBUG)

        cj_str = ';'.join(['%s=%s' % (k, v) for k, v in cookie.items()])
        opt = '|Content-Type=application%2Fx-www-form-urlencoded&Cookie=' + quote_plus(cj_str)
        opt += '|widevine2Challenge=B{SSM}&includeHdcpTestKeyInLicense=true'
        opt += '|JBlicense;hdcpEnforcementResolutionPixels'
        licURL = getURLData('catalog/GetPlaybackResources', asin, opt=opt, extra=True, vMT=vMT, dRes='Widevine2License', retURL=True)

        from xbmcaddon import Addon as KodiAddon
        is_version = KodiAddon(g.is_addon).getAddonInfo('version') if g.is_addon else '0'
        is_binary = xbmc.getCondVisibility('System.HasAddon(kodi.binary.instance.inputstream)')

        if (not s.audioDescriptions) and (streamtype != 2):
            mpd = re.sub(r'(~|%7E)', '', mpd)

        if drm_check and (not g.platform & g.OS_ANDROID) and (not is_binary):
            mpdcontent = getURL(mpd, useCookie=cookie, rjson=False)
            if 'avc1.4D00' in mpdcontent:
                # xbmc.executebuiltin('ActivateWindow(busydialog)')
                return _extrFr(mpdcontent)

        Log(mpd, Log.DEBUG)

        if g.KodiK and extern:
            content = getATVData('GetASINDetails', 'ASINList=' + asin)['titles'][0]
            ct, Info = g.amz.getInfos(content, False)
            title = Info['DisplayTitle']
            thumb = Info.get('Poster', Info['Thumb'])
            mpaa_check = str(Info.get('MPAA', mpaa_str)) in mpaa_str or isAdult
        else:
            mpaa_check = _getListItem('MPAA') in mpaa_str + mpaa_str.replace(' ', '') or isAdult
            title = _getListItem('Label')
            thumb = _getListItem('Art(season.poster)')
            if not thumb:
                thumb = _getListItem('Art(tvshow.poster)')
                if not thumb:
                    thumb = _getListItem('Art(thumb)')

        if streamtype == 1:
            title += ' (Trailer)'
        if not title:
            title = name

        if mpaa_check and not AgeRestrictions().RequestPin():
            return True

        listitem = xbmcgui.ListItem(label=title, path=mpd)

        if g.KodiK and extern:
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
        player = _AmazonPlayer()
        player.asin = asin
        player.cookie = cookie
        player.content = streamtype
        player.extern = extern
        player.resolve(listitem)

        starttime = time.time()
        skip_button = _SkipButton()

        while (not g.monitor.abortRequested()) and player.running:
            if player.isPlayingVideo():
                player.video_lastpos = player.getTime()
                if time.time() > (starttime + player.interval):
                    starttime = time.time()
                    player.updateStream('PLAY')
                if skip and s.skip_scene > 0:
                    for elem in skip:
                        st_pos = elem.get('startTimecodeMs')
                        et_pos = (elem.get('endTimecodeMs') - st_pos) * 0.9 + st_pos
                        btn_type = elem.get('elementType')
                        if st_pos <= (player.video_lastpos * 1000) <= et_pos:
                            skip_button.display(elem)
                        elif skip_button.act_btn == btn_type:
                            skip_button.hide()
            g.monitor.waitForAbort(1)
        skip_button.hide()
        player.finished()
        del player, skip_button
        return True

    isAdult = adultstr == '1'
    amazonUrl = g.BaseUrl + "/dp/" + (name if g.UsePrimeVideo else asin)
    playable = False
    fallback = int(g.addon.getSetting("fallback_method"))
    uhdFB = forcefb < 0 and s.uhdAndroid
    methodOW = fallback - 1 if forcefb > 0 and fallback else s.playMethod
    videoUrl = "%s/?autoplay=%s" % (amazonUrl, ('trailer' if streamtype == 1 else '1'))
    extern = not xbmc.getInfoLabel('Container.PluginName').startswith('plugin.video.amazon')
    fr = ''

    if extern:
        Log('External Call', Log.DEBUG)

    while not playable:
        playable = True

        if (methodOW == 2 or uhdFB) and g.platform & g.OS_ANDROID:
            _AndroidPlayback(asin, streamtype)
        elif methodOW == 3:
            playable = _IStreamPlayback(asin, name, streamtype, isAdult, extern)
        elif not g.platform & g.OS_ANDROID:
            _ExtPlayback(videoUrl, asin, isAdult, methodOW, fr)

        if not playable or not isinstance(playable, bool):
            if fallback:
                methodOW = fallback - 1
                if not isinstance(playable, bool):
                    fr = playable
                    playable = False
            else:
                xbmc.sleep(500)
                g.dialog.ok(getString(30203), getString(30218))
                playable = True

    if methodOW != 3:
        _playDummyVid()


class _window(xbmcgui.WindowDialog):
    def __init__(self, process, asin):
        xbmcgui.WindowDialog.__init__(self)
        self._stopEvent = threading.Event()
        self._pbStart = time.time()
        self._wakeUpThread = threading.Thread(target=self._wakeUpThreadProc, args=(process,))
        self._vidDur = self.getDuration(asin)

    @staticmethod
    def _SetVol(step):
        vol = jsonRPC('Application.GetProperties', 'volume')
        xbmc.executebuiltin('SetVolume(%d,showVolumeBar)' % (vol + step))

    def _wakeUpThreadProc(self, process):
        starttime = time.time()
        while not self._stopEvent.is_set():
            if time.time() > starttime + 60:
                starttime = time.time()
                xbmc.executebuiltin("playercontrol(wakeup)")
            if process:
                process.poll()
                if process.returncode is not None:
                    self.close()
            self._stopEvent.wait(1)

    def wait(self):
        Log('Starting Thread')
        self._wakeUpThread.start()
        self.doModal()
        self._wakeUpThread.join()

    @staticmethod
    def getDuration(asin):
        li_dur = xbmc.getInfoLabel('ListItem.Duration')
        if li_dur:
            if ':' in li_dur:
                return sum(i * int(t) for i, t in zip([3600, 60, 1], li_dur.split(":")))
            return int(li_dur) * 60
        else:
            content = getATVData('GetASINDetails', 'ASINList=' + asin)['titles'][0]
            ct, Info = g.amz.getInfos(content, False)
            return int(Info.get('Duration', 0))

    def close(self):
        Log('Stopping Thread')
        self._stopEvent.set()
        xbmcgui.WindowDialog.close(self)
        watched = xbmc.getInfoLabel('Listitem.PlayCount')
        pBTime = time.time() - self._pbStart
        Log('Dur:%s State:%s PlbTm:%s' % (self._vidDur, watched, pBTime), Log.DEBUG)

        if pBTime > self._vidDur * 0.9 and not watched:
            xbmc.executebuiltin("Action(ToggleWatched)")

    def onAction(self, action):
        if not s.useIntRC:
            return

        ACTION_SELECT_ITEM = 7
        ACTION_PARENT_DIR = 9
        ACTION_PREVIOUS_MENU = 10
        ACTION_PAUSE = 12
        ACTION_STOP = 13
        ACTION_SHOW_INFO = 11
        ACTION_SHOW_GUI = 18
        ACTION_MOVE_LEFT = 1
        ACTION_MOVE_RIGHT = 2
        ACTION_MOVE_UP = 3
        ACTION_MOVE_DOWN = 4
        ACTION_PLAYER_PLAY = 79
        ACTION_NAV_BACK = 92
        KEY_BUTTON_BACK = 275
        ACTION_MOUSE_MOVE = 107

        actionId = action.getId()
        showinfo = action == ACTION_SHOW_INFO
        Log('Action: Id:%s ButtonCode:%s' % (actionId, action.getButtonCode()))

        if action in [ACTION_SHOW_GUI, ACTION_STOP, ACTION_PARENT_DIR, ACTION_PREVIOUS_MENU, ACTION_NAV_BACK,
                      KEY_BUTTON_BACK, ACTION_MOUSE_MOVE]:
            _Input(keys='{EX}')
        elif action in [ACTION_SELECT_ITEM, ACTION_PLAYER_PLAY, ACTION_PAUSE]:
            _Input(keys='space')
            showinfo = True
        elif action == ACTION_MOVE_LEFT:
            _Input(keys='left')
            showinfo = True
        elif action == ACTION_MOVE_RIGHT:
            _Input(keys='right')
            showinfo = True
        elif action == ACTION_MOVE_UP:
            self._SetVol(+2) if s.RMC_vol else _Input(keys='up')
        elif action == ACTION_MOVE_DOWN:
            self._SetVol(-2) if s.RMC_vol else _Input(keys='down')
        # numkeys for pin input
        elif 57 < actionId < 68:
            strKey = str(actionId - 58)
            _Input(keys=strKey)

        if showinfo:
            _Input(9999, 0)
            xbmc.sleep(500)
            _Input(9999, -1)


class _AmazonPlayer(xbmc.Player):
    def __init__(self):
        super(_AmazonPlayer, self).__init__()
        self._g = Globals()
        self.sleeptm = 0.2
        self.video_lastpos = 0
        self.video_totaltime = 0
        self.dbid = 0
        self.asin = ''
        self.cookie = None
        self.interval = 180
        self.running = False
        self.extern = False
        self.resume = 0
        self.watched = 0
        self.content = 0
        self.resumedb = OSPJoin(g.DATA_PATH, 'resume.db')

    def resolve(self, li):
        if self.extern and not self.checkResume():
            xbmcplugin.setResolvedUrl(self._g.pluginhandle, True, xbmcgui.ListItem())
            xbmc.executebuiltin('Container.Refresh')
            return
        if self.resume:
            li.setProperty('resumetime', str(self.resume))
            li.setProperty('totaltime', '1')
            Log('Resuming Video at %s' % self.resume)

        xbmcplugin.setResolvedUrl(self._g.pluginhandle, True, li)
        self.running = True
        self.getTimes('Starting Playback')
        self.updateStream('START')

    def checkResume(self):
        self.dbid = int('0' + _getListItem('DBID'))
        Log(self.dbid)
        if self.dbid:
            dbtype = _getListItem('DBTYPE')
            result = jsonRPC('VideoLibrary.Get%sDetails' % dbtype, 'resume,playcount', {'%sid' % dbtype: self.dbid})
            self.resume = int(result[dbtype.lower() + 'details']['resume']['position'])
            self.watched = int(result[dbtype.lower() + 'details']['playcount'])
        if self.watched:
            self.resume = 0
            return True
        if not self.resume:
            self.getResumePoint()
        if self.resume > 180 and self.extern:
            Log('Displaying Resumedialog')
            res_string = getString(12022).replace("%s", "{}") if g.KodiK else getString(12022)
            sel = g.dialog.contextmenu([res_string.format(time.strftime("%H:%M:%S", time.gmtime(self.resume))), getString(12021)])
            if sel > -1:
                self.resume = self.resume if sel == 0 else 0
            else:
                return False
        return True

    def getResumePoint(self):
        from codecs import open as co
        if not xbmcvfs.exists(self.resumedb) or self.content == 2:
            return {}
        with co(self.resumedb, 'rb') as fp:
            try:
                items = pickle.load(fp)
            except (KeyError, pickle.UnpicklingError):
                items = {}
            self.resume = items.get(self.asin, {}).get('resume', 0)
            fp.close()
        return items

    def saveResumePoint(self):
        from codecs import open as co
        if self.content == 2:
            return
        items = self.getResumePoint()
        with co(self.resumedb, 'wb+') as fp:
            if self.watched and self.asin in items.keys():
                del items[self.asin]
            else:
                items.update({self.asin: {'resume': self.video_lastpos}})
            pickle.dump(items, fp, 2)
            fp.close()

    def onPlayBackEnded(self):
        self.finished()

    def onPlayBackStopped(self):
        self.finished()

    def updateStream(self, event):
        suc, msg = getURLData('usage/UpdateStream', self.asin, useCookie=self.cookie, opt='&event=%s&timecode=%s' %
                              (event, self.video_lastpos))
        if suc and 'statusCallbackIntervalSeconds' in str(msg):
            self.interval = msg['message']['body']['statusCallbackIntervalSeconds']

    def finished(self):
        self.updateStream('STOP')
        if self.running:
            self.running = False
            if self.video_lastpos > 0 and self.video_totaltime > 0:
                self.watched = 1 if (self.video_lastpos * 100) / self.video_totaltime >= 90 else 0
                if self.video_lastpos > 180 and not g.UsePrimeVideo:
                    g.amz.updateRecents(self.asin)
                if self.dbid and g.KodiK:
                    dbtype = _getListItem('DBTYPE')
                    params = {'%sid' % dbtype: self.dbid,
                              'resume': {'position': 0 if self.watched else self.video_lastpos,
                                         'total': self.video_totaltime},
                              'playcount': self.watched}
                    res = '' if 'OK' in jsonRPC('VideoLibrary.Set%sDetails' % dbtype, '', params) else 'NOT '
                    Log('%sUpdated %sid(%s) with: pos(%s) total(%s) playcount(%s)' % (res, dbtype, self.dbid, self.video_lastpos,
                                                                                      self.video_totaltime, self.watched))
                self.saveResumePoint()

    def getTimes(self, msg):
        while self.video_totaltime <= 0:
            sleep(self.sleeptm)
            if self.isPlaying() and self.getTotalTime() >= self.getTime() >= 0:
                self.video_totaltime = self.getTotalTime()
                self.video_lastpos = self.getTime()
        Log('%s: %s/%s' % (msg, self.video_lastpos, self.video_totaltime))


class _SkipButton(xbmcgui.WindowDialog):
    def __init__(self):
        super(_SkipButton, self).__init__()
        x = self.getWidth() - 550
        y = self.getHeight() - 70
        self.skip_button = xbmcgui.ControlButton(x, y, width=500, height=30, label='', textColor='0xFFFFFFFF', focusedColor='0xFFFFA500', disabledColor='0xFFFFA500',
                                                 shadowColor='0xFF000000', focusTexture='', noFocusTexture='', alignment=1, font='font14')
        self.act_btn = ''
        self.btn_list = ('SHOW', 'INTRO', 'RECAP', 'INTRO_RECAP')
        self.seek_time = 0
        self.player = _AmazonPlayer()

    @staticmethod
    def has_seek_bug():
        ver = jsonRPC('JSONRPC.Version')['version']
        return list(ver.values()) < [11, 7, 0]

    def display(self, elem):
        if self.act_btn == '' and xbmcgui.getCurrentWindowId() in (12005, 12901):
            self.seek_time = int(elem.get('endTimecodeMs') / 1000) - 4
            self.act_btn = elem.get('elementType')
            autoskip = self.act_btn in self.btn_list[s.skip_scene - 1]
            langid = 30195 if autoskip else self.btn_list.index(self.act_btn) + 30192
            self.addControl(self.skip_button)
            self.skip_button.setEnabled(autoskip is False)
            self.skip_button.setLabel(getString(langid))
            self.skip_button.setVisible(True)
            self.setFocus(self.skip_button)
            self.show()
            if autoskip:
                sleep(1)
                self.skipScene(1000)

    def hide(self):
        if self.skip_button.getId() > 0:
            self.removeControl(self.skip_button)
        self.act_btn = ''
        self.seek_time = 0
        self.close()

    def onControl(self, control):
        if control.getId() == self.skip_button.getId() and self.player.isPlayingVideo():
            self.skipScene()

    def skipScene(self, wait=0):
        # Workaround for bug in Kodi/ISA:
        #   Jumping to a specfic/absolute time results in asynchronus subtitles timings. Seeking forward/backwards didn't have this issue.
        #   But just seeking forwards isn't possible, values lower 60 will be threated as absolut values.
        #   Avoid this by jumping additionally to start with values lower 60.
        tc = int(self.seek_time - self.player.getTime())
        Log('Seeking to (+4): {}sec / seek incr {}sec / cur pos {}sec'.format(self.seek_time, tc, self.player.getTime()), Log.DEBUG)
        seek_back = True if 60 - tc > 0 and self.has_seek_bug() else False  # seeking forward fixed since JSON-RPC v11.7.0
        if seek_back:
            tc = self.seek_time
            self.player.pause()
            jsonRPC('Player.Seek', param={'playerid': 1, 'value': 0})
            sleep(0.75)
        jsonRPC('Player.Seek', param={'playerid': 1, 'value': {'seconds': tc}})
        sleep(0.75)
        if seek_back:
            self.player.pause()
        Log('Position: {}'.format(self.player.getTime()), Log.DEBUG)
        xbmc.sleep(wait)
        self.hide()

    def onAction(self, action):
        if action in [xbmcgui.ACTION_PREVIOUS_MENU, xbmcgui.ACTION_NAV_BACK]:
            self.close()
