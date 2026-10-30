#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Zentrales SQLite-Datenbank- und Migrationsmodul (db.py)
Verwaltet prozessweit genau eine Verbindung für menuCache.db und videoCache.db
für sowohl web_api.py als auch android_api.py und playback.py.
Alle Dateioperationen nutzen strikt xbmcvfs für volle Netzwerk-/PathSubstitution-Kompatibilität.
"""

import io
import json
import os.path
import pickle
import re
import sqlite3
import threading
import time
from collections import OrderedDict
from collections.abc import MutableMapping
from copy import deepcopy
from os.path import join as OSPJoin

from xbmcvfs import File, delete, exists, listdir, mkdirs

from .logging import Log

_RE_LEGACY_VIDEODATA = re.compile(r'^PVVideoData(.+)\.pvdp$')
_RE_LEGACY_CATALOG = re.compile(r'^PVCatalog(.+)\.pvcp$')
_RE_LEGACY_ART_DB = re.compile(r'^art-(.+)\.db$')
_RE_LEGACY_CACHE_DB = re.compile(r'^cache-(.+)\.db$')

VIDEO_DB_SCHEMA_VERSION = 2

# Whitelist für die sichere Migration alter Pickle-Dateien (verhindert Arbitrary Code Execution)
_SAFE_PICKLE_CLASSES = {
    ('collections', 'OrderedDict'): OrderedDict,
    ('builtins', 'dict'): dict,
    ('builtins', 'list'): list,
    ('builtins', 'tuple'): tuple,
    ('builtins', 'set'): set,
    ('builtins', 'frozenset'): frozenset,
    ('builtins', 'str'): str,
    ('builtins', 'bytes'): bytes,
    ('builtins', 'int'): int,
    ('builtins', 'float'): float,
    ('builtins', 'bool'): bool,
    ('__builtin__', 'dict'): dict,
    ('__builtin__', 'list'): list,
    ('__builtin__', 'tuple'): tuple,
    ('__builtin__', 'set'): set,
    ('__builtin__', 'str'): str,
    ('__builtin__', 'unicode'): str,
    ('__builtin__', 'int'): int,
    ('__builtin__', 'long'): int,
    ('__builtin__', 'float'): float,
    ('__builtin__', 'bool'): bool,
}

_db_lock = threading.RLock()
_menu_conn = None
_video_conn = None
_migrated_paths = set()


class _SafeUnpickler(pickle.Unpickler):
    """Erlaubt beim Migrieren alter .pvdp/.pvcp/resume.db Dateien ausschließlich sichere Basis-Datentypen."""
    def find_class(self, module, name):
        key = (module, name)
        if key in _SAFE_PICKLE_CLASSES:
            return _SAFE_PICKLE_CLASSES[key]
        raise pickle.UnpicklingError(f'Unsafe pickle class blocked: {module}.{name}')


def load_legacy_cache_bytes(raw_bytes):
    """Lädt alte Cache-Dateien (sowohl JSON als auch Legacy-Pickle) sicher in ein Python-Dict."""
    if not raw_bytes:
        return None
    if not raw_bytes.startswith(b'\x80'):
        try:
            return json.loads(raw_bytes.decode('utf-8'))
        except Exception:
            pass
    return _SafeUnpickler(io.BytesIO(raw_bytes), encoding='utf-8', errors='replace').load()


def _get_sqlite3_thread_safety():
    sqlite_threadsafe2python_dbapi = {0: 0, 2: 1, 1: 3}
    conn = sqlite3.connect(':memory:')
    try:
        row = conn.execute(
            "SELECT * FROM pragma_compile_options WHERE compile_options LIKE 'THREADSAFE=%'"
        ).fetchone()
        threadsafety_value = int(row[0].split('=')[1]) if row else 1
    finally:
        conn.close()
    return sqlite_threadsafe2python_dbapi.get(threadsafety_value, 1)


def _connect_sqlite(db_path):
    try:
        from xbmcvfs import translatePath
        db_path = translatePath(db_path)
    except Exception:
        pass
    db_dir = os.path.dirname(db_path)
    if db_dir and not exists(db_dir):
        mkdirs(db_dir)
    check_same_thread = False if _get_sqlite3_thread_safety() == 3 else True
    conn = sqlite3.connect(db_path, check_same_thread=check_same_thread, timeout=15.0)
    conn.execute('PRAGMA journal_mode=WAL;')
    conn.execute('PRAGMA synchronous=NORMAL;')
    conn.execute('PRAGMA temp_store=MEMORY;')
    conn.execute('PRAGMA cache_size=-8000;')
    return conn


def _ensure_column(conn, table_name, col_name, col_def_sql):
    """Prüft via PRAGMA table_info, ob eine Spalte existiert, und fügt sie zerstörungsfrei hinzu."""
    cols = {row[1] for row in conn.execute(f'PRAGMA table_info({table_name})').fetchall()}
    if col_name not in cols:
        conn.execute(f'ALTER TABLE {table_name} ADD COLUMN {col_name} {col_def_sql}')


def _mig_v1(conn):
    """Migration v0 -> v1: Basis-Tabellen, fehlende Spalten und Performance-Indizes zerstörungsfrei sicherstellen."""
    _ensure_column(conn, 'videodata', 'updated_at', 'INTEGER NOT NULL DEFAULT 0')
    _ensure_column(conn, 'art', 'date', 'INTEGER DEFAULT 0')
    _ensure_column(conn, 'resume_points', 'updated_at', 'INTEGER NOT NULL DEFAULT 0')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_videodata_updated ON videodata(market_id, updated_at)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_art_asin ON art(market_id, asin)')


def _mig_v2(conn):
    """
    Migration v1 -> v2: Zerstörungsfreie In-Place-Normalisierung bestehender JSON-Blobs in videodata und art
    sowie Sicherstellung aller Indizes, ohne Videoeinträge zu löschen.
    """
    _ensure_column(conn, 'videodata', 'updated_at', 'INTEGER NOT NULL DEFAULT 0')
    _ensure_column(conn, 'art', 'date', 'INTEGER DEFAULT 0')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_videodata_updated ON videodata(market_id, updated_at)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_art_asin ON art(market_id, asin)')

    # In-place JSON-Normalisierung für videodata (stellt sicher, dass metadata.artmeta und metadata.videometa existieren)
    try:
        conn.execute("""
            UPDATE videodata
            SET data_json = json_set(
                data_json,
                '$.metadata',
                json_patch(
                    '{"artmeta":{},"videometa":{}}',
                     COALESCE(json_extract(data_json, '$.metadata'), '{}')
                )
            )
            WHERE json_valid(data_json) = 1
              AND (
                  json_extract(data_json, '$.metadata.artmeta') IS NULL
                  OR json_extract(data_json, '$.metadata.videometa') IS NULL
              )
        """)
    except sqlite3.OperationalError:
        # Fallback über Python-Batch-Update, falls SQLite ohne JSON1 kompiliert wurde
        rows = conn.execute('SELECT market_id, gti, data_json FROM videodata').fetchall()
        updates = []
        for m_id, gti, raw in rows:
            try:
                obj = json.loads(raw)
                if isinstance(obj, dict):
                    changed = False
                    meta = obj.get('metadata')
                    if not isinstance(meta, dict):
                        obj['metadata'] = {'artmeta': {}, 'videometa': {}}
                        changed = True
                    else:
                        if not isinstance(meta.get('artmeta'), dict):
                            meta['artmeta'] = {}
                            changed = True
                        if not isinstance(meta.get('videometa'), dict):
                            meta['videometa'] = {}
                            changed = True
                    if changed:
                        updates.append((json.dumps(obj, separators=(',', ':')), m_id, gti))
            except Exception:
                pass
        if updates:
            conn.executemany('UPDATE videodata SET data_json = ? WHERE market_id = ? AND gti = ?', updates)


_VIDEO_DB_MIGRATIONS = OrderedDict([
    (1, _mig_v1),
    (2, _mig_v2),
])


def _migrate_video_db_schema(conn):
    """
    Führt inkrementelle, zerstörungsfreie Schema-Migrationen für videoCache.db durch.
    Bestehende Metadaten, Staffel-Bäume, Artworks und Resume-Punkte bleiben vollständig erhalten.
    """
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS db_schema_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        row = conn.execute("SELECT value FROM db_schema_meta WHERE key = 'schema_version'").fetchone()
        if row is not None:
            try:
                current_version = int(row[0])
            except (ValueError, TypeError):
                current_version = 0
        else:
            uv_row = conn.execute('PRAGMA user_version').fetchone()
            current_version = int(uv_row[0]) if uv_row and uv_row[0] else 0

        if current_version < VIDEO_DB_SCHEMA_VERSION:
            for target_ver, mig_fn in _VIDEO_DB_MIGRATIONS.items():
                if current_version < target_ver <= VIDEO_DB_SCHEMA_VERSION:
                    mig_fn(conn)
                    current_version = target_ver
            conn.execute(
                "INSERT OR REPLACE INTO db_schema_meta (key, value) VALUES ('schema_version', ?)",
                (str(VIDEO_DB_SCHEMA_VERSION),)
            )
            conn.execute(f'PRAGMA user_version = {int(VIDEO_DB_SCHEMA_VERSION)}')


def init_dbs(data_path, default_market_id='default'):
    """
    Initialisiert (oder liefert) die beiden zentralen SQLite-Datenbanken menuCache.db und videoCache.db,
    legt alle benötigten Tabellen für Web-API, Android-API und Playback an und führt einmalig
    die Migration vorhandener Alt-Caches über xbmcvfs durch.
    """
    global _menu_conn, _video_conn

    with _db_lock:
        if _menu_conn is None:
            menu_db_path = OSPJoin(data_path, 'menuCache.db')
            _menu_conn = _connect_sqlite(menu_db_path)
            with _menu_conn:
                # Tabelle für web_api.py
                _menu_conn.execute("""
                    CREATE TABLE IF NOT EXISTS menu_cache (
                        market_id TEXT PRIMARY KEY,
                        expiration INTEGER NOT NULL,
                        catalog_json TEXT NOT NULL,
                        updated_at INTEGER NOT NULL
                    )
                """)
                # Tabelle für android_api.py
                _menu_conn.execute("""
                    CREATE TABLE IF NOT EXISTS cache (
                        market_id TEXT NOT NULL,
                        id TEXT NOT NULL,
                        content TEXT,
                        PRIMARY KEY(market_id, id)
                    )
                """)

        if _video_conn is None:
            video_db_path = OSPJoin(data_path, 'videoCache.db')
            _video_conn = _connect_sqlite(video_db_path)
            with _video_conn:
                # Tabellen für web_api.py
                _video_conn.execute("""
                    CREATE TABLE IF NOT EXISTS videodata (
                        market_id TEXT NOT NULL,
                        gti TEXT NOT NULL,
                        data_json TEXT NOT NULL,
                        updated_at INTEGER NOT NULL,
                        PRIMARY KEY (market_id, gti)
                    )
                """)
                _video_conn.execute("""
                    CREATE TABLE IF NOT EXISTS urn2gti (
                        market_id TEXT NOT NULL,
                        urn TEXT NOT NULL,
                        gti TEXT NOT NULL,
                        PRIMARY KEY (market_id, urn)
                    )
                """)
                # Tabellen für android_api.py
                _video_conn.execute("""
                    CREATE TABLE IF NOT EXISTS art (
                        market_id TEXT NOT NULL,
                        asin TEXT NOT NULL,
                        season INTEGER,
                        info TEXT,
                        date INTEGER,
                        PRIMARY KEY(market_id, asin, season)
                    )
                """)
                _video_conn.execute("""
                    CREATE TABLE IF NOT EXISTS miss (
                        market_id TEXT NOT NULL,
                        asins TEXT NOT NULL,
                        title TEXT,
                        year TEXT,
                        content TEXT,
                        info TEXT,
                        PRIMARY KEY(market_id, asins, title)
                    )
                """)
                _video_conn.execute("""
                    CREATE TABLE IF NOT EXISTS seasons (
                        market_id TEXT NOT NULL,
                        seriesasin TEXT NOT NULL,
                        season INTEGER,
                        art TEXT,
                        PRIMARY KEY(market_id, seriesasin, season)
                    )
                """)
                # Tabelle für playback.py
                _video_conn.execute("""
                    CREATE TABLE IF NOT EXISTS resume_points (
                        market_id TEXT NOT NULL,
                        asin TEXT NOT NULL,
                        resume REAL NOT NULL,
                        updated_at INTEGER NOT NULL,
                        PRIMARY KEY (market_id, asin)
                    )
                """)

            _migrate_video_db_schema(_video_conn)

        if data_path and data_path not in _migrated_paths:
            _migrated_paths.add(data_path)
            _migrate_legacy_files(data_path, default_market_id or 'default')

        return _menu_conn, _video_conn, _db_lock


def close_dbs():
    """Schließt die zentralen SQLite-Verbindungen sauber."""
    global _menu_conn, _video_conn
    with _db_lock:
        for conn in (_menu_conn, _video_conn):
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass
        _menu_conn = None
        _video_conn = None


def _decode_bytes_recursive(obj):
    """Konvertiert eventuelle Byte-Strings aus alten Python-2/3-Pickles rekursiv in UTF-8-Strings."""
    if isinstance(obj, bytes):
        return obj.decode('utf-8', errors='replace')
    if isinstance(obj, OrderedDict):
        return OrderedDict((_decode_bytes_recursive(k), _decode_bytes_recursive(v)) for k, v in obj.items())
    if isinstance(obj, dict):
        return {_decode_bytes_recursive(k): _decode_bytes_recursive(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_decode_bytes_recursive(i) for i in obj]
    if isinstance(obj, tuple):
        return tuple(_decode_bytes_recursive(i) for i in obj)
    return obj


def _migrate_legacy_files(data_path, default_market_id):
    """
    Migriert sämtliche Altdateien (PVVideoData*.pvdp, PVCatalog*.pvcp, art-*.db, cache-*.db, resume.db)
    über xbmcvfs in videoCache.db und menuCache.db und löscht die alten Dateien.
    """
    if not exists(data_path):
        return

    dirs_files = listdir(data_path)
    files = dirs_files[1] if len(dirs_files) > 1 else []
    now = int(time.time())

    for fname in files:
        fpath = OSPJoin(data_path, fname)

        # 1. Altes Web-API VideoData-File (PVVideoData<MarketID>.pvdp)
        m_vd = _RE_LEGACY_VIDEODATA.match(fname)
        if m_vd and exists(fpath):
            market_id = m_vd.group(1)
            try:
                with File(fpath) as fp:
                    raw = bytes(fp.readBytes())
                data = _decode_bytes_recursive(load_legacy_cache_bytes(raw))
                if isinstance(data, dict) and 'urn2gti' in data:
                    urn_map = data.get('urn2gti') or {}
                    urn_rows = [(market_id, str(u), str(g)) for u, g in urn_map.items() if u and g]
                    vd_rows = [
                        (market_id, str(k), json.dumps(v, separators=(',', ':')), now)
                        for k, v in data.items()
                        if k != 'urn2gti' and isinstance(v, dict)
                    ]
                    with _video_conn:
                        if urn_rows:
                            _video_conn.executemany(
                                'INSERT OR REPLACE INTO urn2gti (market_id, urn, gti) VALUES (?, ?, ?)',
                                urn_rows
                            )
                        if vd_rows:
                            _video_conn.executemany(
                                'INSERT OR REPLACE INTO videodata (market_id, gti, data_json, updated_at) VALUES (?, ?, ?, ?)',
                                vd_rows
                            )
                    Log(f'Migrated legacy video cache "{fname}" ({len(vd_rows)} items) to videoCache.db', Log.INFO)
            except Exception as exc:
                Log(f'Failed to migrate legacy video cache "{fpath}": {exc}', Log.WARNING)
            finally:
                delete(fpath)
            continue

        # 2. Altes Web-API Catalog-File (PVCatalog<MarketID>.pvcp)
        m_cat = _RE_LEGACY_CATALOG.match(fname)
        if m_cat and exists(fpath):
            market_id = m_cat.group(1)
            try:
                with File(fpath) as fp:
                    raw = bytes(fp.readBytes())
                cached = _decode_bytes_recursive(load_legacy_cache_bytes(raw))
                if isinstance(cached, dict) and cached.get('expiration', 0) > now:
                    exp = int(cached['expiration'])
                    cat_json = json.dumps(cached, separators=(',', ':'))
                    with _menu_conn:
                        _menu_conn.execute(
                            'INSERT OR REPLACE INTO menu_cache (market_id, expiration, catalog_json, updated_at) VALUES (?, ?, ?, ?)',
                            (market_id, exp, cat_json, now)
                        )
                    Log(f'Migrated legacy catalog cache "{fname}" to menuCache.db', Log.INFO)
            except Exception as exc:
                Log(f'Failed to migrate legacy catalog cache "{fpath}": {exc}', Log.WARNING)
            finally:
                delete(fpath)
            continue

        # 3. Alte Android-API art-<MarketID>.db
        m_art = _RE_LEGACY_ART_DB.match(fname)
        if m_art and exists(fpath):
            market_id = m_art.group(1)
            try:
                try:
                    from xbmcvfs import translatePath
                    local_art_path = translatePath(fpath)
                except Exception:
                    local_art_path = fpath
                old_conn = sqlite3.connect(local_art_path)
                try:
                    with _video_conn:
                        for tbl, cols in (
                            ('art', ('asin', 'season', 'info', 'date')),
                            ('miss', ('asins', 'title', 'year', 'content', 'info')),
                            ('seasons', ('seriesasin', 'season', 'art')),
                        ):
                            try:
                                rows = old_conn.execute(f"SELECT {', '.join(cols)} FROM {tbl}").fetchall()
                                if rows:
                                    placeholders = ', '.join(['?'] * (len(cols) + 1))
                                    _video_conn.executemany(
                                        f"INSERT OR IGNORE INTO {tbl} (market_id, {', '.join(cols)}) VALUES ({placeholders})",
                                        [(market_id, *r) for r in rows]
                                    )
                            except sqlite3.OperationalError:
                                pass
                finally:
                    old_conn.close()
                Log(f'Migrated legacy Android art DB "{fname}" to videoCache.db', Log.INFO)
            except Exception as exc:
                Log(f'Failed to migrate legacy art DB "{fname}": {exc}', Log.WARNING)
            finally:
                for suffix in ('', '-wal', '-shm', '-journal'):
                    if exists(fpath + suffix):
                        delete(fpath + suffix)
            continue

        # 4. Alte Android-API cache-<MarketID>.db
        m_cache = _RE_LEGACY_CACHE_DB.match(fname)
        if m_cache and exists(fpath):
            market_id = m_cache.group(1)
            try:
                try:
                    from xbmcvfs import translatePath
                    local_cache_path = translatePath(fpath)
                except Exception:
                    local_cache_path = fpath
                old_conn = sqlite3.connect(local_cache_path)
                try:
                    with _menu_conn:
                        try:
                            rows = old_conn.execute('SELECT id, content FROM cache').fetchall()
                            if rows:
                                _menu_conn.executemany(
                                    'INSERT OR IGNORE INTO cache (market_id, id, content) VALUES (?, ?, ?)',
                                    [(market_id, r[0], r[1]) for r in rows]
                                )
                        except sqlite3.OperationalError:
                            pass
                finally:
                    old_conn.close()
                Log(f'Migrated legacy Android menu cache DB "{fname}" to menuCache.db', Log.INFO)
            except Exception as exc:
                Log(f'Failed to migrate legacy cache DB "{fname}": {exc}', Log.WARNING)
            finally:
                for suffix in ('', '-wal', '-shm', '-journal'):
                    if exists(fpath + suffix):
                        delete(fpath + suffix)
            continue

        # 5. Alte Playback resume.db (Pickle)
        if fname == 'resume.db' and exists(fpath):
            try:
                with File(fpath) as fp:
                    raw = bytes(fp.readBytes())
                if raw:
                    items = _decode_bytes_recursive(load_legacy_cache_bytes(raw))
                    if isinstance(items, dict):
                        rows = [
                            (default_market_id, str(k), float(v.get('resume', 0)), now)
                            for k, v in items.items()
                            if isinstance(v, dict) and v.get('resume', 0) > 0
                        ]
                        if rows:
                            with _video_conn:
                                _video_conn.executemany(
                                    'INSERT OR REPLACE INTO resume_points (market_id, asin, resume, updated_at) VALUES (?, ?, ?, ?)',
                                    rows
                                )
                        Log(f'Migrated {len(rows)} resume points from legacy resume.db to videoCache.db', Log.INFO)
            except Exception as exc:
                Log(f'Failed to migrate legacy resume.db: {exc}', Log.WARNING)
            finally:
                delete(fpath)


def get_resume_point(data_path, market_id, asin):
    """Liest den Resume-Zeitpunkt für eine ASIN und MarketID aus der zentralen videoCache.db."""
    if not asin:
        return 0
    try:
        _, video_conn, lock = init_dbs(data_path, market_id)
        with lock:
            cur = video_conn.execute(
                'SELECT resume FROM resume_points WHERE market_id = ? AND asin = ?',
                (market_id, asin)
            )
            row = cur.fetchone()
        return row[0] if row is not None else 0
    except Exception as exc:
        Log(f'Failed to read resume point from videoCache.db: {exc}', Log.ERROR)
        return 0


def save_resume_point(data_path, market_id, asin, resume_sec, watched=False):
    """Speichert oder löscht den Resume-Zeitpunkt für eine ASIN und MarketID in der zentralen videoCache.db."""
    if not asin:
        return
    try:
        _, video_conn, lock = init_dbs(data_path, market_id)
        with lock:
            with video_conn:
                if watched:
                    video_conn.execute(
                        'DELETE FROM resume_points WHERE market_id = ? AND asin = ?',
                        (market_id, asin)
                    )
                else:
                    video_conn.execute(
                        'INSERT OR REPLACE INTO resume_points (market_id, asin, resume, updated_at) VALUES (?, ?, ?, ?)',
                        (market_id, asin, float(resume_sec), int(time.time()))
                    )
    except Exception as exc:
        Log(f'Failed to save resume point to videoCache.db: {exc}', Log.ERROR)


class SQLiteUrn2Gti(MutableMapping):
    """
    Schnelles In-Memory- und SQLite-gestütztes Mapping für urn2gti,
    partitioniert nach MarketID innerhalb der zentralen videoCache.db.
    """
    def __init__(self, conn, lock, market_id):
        self._conn = conn
        self._lock = lock
        self._market_id = market_id
        self._data = {}
        self._dirty = {}
        self._deleted = set()
        self._load_all()

    def _load_all(self):
        with self._lock:
            cur = self._conn.execute(
                'SELECT urn, gti FROM urn2gti WHERE market_id = ?',
                (self._market_id,)
            )
            self._data = dict(cur.fetchall())

    def __getitem__(self, key):
        return self._data[key]

    def __setitem__(self, key, value):
        if self._data.get(key) != value:
            self._data[key] = value
            self._dirty[key] = value
            self._deleted.discard(key)

    def __delitem__(self, key):
        del self._data[key]
        self._dirty.pop(key, None)
        self._deleted.add(key)

    def __iter__(self):
        return iter(self._data)

    def __len__(self):
        return len(self._data)

    def __contains__(self, key):
        return key in self._data

    def clear_market(self):
        with self._lock:
            with self._conn:
                self._conn.execute('DELETE FROM urn2gti WHERE market_id = ?', (self._market_id,))
        self._data.clear()
        self._dirty.clear()
        self._deleted.clear()

    def flush(self):
        if not self._dirty and not self._deleted:
            return
        with self._lock:
            with self._conn:
                if self._deleted:
                    self._conn.executemany(
                        'DELETE FROM urn2gti WHERE market_id = ? AND urn = ?',
                        [(self._market_id, u) for u in self._deleted]
                    )
                    self._deleted.clear()
                if self._dirty:
                    self._conn.executemany(
                        'INSERT OR REPLACE INTO urn2gti (market_id, urn, gti) VALUES (?, ?, ?)',
                        [(self._market_id, u, g) for u, g in self._dirty.items()]
                    )
                    self._dirty.clear()


class SQLiteVideoData(MutableMapping):
    """
    Dict-kompatibles VideoData-Backend auf Basis der zentralen videoCache.db für alle MarketIDs.
    Lädt Einträge bei Bedarf (Lazy Loading) + Batch-Preloading und schreibt beim Flush
    nur tatsächlich geänderte GTIs in die SQLite-Datenbank.
    """
    def __init__(self, conn, lock, market_id):
        self._conn = conn
        self._lock = lock
        self._market_id = market_id
        self._urn2gti = SQLiteUrn2Gti(conn, lock, market_id)
        self._cache = {}
        self._clean_json = {}
        self._missing = set()
        self._deleted = set()

    def _fetch_one(self, gti):
        with self._lock:
            cur = self._conn.execute(
                'SELECT data_json FROM videodata WHERE market_id = ? AND gti = ?',
                (self._market_id, gti)
            )
            row = cur.fetchone()
        if row is not None:
            raw = row[0]
            val = json.loads(raw)
            self._cache[gti] = val
            self._clean_json[gti] = raw
            return val
        self._missing.add(gti)
        return None

    def preload(self, keys):
        """Lädt mehrere GTIs in einer einzigen SQLite-Abfrage vor (vermeidet N+1 Queries in Browse)."""
        to_load = [
            k for k in keys
            if k and k != 'urn2gti' and k not in self._cache and k not in self._missing
        ]
        if not to_load:
            return
        found = set()
        with self._lock:
            for i in range(0, len(to_load), 400):
                chunk = to_load[i:i + 400]
                placeholders = ','.join(['?'] * len(chunk))
                cur = self._conn.execute(
                    f'SELECT gti, data_json FROM videodata WHERE market_id = ? AND gti IN ({placeholders})',
                    [self._market_id] + chunk
                )
                for gti, raw in cur.fetchall():
                    self._cache[gti] = json.loads(raw)
                    self._clean_json[gti] = raw
                    found.add(gti)
        for k in to_load:
            if k not in found:
                self._missing.add(k)

    def __getitem__(self, key):
        if key == 'urn2gti':
            return self._urn2gti
        if key in self._cache:
            return self._cache[key]
        if key in self._missing:
            raise KeyError(key)
        val = self._fetch_one(key)
        if val is None:
            raise KeyError(key)
        return val

    def __setitem__(self, key, value):
        if key == 'urn2gti':
            if isinstance(value, dict):
                self._urn2gti.clear()
                self._urn2gti.update(value)
            return
        self._cache[key] = value
        self._missing.discard(key)
        self._deleted.discard(key)

    def __delitem__(self, key):
        if key == 'urn2gti':
            self._urn2gti.clear_market()
            return
        self._cache.pop(key, None)
        self._clean_json.pop(key, None)
        self._missing.add(key)
        self._deleted.add(key)

    def __contains__(self, key):
        if key == 'urn2gti':
            return True
        if key in self._cache:
            return True
        if key in self._missing:
            return False
        return self._fetch_one(key) is not None

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def __iter__(self):
        yield 'urn2gti'
        with self._lock:
            cur = self._conn.execute(
                'SELECT gti FROM videodata WHERE market_id = ?',
                (self._market_id,)
            )
            db_keys = {row[0] for row in cur.fetchall()}
        all_keys = (db_keys | set(self._cache.keys())) - self._deleted
        for k in all_keys:
            yield k

    def __len__(self):
        with self._lock:
            cur = self._conn.execute(
                'SELECT COUNT(*) FROM videodata WHERE market_id = ?',
                (self._market_id,)
            )
            count = cur.fetchone()[0]
        new_in_mem = sum(1 for k in self._cache if k not in self._clean_json)
        return 1 + count + new_in_mem

    @staticmethod
    def _deep_merge_dict(target, source, overwrite=False):
        """Fügt Felder aus source tief (deep-merge) in target ein, ohne gecachte Listen/Felder blind zu überschreiben."""
        for k, v in source.items():
            if isinstance(v, dict) and isinstance(target.get(k), dict):
                SQLiteVideoData._deep_merge_dict(target[k], v, overwrite=overwrite)
            elif isinstance(v, list) and isinstance(target.get(k), list):
                for item in v:
                    if item not in target[k]:
                        target[k].append(item)
            else:
                if overwrite or k not in target or target[k] in (None, '', [], {}):
                    target[k] = deepcopy(v) if isinstance(v, (dict, list)) else v

    def merge_entry(self, gti, partial_dict, overwrite=False):
        """
        Fügt neue Felder tief (deep-merge) in einen bestehenden _videodata[gti]-Eintrag ein,
        ohne bereits gecachte Felder (wie children, siblings, parent oder artmeta) zu verlieren.
        """
        if not gti or not isinstance(partial_dict, dict):
            return None
        with self._lock:
            existing = self.get(gti)
            if not isinstance(existing, dict):
                entry = deepcopy(partial_dict)
                self[gti] = entry
                return entry
            self._deep_merge_dict(existing, partial_dict, overwrite=overwrite)
            self[gti] = existing
            return existing

    def clear_market(self):
        self._urn2gti.clear_market()
        with self._lock:
            with self._conn:
                self._conn.execute('DELETE FROM videodata WHERE market_id = ?', (self._market_id,))
        self._cache.clear()
        self._clean_json.clear()
        self._missing.clear()
        self._deleted.clear()

    def flush(self):
        """Schreibt ausschließlich geänderte oder neue VideoData-Einträge in die SQLite-DB."""
        self._urn2gti.flush()
        now = int(time.time())
        to_upsert = []
        for gti, val in list(self._cache.items()):
            raw = json.dumps(val, separators=(',', ':'))
            if self._clean_json.get(gti) != raw:
                to_upsert.append((self._market_id, gti, raw, now))
                self._clean_json[gti] = raw

        if not to_upsert and not self._deleted:
            return

        with self._lock:
            with self._conn:
                if self._deleted:
                    self._conn.executemany(
                        'DELETE FROM videodata WHERE market_id = ? AND gti = ?',
                        [(self._market_id, g) for g in self._deleted]
                    )
                    self._deleted.clear()
                if to_upsert:
                    self._conn.executemany(
                        'INSERT OR REPLACE INTO videodata (market_id, gti, data_json, updated_at) VALUES (?, ?, ?, ?)',
                        to_upsert
                    )