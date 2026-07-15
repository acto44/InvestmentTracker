"""Shared fixtures. INVARIANT (CLAUDE.md: PRIVACY): tests never touch the
real investments.db — every fixture points models at a throwaway database
via models.set_db_path() and restores the default afterwards."""

import os
import sys

# headless Qt for the UI smoke test — must be set before Qt loads
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pytest  # noqa: E402

import models  # noqa: E402
import seed_demo_data  # noqa: E402


@pytest.fixture
def temp_db(tmp_path):
    """A fresh, empty database created through the REAL schema/migration
    code in models.init_db() — never hand-written CREATE TABLE."""
    path = str(tmp_path / 'test_investments.db')
    models.set_db_path(path)
    models.init_db()
    yield path
    models.set_db_path(None)


@pytest.fixture
def demo_db(temp_db):
    """temp_db populated with the fictional ViFi demo portfolio."""
    seed_demo_data.seed(verbose=False)
    return temp_db
