# Amazon Prime Video Addon for Kodi Media Center

This addon supports amazon accounts from Germany, Japan, United Kingdom and United States (referred to as TLDs), as well as all countries supported by PrimeVideo.com (referred to as PrimeVideo, or PV).

Widevine DRM protected streams are reproduced via `InputStream.Adaptive` henceforth referred to as IS.A.

## Disclaimer
This addon is not officially commissioned or supported by Amazon, nor are authors associated with it. Amazon, Prime, Amazon Prime and Prime Video are trademarks registered by Amazon Technologies, inc.

## Features
* access and edit Amazons Watchlist and Video Library (TLD)
* export Movies, TV Shows to Kodi Library (TLD)
* loads Covers and Fanart from TMDB/TVDB (TLD)
* additional age verification (TLD/PV, requires IS.A)
* fallback playack methods (TLD/PV, requires IS.A)

## Known limitations
* HD and FHD video quality are only available on hardware supported devices (Android devices/FireTV/Firesticks). To enable reproduction of such videos you need to enable `Override HDCP status` in IS.A settings, or use a different playback method
* Some features are not yet implemented for PrimeVideo users

## Setup instructions
* install the repository as described in [these instructions](https://github.com/Sandmann79/xbmc/)
* install **Amazon VOD** video addon from Sandmann79’s Repository

## Playback methods
Several playback methods are supported, although `InputStream.Adaptive` is the default since Kodi 18 Leia.

### InputStream.Adaptive
Uses the Inputstream interface with the internal Kodi player, which is available since Kodi 17, to playback Widevine encrypted video streams.

### Android
Uses the [Amazon Prime Video App](https://play.google.com/store/apps/details?id=com.amazon.avod.thirdpartyclient) for playback. If you own an Amazon FireTV/Stick, you have to install the [Amazon Video Wrapper](https://github.com/Sandmann79/xbmc/raw/master/tools_addon/AmazonVideoWrapper.apk).

### Browser
Uses the user selected browser to play the chosen video. You can start the browser in fullscreen/kiosk mode, and with a separate user profile saved in the addon data folder. It's also possible to enter PINs for age restricted videos. This is realized by using [PyAutoGUI](https://pyautogui.readthedocs.io/en/latest/).

This mode requires you to be logged both in the addon and in the browser at the same time.

### Command/Script/Batch
Executes the provided command to start the video. Similarly to the browser mode, you can automatically switch to Fullscreen and enter PIN for age restricted videos. Additionally it is possible to pass the video framerate to the script using `{f}` as a parameter, while `{u}` passes the video URL.

The following script examples use the tools [DisplayChanger](http://12noon.com/?page_id=80) and [xrandr](http://www.x.org/archive/X11R7.5/doc/man/man1/xrandr.1.html) to switch the framerate.  
#### Windows
Use Displaychanger to change refresh rate and start Internet Explorer in Kiosk mode. Displaychanger can do this in one command, there is no need for a script file.

**Script:** `<Displaychanger path>\dc64.exe`  
**Parameters:** `-refresh={f} "C:\Program Files\Internet Explorer\iexplore.exe" -k "{u}"`
#### Linux
Use xrandr to change the refresh rate, start Chrome in Kiosk mode and set the refresh rate back to 60hz.

**Script:** `<script path>\myscript.sh`  
**Parameters:** `{f} "{u}"`  
```sh
#!/bin/sh
/usr/bin/xrandr -r $1
/usr/bin/google-chrome --kiosk $2
/usr/bin/xrandr -r 60
```
