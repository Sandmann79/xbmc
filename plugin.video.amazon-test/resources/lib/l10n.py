#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from kodi_six import xbmc

""" Data for date string deconstruction and reassembly

    Date references:
    https://www.primevideo.com/detail/0LCQSTWDMN9V770DG2DKXY3GVF/  09 10 11 12 01 02 03 04 05
    https://www.primevideo.com/detail/0ND5POOAYD6A4THTH7C1TD3TYE/  06 07 08 09

    Languages: https://www.primevideo.com/settings/language/
"""

datetimeParser = {
    'generic': '^(?P<m>[^W]+)[.,:;\\s-]+(?P<d>[0-9]+),\\s+(?P<y>[0-9]+)(?:\\s+[0-9]+|$)',
    'asianMonthExtractor': '^([0-9]+)[월月]',
    'da_DK': {
        'language': 'Dansk',
        'deconstruct': '^(?P<d>[0-9]+)\\.?\\s+(?P<m>[^\\s]+)\\s+(?P<y>[0-9]+)',
        'months': {
            'januar': 1,
            'februar': 2,
            'marts': 3,
            'april': 4,
            'maj': 5,
            'juni': 6,
            'juli': 7,
            'august': 8,
            'september': 9,
            'oktober': 10,
            'november': 11,
            'december': 12
        },
        'date_fmt': '%d.%m.%y',
        'time_fmt': '%H.%M',
        'iso6392': 'dan'
    },
    'de_DE': {
        'language': 'Deutsch',
        'deconstruct': '^(?P<d>[0-9]+)\\.?\\s+(?P<m>[^\\s]+)\\s+(?P<y>[0-9]+)',
        'months': {
            'januar': 1,
            'februar': 2,
            'märz': 3,
            'april': 4,
            'mai': 5,
            'juni': 6,
            'juli': 7,
            'august': 8,
            'september': 9,
            'oktober': 10,
            'november': 11,
            'dezember': 12,
            'jan.': 1,
            'feb.': 2,
            'mär.': 3,
            'apr.': 4,
            'jun.': 6,
            'jul.': 7,
            'aug.': 8,
            'sept.': 9,
            'okt.': 10,
            'nov.': 11,
            'dez.': 12
        },
        'date_fmt': '%d.%m.%y',
        'time_fmt': '%H:%M',
        'iso6392': 'deu'
    },
    'en_US': {
        'language': 'English',
        'deconstruct': '^(?P<m>[^\\s]+)\\s+(?P<d>[0-9]+),?\\s+(?P<y>[0-9]+)',
        'months': {
            'january': 1,
            'february': 2,
            'march': 3,
            'april': 4,
            'may': 5,
            'june': 6,
            'july': 7,
            'august': 8,
            'september': 9,
            'october': 10,
            'november': 11,
            'december': 12
        },
        'date_fmt': '%m/%d/%y',
        'time_fmt': '%I:%M %p',
        'iso6392': 'eng'
    },
    'en_GB': {
        'deconstruct': '^(?P<d>[0-9]+)\\.?\\s+(?P<m>[^\\s]+)\\s+(?P<y>[0-9]+)',
        'months': {
            'january': 1,
            'february': 2,
            'march': 3,
            'april': 4,
            'may': 5,
            'june': 6,
            'july': 7,
            'august': 8,
            'september': 9,
            'october': 10,
            'november': 11,
            'december': 12
        },
        'iso6392': 'eng'
    },
    'es_ES': {
        'language': 'Español',
        'deconstruct': '^(?P<d>[0-9]+)\\s+de\\s+(?P<m>[^\\s]+),?\\s+de\\s+(?P<y>[0-9]+)',
        'months': {
            'enero': 1,
            'febrero': 2,
            'marzo': 3,
            'abril': 4,
            'mayo': 5,
            'junio': 6,
            'julio': 7,
            'agosto': 8,
            'septiembre': 9,
            'octubre': 10,
            'noviembre': 11,
            'diciembre': 12
        },
        'date_fmt': '%d/%m/%y',
        'time_fmt': '%H:%M',
        'iso6392': 'spa'
    },
    'fi_FI': {
        'language': 'Suomi',
        'deconstruct': '^(?P<d>[0-9]+)\\.?\\s+(?P<m>[^\\s]+)\\s+(?P<y>[0-9]+)',
        'months': {
            'tammikuuta': 1,
            'helmikuuta': 2,
            'maaliskuuta': 3,
            'huhtikuuta': 4,
            'toukokuuta': 5,
            'kesäkuuta': 6,
            'heinäkuuta': 7,
            'elokuuta': 8,
            'syyskuuta': 9,
            'lokakuuta': 10,
            'marraskuuta': 11,
            'joulukuuta': 12
        },
        'date_fmt': '%d.%m.%y',
        'time_fmt': '%H.%M',
        'iso6392': 'fin'
    },
    'fr_FR': {
        'language': 'Français',
        'deconstruct': '^(?P<d>[0-9]+)\\s+(?P<m>[^\\s]+)\\s+(?P<y>[0-9]+)',
        'months': {
            'janvier': 1,
            'janv.': 1,
            'février': 2,
            'févr.': 2,
            'mars': 3,
            'avril': 4,
            'avr.': 4,
            'mai': 5,
            'juin': 6,
            'juillet': 7,
            'juil.': 7,
            'aout': 8,
            'août': 8,
            'septembre': 9,
            'sept.': 9,
            'octobre': 10,
            'oct.': 10,
            'novembre': 11,
            'nov.': 11,
            'décembre': 12,
            'déc.': 12
        },
        'date_fmt': '%d/%m/%y',
        'time_fmt': '%H:%M',
        'iso6392': 'fra'
    },
    'hi_IN': {
        'language': 'हिन्दी',
        'deconstruct': '^(?P<d>[0-9]+)\\s+(?P<m>[^\\s]+)\\s+(?P<y>[0-9]+)',
        'months': {
            'जनवरी': 1,
            'फ़रवरी': 2,
            'मार्च': 3,
            'अप्रैल': 4,
            'मई': 5,
            'जून': 6,
            'जुलाई': 7,
            'अगस्त': 8,
            'सितंबर': 9,
            'अक्तूबर': 10,
            'नवंबर': 11,
            'दिसंबर': 12
        },
        'date_fmt': '%d/%m/%y',
        'time_fmt': '%I:%M %p',
        'iso6392': 'hin'
    },
    'id_ID': {
        'language': 'Bahasa Indonesia',
        'deconstruct': '^(?P<d>[0-9]+)\\s+(?P<m>[^\\s]+)\\s+(?P<y>[0-9]+)',
        'months': {
            'januari': 1,
            'februari': 2,
            'maret': 3,
            'april': 4,
            'mei': 5,
            'juni': 6,
            'juli': 7,
            'agustus': 8,
            'september': 9,
            'oktober': 10,
            'november': 11,
            'desember': 12
        },
        'date_fmt': '%d/%m/%y',
        'time_fmt': '%H.%M',
        'iso6392': 'ind'
    },
    'it_IT': {
        'language': 'Italiano',
        'deconstruct': '^(?P<d>[0-9]+)\\s+(?P<m>[^\\s]+)\\s+(?P<y>[0-9]+)',
        'months': {
            'gennaio': 1,
            'febbraio': 2,
            'marzo': 3,
            'aprile': 4,
            'maggio': 5,
            'giugno': 6,
            'luglio': 7,
            'agosto': 8,
            'settembre': 9,
            'ottobre': 10,
            'novembre': 11,
            'dicembre': 12
        },
        'date_fmt': '%d/%m/%y',
        'time_fmt': '%H:%M',
        'iso6392': 'ita'
    },
    'ko_KR': {
        'language': '한국어',
        'deconstruct': '^(?P<y>[0-9]+)년\\s+(?P<m>[0-9]+)월\\s+(?P<d>[0-9]+)일',
        'date_fmt': '%y. %m. %d.',
        'time_fmt': '%p %I:%M',
        'iso6392': 'kor'
    },
    'nb_NO': {
        'language': 'Norsk',
        'deconstruct': '^(?P<d>[0-9]+)\\.?\\s+(?P<m>[^\\s]+)\\s+(?P<y>[0-9]+)',
        'months': {
            'januar': 1,
            'februar': 2,
            'mars': 3,
            'april': 4,
            'mai': 5,
            'juni': 6,
            'juli': 7,
            'august': 8,
            'september': 9,
            'oktober': 10,
            'november': 11,
            'desember': 12
        },
        'date_fmt': '%d.%m.%y',
        'time_fmt': '%H:%M',
        'iso6392': 'nor'
    },
    'nl_NL': {
        'language': 'Nederlands',
        'deconstruct': '^(?P<d>[0-9]+)\\s+(?P<m>[^\\s]+)\\s+(?P<y>[0-9]+)',
        'months': {
            'januari': 1,
            'februari': 2,
            'maart': 3,
            'april': 4,
            'mei': 5,
            'juni': 6,
            'juli': 7,
            'augustus': 8,
            'september': 9,
            'oktober': 10,
            'november': 11,
            'december': 12
        },
        'date_fmt': '%d-%m-%y',
        'time_fmt': '%H:%M',
        'iso6392': 'nld'
    },
    'pl_PL': {
        'language': 'Polski',
        'deconstruct': '^(?P<d>[0-9]+)\\s+(?P<m>[^\\s]+)\\s+(?P<y>[0-9]+)',
        'months': {
            'stycznia': 1,
            'lutego': 2,
            'marca': 3,
            'kwietnia': 4,
            'maja': 5,
            'czerwca': 6,
            'lipca': 7,
            'sierpnia': 8,
            'września': 9,
            'października': 10,
            'listopada': 11,
            'grudnia': 12
        },
        'date_fmt': '%d.%m.%y',
        'time_fmt': '%H:%M',
        'iso6392': 'pol'
    },
    'pt_BR': {
        'language': 'Português (Brasil)',
        'deconstruct': '^(?P<d>[0-9]+)\\s+de\\s+(?P<m>[^\\s]+),?\\s+de\\s+(?P<y>[0-9]+)',
        'months': {
            'janeiro': 1,
            'fevereiro': 2,
            'março': 3,
            'abril': 4,
            'maio': 5,
            'junho': 6,
            'julho': 7,
            'agosto': 8,
            'setembro': 9,
            'outubro': 10,
            'novembro': 11,
            'dezembro': 12
        },
        'date_fmt': '%d/%m/%y',
        'time_fmt': '%H:%M',
        'iso6392': 'pt'  # only tvdb
    },
    'pt_PT': {
        'language': 'Português (Portugal)',
        'deconstruct': '^(?P<d>[0-9]+)\\s+de\\s+(?P<m>[^\\s]+),?\\s+de\\s+(?P<y>[0-9]+)',
        'months': {
            'janeiro': 1,
            'fevereiro': 2,
            'março': 3,
            'abril': 4,
            'maio': 5,
            'junho': 6,
            'julho': 7,
            'agosto': 8,
            'setembro': 9,
            'outubro': 10,
            'novembro': 11,
            'dezembro': 12
        },
        'date_fmt': '%d/%m/%y',
        'time_fmt': '%H:%M',
        'iso6392': 'por'
    },
    'ru_RU': {
        'language': 'Русский',
        'deconstruct': '^(?P<d>[0-9]+)\\s+(?P<m>[^\\s]+)\\s+(?P<y>[0-9]+)',
        'months': {
            'января': 1,
            'февраля': 2,
            'марта': 3,
            'апреля': 4,
            'мая': 5,
            'июня': 6,
            'июля': 7,
            'августа': 8,
            'сентября': 9,
            'октября': 10,
            'ноября': 11,
            'декабря': 12
        },
        'date_fmt': '%d.%m.%y',
        'time_fmt': '%H:%M',
        'iso6392': 'rus'
    },
    'sv_SE': {
        'language': 'Svenska',
        'deconstruct': '^(?P<d>[0-9]+)\\s+(?P<m>[^\\s]+)\\s+(?P<y>[0-9]+)',
        'months': {
            'januari': 1,
            'februari': 2,
            'mars': 3,
            'april': 4,
            'maj': 5,
            'juni': 6,
            'juli': 7,
            'augusti': 8,
            'september': 9,
            'oktober': 10,
            'november': 11,
            'december': 12
        },
        'date_fmt': '%y-%m-%d',
        'time_fmt': '%H:%M',
        'iso6392': 'swe'
    },
    'ta_IN': {
        'language': 'தமிழ்',
        'deconstruct': '^(?P<d>[0-9]+)\\s+(?P<m>[^\\s]+),?\\s+(?P<y>[0-9]+)',
        'months': {
            'ஜனவரி': 1,
            'பிப்ரவரி': 2,
            'மார்ச்': 3,
            'ஏப்ரல்': 4,
            'மே': 5,
            'ஜூன்': 6,
            'ஜூலை': 7,
            'ஆகஸ்ட்': 8,
            'செப்டம்பர்': 9,
            'அக்டோபர்': 10,
            'நவம்பர்': 11,
            'டிசம்பர்': 12
        },
        'date_fmt': '%d/%m/%y',
        'time_fmt': '%p %I:%M',
        'iso6392': 'tam'
    },
    'te_IN': {
        'language': 'తెలుగు',
        'deconstruct': '^(?P<d>[0-9]+)\\s+(?P<m>[^\\s]+),?\\s+(?P<y>[0-9]+)',
        'months': {
            'జనవరి': 1,
            'ఫిబ్రవరి': 2,
            'మార్చి': 3,
            'ఏప్రిల్': 4,
            'మే': 5,
            'జూన్': 6,
            'జులై': 7,
            'ఆగస్టు': 8,
            'సెప్టెంబర్': 9,
            'అక్టోబర్': 10,
            'నవంబర్': 11,
            'డిసెంబర్': 12
        },
        'date_fmt': '%d-%m-%y',
        'time_fmt': '%I:%M %p',
        'iso6392': 'tel'
    },
    'th_TH': {
        'language': 'ไทย',
        'deconstruct': '^(?P<d>[0-9]+)\\s+(?P<m>[^\\s]+),?\\s+(?P<y>[0-9]+)',
        'months': {
            'มกราคม': 1,
            'กุมภาพันธ์': 2,
            'มีนาคม': 3,
            'เมษายน': 4,
            'พฤษภาคม': 5,
            'มิถุนายน': 6,
            'กรกฎาคม': 7,
            'สิงหาคม': 8,
            'กันยายน': 9,
            'ตุลาคม': 10,
            'พฤศจิกายน': 11,
            'ธันวาคม': 12
        },
        'date_fmt': '%d/%m/%y',
        'time_fmt': '%H:%M',
        'iso6392': 'tha'
    },
    'tr_TR': {
        'language': 'Türkçe',
        'deconstruct': '^(?P<d>[0-9]+)\\s+(?P<m>[^\\s]+)\\s+(?P<y>[0-9]+)',
        'months': {
            'ocak': 1,
            'şubat': 2,
            'mart': 3,
            'nisan': 4,
            'mayıs': 5,
            'haziran': 6,
            'temmuz': 7,
            'ağustos': 8,
            'eylül': 9,
            'ekim': 10,
            'kasım': 11,
            'aralık': 12
        },
        'date_fmt': '%d.%m.%y',
        'time_fmt': '%H:%M',
        'iso6392': 'tur'
    },
    'vi_VN': {
        'deconstruct': '^(?P<d>[0-9]+)\\s+(?P<m>[^\\s]+)\\s+(?P<y>[0-9]+)',
        'months': {
            'tháng một': 1,
            'tháng hai': 2,
            'tháng ba': 3,
            'tháng tư': 4,
            'tháng năm': 5,
            'tháng sáu': 6,
            'tháng bảy': 7,
            'tháng tám': 8,
            'tháng chín': 9,
            'tháng mười': 10,
            'tháng mười một': 11,
            'tháng mười hai': 12
        },
        'iso6392': 'vie'
    },
    'zh_CN': {
        'language': '中文(简体)',
        'deconstruct': '^(?P<y>[0-9]+)[年,\\s]+(?P<m>[0-9]+)[月,\\s]+(?P<d>[0-9]+)[日,\\s]*',
        'months': {
            '一月': 1,
            '二月': 2,
            '三月': 3,
            '四月': 4,
            '五月': 5,
            '六月': 6,
            '七月': 7,
            '八月': 8,
            '九月': 9,
            '十月': 10,
            '十一月': 11,
            '十二月': 12
        },
        'date_fmt': '%y/%m/%d',
        'time_fmt': '%H:%M',
        'iso6392': 'zho'
    },
    'zh_TW': {
        'language': '中文(繁體)',
        'deconstruct': '^(?P<y>[0-9]+)[年,\\s]+(?P<m>[0-9]+)[月,\\s]+(?P<d>[0-9]+)[日,\\s]*',
        'months': {
            '一月': 1,
            '二月': 2,
            '三月': 3,
            '四月': 4,
            '五月': 5,
            '六月': 6,
            '七月': 7,
            '八月': 8,
            '九月': 9,
            '十月': 10,
            '十一月': 11,
            '十二月': 12
        },
        'date_fmt': '%y/%m/%d',
        'time_fmt': '%H:%M',
        'iso6392': 'zhtw'  # only tvdb
    },
    'ms_MY': {
        'language': 'Bahasa Melayu',
        'date_fmt': '%d/%m/%y',
        'time_fmt': '%I:%M %p',
        'iso6392': 'msa'
    },
    'hu_HU': {
        'language': 'Magyar',
        'date_fmt': '%y. %m. %d.',
        'time_fmt': '%H:%M',
        'iso6392': 'hun'
    },
    'ro_RO': {
        'language': 'Română',
        'date_fmt': '%d.%m.%y',
        'time_fmt': '%H:%M',
        'iso6392': 'ron'
    },
    'fil_PH': {
        'language': 'Wikang Filipino',
        'date_fmt': '%m/%d/%y',
        'time_fmt': '%I:%M %p',
        'iso6392': 'fil'
    },
    'cs_CZ': {
        'language': 'Čeština',
        'date_fmt': '%d.%m.%y',
        'time_fmt': '%H:%M',
        'iso6392': 'ces'
    },
    'el_GR': {
        'language': 'Ελληνικά',
        'date_fmt': '%d/%m/%y',
        'time_fmt': '%I:%M %p',
        'iso6392': 'gre'
    },
    'he_IL': {
        'language': 'עברית',
        'date_fmt': '%d.%m.%y',
        'time_fmt': '%H:%M',
        'iso6392': 'heb'
    },
    'ar_AE': {
        'language': 'العربية',
        'date_fmt': '%d /%m /%y',
        'time_fmt': '%I:%M %p',
        'iso6392': 'ara'
    },
    'ja_JP': {
        'language': '日本語',
        'date_fmt': '%y/%m/%d',
        'time_fmt': '%H:%M',
        'iso6392': 'jpn'
    }
}


def getString(string_id, addonInstance=None):
    if string_id < 30000:
        src = xbmc
    elif addonInstance is None:
        from .common import Globals
        src = Globals().addon
    else:
        src = addonInstance
    locString = src.getLocalizedString(string_id)
    return locString
