#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import os
import re
import pickle
import shlex
import subprocess
import threading
import time
from copy import deepcopy
from os.path import join as OSPJoin

from inputstreamhelper import Helper
from kodi_six import xbmc, xbmcgui, xbmcvfs, xbmcplugin
from kodi_six.utils import py2_decode

from .common import Globals, Settings, jsonRPC, sleep, MechanizeLogin, findKey
from .logging import Log
from .configs import getConfig
from .network import getURL, getURLData, getATVData, GrabJSON
from .l10n import getString

try:
    from urllib.parse import quote_plus, urlencode
except ImportError:
    from urllib import quote_plus, urlencode

_g = Globals()
_s = Settings()


def _playDummyVid():
    if not hasattr(_playDummyVid, 'played'):
        dummy_video = OSPJoin(_g.PLUGIN_PATH, 'resources', 'art', 'dummy.wav')
        xbmcplugin.setResolvedUrl(_g.pluginhandle, True, xbmcgui.ListItem(path=dummy_video))
        Log('Playing Dummy Audio', Log.DEBUG)
    _playDummyVid.played = True
    return


def _getListItem(li):
    return py2_decode(xbmc.getInfoLabel('ListItem.%s' % li))


def _Input(mousex=0, mousey=0, click=0, keys=None, delay='0.2'):
    import pyautogui
    '''Control the user's mouse and/or keyboard.
       Arguments:
         mousex, mousey - x, y co-ordinates from top left of screen
         keys - list of keys to press or single key
    '''
    screenWidth, screenHeight = pyautogui.size()
    mousex = int(screenWidth / 2) if mousex == -1 else mousex
    mousey = int(screenHeight / 2) if mousey == -1 else mousey
    exit_cmd = [('alt', 'f4'), ('ctrl', 'shift', 'q'), ('command', 'q')][(_g.platform & -_g.platform).bit_length() - 1]

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
        return out.decode('utf-8').strip()

    def _extrFr(data):
        fps_string = re.compile('frameRate="([^"]*)').findall(data)[0]
        fr = round(eval(fps_string + '.0'), 3)
        return str(fr).replace('.0', '')

    def _ParseStreams(suc, data, retmpd=False, bypassproxy=False):
        HostSet = _s.pref_host
        subUrls = []
        hosts = []

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
            defid_dis = [h_dict[k]['urlSetId'] for k in h_dict if 'DUB' in h_dict[k]['urls']['manifest']['origin']]
            defid = defid_dis[0] if defid_dis else defid
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

                returl = urlset['url'] if bypassproxy else 'http://{}/mpd/{}'.format(_s.proxyaddress, quote_plus(urlset['url']))
                return (returl, subUrls, timecodes) if retmpd else (True, _extrFr(data), None)

        return False, getString(30217), None

    def _getCmdLine(videoUrl, asin):
        scr_path = _s.scr_path
        br_path = _s.br_path.strip()
        scr_param = _s.scr_param.strip()
        kiosk = _s.kiosk == 'true'
        appdata = _s.ownappdata == 'true'
        cust_br = _s.cust_path == 'true'
        nobr_str = getString(30198)
        frdetect = _s.framerate == 'true'

        if _s.playmethod == 1:
            if not xbmcvfs.exists(scr_path):
                return False, nobr_str

            if frdetect:
                suc, fr = _ParseStreams(*getURLData('catalog/GetPlaybackResources', asin, extra=True, useCookie=True))[:2]
                if not suc:
                    return False, fr
            else:
                fr = ''

            return True, scr_path + ' ' + scr_param.replace('{f}', fr).replace('{u}', videoUrl)

        br_platform = (_g.platform & -_g.platform).bit_length()
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

        if (not _g.platform & _g.OS_OSX) and (not cust_br):
            for path in os_paths:
                for exe_file in br_config[_s.browser][0][br_platform]:
                    if xbmcvfs.exists(OSPJoin(path, exe_file)):
                        br_path = path + exe_file
                        break
                    else:
                        Log('Browser %s not found' % (path + exe_file), Log.DEBUG)
                if br_path:
                    break

        if (not xbmcvfs.exists(br_path)) and (not _g.platform & _g.OS_OSX):
            return False, nobr_str

        br_args = br_config[_s.browser][3]
        if kiosk:
            br_args += br_config[_s.browser][1]
        if appdata and br_config[_s.browser][2]:
            br_args += br_config[_s.browser][2] + '"' + OSPJoin(_g.DATA_PATH, str(_s.browser)) + '" '

        if _g.platform & _g.OS_OSX:
            if not cust_br:
                br_path = os_paths + br_config[_s.browser][0][3]
            if br_args.strip():
                br_args = '--args ' + br_args

        br_path += ' %s"%s"' % (br_args, videoUrl)

        return True, br_path

    def _getStartupInfo():
        si = subprocess.STARTUPINFO()
        si.dwFlags = subprocess.STARTF_USESHOWWINDOW
        return si

    def _ExtPlayback(videoUrl, asin, isAdult):
        waitsec = int(_s.clickwait)
        waitprepin = int(_s.waitprepin)
        pin = _s.pin
        waitpin = _s.waitpin
        pininput = _s.pininput == 'true'
        fullscr = _s.fullscreen == 'true'
        videoUrl += '&playerDebug=true' if _s.logging else ''

        xbmc.Player().stop()
        # xbmc.executebuiltin('ActivateWindow(busydialog)')

        suc, url = _getCmdLine(videoUrl, asin)
        if not suc:
            _g.dialog.notification(getString(30203), url, xbmcgui.NOTIFICATION_ERROR)
            return

        Log('Executing: %s' % url)
        if _g.platform & _g.OS_WINDOWS:
            process = subprocess.Popen(url, startupinfo=_getStartupInfo())
        else:
            args = shlex.split(url)
            process = subprocess.Popen(args)
            if _g.platform & _g.OS_LE:
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
            if _s.browser != 0:
                _Input(keys='f')
            else:
                _Input(mousex=-1, mousey=350, click=2)
                xbmc.sleep(500)

        _Input(mousex=9999, mousey=-1)

        # xbmc.executebuiltin('Dialog.Close(busydialog)')
        if _s.hasExtRC:
            return

        myWindow = _window(process, asin)
        myWindow.wait()

    def _AndroidPlayback(asin, streamtype):
        manu = avodapp = ''
        if os.access('/system/bin/getprop', os.X_OK):
            manu = _check_output(['getprop', 'ro.product.manufacturer']).lower()
        if os.access('/system/bin/cmd', os.X_OK):
            avodapp = _check_output(['cmd', 'package', 'list', 'packages', 'com.amazon.avod.thirdpartyclient'])
        elif os.access('/system/bin/pm', os.X_OK):
            avodapp = _check_output(['sh', '-c', 'pm', 'list', 'packages', 'com.amazon.avod.thirdpartyclient'])

        if manu == 'amazon':
            pkg = 'com.fivecent.amazonvideowrapper'
            act = ''
            url = asin
        else:
            burl = _g.BaseUrl.replace('www', 'app' if _g.UsePrimeVideo else 'watch')
            gti = 'gti' if _g.UsePrimeVideo else 'asin'
            pkg = 'com.amazon.avod.thirdpartyclient' if avodapp else 'com.amazon.amazonvideo.livingroom'
            act = 'android.intent.action.VIEW'
            url = '{}/watch?{}={}'.format(burl, gti, asin)
            if not _g.UsePrimeVideo and avodapp:
                url = '%s/piv-apk-play?asin=%s%s' % (_g.BaseUrl, asin, '&playTrailer=T' if streamtype == 1 else '')

        subprocess.Popen(['log', '-p', 'v', '-t', 'Kodi-Amazon', 'Manufacturer: %s' % manu])
        subprocess.Popen(['log', '-p', 'v', '-t', 'Kodi-Amazon', 'Starting App: %s Video: %s' % (pkg, url)])
        Log('Manufacturer: %s' % manu)
        Log('Starting App: %s Video: %s' % (pkg, url))

        if _s.logging:
            amaz_pkgs = ''
            if os.access('/system/xbin/su', os.X_OK) or os.access('/system/bin/su', os.X_OK):
                Log('Logcat:\n%s' % _check_output(['su', '-c', 'logcat -d | grep -iE "(avod|amazonvideo)']))
            Log('Properties:\n%s' % _check_output(['sh', '-c', 'getprop | grep -iE "(ro.product|ro.build|google)"']))
            if os.access('/system/bin/cmd', os.X_OK):
                amaz_pkgs = _check_output(['sh', '-c', 'cmd package list packages | grep -i amazon'])
            elif os.access('/system/bin/pm', os.X_OK):
                amaz_pkgs = _check_output(['sh', '-c', 'pm', 'list', 'packages', 'com.amazon'])
            Log('Installed Amazon Packages:\n%s' % amaz_pkgs)

        xbmc.executebuiltin('StartAndroidActivity("%s", "%s", "", "%s")' % (pkg, act, url))

    def _IStreamPlayback(asin, name, streamtype, isAdult, extern):
        if streamtype == 2:
            u_path = '' if _g.UsePrimeVideo else '/gp/video'
            data = GrabJSON(_g.BaseUrl + u_path + '/detail/' + asin)
            if data:
                state = findKey('liveState', data)
                if state and state['id'].lower() != 'live':
                    _g.dialog.notification(getString(30203), '{} {}'.format(getString(30174), state['text'].lower()), xbmcgui.NOTIFICATION_INFO)
                    return False

        from .ages import AgeRestrictions
        vMT = ['Feature', 'Trailer', 'LiveStreaming'][streamtype]
        dRes = 'PlaybackUrls' if streamtype > 1 else 'PlaybackUrls,SubtitleUrls,ForcedNarratives,TransitionTimecodes'
        opt = '&liveManifestType=accumulating,live&playerType=xp&playerAttributes={"frameRate":"HFR"}&deviceFrameRateOverride=High' if streamtype > 1 else ''
        mpaa_str = AgeRestrictions().GetRestrictedAges() + getString(30171)

        inputstream_helper = Helper('mpd', drm='com.widevine.alpha')
        if not inputstream_helper.check_inputstream():
            Log('No Inputstream Addon found or activated')
            return False

        bypassproxy = _s.proxy_mpdalter or (streamtype > 1)

        # The following code can run two times. In the first iteration, token auth
        # will be prefered. If the request is successful, the loop will be aborted.
        # If not, then the second iteration will fall back to cookie authentification
        # and try again. This is neccessary for content like Amazon Freevee, which is not
        # available though token based authentification.
        
        for preferTokenToCookie in ([True, False] if _s.wvl1_device else [False]):
            cookie, opt_lic, headers, dtid = _getPlaybackVars(preferToken=preferTokenToCookie)
            if not cookie:
                _g.dialog.notification(getString(30203), getString(30200), xbmcgui.NOTIFICATION_ERROR)
                Log('Login error at playback')
                return False

            success, data = getURLData('catalog/GetPlaybackResources', asin, extra=True, vMT=vMT, dRes=dRes, useCookie=cookie, devicetypeid=dtid,
                                       proxyEndpoint=(None if bypassproxy else 'gpr'), opt=opt)
            if success or not isinstance(cookie, dict):
                break

        mpd, subs, timecodes = _ParseStreams(success, data, retmpd=True, bypassproxy=bypassproxy)
        if not mpd:
            _g.dialog.notification(getString(30203), subs, xbmcgui.NOTIFICATION_ERROR)
            return False

        licURL = getURLData('catalog/GetPlaybackResources', asin, devicetypeid=dtid, opt=opt_lic, extra=True, vMT=vMT, dRes='Widevine2License', retURL=True)
        skip = timecodes.get('skipElements')
        Log('Skip Items: %s' % skip, Log.DEBUG)

        from xbmcaddon import Addon as KodiAddon
        is_version = KodiAddon(_g.is_addon).getAddonInfo('version') if _g.is_addon else '0'

        if (not _s.audio_description) and (streamtype != 2) and (dtid == _g.dtid_web):
            mpd = re.sub(r'(~|%7E)', '', mpd)

        Log(mpd, Log.DEBUG)

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

        if 'adaptive' in _g.is_addon:
            listitem.setProperty('inputstream.adaptive.manifest_type', 'mpd')

        Log('Using %s Version: %s' % (_g.is_addon, is_version))
        listitem.setArt({'thumb': thumb})
        listitem.setSubtitles(subs)
        listitem.setProperty('%s.license_type' % _g.is_addon, 'com.widevine.alpha')
        listitem.setProperty('%s.license_key' % _g.is_addon, licURL)
        listitem.setProperty('%s.manifest_headers' % _g.is_addon, urlencode(headers))
        listitem.setProperty('inputstreamaddon' if _g.KodiVersion < 19 else 'inputstream', _g.is_addon)
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

        while (not _g.monitor.abortRequested()) and player.running:
            if player.isPlayingVideo():
                player.video_lastpos = player.getTime()
                if time.time() > (starttime + player.interval):
                    starttime = time.time()
                    player.updateStream()
                if skip and _s.skip_scene > 0:
                    for elem in skip:
                        st_pos = elem.get('startTimecodeMs')
                        et_pos = (elem.get('endTimecodeMs') - 5000)  # * 0.9 + st_pos
                        btn_type = elem.get('elementType')
                        if st_pos <= (player.video_lastpos * 1000) <= et_pos:
                            skip_button.display(elem)
                        elif skip_button.act_btn == btn_type:
                            skip_button.hide()
            _g.monitor.waitForAbort(1)
        skip_button.hide()
        player.finished(True)
        del player, skip_button
        return True

    def _getPlaybackVars(preferToken=True):
        cookie = MechanizeLogin(preferToken=preferToken)
        cj_str = deepcopy(cookie)
        dtid = _g.dtid_web

        if cookie:
            if isinstance(cookie, dict):
                dtid = _g.dtid_android
                headers = _g.headers_android
            else:
                cj_str = {'Cookie': ';'.join(['%s=%s' % (k, v) for k, v in cookie.items()])}
                headers = {'User-Agent': getConfig('UserAgent')}
            cj_str.update({'Content-Type': 'application/x-www-form-urlencoded'})
            cj_str.update(headers)
            opt = '|' + urlencode(cj_str)
            opt += '|widevine2Challenge=B{SSM}&includeHdcpTestKeyInLicense=true'
            opt += '|JBlicense;hdcpEnforcementResolutionPixels'
            return cookie, opt, headers, dtid
        return False

    isAdult = adultstr == '1'
    amazonUrl = _g.BaseUrl + "/dp/" + (py2_decode(name) if _g.UsePrimeVideo else asin)
    videoUrl = "%s/?autoplay=%s" % (amazonUrl, ('trailer' if streamtype == 1 else '1'))
    extern = not xbmc.getInfoLabel('Container.PluginName').startswith('plugin.video.amazon')
    suc = False

    if extern:
        Log('External Call', Log.DEBUG)
    if _s.playmethod == 2 and _g.platform & _g.OS_ANDROID:
        _AndroidPlayback(asin, streamtype)
    elif _s.playmethod == 3:
        suc = _IStreamPlayback(asin, name, streamtype, isAdult, extern)
    elif not _g.platform & _g.OS_ANDROID:
        _ExtPlayback(videoUrl, asin, isAdult)

    if not suc:
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
                return sum(i * int(t) for i, t in zip([1, 60, 3600], reversed(li_dur.split(":"))))
            return int(li_dur) * 60
        else:
            content = getATVData('GetASINDetails', 'ASINList=' + asin)['titles'][0]
            ct, Info = _g.pv.getInfos(content, False)
            return int(Info.get('Duration', 0))

    def close(self):
        Log('Stopping Thread')
        self._stopEvent.set()
        xbmcgui.WindowDialog.close(self)
        watched = xbmc.getInfoLabel('Listitem.PlayCount')
        pBTime = time.time() - self._pbStart
        Log('Dur:%s State:%s PlbTm:%s' % (self._vidDur, watched, pBTime), Log.DEBUG)

        if pBTime > self._vidDur * 0.9 and not watched:
            _playDummyVid()
            Log('Toogle watched state', Log.DEBUG)
            xbmc.executebuiltin('Action(ToggleWatched)')

    def onAction(self, action):
        if not _s.remotectrl:
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
            self._SetVol(+2) if _s.remote_vol else _Input(keys='up')
        elif action == ACTION_MOVE_DOWN:
            self._SetVol(-2) if _s.remote_vol else _Input(keys='down')
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
        self.sleeptm = 0.2
        self.video_lastpos = 0
        self.video_totaltime = 0
        self.dbid = 0
        self.asin = ''
        self.cookie = None
        self.interval = 60
        self.running = False
        self.extern = False
        self.resume = 0
        self.watched = 0
        self.content = 0
        self.rec_added = False
        self.resumedb = OSPJoin(_g.DATA_PATH, 'resume.db')
        self.sendvp = _s.send_vp
        self.event = 'START'

    def resolve(self, li):
        if self.extern and not self.checkResume():
            xbmcplugin.setResolvedUrl(_g.pluginhandle, True, xbmcgui.ListItem())
            xbmc.executebuiltin('Container.Refresh')
            return
        if self.resume:
            li.setProperty('resumetime', str(self.resume))
            li.setProperty('totaltime', '1')
            Log('Resuming Video at %s' % self.resume)

        xbmcplugin.setResolvedUrl(_g.pluginhandle, True, li)
        self.running = True
        self.getTimes('Starting Playback')

    def checkResume(self):
        self.dbid = int('0' + _getListItem('DBID'))
        Log('DBID: %s' % self.dbid)
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
            sel = _g.dialog.contextmenu([getString(12022).format(time.strftime("%H:%M:%S", time.gmtime(self.resume))), getString(12021)])
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

    def onPlayBackSeek(self, time, seekOffset):
        cur_sub = jsonRPC('Player.GetProperties', 'currentsubtitle', param={'playerid': 1})
        Log('Seeking / Current Subtitle: {}'.format(cur_sub), Log.DEBUG)
        if cur_sub:
            jsonRPC('Player.SetSubtitle', param={'playerid': 1, 'subtitle': cur_sub['index']})

    def updateStream(self):
        if not self.asin:
            return
        perc = (self.video_lastpos * 100) / self.video_totaltime if self.video_lastpos > 0 and self.video_totaltime > 0 else 0
        if 0 < self.sendvp <= perc:
            suc, msg = getURLData('usage/UpdateStream', self.asin, useCookie=self.cookie, opt='&event=%s&timecode=%s' % (self.event, self.video_lastpos))
            self.event = 'PLAY'
            if suc and 'statusCallbackIntervalSeconds' in str(msg):
                self.interval = msg['message']['body']['statusCallbackIntervalSeconds']
        if not self.rec_added and self.video_lastpos > 180 and _s.data_source == 2:
            self.rec_added = True
            _g.pv.updateRecents(self.asin)

    def finished(self, forced=False):
        if self.running and (self.video_lastpos > 0 or forced):
            self.running = False
            self.event = 'STOP'
            self.updateStream()
            if self.video_lastpos > 0 and self.video_totaltime > 0:
                self.watched = 1 if (self.video_lastpos * 100) / self.video_totaltime >= 90 else 0
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
            autoskip = self.act_btn in self.btn_list[_s.skip_scene - 1]
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
        Log('Seeking to: {}sec / cur pos {}sec'.format(self.seek_time, self.player.getTime()), Log.DEBUG)
        self.player.seekTime(self.seek_time)
        sleep(0.75)
        Log('Position: {}'.format(self.player.getTime()), Log.DEBUG)
        xbmc.sleep(wait)
        self.hide()

    def onAction(self, action):
        if action in [xbmcgui.ACTION_PREVIOUS_MENU, xbmcgui.ACTION_NAV_BACK]:
            self.close()
