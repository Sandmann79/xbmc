#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from BeautifulSoup import BeautifulStoneSoup
from common import *
from inputstreamhelper import Helper
import subprocess
import threading
import codecs
import shlex

platform = 0
osWindows = 1
osLinux = 2
osOSX = 3
osAndroid = 4
if xbmc.getCondVisibility('system.platform.windows'):
    platform = osWindows
if xbmc.getCondVisibility('system.platform.linux'):
    platform = osLinux
if xbmc.getCondVisibility('system.platform.osx'):
    platform = osOSX
if xbmc.getCondVisibility('system.platform.android'):
    platform = osAndroid

hasExtRC = xbmc.getCondVisibility('System.HasAddon(script.chromium_remotecontrol)')
useIntRC = addon.getSetting("remotectrl") == 'true'
browser = int(addon.getSetting("browser"))
RMC_vol = addon.getSetting("remote_vol") == 'true'


def PLAYVIDEO():
    amazonUrl = BaseUrl + "/dp/" + args.get('asin')
    trailer = args.get('trailer') == '1'
    isAdult = args.get('adult') == '1'
    playable = False
    fallback = int(addon.getSetting("fallback_method"))
    methodOW = fallback - 1 if args.get('forcefb') and fallback else playMethod
    videoUrl = "%s/?autoplay=%s" % (amazonUrl, ('trailer' if trailer == '1' else '1'))
    extern = not xbmc.getInfoLabel('Container.PluginName').startswith('plugin.video.amazon')
    fr = ''

    if extern:
        Log('External Call', xbmc.LOGDEBUG)

    while not playable:
        playable = True

        if methodOW == 2 and platform == osAndroid:
            AndroidPlayback(args.get('asin'), trailer)
        elif methodOW == 3:
            playable = IStreamPlayback(trailer, isAdult, extern)
        elif platform != osAndroid:
            ExtPlayback(videoUrl, isAdult, methodOW, fr)

        if not playable or isinstance(playable, unicode):
            if fallback:
                methodOW = fallback - 1
                if isinstance(playable, unicode):
                    fr = playable
                    playable = False
            else:
                xbmc.sleep(500)
                Dialog.ok(getString(30203), getString(30218))
                playable = True

    if methodOW !=3:
        playDummyVid()


def ExtPlayback(videoUrl, isAdult, method, fr):
    waitsec = int(addon.getSetting("clickwait")) * 1000
    pin = addon.getSetting("pin")
    waitpin = int(addon.getSetting("waitpin")) * 1000
    waitprepin = int(addon.getSetting("waitprepin")) * 1000
    pininput = addon.getSetting("pininput") == 'true'
    fullscr = addon.getSetting("fullscreen") == 'true'
    videoUrl += '&playerDebug=true' if verbLog else ''
    osLE = False

    xbmc.Player().stop()
    xbmc.executebuiltin('ActivateWindow(busydialog)')

    if xbmcvfs.exists('/etc/os-release'):
        osLE = 'libreelec' in xbmcvfs.File('/etc/os-release').read()

    suc, url = getCmdLine(videoUrl, method, fr)
    if not suc:
        Dialog.notification(getString(30203), url, xbmcgui.NOTIFICATION_ERROR)
        return

    Log('Executing: %s' % url)
    if platform == osWindows:
        process = subprocess.Popen(url, startupinfo=getStartupInfo())
    else:
        param = shlex.split(url)
        process = subprocess.Popen(param)
        if osLE:
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
        if browser != 0:
            Input(keys='f')
        else:
            Input(mousex=-1, mousey=350, click=2)
            xbmc.sleep(500)
            Input(mousex=9999, mousey=350)

    Input(mousex=9999, mousey=-1)

    xbmc.executebuiltin('Dialog.Close(busydialog)')
    if hasExtRC:
        return

    myWindow = window(process)
    myWindow.wait()


def AndroidPlayback(asin, trailer):
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
        url = BaseUrl + '/piv-apk-play?asin=' + asin
        if trailer:
            url += '&playTrailer=T'
    subprocess.Popen(['log', '-p', 'v', '-t', 'Kodi-Amazon', 'Manufacturer: ' + manu])
    subprocess.Popen(['log', '-p', 'v', '-t', 'Kodi-Amazon', 'Starting App: %s Video: %s' % (pkg, url)])
    Log('Manufacturer: %s' % manu)
    Log('Starting App: %s Video: %s' % (pkg, url))
    if verbLog:
        if os.access('/system/xbin/su', os.X_OK) or os.access('/system/bin/su', os.X_OK):
            Log('Logcat:\n' + check_output(['su', '-c', 'logcat -d | grep -i com.amazon.avod']))
        Log('Properties:\n' + check_output(['sh', '-c', 'getprop | grep -iE "(ro.product|ro.build|google)"']))
    xbmc.executebuiltin('StartAndroidActivity("%s", "%s", "", "%s")' % (pkg, act, url))


def check_output(*popenargs, **kwargs):
    p = subprocess.Popen(stdout=subprocess.PIPE, stderr=subprocess.STDOUT, *popenargs, **kwargs)
    out, err = p.communicate()
    retcode = p.poll()
    if retcode != 0:
        c = kwargs.get('args')
        if c is None:
            c = popenargs[0]
            e = subprocess.CalledProcessError(retcode, c)
            e.output = str(out) + str(err)
            Log(e, xbmc.LOGERROR)
    return out.strip()


def IStreamPlayback(trailer, isAdult, extern):
    drm_check = addon.getSetting("drm_check") == 'true'
    at_check = addon.getSetting("at_check") == 'true'
    inputstream_helper = Helper('mpd', drm='com.widevine.alpha')

    if not inputstream_helper.check_inputstream():
        Log('No Inputstream Addon found or activated')
        return True

    cookie = MechanizeLogin()
    vMT = 'Trailer' if trailer else 'Feature'

    mpd, subs = getStreams(*getUrldata('catalog/GetPlaybackResources', args.get('asin'), extra=True, vMT=vMT,
                                       opt='&titleDecorationScheme=primary-content', useCookie=cookie), retmpd=True)

    cj_str = ';'.join(['%s=%s' % (k, v) for k, v in cookie.items()])
    opt = '|Content-Type=application%2Fx-www-form-urlencoded&Cookie=' + urllib.quote_plus(cj_str)
    opt += '|widevine2Challenge=B{SSM}&includeHdcpTestKeyInLicense=true'
    opt += '|JBlicense;hdcpEnforcementResolutionPixels'
    licURL = getUrldata('catalog/GetPlaybackResources', args.get('asin'), extra=True, vMT=vMT, dRes='Widevine2License', opt=opt, retURL=True)

    if not mpd:
        Dialog.notification(getString(30203), subs, xbmcgui.NOTIFICATION_ERROR)
        return True

    orgmpd = mpd
    is_version = xbmcaddon.Addon(is_addon).getAddonInfo('version') if is_addon else '0'
    is_binary = xbmc.getCondVisibility('System.HasAddon(kodi.binary.instance.inputstream)')
    mpd = re.sub(r'~', '', mpd)

    if drm_check:
        mpdcontent = getURL(mpd, rjson=False)
        if 'avc1.4D00' in mpdcontent and platform != osAndroid and not is_binary:
            xbmc.executebuiltin('ActivateWindow(busydialog)')
            return extrFr(mpdcontent)
        if mpdcontent.count('EDEF8BA9-79D6-4ACE-A3C8-27DCD51D21ED') > 1 and (platform == osAndroid or is_binary):
            mpd = orgmpd
            at_check = False

    Log(mpd)

    infoLabels = GetStreamInfo(args.get('asin'))
    mpaa_str = RestrAges + getString(30171)
    mpaa_check = infoLabels.get('MPAA', mpaa_str) in mpaa_str or isAdult
    if mpaa_check and not RequestPin():
        return True

    listitem = xbmcgui.ListItem(path=mpd)
    if extern:
        infoLabels['Title'] = infoLabels.get('EpisodeName', infoLabels['Title'])
    if trailer:
        infoLabels['Title'] += ' (Trailer)'
    if 'Thumb' not in infoLabels.keys():
        infoLabels['Thumb'] = None
    if 'Fanart' in infoLabels.keys():
        listitem.setArt({'fanart': infoLabels['Fanart']})
    if 'Poster' in infoLabels.keys():
        listitem.setArt({'tvshow.poster': infoLabels['Poster']})
    else:
        listitem.setArt({'poster': infoLabels['Thumb']})

    if 'adaptive' in is_addon:
        listitem.setProperty('inputstream.adaptive.manifest_type', 'mpd')

    Log('Using %s Version:%s' %(is_addon, is_version))
    listitem.setArt({'thumb': infoLabels['Thumb']})
    listitem.setInfo('video', getInfolabels(infoLabels))
    listitem.setSubtitles(subs)
    listitem.setProperty('%s.license_type' % is_addon, 'com.widevine.alpha')
    listitem.setProperty('%s.license_key' % is_addon, licURL)
    listitem.setProperty('%s.stream_headers' % is_addon, 'user-agent=' + UserAgent)
    listitem.setProperty('inputstreamaddon', is_addon)
    listitem.setMimeType('application/dash+xml')
    listitem.setContentLookup(False)
    xbmcplugin.setResolvedUrl(pluginhandle, True, listitem=listitem)

    valid_track = validAudioTrack()
    Log('Playback started...', 0)
    Log('Video ContentType Movie? %s' % xbmc.getCondVisibility('VideoPlayer.Content(movies)'), 0)
    Log('Video ContentType Episode? %s' % xbmc.getCondVisibility('VideoPlayer.Content(episodes)'), 0)

    if not valid_track and at_check:
        lang = jsonRPC('Player.GetProperties', 'currentaudiostream', {'playerid': 0})['language']
        all_tracks = jsonRPC('Player.GetProperties', 'audiostreams', {'playerid': 0})
        Log(str(all_tracks).replace('},', '}\n'))

        count = 3
        while count and len(all_tracks) > 1:
            cur_track = jsonRPC('Player.GetProperties', 'currentaudiostream', {'playerid': 0})['index']
            all_tracks = [i for i in all_tracks if i['index'] != cur_track]
            Log('Current AudioTrackID %d' % cur_track)
            tracks = all_tracks
            if lang in str(tracks):
                tracks = [i for i in tracks if i['language'] == lang]
            if 'eac3' in str(tracks):
                tracks = [i for i in tracks if i['codec'] == 'eac3']
            chan = max([i['channels'] for i in tracks])
            trackid = -1
            trackbr = 0

            for at in tracks:
                if at['channels'] == chan and at['bitrate'] > trackbr:
                    trackid = at['index']
                    trackbr = at['bitrate']

            if trackid > -1:
                Log('Switching to AudioTrackID %d' % trackid)
                xbmc.Player().setAudioStream(trackid)
                if validAudioTrack():
                    break
            count -= 1
    return True


def validAudioTrack():
    player = xbmc.Player()
    sleeptm = 0.2
    Log('Checking AudioTrack')

    while not player.isPlaying() or not player.isPlayingVideo():
        sleep(sleeptm)

    cac_s = time.time()
    Log('Player Starting: %s/%s' % (player.getTime(), player.getTotalTime()))
    while xbmc.getCondVisibility('!Player.Caching') and cac_s + 1.2 > time.time():
        sleep(sleeptm)

    cac_s = time.time()
    Log('Player Caching: %s/%s' % (player.getTime(), player.getTotalTime()))
    while xbmc.getCondVisibility('Player.Caching') and cac_s + 2 > time.time():
        sleep(sleeptm)

    Log('Player Resuming: %s/%s' % (player.getTime(), player.getTotalTime()))

    chan1_track = xbmc.getInfoLabel('VideoPlayer.AudioChannels')
    sr_track = int(xbmc.getInfoLabel('Player.Process(AudioSamplerate)').replace(',', ''))
    cc_track = xbmc.getInfoLabel('VideoPlayer.AudioCodec')
    ch_track = xbmc.getInfoLabel('Player.Process(AudioChannels)	')
    Log('Codec:%s Samplerate:%s Channels:I(%s)R(%s)' % (cc_track, sr_track, chan1_track, len(ch_track.split(','))))

    if cc_track == 'eac3' and sr_track >= 48000:
        retval = True
    elif cc_track != 'eac3' and sr_track >= 22050:
        retval = True
    else:
        retval = False

    return retval


def parseSubs(data):
    localeConversion = {
        'ar-001': 'ar',
        'cmn-hans': 'zh HANS',
        'cmn-hant': 'zh HANT',
        'da-dk': 'da',
        'es-419': 'es LA',
        'ja-jp': 'ja',
        'ko-kr': 'ko',
        'nb-no': 'nb',
        'sv-se': 'sv',
    }  # Clean up language and locale information where needed
    subs = []
    if addon.getSetting('subtitles') == 'false' or 'subtitleUrls' not in data:
        return subs

    for sub in data['subtitleUrls']:
        lang = sub['languageCode'].strip()
        if lang in localeConversion:
            lang = localeConversion[lang]
        # Clean up where needed
        if '-' in lang:
            p1 = re.split('-', lang)[0]
            p2 = re.split('-', lang)[1]
            if p1 == p2: # Remove redundant locale information when not useful
                lang = p1
            else:
                lang = '%s %s' % (p1, p2.upper())
        # Amazon's en defaults to en_US, not en_UK
        if 'en' == lang:
            lang = 'en US'
        # Readd close-caption information where needed
        if '[' in sub['displayName']:
            cc = re.search(r'(\[[^\]]+\])', sub['displayName'])
            if None is not cc:
                lang = lang + (' %s' % cc.group(1))
        Log('Convert %s Subtitle (%s)' % (sub['displayName'].strip(), lang))
        srtfile = xbmc.translatePath('special://temp/%s.srt' % lang).decode('utf-8')
        with codecs.open(srtfile, 'w', encoding='utf-8') as srt:
            soup = BeautifulStoneSoup(getURL(sub['url'], rjson=False), convertEntities=BeautifulStoneSoup.XML_ENTITIES)
            enc = soup.originalEncoding
            if None is enc:
                enc = 'utf-8'
            num = 0
            for caption in soup.findAll('tt:p'):
                num += 1
                subtext = caption.renderContents().decode(enc).replace('<tt:br>', '\n').replace('</tt:br>', '')
                srt.write('%s\n%s --> %s\n%s\n\n' % (num, caption['begin'], caption['end'], subtext))
        subs.append(srtfile)
    return subs


def GetStreamInfo(asin):
    import movies
    import listmovie
    import tv
    import listtv
    moviedata = movies.lookupMoviedb(asin)
    if moviedata:
        return listmovie.ADD_MOVIE_ITEM(moviedata, onlyinfo=True)
    else:
        epidata = tv.lookupTVdb(asin)
        if epidata:
            return listtv.ADD_EPISODE_ITEM(epidata, onlyinfo=True)
    return {'Title': ''}


def getCmdLine(videoUrl, method, fr):
    scr_path = addon.getSetting("scr_path")
    br_path = addon.getSetting("br_path").strip()
    scr_param = addon.getSetting("scr_param").strip()
    kiosk = addon.getSetting("kiosk") == 'true'
    appdata = addon.getSetting("ownappdata") == 'true'
    cust_br = addon.getSetting("cust_path") == 'true'
    nobr_str = getString(30198)
    frdetect = addon.getSetting("framerate") == 'true'

    if method == 1:
        if not xbmcvfs.exists(scr_path):
            return False, nobr_str

        if frdetect:
            suc, fr = getStreams(*getUrldata('catalog/GetPlaybackResources', args.get('asin'), extra=True, useCookie=True)) if not fr else (True, fr)
            if not suc:
                return False, fr
        else:
            fr = ''

        return True, scr_path + ' ' + scr_param.replace('{f}', fr).replace('{u}', videoUrl)

    os_paths = [None, ('C:\\Program Files\\', 'C:\\Program Files (x86)\\'), ('/usr/bin/', '/usr/local/bin/'), 'open -a ']
    # path(0,win,lin,osx), kiosk, profile, args

    br_config = [[(None, ['Internet Explorer\\iexplore.exe'], '', ''), '-k ', '', ''],
                 [(None, ['Google\\Chrome\\Application\\chrome.exe'],
                   ['google-chrome', 'google-chrome-stable', 'google-chrome-beta', 'chromium-browser'],
                   '"/Applications/Google Chrome.app"'),
                  '--kiosk ', '--user-data-dir=',
                  '--start-maximized --disable-translate --disable-new-tab-first-run --no-default-browser-check --no-first-run '],
                 [(None, ['Mozilla Firefox\\firefox.exe'], ['firefox'], 'firefox'), '', '-profile ', ''],
                 [(None, ['Safari\\Safari.exe'], '', 'safari'), '', '', '']]

    if not cust_br:
        br_path = ''

    if platform != osOSX and not cust_br:
        for path in os_paths[platform]:
            for brfile in br_config[browser][0][platform]:
                if xbmcvfs.exists(os.path.join(path, brfile)):
                    br_path = path + brfile
                    break
                else:
                    Log('Browser %s not found' % (path + brfile), xbmc.LOGDEBUG)
            if br_path:
                break

    if not xbmcvfs.exists(br_path) and platform != osOSX:
        return False, nobr_str

    br_args = br_config[browser][3]
    if kiosk:
        br_args += br_config[browser][1]

    if appdata and br_config[browser][2]:
        br_args += br_config[browser][2] + '"' + os.path.join(pldatapath, str(browser)) + '" '

    if platform == osOSX:
        if not cust_br:
            br_path = os_paths[osOSX] + br_config[browser][0][osOSX]

        if br_args.strip():
            br_args = '--args ' + br_args

    br_path += ' %s"%s"' % (br_args, videoUrl)

    return True, br_path


def getStartupInfo():
    si = subprocess.STARTUPINFO()
    si.dwFlags = subprocess.STARTF_USESHOWWINDOW
    return si


def getStreams(suc, data, retmpd=False):
    HostSet = addon.getSetting("pref_host")
    subUrls = []

    if not suc:
        return False, data

    if retmpd:
        subUrls = parseSubs(data)

    if 'audioVideoUrls' in data.keys():
        hosts = data['audioVideoUrls']['avCdnUrlSets']
    elif 'playbackUrls' in data.keys():
        defid = data['playbackUrls']['defaultUrlSetId']
        h_dict = data['playbackUrls']['urlSets']
        hosts = [h_dict[k] for k in h_dict]
        hosts.insert(0, h_dict[defid])

    while hosts:
        for cdn in hosts:
            prefHost = False if HostSet not in unicode(hosts) or HostSet == 'Auto' else HostSet
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


def extrFr(data):
    fps_string = re.compile('frameRate="([^"]*)').findall(data)[0]
    fr = round(eval(fps_string + '.0'), 3)
    return str(fr).replace('.0', '')


def getUrldata(mode, asin, devicetypeid='AOAGZA014O5RE', version=1, firmware='1', opt='', extra=False,
               useCookie=False, retURL=False, vMT='Feature', dRes='PlaybackUrls,SubtitleUrls'):
    url = ATV_URL + '/cdp/' + mode
    url += '?asin=' + asin
    url += '&deviceTypeID=' + devicetypeid
    url += '&firmware=' + firmware
    url += '&deviceID=' + gen_id()
    url += '&format=json'
    url += '&version=' + str(version)
    if extra:
        url += '&resourceUsage=ImmediateConsumption&consumptionType=Streaming&deviceDrmOverride=CENC' \
               '&deviceStreamingTechnologyOverride=DASH&deviceProtocolOverride=Https&audioTrackId=all' \
               '&deviceBitrateAdaptationsOverride=CVBR%2CCBR'
        url += '&videoMaterialType=' + vMT
        url += '&desiredResources=' + dRes
        url += '&supportedDRMKeyScheme=DUAL_KEY' if platform != osAndroid and 'PlaybackUrls' in dRes else ''
    url += opt
    if retURL:
        return url
    data = getURL(url, useCookie=useCookie, rjson=False)
    if data:
        error = re.findall('{[^"]*"errorCode[^}]*}', data)
        if error:
            return False, Error(json.loads(error[0]))
        return True, json.loads(data)
    return False, 'HTTP Error'


def Error(data):
    code = data['errorCode'].lower()
    Log('%s (%s) ' % (data['message'], code), xbmc.LOGERROR)
    if 'invalidrequest' in code:
        return getString(30204)
    elif 'noavailablestreams' in code:
        return getString(30205)
    elif 'notowned' in code:
        return getString(30206)
    elif 'invalidgeoip' or 'dependency' in code:
        return getString(30207)
    elif 'temporarilyunavailable' in code:
        return getString(30208)
    else:
        return '%s (%s) ' % (data['message'], code)


def Input(mousex=0, mousey=0, click=0, keys=None, delay='200'):
    screenWidth = int(xbmc.getInfoLabel('System.ScreenWidth'))
    screenHeight = int(xbmc.getInfoLabel('System.ScreenHeight'))
    keys_only = sc_only = keybd = ''
    if mousex == -1:
        mousex = screenWidth / 2

    if mousey == -1:
        mousey = screenHeight / 2
    spec_keys = {'{EX}': ('!{F4}', 'control+shift+q', 'kd:cmd t:q ku:cmd'),
                 '{SPC}': ('{SPACE}', 'space', 't:p'),
                 '{LFT}': ('{LEFT}', 'Left', 'kp:arrow-left'),
                 '{RGT}': ('{RIGHT}', 'Right', 'kp:arrow-right'),
                 '{U}': ('{UP}', 'Up', 'kp:arrow-up'),
                 '{DWN}': ('{DOWN}', 'Down', 'kp:arrow-down'),
                 '{BACK}': ('{BS}', 'BackSpace', 'kp:delete'),
                 '{RET}': ('{ENTER}', 'Return', 'kp:return')}

    if keys:
        keys_only = keys
        for sc in spec_keys:
            while sc in keys:
                keys = keys.replace(sc, spec_keys[sc][platform - 1]).strip()
                keys_only = keys_only.replace(sc, '').strip()
        sc_only = keys.replace(keys_only, '').strip()

    if platform == osWindows:
        app = os.path.join(pluginpath, 'tools', 'userinput.exe')
        mouse = ' mouse %s %s' % (mousex, mousey)
        mclk = ' ' + str(click)
        keybd = ' key %s %s' % (keys, delay)
    elif platform == osLinux:
        app = 'xdotool'
        mouse = ' mousemove %s %s' % (mousex, mousey)
        mclk = ' click --repeat %s 1' % click
        if keys_only:
            keybd = ' type --delay %s %s' % (delay, keys_only)

        if sc_only:
            if keybd:
                keybd += ' && ' + app

            keybd += ' key ' + sc_only
    elif platform == osOSX:
        app = 'cliclick'
        mouse = ' m:'
        if click == 1:
            mouse = ' c:'
        elif click == 2:
            mouse = ' dc:'
        mouse += '%s,%s' % (mousex, mousey)
        mclk = ''
        keybd = ' -w %s' % delay
        if keys_only:
            keybd += ' t:%s' % keys_only

        if keys != keys_only:
            keybd += ' ' + sc_only
    if keys:
        cmd = app + keybd
    else:
        cmd = app + mouse
        if click:
            cmd += mclk

    Log('Run command: %s' % cmd)
    rcode = subprocess.call(cmd, shell=True)
    if rcode:
        Log('Returncode: %s' % rcode)


def playDummyVid():
    dummy_video = os.path.join(pluginpath, 'resources', 'dummy.avi')
    xbmcplugin.setResolvedUrl(pluginhandle, True, xbmcgui.ListItem(path=dummy_video))
    Log('Playing Dummy Video', xbmc.LOGDEBUG)
    xbmc.Player().stop()
    return


def SetVol(step):
    vol = jsonRPC('Application.GetProperties', 'volume')
    xbmc.executebuiltin('SetVolume(%d,showVolumeBar)' % (vol + step))


class window(xbmcgui.WindowDialog):
    def __init__(self, process):
        xbmcgui.WindowDialog.__init__(self)
        self._stopEvent = threading.Event()
        self._pbStart = time.time()
        self._wakeUpThread = threading.Thread(target=self._wakeUpThreadProc, args=(process,))
        self._vidDur = self.getDuration()

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
    def getDuration():
        li_dur = xbmc.getInfoLabel('ListItem.Duration')
        if li_dur:
            if ':' in li_dur:
                return sum(i * int(t) for i, t in zip([3600, 60, 1], li_dur.split(":")))
            return int(li_dur) * 60
        else:
            infoLabels = GetStreamInfo(args.get('asin'))
            return int(infoLabels.get('Duration', 0))

    def close(self):
        Log('Stopping Thread')
        self._stopEvent.set()
        xbmcgui.WindowDialog.close(self)
        watched = xbmc.getInfoLabel('Listitem.PlayCount')
        pBTime = time.time() - self._pbStart
        Log('Dur:%s State:%s PlbTm:%s' % (self._vidDur, watched, pBTime), xbmc.LOGDEBUG)

        if pBTime > self._vidDur * 0.9 and not watched:
            xbmc.executebuiltin("Action(ToggleWatched)")

    def onAction(self, action):
        if not useIntRC:
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
        ACTION_VOLUME_UP = 88
        ACTION_VOLUME_DOWN = 89
        ACTION_MUTE = 91
        ACTION_NAV_BACK = 92
        ACTION_BUILT_IN_FUNCTION = 122
        KEY_BUTTON_BACK = 275
        ACTION_BACKSPACE = 110
        ACTION_MOUSE_MOVE = 107

        actionId = action.getId()
        showinfo = action == ACTION_SHOW_INFO
        Log('Action: Id:%s ButtonCode:%s' % (actionId, action.getButtonCode()))

        if action in [ACTION_SHOW_GUI, ACTION_STOP, ACTION_PARENT_DIR, ACTION_PREVIOUS_MENU, ACTION_NAV_BACK,
                      KEY_BUTTON_BACK, ACTION_MOUSE_MOVE]:
            Input(keys='{EX}')
        elif action in [ACTION_SELECT_ITEM, ACTION_PLAYER_PLAY, ACTION_PAUSE]:
            Input(keys='{SPC}')
            showinfo = True
        elif action == ACTION_MOVE_LEFT:
            Input(keys='{LFT}')
            showinfo = True
        elif action == ACTION_MOVE_RIGHT:
            Input(keys='{RGT}')
            showinfo = True
        elif action == ACTION_MOVE_UP:
            SetVol(+2) if RMC_vol else Input(keys='{U}')
        elif action == ACTION_MOVE_DOWN:
            SetVol(-2) if RMC_vol else Input(keys='{DWN}')
        # numkeys for pin input
        elif 57 < actionId < 68:
            strKey = str(actionId - 58)
            Input(keys=strKey)

        if showinfo:
            Input(9999, 0)
            xbmc.sleep(500)
            Input(9999, -1)
