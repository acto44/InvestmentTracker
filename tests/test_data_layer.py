"""Session 2 tests: pre-migration backups, valuation history migration +
single source of truth, append-only audit trail, backup rotation."""

import os
import sqlite3
import time

import pytest

import backups
import excel_io
import metrics
import models


# ── Migration: v1 → current with backfill and backup ─────────────────────────
# (the v1_db fixture lives in conftest.py — shared with test_cashflows)

def test_migration_backfills_and_backs_up(v1_db):
    models.init_db()          # runs the v2 migration on the v1 database

    # pre-migration backup with the from-version in the name
    bdir = os.path.join(os.path.dirname(v1_db), 'backups')
    files = os.listdir(bdir)
    assert any('.v1.' in f for f in files), files

    # backfill: exactly one honestly-labeled row for the valued company
    vals = models.get_valuations(1)
    assert len(vals) == 1
    v = vals[0]
    assert v['source'] == 'legacy_migration'
    assert v['value'] == pytest.approx(50000)
    assert 'original as-of date unknown' in v['note']
    assert models.get_valuations(2) == []      # zero value: no row
    assert models.get_valuations(3) == []      # null value: no row

    # displayed value unchanged, now sourced from history
    c = models.get_company(1)
    assert c['current_valuation'] == pytest.approx(50000)
    assert c['valuation_source'] == 'legacy_migration'
    met = metrics.company_metrics(models.get_rounds(1),
                                  c['current_valuation'])
    assert met['current_value'] == pytest.approx(50000)  # 100% ownership

    # single source of truth: the old column is gone (SQLite >= 3.35)
    conn = models.get_conn()
    cols = {r[1] for r in conn.execute('PRAGMA table_info(companies)')}
    conn.close()
    assert 'current_valuation' not in cols

    # every migration step is in the audit log (v1→v2 and v2→v3)
    entries = models.get_audit_log()
    migs = [e for e in entries if e['action'] == 'migration']
    versions = {m['changes'][0]['new'] for m in migs}
    assert versions == {'2', '3'}


def test_migration_skips_backup_on_empty_db(temp_db):
    bdir = os.path.join(os.path.dirname(temp_db), 'backups')
    premig = [f for f in os.listdir(bdir)] if os.path.isdir(bdir) else []
    assert not any('.v1.' in f for f in premig), \
        'an empty fresh database needs no pre-migration backup'


# ── Latest-valuation selection ────────────────────────────────────────────────

def test_latest_valuation_by_date(temp_db):
    cid = models.add_company('C')
    models.add_valuation(cid, '2024-01-01', 100, 'internal_estimate')
    models.add_valuation(cid, '2025-06-01', 300, 'external_valuation')
    models.add_valuation(cid, '2024-12-01', 200, 'offer')
    cur = models.get_current_valuation(cid)
    assert cur['value'] == pytest.approx(300)
    assert cur['source'] == 'external_valuation'


def test_same_date_tie_breaks_on_created_at(temp_db):
    cid = models.add_company('C')
    conn = models.get_conn()
    # lower id has the LATER created_at: created_at must win over id
    conn.execute(
        "INSERT INTO valuations (company_id, as_of_date, value, source, "
        "created_at) VALUES (?, '2025-01-01', 111, 'internal_estimate', "
        "'2025-01-01T12:00:00Z')", (cid,))
    conn.execute(
        "INSERT INTO valuations (company_id, as_of_date, value, source, "
        "created_at) VALUES (?, '2025-01-01', 222, 'internal_estimate', "
        "'2025-01-01T09:00:00Z')", (cid,))
    conn.commit()
    conn.close()
    assert models.get_current_valuation(cid)['value'] == pytest.approx(111)


def test_valuation_value_must_be_positive(temp_db):
    cid = models.add_company('C')
    with pytest.raises(sqlite3.IntegrityError):
        models.add_valuation(cid, '2025-01-01', -5, 'internal_estimate')
    with pytest.raises(ValueError):
        models.add_valuation(cid, '2025-01-01', 5, 'made_up_source')


# ── Audit trail ───────────────────────────────────────────────────────────────

def _entries(cid=None):
    return models.get_audit_log(company_id=cid)


def test_audit_company_crud(temp_db):
    cid = models.add_company('Audit Co', sector='Tech',
                             origin='ui.company_dialog')
    models.update_company(cid, sector='Fintech', origin='ui.company_dialog')
    models.delete_company(cid, origin='ui.company_dialog')

    ins, upd, deleted = _entries(cid)[::-1]
    assert ins['action'] == 'insert' and ins['origin'] == 'ui.company_dialog'
    assert {'field': 'sector', 'old': 'Tech', 'new': 'Fintech'} \
        in upd['changes']
    assert deleted['action'] == 'delete'
    assert deleted['changes'][0]['old'] == 'Audit Co'


def test_audit_round_and_valuation(temp_db):
    cid = models.add_company('C')
    rid = models.add_round(cid, 'Seed', '2024-01-01', 500,
                           post_money_valuation=10000,
                           origin='ui.round_dialog')
    models.add_valuation(cid, '2024-01-01', 10000, 'round_post_money',
                         round_id=rid, origin='ui.round_dialog')
    models.update_round(rid, amount_invested=600, origin='ui.round_dialog')
    kinds = [(e['table_name'], e['action']) for e in _entries(cid)]
    assert ('funding_rounds', 'insert') in kinds
    assert ('valuations', 'insert') in kinds
    assert ('funding_rounds', 'update') in kinds
    upd = next(e for e in _entries(cid)
               if e['table_name'] == 'funding_rounds'
               and e['action'] == 'update')
    assert upd['changes'] == [
        {'field': 'amount_invested', 'old': 500.0, 'new': 600}]


def test_audit_excel_import_origin(temp_db):
    excel_io.import_rows([{
        'company': 'Sheet Co', 'current_valuation': 7000,
        'round': 'Seed', 'date': '2024-05-01', 'amount_invested': 900,
        'pre_money_valuation': None, 'post_money_valuation': None,
        'shares': None, 'price_per_share': None, 'ownership_pct': 100,
    }])
    entries = models.get_audit_log()
    origins = {e['origin'] for e in entries if e['action'] == 'insert'}
    assert origins == {'excel_import'}
    tables = {e['table_name'] for e in entries}
    assert {'companies', 'funding_rounds', 'valuations'} <= tables


def test_audit_atomicity_failed_write_leaves_no_row(temp_db):
    cid = models.add_company('C')
    before = len(_entries())
    with pytest.raises(sqlite3.OperationalError):
        models.update_company(cid, no_such_column='x')
    assert len(_entries()) == before, \
        'a failing write must not leave an audit row'


def test_audit_truncates_long_text(temp_db):
    cid = models.add_company('C')
    models.update_company(cid, notes='x' * 2000)
    upd = next(e for e in _entries(cid) if e['action'] == 'update')
    new = upd['changes'][0]['new']
    assert new.endswith('…[truncated]') and len(new) < 600


def test_audit_is_append_only(temp_db):
    assert not hasattr(models, 'update_audit_log')
    assert not hasattr(models, 'delete_audit_log')


# ── current_valuation compatibility shim ─────────────────────────────────────

def test_update_company_value_change_creates_point(temp_db):
    cid = models.add_company('C', current_valuation=1000)
    assert len(models.get_valuations(cid)) == 1
    models.update_company(cid, current_valuation=1000)   # unchanged
    assert len(models.get_valuations(cid)) == 1
    models.update_company(cid, current_valuation=2500)   # changed
    vals = models.get_valuations(cid)
    assert len(vals) == 2
    assert models.get_current_valuation(cid)['value'] == pytest.approx(2500)


def test_deleting_round_keeps_valuation_with_null_link(temp_db):
    cid = models.add_company('C')
    rid = models.add_round(cid, 'Seed', '2024-01-01', 500)
    models.add_valuation(cid, '2024-01-01', 9000, 'round_post_money',
                         round_id=rid)
    models.delete_round(rid)
    vals = models.get_valuations(cid)
    assert len(vals) == 1 and vals[0]['round_id'] is None


# ── Backups ───────────────────────────────────────────────────────────────────

def test_routine_backup_and_rotation(demo_db, tmp_path):
    bdir = backups.backup_dir()

    made = backups.routine_backup_if_due()
    assert made and os.path.isfile(made)
    assert backups.routine_backup_if_due() is None, \
        'a fresh routine backup means none is due'

    # plant 12 old routine backups + 2 pre-migration ones
    for i in range(12):
        p = os.path.join(bdir,
                         f'test_investments.db.routine.2024010{i % 10}'
                         f'T00000{i % 10}Z.db')
        with open(p, 'wb') as f:
            f.write(b'old')
        os.utime(p, (time.time() - 90000 - i, time.time() - 90000 - i))
    keep_forever = []
    for i in range(2):
        p = os.path.join(bdir,
                         f'test_investments.db.v{i + 1}.20240101T00000'
                         f'{i}Z.db')
        with open(p, 'wb') as f:
            f.write(b'premig')
        os.utime(p, (time.time() - 900000, time.time() - 900000))
        keep_forever.append(os.path.basename(p))

    # newest routine is now the one made above (recent) -> not due;
    # age it so a new one is created and pruning runs
    os.utime(made, (time.time() - 90000, time.time() - 90000))
    made2 = backups.routine_backup_if_due()
    assert made2

    routine = [f for f in os.listdir(bdir) if '.routine.' in f]
    assert len(routine) == backups.ROUTINE_KEEP, routine
    for f in keep_forever:
        assert f in os.listdir(bdir), 'pre-migration backups are kept forever'


def test_backup_is_a_valid_database(demo_db):
    made = backups.make_backup('routine')
    conn = sqlite3.connect(made)
    n = conn.execute('SELECT COUNT(*) FROM companies').fetchone()[0]
    conn.close()
    assert n == 10, 'backup must be a complete, openable database'


def test_backup_dir_override_via_settings(temp_db, tmp_path):
    custom = str(tmp_path / 'elsewhere')
    models.set_setting('backup_dir', custom)
    made = backups.make_backup('routine')
    assert os.path.dirname(made) == custom
