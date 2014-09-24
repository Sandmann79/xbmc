// ==UserScript==
// @name          Amazon Instant Video Fullscreen Script
// @description   This will remove the white bars alongside amazon prime videos. (Used by XBMC)
// @include       http://www.amazon.com/gp/video/streaming/mini-mode.html*
// @Version       1.0
// @Firefox       1.5+
// @GmVersion     0.6.4
// @Author        Romans I XVI
// ==/UserScript==

(function()
{
   try {

   function addNewStyle(newStyle) {
    var styleElement = document.getElementById('styles_js');
    if (!styleElement) {
        styleElement = document.createElement('style');
        styleElement.type = 'text/css';
        styleElement.id = 'styles_js';
        document.getElementsByTagName('head')[0].appendChild(styleElement);
    }
    styleElement.appendChild(document.createTextNode(newStyle));
}
addNewStyle('body{margin:0 0px!important}');

   } catch (eErr) {
      alert ("Tester utility error: " + eErr);
   }

   return;
})();
