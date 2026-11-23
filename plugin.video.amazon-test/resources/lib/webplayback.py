#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" Playback through the API of the Prime Video web player (GetVodPlaybackResources, GetWidevineLicense)

Since Oct 2026 Amazon refuses HD licenses for devices without Widevine L1 on the classic GetPlaybackResources API,
the add-on then requests SD (480p at most). The web player of a Linux browser gets a license for up to 960x540 from
the same software CDM on this API. The video key is SW_SECURE_DECODE there, inputstream.adaptive notices that and
lets the CDM decode the video. The license is requested through the add-on proxy (/wvlic/), which wraps the
challenge into the JSON body and returns the bare license. The web manifest only lists AAC stereo, the proxy adds the
Dolby Digital Plus tracks of the unfiltered manifest, which use the same audio key. 720p and more stay refused
(Downgrade.Sd), the Linux CDM cannot prove HDCP.
"""
import json
from urllib.parse import quote_plus, urlencode

from .common import Globals, Settings, MechanizeLogin
from .configs import getConfig
from .logging import Log
from .network import getURL, GrabJSON, FQify

WEB_DTID = 'AOAGZA014O5RE'
# Skip markers of the web API -> element types of the skip button
SKIP_TYPES = {'SKIP_INTRO': 'INTRO', 'SKIP_RECAP': 'RECAP', 'SKIP_INTRO_RECAP': 'INTRO_RECAP'}


def _walk(node):
    """ Yields (dict, path) for every dict in a JSON tree """
    stack = [(node, ())]
    while stack:
        cur, path = stack.pop()
        if isinstance(cur, dict):
            yield cur, path
            stack.extend((v, path + (k,)) for k, v in cur.items() if isinstance(v, (dict, list)))
        elif isinstance(cur, list):
            stack.extend((v, path + (i,)) for i, v in enumerate(cur) if isinstance(v, (dict, list)))


def _envelope_value(value):
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for k in ('envelope', 'playbackEnvelope', 'value'):
            if isinstance(value.get(k), str):
                return value[k]
    return None


def _detail(asin):
    """ The detail page of a title as JSON """
    url = FQify(('' if Globals().UsePrimeVideo else '/gp/video') + f'/detail/{asin}')
    response = getURL(url, useCookie=True, rjson=False, silent=True,
                      headers={'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest'})
    if response and response.strip().startswith('{'):
        try:
            return json.loads(response)
        except ValueError:
            pass
    return GrabJSON(url) or {}


def find_envelope(asin):
    """ Envelope and title ID of the feature's playback action on the detail page (state/action/<ASIN>/.../playback)

    The page also holds envelopes of trailers (secondaryActions, autoplayTrailerHero), those are skipped. The playback ID
    of a movie is its GTI, of an episode its ASIN.
    """
    data = _detail(asin)
    best = None
    for node, path in _walk(data):
        env = _envelope_value(node.get('playbackEnvelope'))
        if not env:
            continue
        vmt = node.get('videoMaterialType')
        if node.get('isTrailer') or vmt == 'Trailer' or (vmt is None and node.get('isTrailer') is None):
            continue
        pid = node.get('playbackID') or node.get('titleID') or ''
        if pid == asin:
            score = 0
        elif asin in path:
            score = 1
        else:
            continue
        if node.get('entitlementType') in ('PURCHASE', 'RENTAL', 'PRIME', 'SUBSCRIPTION', 'FREE'):
            score -= 0.5
        if best is None or score < best[0]:
            best = (score, env, pid, path)
    if best is None:
        Log(f'[Web] No playback envelope for {asin} on its detail page', Log.INFO)
        return None, None
    Log(f'[Web] Playback envelope of {asin} at {"/".join(map(str, best[3]))}', Log.DEBUG)
    return best[1], best[2] if best[2].startswith('amzn1.dv.gti.') or best[2] == asin else asin

def _params(title_id):
    g = Globals()
    return {'deviceID': g.deviceID, 'deviceTypeID': WEB_DTID, 'gascEnabled': str(g.UsePrimeVideo).lower(),
            'marketplaceID': g.MarketID, 'firmware': '1', 'titleId': title_id}


def _request_body(envelope):
    return {
        'globalParameters': {
            'deviceCapabilityFamily': 'WebPlayer',
            'playbackEnvelope': envelope,
            'capabilityDiscriminators': {
                'operatingSystem': {'name': 'Linux', 'version': 'unknown'},
                'middleware': {'name': 'Firefox', 'version': '159.0'},
                'nativeApplication': {'name': 'Firefox', 'version': '159.0'},
                'hfrControlMode': 'Legacy',
                'displayResolution': {'height': 1080, 'width': 1920}}},
        'auditPingsRequest': {},
        'widevineServiceCertificateRequest': {},
        'playbackDataRequest': {},
        'timedTextUrlsRequest': {'supportedTimedTextFormats': ['TTMLv2', 'DFXP']},
        'transitionTimecodesRequest': {},
        'vodPlaylistedPlaybackUrlsRequest': {
            'device': {'hdcpLevel': '1.4', 'maxVideoResolution': '1080p', 'supportedStreamingTechnologies': ['DASH'],
                       'streamingTechnologies': {'DASH': {
                           'bitrateAdaptations': ['CBR', 'CVBR'], 'codecs': ['H264'], 'drmKeyScheme': 'DualKey',
                           'drmType': 'Widevine', 'dynamicRangeFormats': ['None'],
                           'edgeDeliveryAuthorizationSchemes': ['PVExchangeV1', 'Transparent'],
                           'fragmentRepresentations': ['ByteOffsetRange', 'SeparateFile'], 'frameRates': ['Standard'],
                           'stitchType': 'MultiPeriod', 'segmentInfoType': 'Base',
                           'timedTextRepresentations': ['NotInManifestNorStream', 'SeparateStreamInManifest'],
                           'trickplayRepresentations': ['NotInManifestNorStream'], 'variableAspectRatio': 'supported'}},
                       'displayWidth': 1920, 'displayHeight': 1080}}}


def _find_mpd(result):
    """ First manifest URL, usually playbackUrls/intraTitlePlaylist/0/urls/<n>/url """
    for node, path in _walk(result):
        for k, v in node.items():
            if isinstance(v, str) and v.startswith('http') and '.mpd' in v:
                return v
    return None


def _unfiltered(url):
    """ The manifest URL without the filter segments of the web player (like the classic API path for web devices) """
    import re
    while '$' in url:
        url = re.sub(r'(.*/)([^/]*\$[^/]*/)', r'\1', url)
    if 'amazon.pv-cdn.net' in url:
        url = url.replace('/dm/', '/')
    url = re.sub(r'/ww_[^/]*', '', url)
    return url.replace('/ondemand/', '/').replace('/iad_2/', '/')


def _subtitles(timed, proxy):
    """ Proxied subtitle URLs with Kodi-friendly file names, like the classic API path of the proxy """
    def lang_code(code):
        return code.split('-')[0].lower()

    chosen = getConfig('sub_langs', 'all').split(',')
    lists = (('subtitleUrls', False), ('forcedNarrativeUrls', True))
    entries = [(sub, forced) for key, forced in lists for sub in timed.get(key) or [] if sub.get('url') and sub.get('languageCode')]
    if 'all' not in chosen and not any(lang_code(s['languageCode']) in chosen for s, _ in entries):
        chosen = ['all']
    counts = {}
    for sub, forced in entries:
        k = (forced, lang_code(sub['languageCode']))
        counts[k] = counts.get(k, 0) + 1
    subs = []
    for sub, forced in entries:
        code = sub['languageCode']
        p1, _, p2 = code.partition('-')
        lang = p1.lower() if counts[(forced, lang_code(code))] == 1 or not p2 else f'{p1.lower()}-{p2.upper()}'
        if 'all' not in chosen and lang_code(code) not in chosen:
            continue
        sdh = 'sdh' in (sub.get('subtype') or '').lower() or 'sdh' in (sub.get('type') or '').lower()
        variant = ('-[CC]' if sdh else '') + ('.Forced' if forced else '')
        subs.append((lang, variant, f'http://{proxy}/subtitles/{quote_plus(sub["url"])}/{lang}{variant}.srt'))
    return [s[2] for s in sorted(subs)]


def _skip_elements(timecodes):
    """ Skip markers of the web API in the format of the classic API (skipElements) """
    elements = []
    for event in (timecodes.get('result') or {}).get('events') or []:
        kind = SKIP_TYPES.get(event.get('eventType'))
        if kind and event.get('endTimeMs'):
            elements.append({'elementType': kind, 'startTimecodeMs': int(event.get('startTimeMs') or 0),
                             'endTimecodeMs': int(event['endTimeMs'])})
    return elements


def prepare(asin):
    """ Playback data for inputstream.adaptive, or None to fall back to the classic API """
    g, s = Globals(), Settings()
    envelope, title_id = find_envelope(asin)
    if not envelope:
        return None
    cookie = MechanizeLogin(preferToken=False)
    if not cookie or isinstance(cookie, dict):
        Log('[Web] No website cookies, the web player API needs them', Log.INFO)
        return None

    ua = getConfig('UserAgent')
    origin = {'Origin': g.BaseUrl, 'Referer': g.BaseUrl + '/'}
    url = f'{g.ATVUrl}/playback/prs/GetVodPlaybackResources?' + urlencode(_params(title_id))
    data = getURL(url, useCookie=cookie, postdata=json.dumps(_request_body(envelope)), silent=True,
                  headers=dict(origin, **{'Content-Type': 'text/plain;charset=UTF-8', 'Accept': '*/*'}))
    if not data:
        Log(f'[Web] GetVodPlaybackResources failed (HTTP {getattr(getURL, "lastResponseCode", "?")})', Log.ERROR)
        return None
    urls = data.get('vodPlaylistedPlaybackUrls') or {}
    if 'result' not in urls:
        info = {k: v for k, v in data.items() if k in ('vodPlaylistedPlaybackUrls', 'error', 'errors', 'message', 'code')}
        Log(f'[Web] No playback URLs (HTTP {getattr(getURL, "lastResponseCode", "?")}): {json.dumps(info or sorted(data))[:1500]}', Log.ERROR)
        return None
    mpd = _find_mpd(urls['result'])
    handoff = (data.get('sessionization') or {}).get('sessionHandoffToken')
    if not mpd or not handoff:
        Log(f'[Web] Unexpected playback data: {json.dumps(urls["result"])[:1000]}', Log.ERROR)
        return None
    cert = ((data.get('widevineServiceCertificate') or {}).get('result') or {}).get('encodedServiceCertificate')

    lic_url = f'{g.ATVUrl}/playback/drm-vod/GetWidevineLicense?' + urlencode(_params(title_id))
    req_headers = dict(origin, **{'Cookie': '; '.join(f'{k}={v}' for k, v in cookie.items()), 'User-Agent': ua,
                                  'X-Pv-Envelope': envelope, 'X-Pv-Handoff': handoff})
    timecodes = {'skipElements': _skip_elements(data.get('transitionTimecodes') or {})}
    Log(f'[Web] Playing {asin} through the web player API', Log.INFO)
    return {'mpd': f'http://{s.proxyaddress}/mpd/{quote_plus(mpd)}/{quote_plus(_unfiltered(mpd))}',
            'subs': _subtitles((data.get('timedTextUrls') or {}).get('result') or {}, s.proxyaddress),
            'timecodes': timecodes,
            'lic_url': f'http://{s.proxyaddress}/wvlic/{quote_plus(lic_url)}',
            'req_headers': req_headers,
            'req_param': '|' + urlencode(req_headers) + '|R{SSM}|',
            'headers': {'User-Agent': ua},
            'cookie': cookie,
            'cert': cert}
