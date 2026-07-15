"""Repo hygiene guard (CLAUDE.md: PRIVACY).

Reads `git ls-files` — the actual tracked state, not intent — and fails if
any tracked path could be the family's real data: databases, the documents/
folder, backups, Excel files or generated reports. Also asserts .gitignore
keeps covering the dangerous patterns.
"""

import glob
import os
import re
import shutil
import subprocess
import time

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# tracked paths matching any of these are a privacy violation
FORBIDDEN = [
    r'\.db$', r'\.sqlite3?$',
    r'^documents/', r'^backups/', r'^reports/',
    r'\.xlsx$', r'\.xls$',
    r'^investments\.db$',
]

# declared fixture/template exemptions (none yet — additions need a
# CLAUDE.md justification and must contain demo data only)
ALLOWED: set = set()

GITIGNORE_MUST_COVER = [
    'investments.db', '*.db', 'documents/', 'backups/', 'reports/',
    '*.xlsx', '*.xls', 'build/', 'dist/', '__pycache__/',
]


def _find_git() -> str:
    exe = shutil.which('git')
    if exe:
        return exe
    hits = glob.glob(os.path.join(
        os.path.expanduser('~'), 'AppData', 'Local', 'GitHubDesktop',
        'app-*', 'resources', 'app', 'git', 'cmd', 'git.exe'))
    if hits:
        return sorted(hits)[-1]
    pytest.fail('git executable not found — the hygiene guard cannot '
                'verify the repo state (install git or GitHub Desktop)')


def _tracked_files() -> list:
    # this machine occasionally refuses process spawns transiently
    # (antivirus); the guard must be reliable, so retry a few times
    last_err = None
    for attempt in range(4):
        try:
            r = subprocess.run([_find_git(), 'ls-files'], cwd=ROOT,
                               capture_output=True, text=True,
                               encoding='utf-8', timeout=60)
            assert r.returncode == 0, f'git ls-files failed: {r.stderr}'
            return [l.strip() for l in r.stdout.splitlines() if l.strip()]
        except OSError as e:
            last_err = e
            time.sleep(0.2 * (attempt + 1))
    pytest.fail(f'could not run git ls-files after retries: {last_err!r}')


def test_no_real_data_is_tracked():
    tracked = _tracked_files()
    assert tracked, 'git ls-files returned nothing — wrong directory?'
    violations = []
    for path in tracked:
        if path in ALLOWED:
            continue
        for pat in FORBIDDEN:
            if re.search(pat, path, re.IGNORECASE):
                violations.append(f'{path}  (matches {pat})')
                break
    assert not violations, (
        'PRIVACY VIOLATION — tracked files that may contain real family '
        'data:\n  ' + '\n  '.join(violations) +
        '\nRemove them from the index (git rm --cached) immediately; '
        'if this was a public push, rotate/scrub history.')


def test_gitignore_covers_the_dangerous_patterns():
    with open(os.path.join(ROOT, '.gitignore'), encoding='utf-8') as f:
        gi = f.read()
    missing = [p for p in GITIGNORE_MUST_COVER if p not in gi]
    assert not missing, f'.gitignore lost required patterns: {missing}'


def test_live_db_name_matches_models():
    """The ignore rules must cover the DB filename models.py actually
    uses — guards against a rename silently unprotecting the data."""
    import models
    default = os.path.basename(models.get_db_path())
    assert default == 'investments.db', (
        f'models.get_db_path() now uses {default!r}; update .gitignore, '
        'FORBIDDEN and this test together, deliberately.')
