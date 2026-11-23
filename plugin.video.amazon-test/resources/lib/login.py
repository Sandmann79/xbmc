#!/usr/bin/env python
# -*- coding: utf-8 -*-

import html
import os
import json
import mechanicalsoup
import re
import requests
import secrets
import socket
import threading
import time
from base64 import urlsafe_b64encode, b64encode, b64decode, b16encode
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from random import randint
from hashlib import sha256
from os.path import join as OSPJoin
from uuid import uuid4
from urllib.parse import urlencode, urlparse, parse_qs
import xml.etree.ElementTree as ET

import pyxbmct
import xbmcgui, xbmc, xbmcvfs

from .common import Globals, Settings, sleep, parseHTML
from .network import getURL
from .logging import Log, WriteLog, LogJSON
from .l10n import getString, datetimeParser
from .configs import getConfig, writeConfig
from .qrcode import make_qr_png


_g = Globals()
_s = Settings()

_RE_REDACT_SENSITIVE = re.compile(
    r'(?i)((?:access_token|refresh_token|source_token|actor_access_token|actor_refresh_token|account_refresh_token|password|guess|otpCode|pin|authorization|cookie|x-amzn-sessionid|ubid-\w+|at-\w+|sess-at-\w+|session-token)["\'\s:=]+)([^"\'&\s,;}{]+)'
)
_RE_REDACT_PEM = re.compile(
    r'-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----'
)
_RE_REDACT_ADP = re.compile(
    r'(?i)(<(?:adp_token|device_private_key|store_authentication_cookie)>).*?(</(?:adp_token|device_private_key|store_authentication_cookie)>)|(\{enc:[^}]+\}(?:\{[^}]+\})+)'
)


def _redact_sensitive(text, email=None):
    if not text:
        return ''
    s = str(text)
    if email:
        s = s.replace(email, '**@**')
    s = _RE_REDACT_PEM.sub('***REDACTED_PRIVATE_KEY***', s)
    s = _RE_REDACT_ADP.sub(lambda m: f'{m.group(1)}***REDACTED***{m.group(2)}' if m.group(1) else '***REDACTED_ADP_TOKEN***', s)
    return _RE_REDACT_SENSITIVE.sub(r'\1***REDACTED***', s)


def _read_der_len(buf, idx):
    b = buf[idx]
    idx += 1
    if b < 0x80:
        return b, idx
    n = b & 0x7f
    return int.from_bytes(buf[idx:idx + n], 'big'), idx + n


def _parse_rsa_private_key(pem_str):
    b64 = ''.join(line.strip() for line in pem_str.strip().splitlines() if not line.startswith('-----'))
    der = b64decode(b64)
    if der[0] != 0x30:
        raise ValueError('Invalid DER RSA private key')
    _, idx = _read_der_len(der, 1)
    # version INTEGER
    if der[idx] != 0x02:
        raise ValueError('Invalid DER RSA key version')
    v_len, idx = _read_der_len(der, idx + 1)
    idx += v_len
    # PKCS#8 wraps PKCS#1 key inside an OCTET STRING after AlgorithmIdentifier SEQUENCE
    if der[idx] == 0x30:
        alg_len, idx = _read_der_len(der, idx + 1)
        idx += alg_len
        if der[idx] != 0x04:
            raise ValueError('Invalid PKCS#8 private key octet string')
        key_len, idx = _read_der_len(der, idx + 1)
        der = der[idx:idx + key_len]
        if der[0] != 0x30:
            raise ValueError('Invalid inner PKCS#1 RSA key')
        _, idx = _read_der_len(der, 1)
        if der[idx] != 0x02:
            raise ValueError('Invalid inner PKCS#1 version')
        v_len, idx = _read_der_len(der, idx + 1)
        idx += v_len
    ints = []
    while len(ints) < 3 and idx < len(der):
        if der[idx] != 0x02:
            raise ValueError('Expected ASN.1 INTEGER in RSA key')
        length, idx = _read_der_len(der, idx + 1)
        ints.append(int.from_bytes(der[idx:idx + length], 'big'))
        idx += length
    # modulus (n), publicExponent (e), privateExponent (d)
    return ints[0], ints[1], ints[2]


def _rsa_sign_sha256(pem_str, data_bytes):
    n, _, d = _parse_rsa_private_key(pem_str)
    k = (n.bit_length() + 7) // 8
    digest = sha256(data_bytes).digest()
    # PKCS#1 v1.5 DigestInfo prefix for SHA-256
    digest_info = bytes.fromhex('3031300d060960864801650304020105000420') + digest
    ps_len = k - len(digest_info) - 3
    if ps_len < 8:
        raise ValueError('RSA key too short for SHA-256 signature')
    em = b'\x00\x01' + (b'\xff' * ps_len) + b'\x00' + digest_info
    sig_int = pow(int.from_bytes(em, 'big'), d, n)
    return b64encode(sig_int.to_bytes(k, 'big')).decode('ascii')


def _adp_sign_headers(method, path, body, adp_token, private_key):
    timestamp = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    payload = f'{method}\n{path}\n{timestamp}\n{body}\n{adp_token}'.encode('utf-8')
    sig = _rsa_sign_sha256(private_key, payload)
    return {
        'x-adp-token': adp_token,
        'x-adp-alg': 'SHA256WithRSA:1.0',
        'x-adp-signature': f'{sig}:{timestamp}',
    }


def getTerritory(user):
    if len(user.get('deviceid', '')) != 32:
        from uuid import uuid4
        user['deviceid'] = uuid4().hex.lower()

    areas = [{'atvurl': '', 'baseurl': '', 'mid': '', 'pv': False, 'country': ''},
             {'atvurl': 'https://atv-ps-eu.amazon.de', 'baseurl': 'https://www.amazon.de', 'mid': 'A1PA6795UKMFR9', 'pv': False, 'locale': 'de',
              'lang': 'de_DE', 'sidomain': 'amazon.de'},
             {'atvurl': 'https://atv-ps-eu.amazon.co.uk', 'baseurl': 'https://www.amazon.co.uk', 'mid': 'A1F83G8C2ARO7P', 'pv': False, 'locale': 'uk',
              'lang': 'en_US', 'sidomain': 'amazon.co.uk'},
             {'atvurl': 'https://atv-ps.amazon.com', 'baseurl': 'https://www.amazon.com', 'mid': 'ATVPDKIKX0DER', 'pv': False, 'locale': 'us', 'lang': 'en_US',
              'sidomain': 'amazon.com'},
             {'atvurl': 'https://atv-ps-fe.amazon.co.jp', 'baseurl': 'https://www.amazon.co.jp', 'mid': 'A1VC38T7YXB528', 'pv': False, 'locale': 'jp',
              'lang': 'ja_JP', 'sidomain': 'amazon.co.jp'},
             {'atvurl': 'https://atv-ps-eu.primevideo.com', 'baseurl': 'https://www.primevideo.com', 'mid': 'A3K6Y4MI8GDYMT', 'pv': True, 'locale': 'us',
              'lang': 'en_US', 'sidomain': 'amazon.com'},
             {'atvurl': 'https://atv-ps-eu.primevideo.com', 'baseurl': 'https://www.primevideo.com', 'mid': 'A2MFUE2XK8ZSSY', 'pv': True, 'locale': 'us',
              'lang': 'en_US', 'sidomain': 'amazon.com'},
             {'atvurl': 'https://atv-ps-fe.primevideo.com', 'baseurl': 'https://www.primevideo.com', 'mid': 'A15PK738MTQHSO', 'pv': True, 'locale': 'us',
              'lang': 'en_US', 'sidomain': 'amazon.com'},
             {'atvurl': 'https://atv-ps.primevideo.com', 'baseurl': 'https://www.primevideo.com', 'mid': 'ART4WZ8MWBX2Y', 'pv': True, 'locale': 'us',
              'lang': 'en_US', 'sidomain': 'amazon.com'}]
    area = areas[_s.region]

    if len(user.get('mid', '')) > 0:
        user.update({k: v for l in areas for k, v in l.items() if l['mid'] == user['mid'] and k not in user})
    elif area['mid']:
        user.update(area)
    else:
        Log('Retrieve territoral config')
        loc = ','.join(k for k, v in datetimeParser.items() if 'language' in v)
        data = getURL(f"https://atv-ps.amazon.com/cdp/usage/v3/GetAppStartupConfig?"
                      f"deviceTypeID=A28RQHJKHM2A2W&deviceID={user['deviceid']}&firmware=1&version=1&supportedLocales={loc}&format=json")
        if not hasattr(data, 'keys'):
            return user, False
        if 'customerConfig' in data.keys():
            terr = data['territoryConfig']
            cust = data['customerConfig']
            host = terr['defaultVideoWebsite']
            reg = cust['homeRegion'].lower()
            reg = '' if 'na' in reg else '-' + reg
            user['atvurl'] = host.replace('www.', '').replace('//', f'//atv-ps{reg}.')
            user['baseurl'] = terr['primeSignupBaseUrl']
            user['mid'] = terr['avMarketplace']
            user['pv'] = 'primevideo' in host
            user.update({k: v for l in areas for k, v in l.items() if l['mid'] == user['mid'] and k in 'locale,sidomain,lang'})
            if 'uxLocale' in cust['locale']:
                user['lang'] = cust['locale']['uxLocale']
    return user, True


def MFACheck(br, email, soup):
    def _insertLF(string, begin=70):
        spc = string.find(' ', begin)
        return string[:spc] + '\n' + string[spc + 1:] if spc > 0 else string

    Log('MFA, DCQ or Captcha form')
    uni_soup = soup.__unicode__()
    try:
        form = br.select_form('form[name="signIn"]')
    except mechanicalsoup.LinkNotFoundError:
        form = br.select_form()

    if 'auth-mfa-form' in uni_soup:
        Log('OTP code', Log.DEBUG)
        msg = soup.find('form', attrs={'id': 'auth-mfa-form'})
        msgtxt = msg.p.get_text(strip=True)
        msgtxt += '\n\n' + soup.find('div', attrs={'class': 'a-alert-content'}).get_text(strip=True) if 'a-alert-content' in uni_soup else ''
        wnd = _InputBox(msgtxt)
        wnd.doModal()
        if len(wnd.inp) > 0:
            br['otpCode'] = wnd.inp
        else:
            return None
    elif 'ap_dcq_form' in uni_soup:
        Log('DCQ form', Log.DEBUG)
        msg = soup.find('div', attrs={'id': 'message_warning'})
        _g.dialog.ok(_g.__plugin__, msg.p.get_text(strip=True))
        dcq = soup.find('div', attrs={'id': 'ap_dcq1a_pagelet'})
        dcq_title = dcq.find('div', attrs={'id': 'ap_dcq1a_pagelet_title'}).get_text(strip=True)
        q_title = []
        q_id = []
        for q in dcq.findAll('div', attrs={'class': 'dcq_question'}):
            if q.span.label:
                label = q.span.label.get_text(strip=True).replace('  ', '').replace('\n', '')
                if q.span.label.span:
                    label = label.replace(str(q.span.label.span), q.span.label.span.text)
                q_title.append(_insertLF(label))
                q_id.append(q.input['id'])

        sel = _g.dialog.select(_insertLF(dcq_title, 60), q_title) if len(q_title) > 1 else 0
        if sel < 0:
            return None

        ret = _g.dialog.input(q_title[sel])
        if ret:
            br[q_id[sel]] = ret
        else:
            return None
    elif ('ap_captcha_img_label' in uni_soup) or ('auth-captcha-image-container' in uni_soup):
        Log('Captcha', Log.DEBUG)
        wnd = _Captcha((getString(30008).split('…')[0]), soup, email)
        wnd.doModal()
        if wnd.email and wnd.cap and wnd.pwd:
            form.set_input({'email': wnd.email, 'password': wnd.pwd, 'guess': wnd.cap})
        else:
            return None
        del wnd
    elif 'claimspicker' in uni_soup:
        Log('Send otp request', Log.DEBUG)
        msg = soup.find('form', attrs={'name': 'claimspicker'})
        cs_title = msg.find('div', attrs={'class': 'a-row a-spacing-small'}).get_text(strip=True)
        cs_quest = msg.find('label', attrs={'class': 'a-form-label'})
        cs_hint = msg.find(lambda tag: tag.name == 'div' and tag.get('class') == ['a-row']).get_text(strip=True)
        choices = []
        if cs_quest:
            for c in soup.findAll('div', attrs={'data-a-input-name': 'option'}):
                choices.append((c.span.get_text(strip=True), c.input['name'], c.input['value']))
            sel = _g.dialog.select(f'{cs_title} - {cs_quest.get_text(strip=True)}', [k[0] for k in choices])
        else:
            sel = 100 if _g.dialog.ok(cs_title, cs_hint) else -1

        if sel > -1:
            if sel < 100:
                form.set_radio({choices[sel][1]: choices[sel][2]})
        else:
            return None
    elif 'auth-select-device-form' in uni_soup:
        Log('Select device form', Log.DEBUG)
        sd_form = soup.find('form', attrs={'id': 'auth-select-device-form'})
        sd_hint = sd_form.parent.p.get_text(strip=True)
        choices = []
        for c in sd_form.findAll('label'):
            choices.append((c.span.get_text(strip=True), c.input['name'], c.input['value']))
        sel = _g.dialog.select(sd_hint, [k[0] for k in choices])

        if sel > -1:
            form.set_radio({choices[sel][1]: choices[sel][2]})
        else:
            return None
    elif 'verifyOtp' in uni_soup:
        Log('verifyOtp', Log.DEBUG)
        br.select_form('form[id="verification-code-form"]')
        msg = [m.get_text() for m in soup.find_all('span', attrs={'class': 'transaction-approval-word-break'})]
        [msg.append(m.get_text()) for m in soup.find_all('div', attrs={'id': 'invalid-otp-code-message'}) if 'invalid-otp-code-message' in uni_soup]
        wnd = _InputBox('\n\n'.join(msg[1:]), task=msg[0])
        wnd.doModal()
        if len(wnd.inp) > 0:
            br['otpCode'] = wnd.inp
        else:
            return None
    elif 'fwcim-form' in uni_soup:
        Log('fcwim / otp email', Log.DEBUG)
        msg = soup.find('div', attrs={'class': 'a-row a-spacing-micro cvf-widget-input-code-label'})
        if msg:
            wnd = _InputBox(msg.get_text(strip=True))
            wnd.doModal()
            if len(wnd.inp) > 0:
                br['code'] = wnd.inp
            else:
                return None
        elif soup.find('img', attrs={'alt': 'captcha'}):
            wnd = _Challenge(soup)
            if not wnd.solve_captcha():
                wnd.doModal()
            if wnd.cap:
                submit = soup.find('input', value='verifyCaptcha')
                form.choose_submit(submit)
                form.set_input({'cvf_captcha_input': wnd.cap})
            else:
                return None
            del wnd
        elif soup.find('div', attrs={'id': 'auth-error-message-box'}):
            br.select_form('form[id="ap_login_form"]')
            br['email'] = email
            return br
        elif soup.find('iframe', attrs={'id': 'cvf-aamation-challenge-iframe'}):
            _g.dialog.ok(getString(30200), getString(30287))
            return None
        else:
            return None
    elif 'validateCaptcha' in uni_soup:
        Log('validateCaptcha', Log.DEBUG)
        wnd = _Challenge(soup)
        if wnd.set_inp and not wnd.solve_captcha():
            wnd.doModal()
        if wnd.cap:
            # MechanicalSoup is using the field names, not IDs
            # id is captchacharacters, which causes exception to be raised
            form.set_input({'field-keywords': wnd.cap})
        elif wnd.set_inp:
            return None
        del wnd
    elif 'pollingForm' in uni_soup and 'verifyOtp' not in uni_soup:
        Log('polling', Log.DEBUG)
        msg = soup.find('span', attrs={'class': 'transaction-approval-word-break'}).get_text(strip=True)
        msg += '\n'
        rows = soup.find('div', attrs={'id': re.compile('.*channelDetails.*')})
        for row in rows.find_all('div', attrs={'class': 'a-row'}):
            msg += re.sub('\\s{2,}', ': ', row.get_text())
        pd = _ProgressDialog(msg)
        pd.show()
        refresh = time.time()
        form_id = form_poll = 'pollingForm'
        per = 0
        while True:
            if per > 99:
                val = -5
            if per < 1:
                val = 5
            per += val
            pd.sl_progress.setPercent(per)
            if pd.iscanceled:
                br = None
                break
            if time.time() > refresh + 5:
                url = br.get_url()
                br.select_form(f'form[id="{form_id}"]')
                br.submit_selected()
                response, soup = parseHTML(br)
                form_id = form_poll
                WriteLog(_redact_sensitive(response, email), 'login-pollingform')
                stat = soup.find('input', attrs={'name': 'transactionApprovalStatus'})['value']
                if stat in ['TransactionCompleted', 'TransactionCompletionTimeout']:
                    parsed_url = urlparse(url)
                    query = parse_qs(parsed_url.query)
                    br.open(query['openid.return_to'][0])
                    break
                elif stat in ['TransactionExpired', 'TransactionResponded']:
                    form_id = 'resend-approval-form'
                else:
                    refresh = time.time()
                br.open(url)
            sleep(0.1)
        pd.close()
    return br


_LOCALE_COUNTRY = {'de': 'DE', 'uk': 'GB', 'us': 'US', 'jp': 'JP'}
_RE_RAW_AUTH_CODE = re.compile(r'^[A-Za-z0-9_-]{12,256}$')


def _get_local_ip():
    for target in (('8.8.8.8', 80), ('192.0.2.1', 80)):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.connect(target)
                ip = sock.getsockname()[0]
                if ip and not ip.startswith('127.'):
                    return ip
        except OSError:
            pass
    try:
        ip = socket.gethostbyname(socket.gethostname())
        if ip and not ip.startswith('127.'):
            return ip
    except OSError:
        pass
    return '127.0.0.1'


def _build_oauth_url(user, clientid, challenge):
    domain = user['sidomain']
    lang = user.get('lang', 'en_US')
    country = _LOCALE_COUNTRY.get(user.get('locale', '').lower()) or lang.split('_')[-1].upper()
    challenge_str = challenge.decode('ascii') if isinstance(challenge, bytes) else str(challenge)
    query = {
        'accountStatusPolicy': 'P1',
        'countryCode': country,
        'disableLoginPrepopulate': 0,
        'language': lang,
        'openid.assoc_handle': 'amzn_piv_android_v2_' + user['locale'],
        'openid.claimed_id': 'http://specs.openid.net/auth/2.0/identifier_select',
        'openid.identity': 'http://specs.openid.net/auth/2.0/identifier_select',
        'openid.mode': 'checkid_setup',
        'openid.ns': 'http://specs.openid.net/auth/2.0',
        'openid.ns.oa2': 'http://www.amazon.com/ap/ext/oauth/2',
        'openid.ns.pape': 'http://specs.openid.net/extensions/pape/1.0',
        'openid.oa2.client_id': f'device:{clientid}',
        'openid.oa2.code_challenge': challenge_str,
        'openid.oa2.code_challenge_method': 'S256',
        'openid.oa2.response_type': 'code',
        'openid.oa2.scope': 'device_auth_access',
        'openid.pape.max_auth_age': 0,
        'openid.return_to': f'https://www.{domain}/ap/maplanding',
        'pageId': 'amzn_dv_ios_blue',
    }
    return f'https://www.{domain}/ap/signin?{urlencode(query)}'


def _extract_auth_code(raw_value):
    if not raw_value:
        return None
    val = str(raw_value).strip()
    if not val:
        return None
    if 'openid.oa2.authorization_code' in val:
        parsed = urlparse(val)
        for source in (parsed.query, parsed.fragment, val.lstrip('?')):
            if not source:
                continue
            codes = parse_qs(source).get('openid.oa2.authorization_code')
            if codes and codes[0].strip():
                return codes[0].strip()
        return None
    if _RE_RAW_AUTH_CODE.fullmatch(val):
        return val
    return None


def _render_qr_login_page(oauth_url, form_action, lang, texts, error=None, done=False):
    lang_attr = html.escape(str(lang or 'en').split('_')[0].lower(), quote=True)
    host = urlparse(oauth_url).netloc or 'www.amazon.com'
    placeholder = f'https://{host}/ap/maplanding?openid.oa2.authorization_code=...'

    if done:
        body = (
            f'<div class="card ok"><h2>{html.escape(texts["done_head"])}</h2>'
            f'<p>{html.escape(texts["done_msg"])}</p></div>'
        )
    else:
        err_html = f'<div class="err">{html.escape(error)}</div>' if error else ''
        body = (
            f'<div class="card">'
            f'<h2>{html.escape(texts["step1_head"])}</h2>'
            f'<a class="btn" href="{html.escape(oauth_url, quote=True)}" target="_blank" rel="noopener noreferrer">{html.escape(texts["step1_btn"])}</a>'
            f'<p class="hint">{html.escape(texts["step1_hint"])}</p>'
            f'</div>'
            f'<div class="card">'
            f'<h2>{html.escape(texts["step2_head"])}</h2>'
            f'<p class="hint">{html.escape(texts["step2_hint"])}</p>'
            f'{err_html}'
            f'<form method="POST" action="{html.escape(form_action, quote=True)}">'
            f'<textarea name="redirect_url" rows="3" placeholder="{html.escape(placeholder, quote=True)}" '
            f'spellcheck="false" autocomplete="off" autocapitalize="off" required></textarea>'
            f'<button class="btn submit" type="submit">{html.escape(texts["submit_btn"])}</button>'
            f'</form>'
            f'</div>'
        )

    return (
        f'<!DOCTYPE html><html lang="{lang_attr}"><head>'
        '<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{html.escape(texts["title"])}</title>'
        '<style>'
        'body{margin:0;padding:16px;background:#0f171e;color:#f2f4f8;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;}'
        '.wrap{max-width:520px;margin:0 auto;}'
        'h1{font-size:1.25rem;margin:0 0 16px;color:#00a8e1;text-align:center;}'
        'h2{font-size:1.05rem;margin:0 0 12px;}'
        '.card{background:#1a242f;border-radius:10px;padding:16px;margin-bottom:14px;box-shadow:0 2px 8px rgba(0,0,0,.35);}'
        '.card.ok{border:1px solid #2ecc71;text-align:center;}'
        '.hint{font-size:.9rem;color:#c3ccd4;line-height:1.45;margin:10px 0 0;}'
        '.btn{display:block;width:100%;box-sizing:border-box;text-align:center;padding:13px 16px;border:0;border-radius:8px;'
        'background:#00a8e1;color:#fff;font-size:1rem;font-weight:600;text-decoration:none;cursor:pointer;}'
        '.btn.submit{background:#1f8b4c;margin-top:10px;}'
        'textarea{width:100%;box-sizing:border-box;padding:10px;border-radius:8px;border:1px solid #3c4d5e;'
        'background:#0f171e;color:#fff;font-size:.9rem;resize:vertical;}'
        '.err{background:#5a1e24;border:1px solid #e74c3c;color:#ffd6d6;padding:10px;border-radius:8px;margin-bottom:10px;font-size:.9rem;}'
        '</style></head><body><div class="wrap">'
        f'<h1>{html.escape(texts["title"])}</h1>{body}</div></body></html>'
    ).encode('utf-8')


class _ReusableThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True


def _start_login_server(oauth_url, lang):
    token = secrets.token_urlsafe(9)
    expected_path = f'/{token}'
    texts = {
        'title': getString(30319),
        'step1_head': getString(30320),
        'step1_btn': getString(30321),
        'step1_hint': getString(30322),
        'step2_head': getString(30323),
        'step2_hint': getString(30324),
        'submit_btn': getString(30325),
        'done_head': getString(30326),
        'done_msg': getString(30327),
        'invalid_msg': getString(30328),
    }
    state = {
        'event': threading.Event(),
        'lock': threading.Lock(),
        'auth_code': None,
        'on_received': None,
    }

    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            return

        def _send_html(self, status, content):
            self.send_response(status)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(content)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(content)

        def _path_ok(self):
            req_path = urlparse(self.path).path.rstrip('/')
            return req_path == expected_path

        def do_GET(self):
            if not self._path_ok():
                self.send_error(404)
                return
            with state['lock']:
                done = state['auth_code'] is not None
            page = _render_qr_login_page(oauth_url, expected_path, lang, texts, done=done)
            self._send_html(200, page)

        def do_POST(self):
            if not self._path_ok():
                self.send_error(404)
                return
            try:
                length = int(self.headers.get('Content-Length', '0'))
            except ValueError:
                length = 0
            if length <= 0 or length > 16384:
                self.send_error(413 if length > 16384 else 400)
                return
            raw_body = self.rfile.read(length).decode('utf-8', errors='replace')
            form = parse_qs(raw_body)
            submitted = form.get('redirect_url', [''])[0]
            code = _extract_auth_code(submitted)
            if not code:
                page = _render_qr_login_page(oauth_url, expected_path, lang, texts, error=texts['invalid_msg'])
                self._send_html(400, page)
                return
            cb = None
            with state['lock']:
                if state['auth_code'] is None:
                    state['auth_code'] = code
                    state['event'].set()
                    cb = state['on_received']
            page = _render_qr_login_page(oauth_url, expected_path, lang, texts, done=True)
            self._send_html(200, page)
            if cb:
                try:
                    cb()
                except Exception:
                    pass

    server = _ReusableThreadingHTTPServer(('0.0.0.0', 0), _Handler)
    port = server.server_address[1]
    lan_ip = _get_local_ip()
    lan_url = f'http://{lan_ip}:{port}{expected_path}'
    thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': 0.2}, daemon=True)
    thread.start()
    Log(f'QR login helper server listening on {lan_ip}:{port}', Log.DEBUG)
    return server, lan_url, state


def _browser_qr_login(user, clientid, challenge):
    oauth_url = _build_oauth_url(user, clientid, challenge)
    server, lan_url, state = _start_login_server(oauth_url, user.get('lang', 'en_US'))
    qr_path = OSPJoin(_g.DATA_PATH, f'qr-login-{int(time.time() * 1000)}.png')
    stop_watcher = threading.Event()
    dlg = None
    try:
        png_bytes = make_qr_png(lan_url, scale=10, border=4)
        with xbmcvfs.File(qr_path, 'w') as fp_qr:
            fp_qr.write(bytearray(png_bytes))

        dlg = _QRLoginDialog(getString(30314), qr_path, lan_url)
        with state['lock']:
            state['on_received'] = dlg.close

        monitor = xbmc.Monitor()

        def _watch():
            while not stop_watcher.is_set():
                if state['event'].is_set() or monitor.abortRequested():
                    try:
                        dlg.close()
                    except Exception:
                        pass
                    break
                state['event'].wait(0.25)

        watcher = threading.Thread(target=_watch, daemon=True)
        watcher.start()
        dlg.doModal()
    finally:
        stop_watcher.set()
        try:
            server.shutdown()
            server.server_close()
        except Exception:
            pass
        if xbmcvfs.exists(qr_path):
            xbmcvfs.delete(qr_path)

    auth_code = state['auth_code']
    if not auth_code and dlg and dlg.manual_requested:
        while True:
            keyboard = xbmc.Keyboard('', getString(30318))
            keyboard.doModal()
            if not keyboard.isConfirmed():
                return None
            auth_code = _extract_auth_code(keyboard.getText())
            if auth_code:
                break
            _g.dialog.ok(getString(30200), getString(30318))

    if not auth_code:
        return None
    return f"https://www.{user['sidomain']}/ap/maplanding?{urlencode({'openid.oa2.authorization_code': auth_code})}"


def LogIn(retToken=False):
    def _setLoginPW(visible):
        keyboard = xbmc.Keyboard('', getString(30003))
        keyboard.setHiddenInput(visible is False)
        keyboard.doModal(60000)
        if keyboard.isConfirmed() and keyboard.getText():
            password = keyboard.getText()
            return password
        return False

    def _findElem(br, form=None, link=None, log='si'):
        response, soup = parseHTML(br)
        while 'validateCaptcha' in response:
            br = MFACheck(br, email, soup)
            if br is None:
                return False
            if not br.get_current_form() is None:
                br.submit_selected()
            response, soup = parseHTML(br)

        caperr = -5
        while caperr:
            try:
                if form:
                    br.select_form(f'form[name="{form}"]')
                elif link:
                    link = [link] if isinstance(link, dict) else link
                    suc = False
                    for lnk in link:
                        try:
                            br.follow_link(attrs=lnk)
                            suc = True
                            break
                        except mechanicalsoup.LinkNotFoundError:
                            pass
                    if not suc:
                        raise mechanicalsoup.LinkNotFoundError
                break
            except mechanicalsoup.LinkNotFoundError:
                sleep(randint(750, 3000) / 1000)
                caperr += 1
                if _s.data_source == 0 and _s.enable_uhd is False:
                    from .network import getUA
                    getUA(True)
                    br.session.headers.update({'User-Agent': getConfig('UserAgent')})
                Log(f'Connect to SignIn Page {-caperr} attempts left')
                br.refresh()
                WriteLog(_redact_sensitive(br.get_current_page(), email), f'login-{log}')
        else:
            _g.dialog.ok(getString(30200), getString(30213).format(_g.LOG_PATH))
            return False
        return True

    def _finalize_login(user, cj, addUser):
        if _s.multiuser:
            user['name'] = _g.dialog.input(getString(30135), user['name'])
            if not user['name']:
                return False

        remLoginData(False)
        _s.login_acc = user['name']
        if not _s.multiuser:
            _g.dialog.ok(getString(30215), f"{getString(30014)} {user['name']}")

        addUser(user)
        return getToken(user) if retToken else cj

    class LoginLocked(Exception):
        pass

    from contextlib import contextmanager

    @contextmanager
    def LoginLock():
        try:
            bLocked = 'false' != getConfig('loginlock', 'false')
            if not bLocked:
                writeConfig('loginlock', 'true')
            yield bLocked
        except LoginLocked:  # Already locked
            pass
        except Exception as e:  # Something went horribly wrong, release and re-raise
            writeConfig('loginlock', 'false')
            raise e
        else:  # All fine, release
            writeConfig('loginlock', 'false')

    with LoginLock() as locked:
        if locked:
            raise LoginLocked

        Log('Login')
        from .users import loadUser, addUser
        user = getTerritory(loadUser(empty=True))
        if False is user[1]:
            return False
        user = user[0]

        sel = _g.dialog.select(getString(30008).split('…')[0], [getString(30314), getString(30315)])
        if sel < 0:
            return False

        if sel == 0:
            clientid = b16encode(f"{user['deviceid']}#{_g.dtid_android_parent}".encode()).decode().lower()
            verifier = urlsafe_b64encode(os.urandom(32)).rstrip(b"=")
            challenge = urlsafe_b64encode(sha256(verifier).digest()).rstrip(b"=")
            url = _browser_qr_login(user, clientid, challenge)
            if not url:
                return False
            user = registerDevice(url, user, verifier, clientid)
            if not user:
                return False
            cj = requests.cookies.RequestsCookieJar()
            for cname, cval in (user.get('cookie') or {}).items():
                cj.set(cname, cval)
            return _finalize_login(user, cj, addUser)

        password = ''
        keyboard = xbmc.Keyboard('', getString(30002))
        keyboard.doModal()
        if keyboard.isConfirmed() and keyboard.getText():
            email = keyboard.getText()
            password = _setLoginPW(_s.show_pass)

        if password:
            cj = requests.cookies.RequestsCookieJar()
            br = mechanicalsoup.StatefulBrowser(soup_config={'features': 'html.parser'})
            br.set_cookiejar(cj)
            br.session.verify = _s.ssl_verif
            br.set_verbose(2)
            Log('Connect to SignIn Page')
            if False:
                br.session.headers.update({'User-Agent': getConfig('UserAgent')})
                br.open(user['baseurl'] + ('/gp/flex/sign-out.html' if not user['pv'] else '/auth-redirect/?signin=1'))
                Log(br.session.headers)
                br.session.headers.update({
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Encoding': 'gzip, deflate',
                    'Accept-Language': _g.userAcceptLanguages,
                    'Cache-Control': 'max-age=0',
                    'Connection': 'keep-alive',
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'Origin': '/'.join(br.get_url().split('/')[0:3]),
                    'Upgrade-Insecure-Requests': '1'
                })
            else:
                clientid = b16encode(f"{user['deviceid']}#{_g.dtid_android_parent}".encode()).decode().lower()
                verifier = urlsafe_b64encode(os.urandom(32)).rstrip(b"=")
                challenge = urlsafe_b64encode(sha256(verifier).digest()).rstrip(b"=")
                frc = b64encode(os.urandom(313)).decode("ascii")
                map_md = {'device_registration_data': {'software_version': '130050002'},
                          'app_identifier': {'package': 'com.amazon.avod.thirdpartyclient',
                                             'SHA-256': ['2f19adeb284eb36f7f07786152b9a1d14b21653203ad0b04ebbf9c73ab6d7625'],
                                             'app_version': '404000357',
                                             'app_version_name': '3.0.404.357',
                                             'app_sms_hash': 'e0kK4QFSWp0',
                                             'map_version': 'MAPAndroidLib-1.3.34875.0'},
                          'app_info': {'auto_pv': 0, 'auto_pv_with_smsretriever': 0, 'smartlock_supported': 0, 'permission_runtime_grant': 0}}
                init_cookie = {'frc': frc, 'map-md': b64encode(json.dumps(map_md).encode()).decode(), 'sid': ''}
                br.session.headers.update(_g.headers_android)
                br.open('https://www.' + user['sidomain'])
                WriteLog(_redact_sensitive(br.get_current_page(), email), 'login-bu')
                if not _findElem(br, link=[{'class': 'nav-show-sign-in'}, {'data-nav-ref': 'nav_ya_signin'}], log='bu'):
                    return False
                up = urlparse(br.get_url())
                query = {k: v[0] for k, v in parse_qs(up.query).items()}
                up_rt = urlparse(query['openid.return_to'])
                up_rt = up_rt._replace(netloc=up.netloc, path='/ap/maplanding', query='')
                query['openid.assoc_handle'] = 'amzn_piv_android_v2_' + user['locale']
                query['openid.return_to'] = up_rt.geturl()
                query.update({
                    'openid.oa2.response_type': 'code',
                    'openid.oa2.code_challenge_method': 'S256',
                    'openid.oa2.code_challenge': challenge.decode(),
                    'pageId': 'amzn_dv_ios_blue',
                    'openid.ns.oa2': 'http://www.amazon.com/ap/ext/oauth/2',
                    'openid.oa2.client_id': f'device:{clientid}',
                    'openid.ns.pape': 'http://specs.openid.net/extensions/pape/1.0',
                    'openid.oa2.scope': 'device_auth_access',
                    'openid.mode': 'checkid_setup',
                    'openid.identity': 'http://specs.openid.net/auth/2.0/identifier_select',
                    'openid.ns': 'http://specs.openid.net/auth/2.0',
                    'accountStatusPolicy': 'P1',
                    'openid.claimed_id': 'http://specs.openid.net/auth/2.0/identifier_select',
                    'language': user['lang'],
                    'disableLoginPrepopulate': 0,
                    'openid.pape.max_auth_age': 0
                })
                up = up._replace(query=urlencode(query))
                br.session.headers.update(
                    {'upgrade-insecure-requests': '1',
                     'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
                     'x-requested-with': 'com.amazon.avod.thirdpartyclient',
                     'sec-fetch-site': 'none',
                     'sec-fetch-mode': 'navigate',
                     'sec-fetch-user': '?1',
                     'sec-fetch-dest': 'document',
                     'accept-language': f"{user['lang'].replace('_', '-')},{user['lang'].split('_')[0]};q=0.9,en-US;q=0.8,en;q=0.7",
                     'host': up.netloc
                     }
                )
                br.session.cookies.update(init_cookie)
                br.open(up.geturl())

            if not _findElem(br, form='signIn'):
                return False
            form = br.get_current_form()
            form.set_input({'email': email, 'password': password})
            if 'true' == _s.rememberme:
                try:
                    form.set_checkbox({'rememberMe': True})
                except:
                    pass
            br.submit_selected()
            response, soup = parseHTML(br)
            WriteLog(_redact_sensitive(response, email), 'login')

            while any(sp in response for sp in _g.mfa_keywords):
                br = MFACheck(br, email, soup)
                if br is None:
                    return False
                if not br.get_current_form() is None:
                    br.submit_selected()
                response, soup = parseHTML(br)
                WriteLog(_redact_sensitive(response, email), 'login-mfa')

            if 'accountFixup' in response:
                Log('Login AccountFixup')
                skip_link = br.find_link(id='ap-account-fixup-phone-skip-link')
                br.follow_link(skip_link)
                response, soup = parseHTML(br)
                WriteLog(_redact_sensitive(response, email), 'login-fixup')

            # Some PrimeVideo endpoints still return you to the store, directly
            url = br.get_url()
            if url.endswith('?ref_=av_auth_return_redir') or ('action=sign-out' in response) or ('openid.oa2.authorization_code' in url):
                if 'openid.oa2.authorization_code' in url:
                    user = registerDevice(url, user, verifier, clientid, frc)
                    if not user:
                        return False
                else:  # Raw HTML
                    try:
                        name = re.search(r'config\.customerName[\x27,]+([^\x27]+)', response).group(1)
                    except AttributeError:
                        name = soup.find('span', attrs={'data-automation-id': 'nav-active-profile-name'})
                        name = getString(30209) if name is None else name.get_text(strip=True)
                    user.update({'name': name, 'cookie': cj.get_dict()})

                return _finalize_login(user, cj, addUser)
            elif 'message_error' in response:
                writeConfig('login_pass', '')
                msg = soup.find('div', attrs={'id': 'message_error'})
                Log(f'Login Error: {msg.get_text(strip=True)}')
                _g.dialog.ok(getString(30200), msg.get_text(strip=True))
            elif 'message_warning' in response:
                msg = soup.find('div', attrs={'id': 'message_warning'})
                Log(f'Login Warning: {msg.get_text(strip=True)}')
            elif 'auth-error-message-box' in response:
                msg = soup.find('div', attrs={'id': 'auth-error-message-box'})
                Log(f'Login MFA: {msg.get_text(strip=True)}')
                _g.dialog.ok(msg.div.h4.get_text(strip=True), msg.div.div.get_text(strip=True))
            elif 'error-slot' in response:
                msg_title = soup.find('div', attrs={'class': 'ap_error_page_title'}).get_text(strip=True)
                msg_cont = soup.find('div', attrs={'class': 'ap_error_page_message'}).get_text(strip=True)
                Log(f'Login Error: {msg_cont}')
                _g.dialog.ok(msg_title, msg_cont)
            else:
                _g.dialog.ok(getString(30200), getString(30213).format(_g.LOG_PATH))
    return False


def registerDevice(url, user, verifier, clientid, frc=None):
    parsed_url = parse_qs(urlparse(url).query)
    auth_code = parsed_url["openid.oa2.authorization_code"][0]
    domain = user['sidomain']

    # Step 1: Register parent MAP/Android device (A1MPSLFC7L5AFK) with mac_dms credentials
    data = {
        'auth_data': {
            'use_global_authentication': 'true',
            'client_id': clientid,
            'authorization_code': auth_code,
            'code_verifier': verifier.decode(),
            'code_algorithm': 'SHA-256',
            'client_domain': 'DeviceLegacy',
        },
        'registration_data': deviceData(user, _g.dtid_android_parent),
        'requested_token_type': [
            'bearer',
            'mac_dms',
            'store_authentication_cookie',
            'website_cookies',
        ],
        'requested_extensions': [
            'device_info',
            'customer_info',
        ],
        'cookies': {
            'domain': '.' + domain,
            'website_cookies': [],
        },
        'device_metadata': _deviceMetadata(user, _g.dtid_android_parent),
    }
    if frc:
        data['user_context_map'] = {'frc': frc}

    headers = _g.headers_android.copy()
    headers.update({
        'x-amzn-identity-auth-domain': 'api.' + domain,
        'X-Amzn-RequestId': str(uuid4()),
        'Accept-Language': user.get('lang', 'en_US').replace('_', '-'),
        'Content-Type': 'application/json',
        'Accept-Encoding': 'gzip',
    })
    resp = getURL(f'https://api.{domain}/auth/register', headers=headers, postdata=json.dumps(data))
    WriteLog(_redact_sensitive(resp), 'login-register')

    resp_body = resp.get('response', {}) if isinstance(resp, dict) else {}
    if 'error' in resp_body or 'success' not in resp_body:
        err_msg = resp_body.get('error', {}).get('message', 'Device registration failed')
        Log(f'Parent device registration failed: {err_msg}', Log.ERROR)
        _g.dialog.notification(_g.__plugin__, err_msg, xbmcgui.NOTIFICATION_INFO)
        return False

    reg_data = resp_body['success']
    parent_tokens = reg_data['tokens']
    parent_bearer = parent_tokens['bearer']
    mac_dms = parent_tokens.get('mac_dms', {})
    if not mac_dms.get('adp_token') or not mac_dms.get('device_private_key'):
        Log('Missing mac_dms credentials in /auth/register response', Log.ERROR)
        _g.dialog.notification(_g.__plugin__, 'Missing mac_dms credentials', xbmcgui.NOTIFICATION_ERROR)
        return False

    # Step 2: Register associated Prime Video device (A43PXU4ZN2AL1) via FIRS
    firs_path = '/FirsProxy/registerAssociatedDevice'
    pid = sha256(user['deviceid'].encode('utf-8')).hexdigest().upper()[23:31]
    firs_body = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<request><parameters>'
        f'<deviceType>{_g.dtid_android}</deviceType>'
        f'<deviceSerialNumber>{user["deviceid"]}</deviceSerialNumber>'
        f'<pid>{pid}</pid>'
        '<deregisterExisting>true</deregisterExisting>'
        '<softwareVersion>404000357</softwareVersion>'
        '<softwareComponentId>com.amazon.avod.thirdpartyclient</softwareComponentId>'
        '</parameters></request>'
    )
    firs_headers = _adp_sign_headers('POST', firs_path, firs_body, mac_dms['adp_token'], mac_dms['device_private_key'])
    firs_headers.update({
        'Content-Type': 'text/xml',
        'X-Amzn-RequestId': str(uuid4()),
        'User-Agent': _g.headers_android['User-Agent'],
        'Accept-Encoding': 'gzip',
    })
    firs_resp = getURL('https://firs-ta-g7g.amazon.com' + firs_path, headers=firs_headers, postdata=firs_body, rjson=False)
    WriteLog(_redact_sensitive(firs_resp), 'login-register-assoc')

    child_adp_token = None
    child_private_key = None
    if firs_resp:
        try:
            root = ET.fromstring(firs_resp)
            child_adp_token = root.findtext('adp_token')
            child_private_key = root.findtext('device_private_key')
        except ET.ParseError as exc:
            Log(f'Failed to parse FIRS XML response: {exc}', Log.ERROR)
    if not child_adp_token or not child_private_key:
        Log('Associated device registration failed', Log.ERROR)
        _g.dialog.notification(_g.__plugin__, 'Associated device registration failed', xbmcgui.NOTIFICATION_ERROR)
        return False

    # Step 3: Exchange child dms_token for A43PXU4ZN2AL1 bearer access + refresh tokens
    tok_path = '/auth/token'
    tok_body = json.dumps({
        'app_name': 'com.amazon.avod.thirdpartyclient',
        'app_version': '130050002',
        'source_token_type': 'dms_token',
        'source_token': 'source_token',
        'requested_token_type': 'refresh_token',
        'device_metadata': _deviceMetadata(user, _g.dtid_android),
        'map_version': {
            'current_version': '20241101N',
            'package_name': 'com.amazon.avod.thirdpartyclient',
            'platform': 'Android',
            'client_metrics_integrated': True,
        },
    }, separators=(',', ':'))
    tok_headers = _adp_sign_headers('POST', tok_path, tok_body, child_adp_token, child_private_key)
    tok_headers.update({
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'X-Amzn-RequestId': str(uuid4()),
        'x-amzn-identity-auth-domain': 'api.' + domain,
        'User-Agent': _g.headers_android['User-Agent'],
        'Accept-Encoding': 'gzip',
    })
    child_resp = getURL(f'https://api.{domain}{tok_path}', headers=tok_headers, postdata=tok_body)
    WriteLog(_redact_sensitive(child_resp), 'login-register-token')

    if not isinstance(child_resp, dict) or 'access_token' not in child_resp or 'refresh_token' not in child_resp:
        Log('Failed to exchange associated device dms_token for refresh_token', Log.ERROR)
        _g.dialog.notification(_g.__plugin__, 'Failed to obtain device token', xbmcgui.NOTIFICATION_ERROR)
        return False

    website_cookies = parent_tokens.get('website_cookies', [])
    if not website_cookies:
        cookie_headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': 'AmazonWebView/MAPClientLib/130050002/Android/11/SHIELD Android TV',
            'X-Amzn-RequestId': str(uuid4()),
            'x-amzn-identity-auth-domain': 'api.' + domain,
            'Accept-Encoding': 'gzip',
        }
        cookie_data = {
            'requested_token_type': 'auth_cookies',
            'app_name': 'com.amazon.avod.thirdpartyclient',
            'app_version': '130050002',
            'di.sdk.version': '20241101N',
            'domain': '.' + domain,
            'source_token_type': 'refresh_token',
            'source_token': parent_bearer['refresh_token'],
        }
        cookie_resp = getURL(f'https://api.{domain}/auth/token', headers=cookie_headers, postdata=cookie_data)
        if isinstance(cookie_resp, dict):
            website_cookies = cookie_resp.get('response', {}).get('tokens', {}).get('cookies', {}).get('.' + domain, [])

    customer = reg_data['extensions']['customer_info']
    user['name'] = customer.get('given_name', customer.get('name', getString(30209)))
    user['token'] = {
        'access': child_resp['access_token'],
        'refresh': child_resp['refresh_token'],
        'expires': int(time.time()) + int(child_resp.get('expires_in', 3600)),
        'parent_refresh': parent_bearer['refresh_token'],
    }
    user['cookie'] = {
        c['Name'] + '-av' if c['Name'].endswith('-main') and user['pv'] else c['Name']: c['Value'].strip('"')
        for c in website_cookies
    }
    return user


def deviceData(user, dtid=None):
    return {
        'domain': 'DeviceLegacy',
        'device_type': dtid or _g.dtid_android,
        'device_serial': user['deviceid'],
        'app_name': 'com.amazon.avod.thirdpartyclient',
        'app_version': '404000357',
        'device_model': 'mdarcy/nvidia/SHIELD Android TV',
        'os_version': 'NVIDIA/mdarcy/mdarcy:11/RQ1A.210105.003/7094531_2971.7725:user/release-keys',
        'software_version': '130050002',
    }


def _deviceMetadata(user, dtid):
    return {
        'device_os_family': 'android',
        'device_type': dtid,
        'device_serial': user['deviceid'],
        'manufacturer': 'NVIDIA',
        'model': 'SHIELD Android TV',
        'os_version': '30',
        'product': 'mdarcy',
    }


def getToken(user=None):
    from .users import loadUser, updateUser
    if user is None:
        user = loadUser()
    token = user.get('token')
    if isinstance(token, dict):
        if int(time.time()) >= token['expires'] - 60:
            newtoken = refreshToken(user)
            if not newtoken:
                return False
            user['token'] = newtoken
            updateUser('token', newtoken)
        return {'Authorization': 'Bearer ' + user['token']['access']}
    return False


def _requestActorToken(user, actor_id, use_actor_refresh=False):
    domain = user['sidomain']
    token = user['token']
    parent_entry = {
        'device_type': _g.dtid_android_parent,
        'account_refresh_token': {'token': token['parent_refresh']},
    }
    if use_actor_refresh and token.get('actor_refresh'):
        parent_entry['actor_refresh_token'] = {'token': token['actor_refresh']}

    payload = {
        'app_name': 'com.amazon.avod.thirdpartyclient',
        'app_version': '130050002',
        'source_token_type': 'refresh_token',
        'requested_token_type': 'actor_access_token',
        'source_device_tokens': [
            parent_entry,
            {
                'device_type': _g.dtid_android,
                'account_refresh_token': {'token': token['refresh']},
            },
        ],
        'actor_id': actor_id,
    }
    headers = {
        'Content-Type': 'application/json',
        'User-Agent': 'AmazonWebView/MAPClientLib/130050002/Android/11/SHIELD Android TV',
        'X-Amzn-RequestId': str(uuid4()),
        'x-amzn-identity-auth-domain': 'api.' + domain,
        'Accept-Encoding': 'gzip',
    }
    return getURL(f'https://api.{domain}/auth/token', headers=headers, postdata=json.dumps(payload, separators=(',', ':')))


def refreshToken(user, aid=None):
    domain = user['sidomain']
    token = user['token']
    target_aid = aid if aid else token.get('actor_id')

    if target_aid:
        if not token.get('parent_refresh'):
            Log('Missing parent_refresh token for profile switching; please log in again', Log.ERROR)
            if aid:
                return False
            token.pop('actor_id', None)
            token.pop('actor_refresh', None)
        else:
            use_actor_refresh = (aid is None or aid == token.get('actor_id')) and bool(token.get('actor_refresh'))
            response = _requestActorToken(user, target_aid, use_actor_refresh=use_actor_refresh)
            # If renewing with cached actor_refresh_token fails, retry once using only account_refresh_tokens
            if use_actor_refresh and (not isinstance(response, dict) or 'device_tokens' not in response):
                Log('Actor token refresh with actor_refresh_token failed, retrying with account_refresh_tokens', Log.WARNING)
                use_actor_refresh = False
                response = _requestActorToken(user, target_aid, use_actor_refresh=False)

            device_tokens = response.get('device_tokens') if isinstance(response, dict) else None
            if device_tokens:
                child_access = None
                parent_actor_refresh = None
                for dt in device_tokens:
                    dtype = dt.get('device_type')
                    if dtype == _g.dtid_android and 'actor_access_token' in dt:
                        child_access = dt['actor_access_token']
                    elif dtype == _g.dtid_android_parent and 'actor_refresh_token' in dt:
                        parent_actor_refresh = dt['actor_refresh_token'].get('token')
                if child_access and 'token' in child_access:
                    token['access'] = child_access['token']
                    token['expires'] = int(time.time()) + int(child_access.get('expires_in', 3600))
                    token['actor_id'] = target_aid
                    if parent_actor_refresh:
                        token['actor_refresh'] = parent_actor_refresh
                    elif not use_actor_refresh:
                        token.pop('actor_refresh', None)
                    Log('Actor token renewed')
                    return token

            LogJSON(response)
            Log('Actor token not renewed', Log.ERROR)
            if aid:
                return False
            # Fall back to standard account access_token renewal if stored profile is no longer valid
            token.pop('actor_id', None)
            token.pop('actor_refresh', None)

    data = deviceData(user)
    data['source_token_type'] = 'refresh_token'
    data['requested_token_type'] = 'access_token'
    data['source_token'] = token['refresh']
    headers = _g.headers_android.copy()
    headers.pop('x-gasc-enabled', '')
    headers.pop('X-Requested-With', '')
    headers.update({'x-amzn-identity-auth-domain': 'api.' + domain, 'Accept-Language': 'en-US', 'x-amzn-requestid': str(uuid4()).replace('-', '')})
    response = getURL(f'https://api.{domain}/auth/token', headers=headers, postdata=data)
    if isinstance(response, dict) and 'access_token' in response:
        token['access'] = response['access_token']
        token['expires'] = int(time.time() + int(response['expires_in']))
        Log('Token renewed')
        return token
    else:
        LogJSON(response)
        Log('Token not renewed', Log.ERROR)
    return False


def remLoginData(info=True):
    for fn in xbmcvfs.listdir(_g.DATA_PATH)[1]:
        if fn.startswith('cookie'):
            xbmcvfs.delete(OSPJoin(_g.DATA_PATH, fn))
    writeConfig('accounts', '')
    writeConfig('login_name', '')
    writeConfig('login_pass', '')
    writeConfig('GenDeviceID', '')

    if info:
        writeConfig('accounts.lst', '')
        writeConfig('profile', '')
        writeConfig('profileID', '')
        _s.login_acc = ''
        _g.dialog.notification(_g.__plugin__, getString(30211), xbmcgui.NOTIFICATION_INFO)


class _Captcha(pyxbmct.AddonDialogWindow):
    def __init__(self, title='', soup=None, email=None):
        super(_Captcha, self).__init__(title)
        if soup.find('div', attrs={'id': 'ap_captcha_img_label'}):
            head = soup.find('div', attrs={'id': 'message_warning'})
            if not head:
                head = soup.find('div', attrs={'id': 'message_error'})
            title = soup.find('div', attrs={'id': 'ap_captcha_guess_alert'})
            self.head = head.p.get_text(strip=True)
            self.head = re.sub('(?i)<[^>]*>', '', self.head)
            self.picurl = soup.find('div', attrs={'id': 'ap_captcha_img'}).img.get('src')
        else:
            self.head = soup.find('span', attrs={'class': 'a-list-item'}).get_text(strip=True)
            title = soup.find('div', attrs={'id': 'auth-guess-missing-alert'}).div.div
            self.picurl = soup.find('div', attrs={'id': 'auth-captcha-image-container'}).img.get('src')
        self.setGeometry(500, 550, 9, 2)
        self.email = email
        self.pwd = ''
        self.cap = ''
        if '.gif' in self.picurl:
            cap = getURL(self.picurl, rjson=False, binary=True)
            self.picurl = OSPJoin(_g.DATA_PATH, f'cap-{int(time.time() * 1000)}.gif')
            with xbmcvfs.File(self.picurl, 'w') as fp_cap:
                fp_cap.write(bytearray(cap))
        self.title = title.get_text(strip=True)
        self.image = pyxbmct.Image('', aspectRatio=2)
        self.tb_head = pyxbmct.TextBox()
        self.fl_title = pyxbmct.FadeLabel(_alignment=pyxbmct.ALIGN_CENTER)
        self.username = pyxbmct.Edit('', _alignment=pyxbmct.ALIGN_LEFT | pyxbmct.ALIGN_CENTER_Y)
        self.password = pyxbmct.Edit('', _alignment=pyxbmct.ALIGN_LEFT | pyxbmct.ALIGN_CENTER_Y)
        self.captcha = pyxbmct.Edit('', _alignment=pyxbmct.ALIGN_LEFT | pyxbmct.ALIGN_CENTER_Y)
        self.btn_submit = pyxbmct.Button(getString(30008).split('…')[0])
        self.btn_cancel = pyxbmct.Button(getString(30123))
        self.set_controls()
        self.set_navigation()

    def set_controls(self):
        self.placeControl(self.tb_head, 0, 0, columnspan=2, rowspan=3)
        self.placeControl(pyxbmct.Label(getString(30002), alignment=pyxbmct.ALIGN_CENTER_Y | pyxbmct.ALIGN_CENTER), 2, 0)
        self.placeControl(pyxbmct.Label(getString(30003), alignment=pyxbmct.ALIGN_CENTER_Y | pyxbmct.ALIGN_CENTER), 3, 0)
        self.placeControl(self.username, 2, 1, pad_y=8)
        self.placeControl(self.password, 3, 1, pad_y=8)
        self.placeControl(self.image, 4, 0, rowspan=2, columnspan=2)
        self.placeControl(self.fl_title, 6, 0, columnspan=2)
        self.placeControl(self.captcha, 7, 0, columnspan=2, pad_y=8)
        self.placeControl(self.btn_submit, 8, 0)
        self.placeControl(self.btn_cancel, 8, 1)
        self.connect(self.btn_cancel, self.cancel)
        self.connect(self.btn_submit, self.submit)
        self.connect(pyxbmct.ACTION_NAV_BACK, self.cancel)
        self.username.setText(self.email)
        self.username.setEnabled(False)
        self.password.setType(0 if _s.show_pass else 6, '')
        self.tb_head.setText(self.head)
        self.fl_title.addLabel(self.title)
        self.image.setImage(self.picurl, False)

    def set_navigation(self):
        self.username.controlUp(self.btn_submit)
        self.username.controlDown(self.password)
        self.password.controlUp(self.username)
        self.password.controlDown(self.captcha)
        self.captcha.controlUp(self.password)
        self.captcha.controlDown(self.btn_submit)
        self.btn_submit.controlUp(self.captcha)
        self.btn_submit.controlDown(self.username)
        self.btn_cancel.controlUp(self.captcha)
        self.btn_cancel.controlDown(self.username)
        self.btn_submit.controlRight(self.btn_cancel)
        self.btn_submit.controlLeft(self.btn_cancel)
        self.btn_cancel.controlRight(self.btn_submit)
        self.btn_cancel.controlLeft(self.btn_submit)
        self.setFocus(self.password)

    def rmcap(self):
        if xbmcvfs.exists(self.picurl):
            xbmcvfs.delete(self.picurl)

    def cancel(self):
        self.rmcap()
        self.close()

    def submit(self):
        self.rmcap()
        self.pwd = self.password.getText()
        self.cap = self.captcha.getText()
        self.email = self.username.getText()
        self.close()


class _Challenge(pyxbmct.AddonDialogWindow):
    def __init__(self, msg):
        self.head = msg.find('title').get_text(strip=True)
        self.set_inp = True
        self.cap = ''
        img = msg.find('img', attrs={'alt': 'captcha'})
        box = img.find_parent('div', class_='a-box-inner a-padding-extra-large') if img else None
        if box is None:
            hint_node = msg.find('p', class_='a-last')
            if hint_node:
                self.hint = hint_node.get_text(strip=True)
                form = msg.find('form').find('div', class_='a-box-inner')
                self.task = form.h4.get_text(strip=True)
                self.img_url = form.find('img')['src']
            else:
                self.set_inp = False
                return
        else:
            self.hint = '\n'.join([box.find('span', class_=cl).get_text() for cl in ['a-size-large', 'a-size-base a-color-secondary']
                                   if box.find('span', class_=cl)])
            self.task = box.find('label', class_='a-form-label').get_text(strip=True)
            self.img_url = img['src']

        super(_Challenge, self).__init__(self.head)
        self.setGeometry(500, 450, 8, 2)
        self.img = pyxbmct.Image(self.img_url, aspectRatio=2)
        self.tb_hint = pyxbmct.TextBox()
        self.fl_task = pyxbmct.FadeLabel(_alignment=pyxbmct.ALIGN_CENTER)
        self.ed_cap = pyxbmct.Edit('', _alignment=pyxbmct.ALIGN_LEFT | pyxbmct.ALIGN_CENTER_Y)
        self.btn_submit = pyxbmct.Button('OK')
        self.btn_cancel = pyxbmct.Button(getString(30123))
        self.set_controls()
        self.set_navigation()

    def solve_captcha(self):
        try:
            from amazoncaptcha import AmazonCaptcha
        except ImportError:
            Log('Module amazoncaptcha not installed', Log.DEBUG)
            return False
        captcha = AmazonCaptcha.fromlink(self.img_url)
        res = captcha.solve()
        if res != 'Not solved':
            Log(f'Recognized captcha: {res}  IMG url: {self.img_url}')
            self.cap = res
            self.close()
            return True
        return False

    def set_controls(self):
        self.placeControl(self.tb_hint, 0, 0, 2, 2)
        self.placeControl(self.img, 2, 0, 3, 2)
        self.placeControl(self.fl_task, 5, 0, 1, 2)
        self.placeControl(self.ed_cap, 6, 0, 1, 2)
        self.placeControl(self.btn_submit, 7, 0)
        self.placeControl(self.btn_cancel, 7, 1)
        self.connect(self.btn_cancel, self.close)
        self.connect(self.btn_submit, self.submit)
        self.connect(pyxbmct.ACTION_NAV_BACK, self.close)
        self.tb_hint.setText(self.hint)
        self.fl_task.addLabel(self.task)
        self.setFocus(self.ed_cap)

    def set_navigation(self):
        self.ed_cap.controlUp(self.btn_submit)
        self.ed_cap.controlDown(self.btn_submit)
        self.btn_submit.controlUp(self.ed_cap)
        self.btn_submit.controlDown(self.ed_cap)
        self.btn_cancel.controlUp(self.ed_cap)
        self.btn_cancel.controlDown(self.ed_cap)
        self.btn_submit.controlRight(self.btn_cancel)
        self.btn_submit.controlLeft(self.btn_cancel)
        self.btn_cancel.controlRight(self.btn_submit)
        self.btn_cancel.controlLeft(self.btn_submit)

    def submit(self):
        self.cap = self.ed_cap.getText()
        self.close()


class _InputBox(pyxbmct.AddonDialogWindow):
    def __init__(self, msg, task='', head=None):
        if head is None:
            head = _g.__plugin__
        super(_InputBox, self).__init__(head)
        self.tskv = 1 if len(task) > 0 else 0
        self.setGeometry(450, 400, 6 + self.tskv, 2)
        self.inp = ''
        self.msg = msg
        self.task = task
        self.tb_msg = pyxbmct.TextBox()
        self.fl_task = pyxbmct.FadeLabel(_alignment=pyxbmct.ALIGN_CENTER)
        self.ed_cap = pyxbmct.Edit('', _alignment=pyxbmct.ALIGN_LEFT | pyxbmct.ALIGN_CENTER_Y)
        self.btn_submit = pyxbmct.Button('OK')
        self.btn_cancel = pyxbmct.Button(getString(30123))
        self.set_controls()
        self.set_navigation()

    def set_controls(self):
        self.placeControl(self.tb_msg, 0, 0, 3, 2)
        if self.tskv:
            self.placeControl(self.fl_task, 4, 0, 1, 2)
        self.placeControl(self.ed_cap, 4 + self.tskv, 0, 1, 2)
        self.placeControl(self.btn_submit, 5 + self.tskv, 0)
        self.placeControl(self.btn_cancel, 5 + self.tskv, 1)
        self.connect(self.btn_cancel, self.close)
        self.connect(self.btn_submit, self.submit)
        self.connect(pyxbmct.ACTION_NAV_BACK, self.close)
        self.tb_msg.setText(self.msg)
        self.fl_task.addLabel(self.task)
        self.setFocus(self.ed_cap)

    def set_navigation(self):
        self.ed_cap.controlUp(self.btn_submit)
        self.ed_cap.controlDown(self.btn_submit)
        self.btn_submit.controlUp(self.ed_cap)
        self.btn_submit.controlDown(self.ed_cap)
        self.btn_cancel.controlUp(self.ed_cap)
        self.btn_cancel.controlDown(self.ed_cap)
        self.btn_submit.controlRight(self.btn_cancel)
        self.btn_submit.controlLeft(self.btn_cancel)
        self.btn_cancel.controlRight(self.btn_submit)
        self.btn_cancel.controlLeft(self.btn_submit)

    def submit(self):
        self.inp = self.ed_cap.getText()
        self.close()


class _ProgressDialog(pyxbmct.AddonDialogWindow):
    def __init__(self, msg):
        super(_ProgressDialog, self).__init__('Amazon')
        self.sl_progress = pyxbmct.Slider(textureback=OSPJoin(_g.PLUGIN_PATH, 'resources', 'art', 'transp.png'))
        self.btn_cancel = pyxbmct.Button(getString(30123))
        self.tb_msg = pyxbmct.TextBox()
        self.iscanceled = False
        self.connect(self.btn_cancel, self.cancel)
        self.setGeometry(500, 400, 6, 3)
        self.placeControl(self.tb_msg, 0, 0, 4, 3)
        self.placeControl(self.sl_progress, 4, 0, 0, 3)
        self.placeControl(self.btn_cancel, 5, 1, 1, 1)
        self.tb_msg.setText(msg)
        self.sl_progress.setEnabled(False)

    def cancel(self):
        self.iscanceled = True


class _QRLoginDialog(pyxbmct.AddonDialogWindow):
    def __init__(self, title, qr_path, lan_url):
        super(_QRLoginDialog, self).__init__(title)
        self.setGeometry(700, 560, 10, 2)
        self.qr_path = qr_path
        self.lan_url = lan_url
        self.manual_requested = False
        self.cancelled = False
        self.tb_info = pyxbmct.TextBox()
        self.img_qr = pyxbmct.Image('', aspectRatio=2)
        self.btn_manual = pyxbmct.Button(getString(30317))
        self.btn_cancel = pyxbmct.Button(getString(30123))
        self.set_controls()
        self.set_navigation()

    def set_controls(self):
        self.placeControl(self.tb_info, 0, 0, rowspan=2, columnspan=2)
        self.placeControl(self.img_qr, 2, 0, rowspan=7, columnspan=2, pad_y=6)
        self.placeControl(self.btn_manual, 9, 0)
        self.placeControl(self.btn_cancel, 9, 1)
        self.connect(self.btn_manual, self._manual)
        self.connect(self.btn_cancel, self._cancel)
        self.connect(pyxbmct.ACTION_NAV_BACK, self._cancel)
        self.tb_info.setText(f'{getString(30316)}\n[B]{self.lan_url}[/B]')
        self.img_qr.setImage(self.qr_path, False)

    def set_navigation(self):
        self.btn_manual.controlRight(self.btn_cancel)
        self.btn_manual.controlLeft(self.btn_cancel)
        self.btn_cancel.controlRight(self.btn_manual)
        self.btn_cancel.controlLeft(self.btn_manual)
        self.setFocus(self.btn_manual)

    def _manual(self):
        self.manual_requested = True
        self.close()

    def _cancel(self):
        self.cancelled = True
        self.close()

