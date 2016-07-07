#!/usr/bin/env python
# -*- coding: utf-8 -*-
from BeautifulSoup import BeautifulStoneSoup
import subprocess
import common
import random
import threading
import codecs

pluginhandle = common.pluginhandle
xbmc = common.xbmc
xbmcplugin = common.xbmcplugin
urllib = common.urllib
urllib2 = common.urllib2
sys = common.sys
xbmcgui = common.xbmcgui
re = common.re
json = common.json
addon = common.addon
os = common.os
hashlib = common.hashlib
time = common.time
xbmcvfs = common.xbmcvfs
Dialog = xbmcgui.Dialog()

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

hasExtRC = xbmc.getCondVisibility('System.HasAddon(script.chromium_remotecontrol)') is True
useIntRC = addon.getSetting("remotectrl") == 'true'
playMethod = int(addon.getSetting("playmethod"))
browser = int(addon.getSetting("browser"))
verbLog = addon.getSetting('logging') == 'true'


def PLAYVIDEO():
    amazonUrl = common.BASE_URL + "/dp/" + common.args.asin
    waitsec = int(addon.getSetting("clickwait")) * 1000
    pin = addon.getSetting("pin")
    waitpin = int(addon.getSetting("waitpin")) * 1000
    waitprepin = int(addon.getSetting("waitprepin")) * 1000
    trailer = common.args.trailer == '1'
    isAdult = int(common.args.adult) == '1'
    pininput = addon.getSetting("pininput") == 'true'
    fullscr = addon.getSetting("fullscreen") == 'true'
    xbmc.Player().stop()

    if trailer:
        videoUrl = amazonUrl + "/?autoplaytrailer=1"
    else:
        videoUrl = amazonUrl + "/?autoplay=1"

    if playMethod == 2 or platform == osAndroid:
        AndroidPlayback(common.args.asin, trailer)
    elif playMethod == 3:
        IStreamPlayback(trailer, isAdult)
    else:
        if common.verbLog:
            videoUrl += '&playerDebug=true'

        url, err = getCmdLine(videoUrl)
        if not url:
            Dialog.notification(common.getString(30203), err, xbmcgui.NOTIFICATION_ERROR)
            return
        common.Log('Executing: %s' % url)
        if platform == 1:
            process = subprocess.Popen(url, startupinfo=getStartupInfo())
        else:
            process = subprocess.Popen(url, shell=True)

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

        if hasExtRC:
            return

        myWindow = window()
        myWindow.wait(process)


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
        url = common.BASE_URL + '/piv-apk-play?asin=' + asin
        if trailer:
            url += '&playTrailer=T'
    subprocess.Popen(['log', '-p', 'v', '-t', 'Kodi-Amazon', 'Manufacturer: ' + manu])
    subprocess.Popen(['log', '-p', 'v', '-t', 'Kodi-Amazon', 'Starting App: %s Video: %s' % (pkg, url)])
    common.Log('Manufacturer: %s' % manu)
    common.Log('Starting App: %s Video: %s' % (pkg, url))
    if verbLog:
        if os.access('/system/xbin/su', os.X_OK) or os.access('/system/bin/su', os.X_OK):
            common.Log('Logcat:\n' + check_output(['su', '-c', 'logcat -d | grep -i com.amazon.avod']))
        common.Log('Properties:\n' + check_output(['sh', '-c', 'getprop | grep -iE "(ro.product|ro.build|google)"']))
    xbmc.executebuiltin('StartAndroidActivity("%s", "%s", "", "%s")' % (pkg, act, url))


def check_output(*popenargs, **kwargs):
    p = subprocess.Popen(stdout=subprocess.PIPE, stderr=subprocess.STDOUT, *popenargs, **kwargs)
    out, err = p.communicate()
    retcode = p.poll()
    if retcode != 0:
        c = kwargs.get("args")
        if c is None:
            c = popenargs[0]
            e = subprocess.CalledProcessError(retcode, c)
            e.output = str(out) + str(err)
            common.Log(e, xbmc.LOGERROR)
    return out.strip()


def IStreamPlayback(trailer, isAdult):
    values = getFlashVars()
    if not values:
        return

    infoLabels = GetStreamInfo(common.args.asin)
    mpaa_str = common.RestrAges + common.getString(30171)
    mpaa_check = infoLabels.get('MPAA', mpaa_str) in mpaa_str or isAdult
    vMT = 'Trailer' if trailer else 'Feature'

    mpd, subs = getStreams(*getUrldata('catalog/GetPlaybackResources', values, extra=True, vMT=vMT,
                                       opt='&titleDecorationScheme=primary-content'), retmpd=True)
    licURL = getUrldata('catalog/GetPlaybackResources', values, extra=True, vMT=vMT, dRes='Widevine2License',
                        retURL=True)
    common.Log(mpd)
    if not mpd:
        Dialog.notification(common.getString(30203), subs, xbmcgui.NOTIFICATION_ERROR)
        return

    if mpaa_check and not common.RequestPin():
        return

    listitem = xbmcgui.ListItem(path=mpd)
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

    listitem.setArt({'thumb': infoLabels['Thumb']})
    listitem.setInfo('video', infoLabels)
    listitem.setSubtitles(subs)
    listitem.setProperty('inputstream.mpd.license_type', 'com.widevine.alpha')
    listitem.setProperty('inputstream.mpd.license_key', licURL)
    listitem.setProperty('inputstreamaddon', 'inputstream.mpd')
    xbmcplugin.setResolvedUrl(pluginhandle, True, listitem=listitem)


def parseSubs(data):
    subs = []
    if addon.getSetting('subtitles') == 'false' or 'subtitleUrls' not in data:
        return subs

    for sub in data['subtitleUrls']:
        lang = sub['displayName'].split('(')[0].strip()
        common.Log('Convert %s Subtitle' % lang)
        srtfile = xbmc.translatePath('special://temp/%s.srt' % lang).decode('utf-8')
        srt = codecs.open(srtfile, 'w', encoding='utf-8')
        soup = BeautifulStoneSoup(common.getURL(sub['url']), convertEntities=BeautifulStoneSoup.XML_ENTITIES)
        enc = soup.originalEncoding
        num = 0
        for caption in soup.findAll('tt:p'):
            num += 1
            subtext = caption.renderContents().decode(enc).replace('<tt:br>', '\n').replace('</tt:br>', '')
            srt.write(u'%s\n%s --> %s\n%s\n\n' % (num, caption['begin'], caption['end'], subtext))
        srt.close()
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


def getCmdLine(videoUrl):
    scr_path = addon.getSetting("scr_path")
    br_path = addon.getSetting("br_path").strip()
    scr_param = addon.getSetting("scr_param").strip()
    kiosk = addon.getSetting("kiosk") == 'true'
    appdata = addon.getSetting("ownappdata") == 'true'
    cust_br = addon.getSetting("cust_path") == 'true'
    nobr_str = common.getString(30198)

    if playMethod == 1:
        if not xbmcvfs.exists(scr_path):
            return False, nobr_str

        fr, err = getPlaybackInfo()
        if not fr:
            return False, err

        return scr_path + ' ' + scr_param.replace('{f}', fr).replace('{u}', videoUrl), False

    os_paths = [None, ('C:\\Program Files\\', 'C:\\Program Files (x86)\\'), ('/usr/bin/', '/usr/local/bin/'),
                'open -a ']
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
                    common.Log('Browser %s not found' % (path + brfile), xbmc.LOGDEBUG)
            if br_path:
                break

    if not xbmcvfs.exists(br_path) and platform != osOSX:
        return False, nobr_str

    br_args = br_config[browser][3]
    if kiosk:
        br_args += br_config[browser][1]

    if appdata and br_config[browser][2]:
        br_args += br_config[browser][2] + '"' + os.path.join(common.pldatapath, str(browser)) + '" '

    if platform == osOSX:
        if not cust_br:
            br_path = os_paths[osOSX] + br_config[browser][0][osOSX]

        if br_args.strip():
            br_args = '--args ' + br_args

    br_path += ' %s"%s"' % (br_args, videoUrl)

    return br_path, nobr_str


def getStartupInfo():
    si = subprocess.STARTUPINFO()
    si.dwFlags = subprocess.STARTF_USESHOWWINDOW
    return si


def getStreams(suc, data, retmpd=False):
    prefHost = addon.getSetting("pref_host")

    if not suc:
        return False, data

    if retmpd:
        subUrls = parseSubs(data)

    if prefHost not in str(data) or prefHost == 'Auto':
        prefHost = False

    for cdn in data['audioVideoUrls']['avCdnUrlSets']:
        if prefHost and prefHost not in cdn['cdn']:
            continue

        common.Log('Using Host: ' + cdn['cdn'])

        for urlset in cdn['avUrlInfoList']:
            if retmpd:
                return urlset['url'], subUrls
            data = common.getURL(urlset['url'])
            fps_string = re.compile('frameRate="([^"]*)').findall(data)[0]
            fr = round(eval(fps_string + '.0'), 3)
            return str(fr).replace('.0', ''), True
    return '', False


def getPlaybackInfo():
    if addon.getSetting("framerate") == 'false':
        return '', False
    Dialog.notification(common.getString(20186), '', xbmcgui.NOTIFICATION_INFO, 60000, False)
    values = getFlashVars()
    if not values:
        return '', False
    fr, err = getStreams(*getUrldata('catalog/GetPlaybackResources', values, extra=True))
    Dialog.notification(common.getString(20186), '', xbmcgui.NOTIFICATION_INFO, 10, False)
    return fr, err


def getFlashVars():
    cookie = common.mechanizeLogin()
    if not cookie:
        return False
    url = common.BASE_URL + '/gp/deal/ajax/getNotifierResources.html'
    showpage = json.loads(common.getURL(url, useCookie=cookie))

    if not showpage:
        Dialog.notification(common.__plugin__, Error({'errorCode': 'invalidrequest', 'message': 'getFlashVars'}),
                            xbmcgui.NOTIFICATION_ERROR)
        return False

    values = {'asin': common.args.asin,
              'deviceTypeID': 'AOAGZA014O5RE',
              'userAgent': common.UserAgent}
    values.update(showpage['resourceData']['GBCustomerData'])

    if 'customerId' not in values:
        Dialog.notification(common.getString(30200), common.getString(30210), xbmcgui.NOTIFICATION_ERROR)
        return False

    values['deviceID'] = common.gen_id()
    rand = 'onWebToken_' + str(random.randint(0, 484))
    pltoken = common.getURL(common.BASE_URL + "/gp/video/streaming/player-token.json?callback=" + rand,
                            useCookie=cookie)
    try:
        values['token'] = re.compile('"([^"]*).*"([^"]*)"').findall(pltoken)[0][1]
    except:
        Dialog.notification(common.getString(30200), common.getString(30201), xbmcgui.NOTIFICATION_ERROR)
        return False
    return values


def getUrldata(mode, values, devicetypeid=False, version=1, firmware='1', opt='', extra=False,
               useCookie=False, retURL=False, vMT='Feature', dRes='AudioVideoUrls%2CSubtitleUrls'):
    if not devicetypeid:
        devicetypeid = values['deviceTypeID']
    url = common.ATV_URL + '/cdp/' + mode
    url += '?asin=' + values['asin']
    url += '&deviceTypeID=' + devicetypeid
    url += '&firmware=' + firmware
    url += '&customerID=' + values['customerId']
    url += '&deviceID=' + values['deviceID']
    url += '&marketplaceID=' + values['marketplaceId']
    url += '&token=' + values['token']
    url += '&format=json'
    url += '&version=' + str(version)
    url += opt
    if extra:
        url += '&resourceUsage=ImmediateConsumption&consumptionType=Streaming&deviceDrmOverride=CENC' \
               '&deviceStreamingTechnologyOverride=DASH&deviceProtocolOverride=Http&audioTrackId=all'
        url += '&videoMaterialType=' + vMT
        url += '&desiredResources=' + dRes
    if retURL:
        return url
    data = common.getURL(url, common.ATV_URL.split('//')[1], useCookie=useCookie)
    if data:
        jsondata = json.loads(data)
        del data
        if 'errorsByResource' in jsondata:
            for field in jsondata['errorsByResource']:
                if 'AudioVideoUrls' in field:
                    return False, Error(jsondata['errorsByResource'][field])
        return True, jsondata
    return False, 'HTTP Fehler'


def Error(data):
    code = data['errorCode'].lower()
    common.Log('%s (%s) ' % (data['message'], code), xbmc.LOGERROR)
    if 'invalidrequest' in code:
        return common.getString(30204)
    elif 'noavailablestreams' in code:
        return common.getString(30205)
    elif 'notowned' in code:
        return common.getString(30206)
    elif 'invalidgeoip' in code:
        return common.getString(30207)
    elif 'temporarilyunavailable' in code:
        return common.getString(30208)
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
        app = os.path.join(common.pluginpath, 'tools', 'userinput.exe')
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

    common.Log('Run command: %s' % cmd)
    rcode = subprocess.call(cmd, shell=True)
    if rcode:
        common.Log('Returncode: %s' % rcode)


class window(xbmcgui.WindowDialog):
    def __init__(self):
        xbmcgui.WindowDialog.__init__(self)
        self._stopEvent = threading.Event()
        self._pbStart = time.time()

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

    def wait(self, process):
        common.Log('Starting Thread')
        self._wakeUpThread = threading.Thread(target=self._wakeUpThreadProc, args=(process,))
        self._wakeUpThread.start()
        self.doModal()
        self._wakeUpThread.join()

    def close(self):
        common.Log('Stopping Thread')
        self._stopEvent.set()
        xbmcgui.WindowDialog.close(self)
        vidDur = int(xbmc.getInfoLabel('ListItem.Duration')) * 60
        watched = xbmc.getInfoLabel('Listitem.PlayCount')
        isLast = xbmc.getInfoLabel('Container().Position') == xbmc.getInfoLabel('Container().NumItems')
        pBTime = time.time() - self._pbStart

        if pBTime > vidDur * 0.9 and not watched:
            xbmc.executebuiltin("Action(ToggleWatched)")
            if not isLast:
                xbmc.executebuiltin("Action(Up)")

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
        common.Log('Action: Id:%s ButtonCode:%s' % (actionId, action.getButtonCode()))

        if action in [ACTION_SHOW_GUI, ACTION_STOP, ACTION_PARENT_DIR, ACTION_PREVIOUS_MENU, ACTION_NAV_BACK,
                      KEY_BUTTON_BACK, ACTION_MOUSE_MOVE]:
            Input(keys='{EX}')
        elif action in [ACTION_SELECT_ITEM, ACTION_PLAYER_PLAY, ACTION_PAUSE]:
            Input(keys='{SPC}')
        elif action == ACTION_MOVE_LEFT:
            Input(keys='{LFT}')
        elif action == ACTION_MOVE_RIGHT:
            Input(keys='{RGT}')
        elif action == ACTION_MOVE_UP:
            Input(keys='{U}')
        elif action == ACTION_MOVE_DOWN:
            Input(keys='{DWN}')
        elif action == ACTION_SHOW_INFO:
            Input(9999, 0)
            xbmc.sleep(800)
            Input(9999, -1)
        # numkeys for pin input
        elif 57 < actionId < 68:
            strKey = str(actionId - 58)
            Input(keys=strKey)
