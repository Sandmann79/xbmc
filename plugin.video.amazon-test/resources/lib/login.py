#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import os
import json
import mechanicalsoup
import re
import requests
import time
from base64 import urlsafe_b64encode, b64encode
from random import randint
from hashlib import sha256
from os.path import join as OSPJoin
from uuid import uuid4
from binascii import hexlify

import pyxbmct
from kodi_six import xbmcgui, xbmc, xbmcvfs
from kodi_six.utils import py2_decode

from .common import Globals, Settings, sleep, parseHTML
from .network import getURL
from .logging import Log, WriteLog, LogJSON
from .l10n import getString, datetimeParser
from .configs import getConfig, writeConfig

try:
    from urlparse import urlparse, parse_qs, urlunparse
    from urllib import urlencode, quote_plus
except ImportError:
    from urllib.parse import urlparse, parse_qs, urlencode, quote_plus, urlunparse

_g = Globals()
_s = Settings()


def getTerritory(user):
    if len(user.get('deviceid', '')) != 32:
        from uuid import uuid4
        user['deviceid'] = uuid4().hex.lower()

    areas = [{'atvurl': '', 'baseurl': '', 'mid': '', 'pv': False, 'country': ''},
             {'atvurl': 'https://atv-ps-eu.amazon.de', 'baseurl': 'https://www.amazon.de', 'mid': 'A1PA6795UKMFR9', 'pv': False, 'locale': 'de',
              'lang': 'de_DE', 'sidomain': 'amazon.de'},
             {'atvurl': 'https://atv-ps-eu.amazon.co.uk', 'baseurl': 'https://www.amazon.co.uk', 'mid': 'A1F83G8C2ARO7P', 'pv': False, 'locale': 'uk',
              'lang': 'en_UK', 'sidomain': 'amazon.co.uk'},
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
        data = getURL(
            'https://atv-ps.amazon.com/cdp/usage/v3/GetAppStartupConfig?deviceTypeID=A28RQHJKHM2A2W&deviceID=%s&firmware=1&version=1&supportedLocales=%s&format=json'
            % (user['deviceid'], loc))
        if not hasattr(data, 'keys'):
            return user, False
        if 'customerConfig' in data.keys():
            terr = data['territoryConfig']
            cust = data['customerConfig']
            host = terr['defaultVideoWebsite']
            reg = cust['homeRegion'].lower()
            reg = '' if 'na' in reg else '-' + reg
            user['atvurl'] = host.replace('www.', '').replace('//', '//atv-ps%s.' % reg)
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
            sel = _g.dialog.select('%s - %s' % (cs_title, cs_quest.get_text(strip=True)), [k[0] for k in choices])
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
        if soup.find('img', attrs={'alt': 'captcha'}):
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
    elif 'validateCaptcha' in uni_soup:
        Log('validateCaptcha', Log.DEBUG)
        wnd = _Challenge(soup)
        if not wnd.solve_captcha():
            wnd.doModal()
        if wnd.cap:
            # MechanicalSoup is using the field names, not IDs
            # id is captchacharacters, which causes exception to be raised
            form.set_input({'field-keywords': wnd.cap})
        else:
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
                br.select_form('form[id="{}"]'.format(form_id))
                br.submit_selected()
                response, soup = parseHTML(br)
                form_id = form_poll
                WriteLog(response.replace(py2_decode(email), '**@**'), 'login-pollingform')
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
                    br.select_form('form[name="{}"]'.format(form))
                elif link:
                    br.follow_link(attrs=link)
                break
            except mechanicalsoup.LinkNotFoundError:
                sleep(randint(750, 3000) / 1000)
                caperr += 1
                if _s.register_device is False:
                    from .network import getUA
                    getUA(True)
                    br.session.headers.update({'User-Agent': getConfig('UserAgent')})
                Log('Connect to SignIn Page %s attempts left' % -caperr)
                br.refresh()
                WriteLog(str(br.get_current_page()), 'login-{}'.format(log))
        else:
            _g.dialog.ok(getString(30200), getString(30213).format(_g.LOG_PATH))
            return False
        return True

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
            if _s.register_device is False and _s.data_source == 0:
                br.session.headers.update({'User-Agent': getConfig('UserAgent')})
                br.open(user['baseurl'] + ('/gp/flex/sign-out.html' if not user['pv'] else '/auth-redirect/?signin=1'))
                Log(br.get_url(), Log.DEBUG)
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
                clientid = hexlify(user['deviceid'].encode() + b'#A1MPSLFC7L5AFK')  # + _g.dtid_android.encode()).hex()
                verifier = urlsafe_b64encode(os.urandom(32)).rstrip(b"=")
                challenge = urlsafe_b64encode(sha256(verifier).digest()).rstrip(b"=")
                frc = b64encode(os.urandom(313)).decode("ascii")
                map_md = {'device_registration_data': {'software_version': '130050002'},
                          'app_identifier': {'package': 'com.amazon.avod.thirdpartyclient',
                                             'SHA-256': ['2f19adeb284eb36f7f07786152b9a1d14b21653203ad0b04ebbf9c73ab6d7625'],
                                             'app_version': '351003955',
                                             'app_version_name': '3.0.351.3955',
                                             'app_sms_hash': 'e0kK4QFSWp0',
                                             'map_version': 'MAPAndroidLib-1.3.14913.0'},
                          'app_info': {'auto_pv': 0, 'auto_pv_with_smsretriever': 0, 'smartlock_supported': 0, 'permission_runtime_grant': 0}}
                init_cookie = {'frc': frc, 'map-md': b64encode(json.dumps(map_md).encode()).decode(), 'sid': ''}
                br.session.headers.update(_g.headers_android)
                br.open('https://www.' + user['sidomain'])
                WriteLog(str(br.get_current_page()), 'login-bu')
                if not _findElem(br, link={'class': 'nav-show-sign-in'}, log='bu'):
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
                    'openid.oa2.client_id': 'device:{}'.format(clientid),
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
                     'accept-language': '{},{};q=0.9,en-US;q=0.8,en;q=0.7'.format(user['lang'].replace('_', '-'), user['lang'].split('_')[0]),
                     'host': up.netloc
                     }
                )
                br.session.cookies.update(init_cookie)
                br.open(up.geturl())
                Log(up.geturl(), Log.DEBUG)

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
            WriteLog(response.replace(py2_decode(email), '**@**'), 'login')

            while any(sp in response for sp in _g.mfa_keywords):
                br = MFACheck(br, email, soup)
                if br is None:
                    return False
                if not br.get_current_form() is None:
                    br.submit_selected()
                response, soup = parseHTML(br)
                WriteLog(response.replace(py2_decode(email), '**@**'), 'login-mfa')

            if 'accountFixup' in response:
                Log('Login AccountFixup')
                skip_link = br.find_link(id='ap-account-fixup-phone-skip-link')
                br.follow_link(skip_link)
                response, soup = parseHTML(br)
                WriteLog(response.replace(py2_decode(email), '**@**'), 'login-fixup')

            url = br.get_url()
            # Some PrimeVideo endpoints still return you to the store, directly
            if url.endswith('?ref_=av_auth_return_redir') or ('action=sign-out' in response) or ('openid.oa2.authorization_code' in url):
                if 'openid.oa2.authorization_code' in url:
                    user = registerDevice(url, user, verifier, clientid)
                else:  # Raw HTML
                    try:
                        name = re.search(r'config\.customerName[\x27,]+([^\x27]+)', response).group(1)
                    except AttributeError:
                        name = soup.find('span', attrs={'data-automation-id': 'nav-active-profile-name'})
                        name = getString(30209) if name is None else name.get_text(strip=True)
                    user.update({'name': name, 'cookie': cj.get_dict()})

                if _s.multiuser:
                    user['name'] = _g.dialog.input(getString(30135), user['name'])
                    if not user['name']:
                        return False

                remLoginData(False)
                _s.login_acc = user['name']
                if not _s.multiuser:
                    _g.dialog.ok(getString(30215), '{0} {1}'.format(getString(30014), user['name']))

                addUser(user)
                return getToken(user) if retToken else cj
            elif 'message_error' in response:
                writeConfig('login_pass', '')
                msg = soup.find('div', attrs={'id': 'message_error'})
                Log('Login Error: %s' % msg.get_text(strip=True))
                _g.dialog.ok(getString(30200), msg.get_text(strip=True))
            elif 'message_warning' in response:
                msg = soup.find('div', attrs={'id': 'message_warning'})
                Log('Login Warning: %s' % msg.get_text(strip=True))
            elif 'auth-error-message-box' in response:
                msg = soup.find('div', attrs={'id': 'auth-error-message-box'})
                Log('Login MFA: %s' % msg.get_text(strip=True))
                _g.dialog.ok(msg.div.h4.get_text(strip=True), msg.div.div.get_text(strip=True))
            elif 'error-slot' in response:
                msg_title = soup.find('div', attrs={'class': 'ap_error_page_title'}).get_text(strip=True)
                msg_cont = soup.find('div', attrs={'class': 'ap_error_page_message'}).get_text(strip=True)
                Log('Login Error: {}'.format(msg_cont))
                _g.dialog.ok(msg_title, msg_cont)
            else:
                _g.dialog.ok(getString(30200), getString(30213).format(_g.LOG_PATH))
    return False


def registerDevice(url, user, verifier, clientid):
    parsed_url = parse_qs(urlparse(url).query)
    auth_code = parsed_url["openid.oa2.authorization_code"][0]
    domain = user['sidomain']

    data = {
        'auth_data': {
            'client_id': clientid,
            'authorization_code': auth_code,
            'code_verifier': verifier.decode(),
            'code_algorithm': 'SHA-256',
            'client_domain': 'DeviceLegacy',
        },
        'registration_data': deviceData(user),
        'requested_token_type': [
            'bearer',
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
    }

    headers = _g.headers_android
    headers.update({'x-amzn-identity-auth-domain': 'api.' + domain, 'x-amzn-requestid': str(uuid4()).replace('-', ''), 'Content-Type': 'application/json'})
    resp = getURL('https://api.{}/auth/register'.format(domain), headers=headers, postdata=json.dumps(data))
    WriteLog(str(resp), 'login-register')

    if 'error' in resp['response']:
        _g.dialog.notification(_g.__plugin__, resp['response']['error']['message'], xbmcgui.NOTIFICATION_INFO)
        return False

    data = resp['response']['success']
    bearer = data['tokens']['bearer']
    customer = data['extensions']['customer_info']
    user['name'] = customer.get('given_name', customer.get('name', getString(30209)))
    user['token'] = {'access': bearer['access_token'], 'refresh': bearer['refresh_token'], 'expires': int(time.time()) + int(bearer['expires_in'])}
    user['cookie'] = {c['Name'] + '-av' if c['Name'].endswith('-main') and user['pv'] else c['Name']: c['Value'] for c in data['tokens']['website_cookies']}
    return user


def deviceData(user):
    return {
        'domain': 'DeviceLegacy',
        'device_type': _g.dtid_android,
        'device_serial': user['deviceid'],
        'app_name': 'com.amazon.avod.thirdpartyclient',
        'app_version': '296016847',
        'device_model': 'mdarcy/nvidia/SHIELD Android TV',
        'os_version': 'NVIDIA/mdarcy/mdarcy:11/RQ1A.210105.003/7094531_2971.7725:user/release-keys'
    }


def getToken(user=None):
    from .users import loadUser, updateUser
    if user is None:
        user = loadUser()
    token = user.get('token')
    if isinstance(token, dict):
        if int(time.time()) > token['expires']:
            newtoken = refreshToken(user)
            if not newtoken:
                return False
            updateUser('token', newtoken)
        return {'Authorization': 'Bearer ' + user['token']['access']}
    return False


def refreshToken(user, aid=None):
    domain = user['sidomain']
    token = user['token']
    data = deviceData(user)
    data['source_token_type'] = 'refresh_token'
    #data['source_token'] = token['refresh']
    if aid:
        data['requested_token_type'] = 'actor_access_token'
        data['source_device_tokens'] = [{'device_type': _g.dtid_android, 'account_refresh_token': {'token': token['refresh']}}]
        data['actor_id'] = aid
    else:
        data['requested_token_type'] = 'access_token'
        data['source_token'] = token['refresh']
    LogJSON(data)
    headers = _g.headers_android
    headers.pop('x-gasc-enabled')
    headers.pop('X-Requested-With')
    headers.update({'x-amzn-identity-auth-domain': 'api.' + domain, 'Accept-Language': 'en-US', 'x-amzn-requestid': str(uuid4()).replace('-', '')})
    response = getURL('https://api.{}/auth/token'.format(domain), headers=headers, postdata=data)
    if 'access_token' in response:
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
        if py2_decode(fn).startswith('cookie'):
            xbmcvfs.delete(OSPJoin(_g.DATA_PATH, fn))
    writeConfig('accounts', '')
    writeConfig('login_name', '')
    writeConfig('login_pass', '')
    writeConfig('GenDeviceID', '')

    if info:
        writeConfig('accounts.lst', '')
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
            self.picurl = OSPJoin(_g.DATA_PATH, 'cap-{}.gif'.format(int(time.time() * 1000)))
            open(self.picurl, 'wb').write(cap)
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
        img = msg.find('img', attrs={'alt': 'captcha'})
        box = img.find_parent('div', class_='a-box-inner a-padding-extra-large') if img else None
        if box is None:
            self.hint = msg.find('p', class_='a-last').get_text(strip=True)
            form = msg.find('form').find('div', class_='a-box-inner')
            self.task = form.h4.get_text(strip=True)
            self.img_url = form.find('img')['src']
        else:
            self.hint = '\n'.join([box.find('span', class_=cl).get_text() for cl in ['a-size-large', 'a-size-base a-color-secondary']
                                   if box.find('span', class_=cl)])
            self.task = box.find('label', class_='a-form-label').get_text(strip=True)
            self.img_url = img['src']

        super(_Challenge, self).__init__(self.head)
        self.setGeometry(500, 450, 8, 2)
        self.cap = ''
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
            Log('Recognized captcha: %s  IMG url: %s' % (res, self.img_url))
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
