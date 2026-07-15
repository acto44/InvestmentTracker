"""Fixture self-checks: the temp/demo databases are real (built by the
actual schema code), populated, isolated from the live database, and the
seeder stays idempotent."""

import os

import models
import seed_demo_data


def test_temp_db_has_the_real_schema(temp_db):
    conn = models.get_conn()
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    conn.close()
    assert {'companies', 'funding_rounds', 'documents',
            'settings'} <= tables
    assert os.path.basename(temp_db) == 'test_investments.db'


def test_temp_db_migrations_applied(temp_db):
    conn = models.get_conn()
    cols = {r[1] for r in conn.execute('PRAGMA table_info(companies)')}
    conn.close()
    # columns added by the migration loop in models.init_db()
    assert {'entity', 'website', 'description', 'thesis',
            'investment_type'} <= cols


def test_demo_db_is_populated(demo_db):
    companies = models.get_all_companies()
    assert len(companies) == 10
    entities = {c['entity'] for c in companies}
    assert entities == {'Portfolio A', 'Portfolio B'}
    rounds = [models.get_rounds(c['id']) for c in companies]
    assert all(rounds), 'every demo company has at least one round'


def test_seed_is_idempotent(demo_db):
    before = len(models.get_all_companies())
    seed_demo_data.seed(verbose=False)
    assert len(models.get_all_companies()) == before


def test_seed_refuses_populated_default_path(demo_db, monkeypatch):
    """The safety guard: against the DEFAULT db path (possibly a live
    family file) the seeder must refuse to replace existing data."""
    monkeypatch.setattr(models, 'db_path_is_default', lambda: True)
    import pytest
    with pytest.raises(SystemExit):
        seed_demo_data.seed(verbose=False)
    seed_demo_data.seed(verbose=False, force=True)   # explicit override ok


def test_fixtures_never_touch_the_live_db(temp_db):
    assert 'test_investments.db' in models.get_db_path()
    assert temp_db != os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'investments.db')


def test_override_resets_after_fixture():
    # runs without the fixture: default path must be back
    assert os.path.basename(models.get_db_path()) == 'investments.db'
