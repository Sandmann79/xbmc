import os
import polib
import requests
import json
import time
import re
from pathlib import Path

# ==============================
# CONFIG
# ==============================

DEEPL_API_KEY = os.getenv("DEEPL_API_KEY")
print (f"Using API-Key: {DEEPL_API_KEY}")
if not DEEPL_API_KEY:
    raise RuntimeError("DEEPL_API_KEY not set")

DEEPL_URL = "https://api-free.deepl.com/v2/translate"
PROTECTED_BRANDS = ["Prime", "Amazon", "Kodi", "Add-On", "Addon", "PrimeVideo"]
BATCH_SIZE = 50
CACHE_FILE = "./../translation_cache.json"
MAX_RETRIES = 5

LANG_ROOT = Path("./plugin.video.amazon-test/resources/language")  # root folder containing resource.language.xx_xx

LANGUAGE_MAP = {
    "af_za": "AF", "ar_sa": "AR", "bg_bg": "BG",
    "cs_cz": "CS", "da_dk": "DA", "de_de": "DE",
    "el_gr": "EL", "es_es": "ES", "et_ee": "ET",
    "fi_fi": "FI", "fr_fr": "FR", "hu_hu": "HU",
    "id_id": "ID", "it_it": "IT", "ja_jp": "JA",
    "ko_kr": "KO", "lt_lt": "LT", "lv_lv": "LV",
    "nb_no": "NB", "nl_nl": "NL", "pl_pl": "PL",
    "pt_br": "PT-BR", "pt_pt": "PT-PT",
    "ro_ro": "RO", "ru_ru": "RU", "sk_sk": "SK",
    "sl_si": "SL", "sv_se": "SV", "tr_tr": "TR",
    "uk_ua": "UK", "zh_cn": "ZH", "zh_tw": "ZH",
}

# ==============================
# CACHE
# ==============================

if os.path.exists(CACHE_FILE):
    with open(CACHE_FILE, "r", encoding="utf-8") as f:
        CACHE = json.load(f)
else:
    CACHE = {}

def save_cache():
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(CACHE, f, ensure_ascii=False, indent=2)

# ==============================
# PLACEHOLDER PROTECTION
# ==============================

PLACEHOLDER_PATTERN = re.compile(
    r'(%[-+#0-9.]*[a-zA-Z]|\{\w+(?::[^}]+)?\})'
)

def protect_placeholders(text):
    placeholders = PLACEHOLDER_PATTERN.findall(text)
    protected = text
    for i, ph in enumerate(placeholders):
        protected = protected.replace(ph, f"__PH_{i}__")
    return protected, placeholders

def restore_placeholders(text, placeholders):
    restored = text
    for i, ph in enumerate(placeholders):
        restored = restored.replace(f"__PH_{i}__", ph)
    return restored

# ==============================
# DEEPL BATCH TRANSLATE
# ==============================

def deepl_batch_translate(texts, target_lang):
    # Header exakt wie in der Doc, 'DeepL-Auth-Key' ist wichtig
    headers = {
        "Authorization": f"DeepL-Auth-Key {DEEPL_API_KEY}",
        "Content-Type": "application/json",
        "User-Agent": "KodiPluginTranslator/1.0"
    }
    
    # Payload als Dictionary (wird durch json= automatisch zu JSON)
    payload = {
        "text": texts,
        "target_lang": target_lang.upper(),
        "source_lang": "EN",
        "ignore_tags": ["notranslate"],   # WICHTIG: Schützt alles in <notranslate>
        "formality": "less",              # BONUS: "Du"-Form ist oft kürzer
        "context": "This is a user interface string for a media player plugin. Keep it very short and concise."
    }
    
    if target_lang in ['HU']:
        del payload['formality']

    for attempt in range(MAX_RETRIES):
        try:
            # json=payload setzt automatisch den Content-Type auf application/json
            response = requests.post(
                DEEPL_URL,
                headers=headers,
                json=payload, 
                timeout=60
            )

            if response.status_code == 200:
                return [t["text"] for t in response.json()["translations"]]
            
            # Falls immer noch Fehler, Details ausgeben
            print(f"DeepL Fehler {response.status_code}: {response.text}")
            
            if response.status_code == 429:
                time.sleep(2 ** attempt)
                continue
            break

        except Exception as e:
            print(f"Verbindungsfehler: {e}")
            time.sleep(2 ** attempt)

    raise RuntimeError("Anfrage an DeepL fehlgeschlagen.")


# ==============================
# MAIN
# ==============================

def process():

    # Load English reference
    en_path = next(LANG_ROOT.glob("resource.language.en_*/strings.po"), None)
    if not en_path:
        raise RuntimeError("English reference not found")

    en_po = polib.pofile(str(en_path))
    en_dict = {e.msgid: e for e in en_po if e.msgid.strip()}

    for lang_dir in LANG_ROOT.glob("resource.language.*"):

        lang_code = lang_dir.name.replace("resource.language.", "").lower()

        if lang_code.startswith("en") or lang_code.startswith("de"):
            continue

        target_lang = LANGUAGE_MAP.get(lang_code)
        if not target_lang:
            print(f"\nSkipping unsupported: {lang_code}")
            continue

        po_path = lang_dir / "strings.po"
        if not po_path.exists():
            continue

        print(f"\nProcessing {lang_code} → {target_lang}")

        po = polib.pofile(str(po_path))
        existing_ids = {e.msgid for e in po}
        entries_to_translate = []
        new_strings_count = 0  # Zähler für neue IDs

        # 1️⃣ Add missing entries from English (inkl. msgctxt!)
        for msgid, en_entry in en_dict.items():
            if msgid not in existing_ids:
                new_entry = polib.POEntry(
                    msgid=msgid,
                    msgstr="",
                    msgctxt=en_entry.msgctxt  # WICHTIG: Kontext kopieren
                )
                po.append(new_entry)
                entries_to_translate.append(new_entry)
                new_strings_count += 1

        # 2️⃣ Find empty or fuzzy entries
        # (Zähler für alle, die eine Übersetzung brauchen)
        initial_translate_count = len(list(set(entries_to_translate))) 
        for entry in po:
            if (not entry.msgstr.strip() or "fuzzy" in entry.flags) and entry.msgid.strip():
                entries_to_translate.append(entry)

        # Remove duplicates
        entries_to_translate = list(set(entries_to_translate))
        total_to_translate = len(entries_to_translate)
        
        if total_to_translate == 0:
            print("   -> Language is already up to date.")
            continue
        else:
            print(f"   -> Added {new_strings_count} missing strings from English reference.")
            print(f"   -> Total strings to translate/update: {total_to_translate}")

            
        # 3️⃣ Translate in batches
        for i in range(0, len(entries_to_translate), BATCH_SIZE):

            batch = entries_to_translate[i:i+BATCH_SIZE]
            protected_texts = []
            placeholder_sets = []

            for entry in batch:

                cache_key = f"{target_lang}:{entry.msgid}"
                if cache_key in CACHE:
                    entry.msgstr = CACHE[cache_key]
                    entry.flags = [f for f in entry.flags if f != "fuzzy"]
                    continue
                    
                protected, placeholders = protect_placeholders(entry.msgid)
                
                # NEU: Markennamen mit XML-Tags schützen
                for brand in PROTECTED_BRANDS:
                    # Nutze Case-Insensitive Replace oder exakten Match
                    protected = protected.replace(brand, f"<notranslate>{brand}</notranslate>")

                protected_texts.append(protected)
                placeholder_sets.append((entry, placeholders))

            if not protected_texts:
                continue

            translations = deepl_batch_translate(protected_texts, target_lang)

            for (entry, placeholders), translated in zip(placeholder_sets, translations):

                restored = restore_placeholders(translated.replace("<notranslate>", "").replace("</notranslate>", ""), placeholders)
                entry.msgstr = restored
                entry.flags = [f for f in entry.flags if f != "fuzzy"]

                CACHE[f"{target_lang}:{entry.msgid}"] = restored

        po.save()

    save_cache()
    print("\nAll languages synchronized and translated.")

# ==============================
# RUN
# ==============================

if __name__ == "__main__":
    process()
