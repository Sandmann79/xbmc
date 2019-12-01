#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from .common import *
from inputstreamhelper import Helper
import subprocess
import threading
import shlex

platform = 0
OS_WINDOWS = 1
OS_LINUX = 2
OS_OSX = 4
OS_ANDROID = 8
OS_LE = 16

if xbmc.getCondVisibility('system.platform.windows'):
    platform |= OS_WINDOWS
if xbmc.getCondVisibility('system.platform.linux'):
    platform |= OS_LINUX
if xbmc.getCondVisibility('system.platform.osx'):
    platform |= OS_OSX
if xbmc.getCondVisibility('system.platform.android'):
    platform |= OS_ANDROID
if (xbmcvfs.exists('/etc/os-release')) and ('libreelec' in xbmcvfs.File('/etc/os-release').read()):
    platform |= OS_LE


def PLAYVIDEO():
    amazonUrl = BaseUrl + "/dp/" + var.args.get('asin')
    trailer = var.args.get('trailer')
    isAdult = var.args.get('adult') == '1'
    playable = False
    fallback = int(var.addon.getSetting("fallback_method"))
    methodOW = fallback - 1 if var.args.get('forcefb') and fallback else var.playMethod
    videoUrl = "{}/?autoplay={}".format(amazonUrl, ('trailer' if trailer == '1' else '1'))
    extern = not xbmc.getInfoLabel('Container.PluginName').startswith('plugin.video.amazon')
    uhdAndroid = trailer == '-1'
    fr = ''

    if extern:
        Log('External Call', xbmc.LOGDEBUG)

    while not playable:
        playable = True

        if (methodOW == 2 or uhdAndroid) and platform & OS_ANDROID:
            AndroidPlayback(var.args.get('asin'), trailer == '1')
        elif methodOW == 3:
            playable = IStreamPlayback(trailer == '1', isAdult, extern)
        elif not platform & OS_ANDROID:
            ExtPlayback(videoUrl, isAdult, methodOW, fr)

        if not playable or isinstance(playable, type(u'')):
            if fallback:
                methodOW = fallback - 1
                if isinstance(playable, type(u'')):
                    fr = playable
                    playable = False
            else:
                xbmc.sleep(500)
                Dialog.ok(getString(30203), getString(30218))
                playable = True

    if methodOW != 3:
        playDummyVid()


def ExtPlayback(videoUrl, isAdult, method, fr):
    waitsec = int(var.addon.getSetting("clickwait")) * 1000
    pin = var.addon.getSetting("pin")
    waitpin = int(var.addon.getSetting("waitpin")) * 1000
    waitprepin = int(var.addon.getSetting("waitprepin")) * 1000
    pininput = var.addon.getSetting("pininput") == 'true'
    fullscr = var.addon.getSetting("fullscreen") == 'true'
    videoUrl += '&playerDebug=true' if var.verbLog else ''

    xbmc.Player().stop()

    suc, url = getCmdLine(videoUrl, method, fr)
    if not suc:
        Dialog.notification(getString(30203), url, xbmcgui.NOTIFICATION_ERROR)
        return

    Log('Executing: {}'.format(url))
    if platform & OS_WINDOWS:
        process = subprocess.Popen(url, startupinfo=getStartupInfo())
    else:
        param = shlex.split(url)
        process = subprocess.Popen(param)
        if platform & OS_LE:
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
        if var.browser != 0:
            Input(keys='f')
        else:
            Input(mousex=-1, mousey=350, click=2)
            xbmc.sleep(500)
            Input(mousex=9999, mousey=350)

    Input(mousex=9999, mousey=-1)

    if var.hasExtRC:
        return

    myWindow = window(process)
    myWindow.wait()


def AndroidPlayback(asin, trailer):
    manu = net = ''
    if os.access('/system/bin/getprop', os.X_OK):
        manu = check_output(['getprop', 'ro.product.manufacturer'])
        net = check_output(['getprop', 'ro.telephony.default_network'])

    if manu == 'Amazon':
        pkg = 'com.fivecent.amazonvideowrapper'
        act = ''
        url = asin
    elif not net:
        pkg = 'com.amazon.amazonvideo.livingroom'
        act = 'android.intent.action.VIEW'
        url = '{}/watch?asin={}'.format(BaseUrl.replace('www', 'watch'), asin)
    else:
        pkg = 'com.amazon.avod.thirdpartyclient'
        act = 'android.intent.action.VIEW'
        url = BaseUrl + '/piv-apk-play?asin=' + asin
        if trailer:
            url += '&playTrailer=T'
    subprocess.Popen(['log', '-p', 'v', '-t', 'Kodi-Amazon', 'Manufacturer: ' + manu])
    subprocess.Popen(['log', '-p', 'v', '-t', 'Kodi-Amazon', 'Starting App: {} Video: {}'.format(pkg, url)])
    Log('Manufacturer: {}'.format(manu))
    Log('Starting App: {} Video: {}'.format(pkg, url))
    if var.verbLog:
        if os.access('/system/xbin/su', os.X_OK) or os.access('/system/bin/su', os.X_OK):
            Log('Logcat:\n' + check_output(['su', '-c', 'logcat -d | grep -i com.amazon.avod']))
        Log('Properties:\n' + check_output(['sh', '-c', 'getprop | grep -iE "(ro.product|ro.build|google)"']))
    xbmc.executebuiltin('StartAndroidActivity("{}", "{}", "", "{}")'.format(pkg, act, url))


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
    drm_check = var.addon.getSetting("drm_check") == 'true'
    verifyISA = '{"jsonrpc":"2.0","id":1,"method":"Addons.GetAddonDetails","params":{"addonid":"inputstream.adaptive"}}'
    if 'error' in xbmc.executeJSONRPC(verifyISA):
        xbmc.executebuiltin('UpdateAddonRepos', True)
        xbmc.executebuiltin('InstallAddon(inputstream.adaptive)', True)
        if 'error' in xbmc.executeJSONRPC(verifyISA):
            Log('InputStream.Adaptive addon is not installed')
            playDummyVid()
            return True
    inputstream_helper = Helper('mpd', drm='com.widevine.alpha')
    vMT = 'Trailer' if trailer else 'Feature'

    if not inputstream_helper.check_inputstream():
        Log('No Inputstream Addon found or activated')
        return True

    cookie = MechanizeLogin()
    if not cookie:
        Dialog.notification(getString(30203), getString(30200), xbmcgui.NOTIFICATION_ERROR)
        Log('Login error at playback')
        playDummyVid()
        return True

    mpd, subs = getStreams(*getUrldata('catalog/GetPlaybackResources', var.args.get('asin'), extra=True, vMT=vMT, useCookie=cookie), retmpd=True)

    cj_str = ';'.join(['{}={}'.format(k, v) for k, v in cookie.items()])
    opt = '|Content-Type=application%2Fx-www-form-urlencoded&Cookie=' + quote_plus(cj_str)
    opt += '|widevine2Challenge=B{SSM}&includeHdcpTestKeyInLicense=true'
    opt += '|JBlicense;hdcpEnforcementResolutionPixels'
    licURL = getUrldata('catalog/GetPlaybackResources', var.args.get('asin'), extra=True, vMT=vMT, dRes='Widevine2License', opt=opt, retURL=True)

    if not mpd:
        Dialog.notification(getString(30203), subs, xbmcgui.NOTIFICATION_ERROR)
        return True

    is_version = xbmcaddon.Addon(is_addon).getAddonInfo('version') if is_addon else '0'
    is_binary = xbmc.getCondVisibility('System.HasAddon(kodi.binary.instance.inputstream)')
    mpd = re.sub(r'~', '', mpd)

    if drm_check:
        mpdcontent = getURL(mpd, rjson=False)
        if 'avc1.4D00' in mpdcontent and not platform & OS_ANDROID and not is_binary:
            return extrFr(mpdcontent)

    Log(mpd)

    infoLabels = GetStreamInfo(var.args.get('asin'))
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

    Log('Using {} Version:{}'.format(is_addon, is_version))
    listitem.setArt({'thumb': infoLabels['Thumb']})
    listitem.setInfo('video', getInfolabels(infoLabels))
    listitem.setSubtitles(subs)
    listitem.setProperty('{}.license_type'.format(is_addon), 'com.widevine.alpha')
    listitem.setProperty('{}.license_key'.format(is_addon), licURL)
    listitem.setProperty('{}.stream_headers'.format(is_addon), 'user-agent=' + UserAgent)
    listitem.setProperty('inputstreamaddon', is_addon)
    listitem.setMimeType('application/dash+xml')
    listitem.setContentLookup(False)
    player = AmazonPlayer()
    player.asin = var.args.get('asin')
    player.cookie = cookie
    player.content = trailer
    player.extern = extern
    player.resolve(listitem)
    starttime = time.time()

    monitor = xbmc.Monitor()
    while (not monitor.abortRequested()) and player.running:
        if player.isPlayingVideo():
            player.video_lastpos = player.getTime()
            if time.time() > starttime + player.interval:
                starttime = time.time()
                player.updateStream('PLAY')
        sleep(1)

    del player
    return True


def PlayerInfo(msg, sleeptm=0.2):
    player = xbmc.Player()
    while not player.isPlayingVideo():
        sleep(sleeptm)
    while player.isPlayingVideo() and (player.getTime() >= player.getTotalTime()):
        sleep(sleeptm)
    if player.isPlayingVideo():
        Log('{}: {}/{}'.format(msg, player.getTime(), player.getTotalTime()))
    del player


def parseSubs(data):
    bForcedOnly = False  # Whether or not we should only download forced subtitles
    down_lang = int('0' + var.addon.getSetting('sub_lang'))
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
    if 'forced_only' == lang_main and down_lang > 1:
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
            if p1 == p2:  # Remove redundant locale information when not useful
                lang = p1
            else:
                lang = '{} {}'.format(p1, p2.upper())
        # Amazon's en defaults to en_US, not en_UK
        if 'en' == lang:
            lang = 'en US'
        # Read close-caption information where needed
        if '[' in sub['displayName']:
            cc = re.search(r'(\[[^\]]+\])', sub['displayName'])
            if None is not cc:
                lang = lang + (' {}'.format(cc.group(1)))
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
        srtfile = xbmc.translatePath('special://temp/{}.srt'.format(sub['languageCode']))
        subDisplayLang = '“{}” subtitle ({})'.format(sub['displayName'].strip(), sub['languageCode'])
        content = ''
        with codecs.open(srtfile, 'w', encoding='utf-8') as srt:
            num = 0
            # Since .srt are available on amazon's servers, we strip the default extension and try downloading it just once
            subUrl = re.search(r'^(.*?\.)[^.]{1,}$', sub['url'])
            content = '' if None is subUrl else getURL(subUrl.group(1) + 'srt', rjson=False, attempt=777)
            if 0 < len(content):
                Log('Downloaded {}'.format(subDisplayLang))
                srt.write(content)
            else:
                content = getURL(sub['url'], rjson=False, attempt=3)
                if 0 < len(content):
                    Log('Converting {}'.format(subDisplayLang))
                    for tt in re.compile('<tt:p(.*)').findall(content):
                        tt = re.sub('<tt:br[^>]*>', '\n', tt)
                        tt = re.search(r'begin="([^"]*).*end="([^"]*).*>([^<]*).', tt)
                        subtext = tt.group(3)
                        for ec in escape_chars:
                            subtext = subtext.replace(ec[0], ec[1])
                        if tt:
                            num += 1
                            srt.write('{}\n{} --> {}\n{}\n\n'.format(num, tt.group(1), tt.group(2), subtext))
        if 0 == len(content):
            Log('Unable to download {}'.format(subDisplayLang))
        else:
            subs.append(srtfile)
    return subs


def GetStreamInfo(asin):
    from . import movies
    from . import listmovie
    from . import tv
    from . import listtv
    moviedata = movies.lookupMoviedb(asin)
    if moviedata:
        return listmovie.ADD_MOVIE_ITEM(moviedata, onlyinfo=True)
    else:
        epidata = tv.lookupTVdb(asin)
        if epidata:
            return listtv.ADD_EPISODE_ITEM(epidata, onlyinfo=True)
    return {'Title': ''}


def getCmdLine(videoUrl, method, fr):
    scr_path = var.addon.getSetting("scr_path")
    br_path = var.addon.getSetting("br_path").strip()
    scr_param = var.addon.getSetting("scr_param").strip()
    kiosk = var.addon.getSetting("kiosk") == 'true'
    appdata = var.addon.getSetting("ownappdata") == 'true'
    cust_br = var.addon.getSetting("cust_path") == 'true'
    nobr_str = getString(30198)
    frdetect = var.addon.getSetting("framerate") == 'true'

    if method == 1:
        if not xbmcvfs.exists(scr_path):
            return False, nobr_str

        if frdetect:
            suc, fr = getStreams(*getUrldata('catalog/GetPlaybackResources', var.args.get('asin'), extra=True, useCookie=True)) if not fr else (True, fr)
            if not suc:
                return False, fr
        else:
            fr = ''

        return True, scr_path + ' ' + scr_param.replace('{f}', fr).replace('{u}', videoUrl)

    br_platform = (platform & -platform).bit_length()
    os_paths = [None, ('C:\\Program Files\\', 'C:\\Program Files (x86)\\'), ('/usr/bin/', '/usr/local/bin/'), 'open -a '][br_platform]
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

    if not platform & OS_OSX and not cust_br:
        for path in os_paths:
            for brfile in br_config[var.browser][0][platform]:
                if xbmcvfs.exists(os.path.join(path, brfile)):
                    br_path = path + brfile
                    break
                else:
                    Log('Browser {} not found'.format(path + brfile), xbmc.LOGDEBUG)
            if br_path:
                break

    if not xbmcvfs.exists(br_path) and not platform & OS_OSX:
        return False, nobr_str

    br_args = br_config[var.browser][3]
    if kiosk:
        br_args += br_config[var.browser][1]

    if appdata and br_config[var.browser][2]:
        br_args += br_config[var.browser][2] + '"' + os.path.join(pldatapath, str(var.browser)) + '" '

    if platform & OS_OSX:
        if not cust_br:
            br_path = os_paths + br_config[var.browser][0][3]

        if br_args.strip():
            br_args = '--args ' + br_args

    br_path += ' {}"{}"'.format(br_args, videoUrl)

    return True, br_path


def getStartupInfo():
    si = subprocess.STARTUPINFO()
    si.dwFlags = subprocess.STARTF_USESHOWWINDOW
    return si


def getStreams(suc, data, retmpd=False):
    HostSet = var.addon.getSetting("pref_host")
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
            hs = str(hosts)
            prefHost = False if HostSet not in hs or HostSet == 'Auto' else HostSet
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
               useCookie=False, retURL=False, vMT='Feature', dRes='PlaybackUrls,SubtitleUrls,ForcedNarratives'):
    url = ATV_URL + '/cdp/' + mode
    url += '?asin=' + asin
    url += '&deviceTypeID=' + devicetypeid
    url += '&firmware=' + firmware
    url += '&deviceID=' + gen_id()
    url += '&marketplaceID=A1PA6795UKMFR9'
    url += '&format=json'
    url += '&version=' + str(version)
    if extra:
        url += '&resourceUsage=ImmediateConsumption&consumptionType=Streaming&deviceDrmOverride=CENC' \
               '&deviceStreamingTechnologyOverride=DASH&deviceProtocolOverride=Https&audioTrackId=all' \
               '&deviceBitrateAdaptationsOverride=CVBR%2CCBR&gascEnabled=false'
        url += '&videoMaterialType=' + vMT
        url += '&desiredResources=' + dRes
        url += '&supportedDRMKeyScheme=DUAL_KEY' if not platform & OS_ANDROID and 'PlaybackUrls' in dRes else ''
    url += opt
    if retURL:
        return url
    data = getURL(url, useCookie=useCookie, postdata='')
    if data:
        if 'error' in data.keys():
            return False, Error(data['error'])
        elif 'AudioVideoUrls' in data.get('errorsByResource', ''):
            return False, Error(data['errorsByResource']['AudioVideoUrls'])
        elif 'PlaybackUrls' in data.get('errorsByResource', ''):
            return False, Error(data['errorsByResource']['PlaybackUrls'])
        else:
            return True, data
    return False, 'HTTP Error'


def Error(data):
    code = data['errorCode'].lower()
    Log('{} ({}) '.format(data['message'], code), xbmc.LOGERROR)
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
        return '{} ({}) '.format(data['message'], code)


def Input(mousex=0, mousey=0, click=0, keys=None, delay='200'):
    screenWidth = int(xbmc.getInfoLabel('System.ScreenWidth'))
    screenHeight = int(xbmc.getInfoLabel('System.ScreenHeight'))
    keys_only = sc_only = keybd = ''
    if mousex == -1:
        mousex = screenWidth / 2

    if mousey == -1:
        mousey = screenHeight / 2
    spec_keys = {'{EX}': ('!{F4}', 'alt+F4', 'kd:cmd t:q ku:cmd'),
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

    if platform & OS_WINDOWS:
        app = os.path.join(pluginpath, 'tools', 'userinput.exe')
        if not os.path.exists(app):
            Dialog.notification(getString(30227), getString(30228), xbmcgui.NOTIFICATION_ERROR)
            return
        mouse = ' mouse {} {}'.format(mousex, mousey)
        mclk = ' ' + str(click)
        keybd = ' key {} {}'.format(keys, delay)
    elif platform & OS_LINUX:
        app = 'xdotool'
        mouse = ' mousemove {} {}'.format(mousex, mousey)
        mclk = ' click --repeat {} 1'.format(click)
        if keys_only:
            keybd = ' type --delay {} {}'.format(delay, keys_only)

        if sc_only:
            if keybd:
                keybd += ' && ' + app

            keybd += ' key ' + sc_only
    elif platform & OS_OSX:
        app = 'cliclick'
        mouse = ' m:'
        if click == 1:
            mouse = ' c:'
        elif click == 2:
            mouse = ' dc:'
        mouse += '{},{}'.format(mousex, mousey)
        mclk = ''
        keybd = ' -w {}'.format(delay)
        if keys_only:
            keybd += ' t:{}'.format(keys_only)

        if keys != keys_only:
            keybd += ' ' + sc_only
    if keys:
        cmd = app + keybd
    else:
        cmd = app + mouse
        if click:
            cmd += mclk

    Log('Run command: {}'.format(cmd))
    rcode = subprocess.call(cmd, shell=True)
    if rcode:
        Log('Returncode: {}'.format(rcode))


def playDummyVid():
    dummy_video = os.path.join(pluginpath, 'resources', 'dummy.avi')
    xbmcplugin.setResolvedUrl(var.pluginhandle, True, xbmcgui.ListItem(path=dummy_video))
    Log('Playing Dummy Video', xbmc.LOGDEBUG)
    xbmc.Player().stop()
    return


def SetVol(step):
    vol = jsonRPC('Application.GetProperties', 'volume')
    xbmc.executebuiltin('SetVolume(%d,showVolumeBar)'.format(vol + step))


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
            infoLabels = GetStreamInfo(var.args.get('asin'))
            return int(infoLabels.get('Duration', 0))

    def close(self):
        Log('Stopping Thread')
        self._stopEvent.set()
        xbmcgui.WindowDialog.close(self)
        watched = xbmc.getInfoLabel('Listitem.PlayCount')
        pBTime = time.time() - self._pbStart
        Log('Dur:{} State:{} PlbTm:{}'.format(self._vidDur, watched, pBTime), xbmc.LOGDEBUG)

        if pBTime > self._vidDur * 0.9 and not watched:
            xbmc.executebuiltin("Action(ToggleWatched)")

    def onAction(self, action):
        if not var.useIntRC:
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
        Log('Action: Id:{} ButtonCode:{}'.format(actionId, action.getButtonCode()))

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
            SetVol(+2) if var.RMC_vol else Input(keys='{U}')
        elif action == ACTION_MOVE_DOWN:
            SetVol(-2) if var.RMC_vol else Input(keys='{DWN}')
        # numkeys for pin input
        elif 57 < actionId < 68:
            strKey = str(actionId - 58)
            Input(keys=strKey)

        if showinfo:
            Input(9999, 0)
            xbmc.sleep(500)
            Input(9999, -1)


class AmazonPlayer(xbmc.Player):
    def __init__(self):
        super(AmazonPlayer, self).__init__()
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
        self.resumedb = os.path.join(pldatapath, 'resume.db')

    def resolve(self, li):
        if self.extern and not self.checkResume():
            xbmcplugin.setResolvedUrl(var.pluginhandle, True, xbmcgui.ListItem())
            xbmc.executebuiltin('Container.Refresh')
            return
        if self.resume:
            li.setProperty('resumetime', str(self.resume))
            li.setProperty('totaltime', '1')
            Log('Resuming Video at {}'.format(self.resume))

        xbmcplugin.setResolvedUrl(var.pluginhandle, True, li)
        self.running = True
        self.getTimes('Starting Playback')
        self.updateStream('START')

    def checkResume(self):
        self.dbid = int('0' + self.getListItem('DBID'))
        if self.dbid:
            dbtype = self.getListItem('DBTYPE')
            result = jsonRPC('VideoLibrary.Get{}Details'.format(dbtype), 'resume,playcount', {'{}id'.format(dbtype): self.dbid})
            self.resume = int(result[dbtype.lower() + 'details']['resume']['position'])
            self.watched = int(result[dbtype.lower() + 'details']['playcount'])
        if not self.resume:
            self.getResumePoint()
        if self.watched:
            return True
        if self.resume > 180 and self.extern:
            res_string = getString(12022).replace("{}", "{}") if KodiK else getString(12022)
            sel = Dialog.contextmenu([res_string.format(time.strftime("%H:%M:{}", time.gmtime(self.resume))), getString(12021)])
            if sel > -1:
                self.resume = self.resume if sel == 0 else 0
            else:
                return False
        return True

    @staticmethod
    def getListItem(li):
        return py2_decode(xbmc.getInfoLabel('ListItem.{}'.format(li)))

    def getResumePoint(self):
        if not xbmcvfs.exists(self.resumedb) or self.content == 2:
            return {}
        with open(self.resumedb, 'rb') as fp:
            items = pickle.load(fp)
            self.resume = items.get(self.asin, {}).get('resume')
            fp.close()
        return items

    def saveResumePoint(self):
        if self.content == 2:
            return
        items = self.getResumePoint()
        with open(self.resumedb, 'wb+') as fp:
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
        suc, msg = getUrldata('usage/UpdateStream', self.asin, useCookie=self.cookie, opt='&event={}&timecode={}'.format(event, self.video_lastpos))
        if suc and 'statusCallbackIntervalSeconds' in str(msg):
            self.interval = msg['message']['body']['statusCallbackIntervalSeconds']

    def finished(self):
        self.updateStream('STOP')
        if self.running:
            self.running = False
            if self.video_lastpos > 0 and self.video_totaltime > 0:
                self.watched = 1 if (self.video_lastpos * 100) / self.video_totaltime >= 90 else 0
                if self.dbid and KodiK:
                    dbtype = self.getListItem('DBTYPE')
                    params = {'{}id'.format(dbtype): self.dbid,
                              'resume': {'position': 0 if self.watched else self.video_lastpos,
                                         'total': self.video_totaltime},
                              'playcount': self.watched}
                    res = '' if 'OK' in jsonRPC('VideoLibrary.Set{}Details'.format(dbtype), '', params) else 'NOT '
                    Log('{}Updated {}id({}) with: pos({}) total({}) playcount({})'.format(res, dbtype, self.dbid, self.video_lastpos,
                                                                                          self.video_totaltime, self.watched))
                self.saveResumePoint()

    def getTimes(self, msg):
        while self.video_totaltime <= 0:
            sleep(self.sleeptm)
            if self.isPlaying() and self.getTotalTime() >= self.getTime() >= 0:
                self.video_totaltime = self.getTotalTime()
                self.video_lastpos = self.getTime()
        Log('{}: {}/{}'.format(msg, self.video_lastpos, self.video_totaltime))
