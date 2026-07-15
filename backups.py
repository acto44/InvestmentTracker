"""Database backups (CLAUDE.md: the data layer must be trustworthy).

Two kinds, both created with SQLite's online backup API (safe while other
connections are open — never a raw file copy of a live database):

- pre-migration:  <dbname>.v<from_schema_version>.<UTC ts>.db
                  made automatically before ANY schema migration runs;
                  kept forever (never pruned)
- routine:        <dbname>.routine.<UTC ts>.db
                  made on app start when the newest routine backup is
                  older than 24 hours; only the last 10 are kept

Location: backups/ next to the database, overridable via the settings key
'backup_dir'. The folder is gitignored and guarded by the hygiene test.
"""

from __future__ import annotations

import os
import re
import sqlite3
from datetime import datetime, timezone

import models

ROUTINE_KEEP = 10
ROUTINE_MAX_AGE_HOURS = 24

_PREMIG_RE = re.compile(r'\.v\d+\.\d{8}T\d{6}Z\.db$')
_ROUTINE_RE = re.compile(r'\.routine\.\d{8}T\d{6}Z\.db$')


def backup_dir() -> str:
    override = ''
    try:
        override = models.get_setting('backup_dir', '')
    except Exception:
        pass  # settings table may not exist yet (first boot)
    d = override or os.path.join(os.path.dirname(models.get_db_path()),
                                 'backups')
    os.makedirs(d, exist_ok=True)
    return d


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')


def make_backup(tag: str) -> str:
    """Copy the current database via the SQLite backup API."""
    db = models.get_db_path()
    name = f"{os.path.basename(db)}.{tag}.{_timestamp()}.db"
    dest = os.path.join(backup_dir(), name)
    src = sqlite3.connect(db)
    dst = sqlite3.connect(dest)
    try:
        with dst:
            src.backup(dst)
    finally:
        src.close()
        dst.close()
    return dest


def pre_migration_backup(from_schema_version: int) -> str:
    """Called by the migration runner in models.py before any migration —
    every future schema change gets this protection for free."""
    return make_backup(f'v{from_schema_version}')


def _routine_files() -> list:
    d = backup_dir()
    files = [os.path.join(d, f) for f in os.listdir(d)
             if _ROUTINE_RE.search(f)]
    return sorted(files, key=os.path.getmtime)


def routine_backup_if_due(now=None) -> str | None:
    """On app start: back up if the newest routine backup is older than
    24h (or none exists). Prunes routine backups beyond the newest 10;
    pre-migration backups are never touched."""
    files = _routine_files()
    now_ts = (now or datetime.now(timezone.utc)).timestamp()
    if files:
        age_h = (now_ts - os.path.getmtime(files[-1])) / 3600
        if age_h < ROUTINE_MAX_AGE_HOURS:
            return None
    dest = make_backup('routine')
    for old in _routine_files()[:-ROUTINE_KEEP]:
        try:
            os.remove(old)
        except OSError:
            pass
    return dest
