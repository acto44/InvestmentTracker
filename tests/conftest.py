"""Shared fixtures. INVARIANT (CLAUDE.md: PRIVACY): tests never touch the
real investments.db — every fixture points models at a throwaway database
via models.set_db_path() and restores the default afterwards."""

import os
import sys

# headless Qt for the UI smoke test — must be set before Qt loads
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import socket  # noqa: E402
import urllib.request  # noqa: E402

import pytest  # noqa: E402

import models  # noqa: E402
import seed_demo_data  # noqa: E402


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """INVARIANT (CLAUDE.md: AI): the suite must be INCAPABLE of calling
    a real API. Any socket connect or urlopen raises; tests that need a
    provider use FakeProvider or monkeypatch urlopen with a fake (their
    own monkeypatch overrides this one for the test's duration)."""
    def _blocked(*args, **kwargs):
        raise RuntimeError(
            "Blocked: network access attempted during tests — use a "
            "FakeProvider or mock urlopen (tests/conftest.py no_network)")
    monkeypatch.setattr(socket.socket, 'connect', _blocked)
    monkeypatch.setattr(socket, 'create_connection', _blocked)
    monkeypatch.setattr(urllib.request, 'urlopen', _blocked)


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


@pytest.fixture
def v1_db(tmp_path):
    """A REAL v1 database built by the actual v1 schema code, populated
    with one valued, one zero-valued and one unvalued company — for
    migration tests (init_db() then migrates it to the current version)."""
    path = str(tmp_path / 'test_investments.db')
    models.set_db_path(path)
    conn = models.get_conn()
    models._init_schema_v1(conn)
    conn.execute(
        "INSERT INTO companies (name, entity, current_valuation) "
        "VALUES ('Valued Co', 'A', 50000)")
    conn.execute(
        "INSERT INTO companies (name, entity, current_valuation) "
        "VALUES ('Zero Co', 'A', 0)")
    conn.execute(
        "INSERT INTO companies (name, entity) VALUES ('Unvalued Co', 'A')")
    conn.execute(
        "INSERT INTO funding_rounds (company_id, round_name, date, "
        "amount_invested, ownership_pct) VALUES (1, 'Seed', '2021-01-01', "
        "1000, 100)")
    conn.commit()
    conn.close()
    yield path
    models.set_db_path(None)
