import json
import sqlite3
import os
import shutil
from datetime import date, datetime, timezone


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

def _base():
    if getattr(__import__('sys'), 'frozen', False):
        return os.path.dirname(__import__('sys').executable)
    return os.path.dirname(os.path.abspath(__file__))

# Tests point the whole app at a throwaway database through this override —
# fixtures must NEVER touch the real investments.db (see CLAUDE.md: PRIVACY).
_DB_PATH_OVERRIDE = None

def set_db_path(path):
    """Override where the database lives (None = back to the default)."""
    global _DB_PATH_OVERRIDE
    _DB_PATH_OVERRIDE = path

def db_path_is_default() -> bool:
    """True when no override is active — i.e. we are pointing at the
    live database next to the app (see seed_demo_data's safety guard)."""
    return _DB_PATH_OVERRIDE is None

def get_db_path():
    if _DB_PATH_OVERRIDE:
        return _DB_PATH_OVERRIDE
    return os.path.join(_base(), "investments.db")

def get_docs_dir():
    d = os.path.join(_base(), "documents")
    os.makedirs(d, exist_ok=True)
    return d

def get_conn():
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def _init_schema_v1(conn):
    """Schema as it was before versioned migrations existed (v1).
    Kept callable on its own so migration tests can build a real v1
    database through the actual code path."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS companies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            entity TEXT DEFAULT '',
            sector TEXT,
            country TEXT,
            first_investment_date TEXT,
            current_valuation REAL,
            notes TEXT
        );
        CREATE TABLE IF NOT EXISTS funding_rounds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
            round_name TEXT,
            date TEXT,
            amount_invested REAL,
            pre_money_valuation REAL,
            post_money_valuation REAL,
            shares_received REAL,
            price_per_share REAL,
            total_shares_outstanding REAL,
            ownership_pct REAL,
            status TEXT DEFAULT 'Closed'
        );
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE,
            round_id INTEGER REFERENCES funding_rounds(id) ON DELETE CASCADE,
            doc_type TEXT,
            original_filename TEXT,
            stored_filename TEXT,
            added_date TEXT
        );
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        INSERT OR IGNORE INTO settings (key, value) VALUES ('currency', 'TKR');
        INSERT OR IGNORE INTO settings (key, value) VALUES ('currency_name', 'TKR');
    """)
    conn.commit()
    # Migrations — wrapped individually so later ones run even if earlier ones already ran
    for sql in [
        "ALTER TABLE companies ADD COLUMN entity TEXT DEFAULT ''",
        "ALTER TABLE companies ADD COLUMN website TEXT DEFAULT ''",
        "ALTER TABLE companies ADD COLUMN description TEXT DEFAULT ''",
        "ALTER TABLE companies ADD COLUMN thesis TEXT DEFAULT ''",
        "ALTER TABLE companies ADD COLUMN investment_type TEXT DEFAULT ''",
    ]:
        try:
            conn.execute(sql)
            conn.commit()
        except Exception:
            pass


# ── Versioned migrations (v2+) ────────────────────────────────────────────────
# Every migration gets a pre-migration backup first (see backups.py) and
# writes one 'migration' audit entry naming from/to version.

def _has_column(conn, table, column) -> bool:
    return column in {r[1] for r in conn.execute(f'PRAGMA table_info({table})')}


def _migrate_v2(conn):
    """Valuation history + audit trail; replaces companies.current_valuation."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS valuations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
            round_id INTEGER REFERENCES funding_rounds(id) ON DELETE SET NULL,
            as_of_date TEXT NOT NULL,
            value REAL NOT NULL CHECK(value > 0),
            source TEXT NOT NULL CHECK(source IN (
                'round_post_money','internal_estimate','external_valuation',
                'offer','exit','legacy_migration')),
            note TEXT DEFAULT '',
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_valuations_company_date
            ON valuations(company_id, as_of_date);
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts_utc TEXT NOT NULL,
            table_name TEXT NOT NULL,
            row_id INTEGER,
            company_id INTEGER,
            action TEXT NOT NULL CHECK(action IN
                ('insert','update','delete','migration')),
            changes TEXT NOT NULL,
            origin TEXT NOT NULL
        );
    """)
    # Backfill: one honest row per company that had a value. No invented
    # dates — as_of is the migration date and the note says so.
    if _has_column(conn, 'companies', 'current_valuation'):
        today = date.today().isoformat()
        now = _utcnow()
        for row in conn.execute(
                "SELECT id, current_valuation FROM companies "
                "WHERE current_valuation IS NOT NULL "
                "AND current_valuation > 0").fetchall():
            conn.execute(
                "INSERT INTO valuations (company_id, as_of_date, value, "
                "source, note, created_at) VALUES (?,?,?,?,?,?)",
                (row['id'], today, row['current_valuation'],
                 'legacy_migration',
                 'carried over from single-value field; original as-of '
                 'date unknown', now))
        # single source of truth: drop the old column where SQLite allows
        if sqlite3.sqlite_version_info >= (3, 35, 0):
            conn.execute(
                "ALTER TABLE companies DROP COLUMN current_valuation")


def _migrate_v3(conn):
    """Cash-flow ledger: every money movement gets a first-class home.
    Amounts are stored POSITIVE; direction comes from the type via
    metrics.signed_amount() (see CLAUDE.md: SIGN CONVENTION). Backfills
    one 'investment' flow per existing round."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS cashflows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
            round_id INTEGER REFERENCES funding_rounds(id) ON DELETE SET NULL,
            date TEXT NOT NULL,
            type TEXT NOT NULL CHECK(type IN (
                'investment','follow_on','exit_proceeds','partial_sale',
                'dividend','distribution','fee','other_in','other_out')),
            amount REAL NOT NULL CHECK(amount > 0),
            shares_delta REAL,
            note TEXT DEFAULT '',
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_cashflows_company_date
            ON cashflows(company_id, date);
    """)
    now = _utcnow()
    for r in conn.execute(
            "SELECT id, company_id, date, amount_invested FROM "
            "funding_rounds WHERE amount_invested IS NOT NULL "
            "AND amount_invested > 0").fetchall():
        conn.execute(
            "INSERT INTO cashflows (company_id, round_id, date, type, "
            "amount, note, created_at) VALUES (?,?,?,?,?,?,?)",
            (r['company_id'], r['id'], r['date'] or '', 'investment',
             r['amount_invested'], 'backfilled from funding round', now))


def _migrate_v4(conn):
    """Company journal: short dated 'how it's going' notes (ideally
    quarterly). Reports print the latest entries."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS company_updates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
            date TEXT NOT NULL,
            period_label TEXT,
            title TEXT,
            text TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_updates_company_date
            ON company_updates(company_id, date);
    """)


MIGRATIONS = [(2, _migrate_v2), (3, _migrate_v3), (4, _migrate_v4)]
SCHEMA_VERSION = max(v for v, _ in MIGRATIONS)


def _run_versioned_migrations():
    conn = get_conn()
    row = conn.execute(
        "SELECT value FROM settings WHERE key='schema_version'").fetchone()
    current = int(row['value']) if row else 1
    pending = [(v, fn) for v, fn in MIGRATIONS if v > current]
    if not pending:
        conn.close()
        return

    has_data = conn.execute(
        "SELECT EXISTS(SELECT 1 FROM companies) "
        "OR EXISTS(SELECT 1 FROM funding_rounds)").fetchone()[0]
    conn.close()
    if has_data:
        import backups
        backups.pre_migration_backup(current)

    for target, fn in pending:
        conn = get_conn()
        try:
            fn(conn)
            conn.execute(
                "INSERT OR REPLACE INTO settings (key,value) "
                "VALUES ('schema_version', ?)", (str(target),))
            conn.execute(
                "INSERT INTO audit_log (ts_utc, table_name, row_id, "
                "company_id, action, changes, origin) "
                "VALUES (?,?,?,?,?,?,?)",
                (_utcnow(), 'schema', None, None, 'migration',
                 json.dumps([{'field': 'schema_version',
                              'old': str(target - 1),
                              'new': str(target)}]),
                 'migration'))
            conn.commit()
        except Exception:
            conn.rollback()
            conn.close()
            raise
        conn.close()


def init_db():
    conn = get_conn()
    _init_schema_v1(conn)
    conn.close()
    _run_versioned_migrations()

# ── Default audit origin ──────────────────────────────────────────────────────
# Callers either pass origin=... per call, or wrap a whole flow with
# @with_origin('excel_import') so every mutation inside is attributed.

_DEFAULT_ORIGIN = 'app'


def with_origin(name):
    """Decorator: every model mutation inside runs with this audit origin
    unless the call passes its own."""
    import functools

    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            global _DEFAULT_ORIGIN
            prev = _DEFAULT_ORIGIN
            _DEFAULT_ORIGIN = name
            try:
                return fn(*args, **kwargs)
            finally:
                _DEFAULT_ORIGIN = prev
        return wrapper
    return deco


def _origin(origin):
    return origin if origin and origin != 'app' else _DEFAULT_ORIGIN


# ── Audit trail (append-only; see CLAUDE.md) ─────────────────────────────────
# Every financially meaningful mutation writes its entry IN THE SAME
# TRANSACTION as the change. There are deliberately no update/delete
# functions for audit_log.

_AUDIT_TRUNCATE = 500


def _trunc(v):
    s = v if isinstance(v, str) else v
    if isinstance(s, str) and len(s) > _AUDIT_TRUNCATE:
        return s[:_AUDIT_TRUNCATE] + '…[truncated]'
    return v


def _diff(old: dict, new: dict) -> list:
    """[{field, old, new}] for fields that actually changed."""
    out = []
    for k, nv in new.items():
        ov = old.get(k) if old else None
        if ov != nv:
            out.append({'field': k, 'old': _trunc(ov), 'new': _trunc(nv)})
    return out


def _audit(conn, table, row_id, action, changes, origin, company_id=None):
    conn.execute(
        "INSERT INTO audit_log (ts_utc, table_name, row_id, company_id, "
        "action, changes, origin) VALUES (?,?,?,?,?,?,?)",
        (_utcnow(), table, row_id, company_id, action,
         json.dumps(changes, ensure_ascii=False), _origin(origin)))


def get_audit_log(company_id=None, limit=500):
    conn = get_conn()
    if company_id is not None:
        rows = conn.execute(
            "SELECT * FROM audit_log WHERE company_id=? "
            "ORDER BY id DESC LIMIT ?", (company_id, limit)).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?",
            (limit,)).fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        try:
            d['changes'] = json.loads(d['changes'])
        except Exception:
            d['changes'] = []
        out.append(d)
    return out


# ── Valuation history (single source of truth for current value) ─────────────

VALUATION_SOURCES = ('round_post_money', 'internal_estimate',
                     'external_valuation', 'offer', 'exit',
                     'legacy_migration')

_LATEST_VALUATION_SQL = (
    "SELECT * FROM valuations WHERE company_id=? "
    "ORDER BY as_of_date DESC, created_at DESC, id DESC LIMIT 1")


def get_current_valuation(company_id):
    """The row with the latest as_of_date (ties: latest created_at, then
    id). This is THE way to obtain a company's current value."""
    conn = get_conn()
    row = conn.execute(_LATEST_VALUATION_SQL, (company_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_valuations(company_id):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM valuations WHERE company_id=? "
        "ORDER BY as_of_date DESC, created_at DESC, id DESC",
        (company_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_valuation_for_round(round_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM valuations WHERE round_id=?",
                       (round_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def add_valuation(company_id, as_of_date, value, source, note='',
                  round_id=None, origin='app'):
    if source not in VALUATION_SOURCES:
        raise ValueError(f'unknown valuation source: {source!r}')
    conn = get_conn()
    try:
        c = conn.execute(
            "INSERT INTO valuations (company_id, round_id, as_of_date, "
            "value, source, note, created_at) VALUES (?,?,?,?,?,?,?)",
            (company_id, round_id, as_of_date, value, source, note,
             _utcnow()))
        vid = c.lastrowid
        _audit(conn, 'valuations', vid, 'insert',
               _diff({}, {'as_of_date': as_of_date, 'value': value,
                          'source': source, 'note': note,
                          'round_id': round_id}),
               origin, company_id=company_id)
        conn.commit()
    except Exception:
        conn.rollback()
        conn.close()
        raise
    conn.close()
    return vid


def update_valuation(valuation_id, origin='app', **kwargs):
    if not kwargs:
        return
    if 'source' in kwargs and kwargs['source'] not in VALUATION_SOURCES:
        raise ValueError(f"unknown valuation source: {kwargs['source']!r}")
    conn = get_conn()
    try:
        old = conn.execute("SELECT * FROM valuations WHERE id=?",
                           (valuation_id,)).fetchone()
        if not old:
            conn.close()
            return
        old = dict(old)
        fields = ', '.join(f"{k}=?" for k in kwargs)
        conn.execute(f"UPDATE valuations SET {fields} WHERE id=?",
                     [*kwargs.values(), valuation_id])
        changes = _diff(old, kwargs)
        if changes:
            _audit(conn, 'valuations', valuation_id, 'update', changes,
                   origin, company_id=old['company_id'])
        conn.commit()
    except Exception:
        conn.rollback()
        conn.close()
        raise
    conn.close()


def delete_valuation(valuation_id, origin='app'):
    conn = get_conn()
    try:
        old = conn.execute("SELECT * FROM valuations WHERE id=?",
                           (valuation_id,)).fetchone()
        if not old:
            conn.close()
            return
        old = dict(old)
        conn.execute("DELETE FROM valuations WHERE id=?", (valuation_id,))
        _audit(conn, 'valuations', valuation_id, 'delete',
               [{'field': k, 'old': _trunc(v), 'new': None}
                for k, v in old.items() if k != 'id' and v is not None],
               origin, company_id=old['company_id'])
        conn.commit()
    except Exception:
        conn.rollback()
        conn.close()
        raise
    conn.close()


# ── Companies ────────────────────────────────────────────────────────────────

_LATEST_PER_COMPANY_SQL = """
    SELECT company_id, value, as_of_date, source FROM (
        SELECT company_id, value, as_of_date, source,
               ROW_NUMBER() OVER (PARTITION BY company_id
                   ORDER BY as_of_date DESC, created_at DESC, id DESC) rn
        FROM valuations) WHERE rn = 1
"""


def _attach_valuations(conn, companies: list):
    """Populate c['current_valuation'] (+ as-of/source) from the valuation
    history — the ONLY place the key is produced since the column was
    dropped in schema v2."""
    latest = {r['company_id']: r
              for r in conn.execute(_LATEST_PER_COMPANY_SQL).fetchall()}
    for c in companies:
        v = latest.get(c['id'])
        c['current_valuation'] = v['value'] if v else None
        c['valuation_as_of'] = v['as_of_date'] if v else None
        c['valuation_source'] = v['source'] if v else None
    return companies


def get_all_companies():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM companies ORDER BY entity, name").fetchall()
    companies = _attach_valuations(conn, [dict(r) for r in rows])
    conn.close()
    return companies

def get_companies_by_entity():
    """Returns {entity_name: [company, ...]} sorted alphabetically."""
    result: dict = {}
    for c in get_all_companies():
        key = c.get('entity') or 'Other'
        result.setdefault(key, []).append(c)
    return result

def get_entities():
    conn = get_conn()
    rows = conn.execute(
        "SELECT DISTINCT entity FROM companies WHERE entity IS NOT NULL AND entity != '' ORDER BY entity"
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]

def get_company(company_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM companies WHERE id=?", (company_id,)).fetchone()
    if not row:
        conn.close()
        return None
    company = _attach_valuations(conn, [dict(row)])[0]
    conn.close()
    return company

def add_company(name, entity='', sector='', country='', first_investment_date='',
                current_valuation=None, notes='', website='', description='',
                origin='app'):
    """current_valuation is a compatibility shim: it is recorded as a
    valuation-history point (source 'internal_estimate', as of today) —
    the companies table no longer has that column."""
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute(
            "INSERT INTO companies (name,entity,sector,country,first_investment_date,notes,website,description) VALUES (?,?,?,?,?,?,?,?)",
            (name, entity, sector, country, first_investment_date, notes, website, description)
        )
        cid = c.lastrowid
        _audit(conn, 'companies', cid, 'insert',
               _diff({}, {'name': name, 'entity': entity, 'sector': sector,
                          'country': country,
                          'first_investment_date': first_investment_date,
                          'notes': notes, 'website': website,
                          'description': description}),
               origin, company_id=cid)
        conn.commit()
    except Exception:
        conn.rollback()
        conn.close()
        raise
    conn.close()
    if current_valuation is not None and current_valuation > 0:
        add_valuation(cid, date.today().isoformat(), current_valuation,
                      'internal_estimate', note='initial valuation',
                      origin=origin)
    return cid

def update_company(company_id, origin='app', **kwargs):
    if not kwargs:
        return
    # compatibility shim: a current_valuation "edit" becomes a new
    # valuation point — but only when the value actually changed
    new_val = kwargs.pop('current_valuation', None)
    if kwargs:
        conn = get_conn()
        try:
            old = conn.execute("SELECT * FROM companies WHERE id=?",
                               (company_id,)).fetchone()
            old = dict(old) if old else {}
            fields = ', '.join(f"{k}=?" for k in kwargs)
            conn.execute(f"UPDATE companies SET {fields} WHERE id=?",
                         [*kwargs.values(), company_id])
            changes = _diff(old, kwargs)
            if changes:
                _audit(conn, 'companies', company_id, 'update', changes,
                       origin, company_id=company_id)
            conn.commit()
        except Exception:
            conn.rollback()
            conn.close()
            raise
        conn.close()
    if new_val is not None and new_val > 0:
        latest = get_current_valuation(company_id)
        if latest is None or abs(latest['value'] - new_val) > 1e-9:
            add_valuation(company_id, date.today().isoformat(), new_val,
                          'internal_estimate', note='value edited in app',
                          origin=origin)

def delete_company(company_id, origin='app'):
    conn = get_conn()
    try:
        old = conn.execute("SELECT * FROM companies WHERE id=?",
                           (company_id,)).fetchone()
        name = dict(old).get('name') if old else None
        conn.execute("DELETE FROM companies WHERE id=?", (company_id,))
        _audit(conn, 'companies', company_id, 'delete',
               [{'field': 'name', 'old': _trunc(name), 'new': None}],
               origin, company_id=company_id)
        conn.commit()
    except Exception:
        conn.rollback()
        conn.close()
        raise
    conn.close()

# ── Rounds ───────────────────────────────────────────────────────────────────

def get_rounds(company_id):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM funding_rounds WHERE company_id=? ORDER BY date", (company_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_round(round_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM funding_rounds WHERE id=?", (round_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def add_round(company_id, round_name='', date='', amount_invested=None,
              pre_money_valuation=None, post_money_valuation=None,
              shares_received=None, price_per_share=None,
              total_shares_outstanding=None, ownership_pct=None,
              status='Closed', origin='app'):
    if ownership_pct is None and shares_received and total_shares_outstanding:
        ownership_pct = (shares_received / total_shares_outstanding) * 100
    fields = {'round_name': round_name, 'date': date,
              'amount_invested': amount_invested,
              'pre_money_valuation': pre_money_valuation,
              'post_money_valuation': post_money_valuation,
              'shares_received': shares_received,
              'price_per_share': price_per_share,
              'total_shares_outstanding': total_shares_outstanding,
              'ownership_pct': ownership_pct, 'status': status}
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute(
            """INSERT INTO funding_rounds
               (company_id,round_name,date,amount_invested,pre_money_valuation,
                post_money_valuation,shares_received,price_per_share,
                total_shares_outstanding,ownership_pct,status)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (company_id, round_name, date, amount_invested, pre_money_valuation,
             post_money_valuation, shares_received, price_per_share,
             total_shares_outstanding, ownership_pct, status)
        )
        rid = c.lastrowid
        _audit(conn, 'funding_rounds', rid, 'insert',
               _diff({}, {k: v for k, v in fields.items() if v not in (None, '')}),
               origin, company_id=company_id)
        # write-through: the round's money movement lives in the ledger
        if amount_invested and amount_invested > 0:
            fc = conn.execute(
                "INSERT INTO cashflows (company_id, round_id, date, type, "
                "amount, note, created_at) VALUES (?,?,?,?,?,?,?)",
                (company_id, rid, date or '', 'investment',
                 amount_invested, f'round {round_name}'.strip(), _utcnow()))
            _audit(conn, 'cashflows', fc.lastrowid, 'insert',
                   _diff({}, {'date': date, 'type': 'investment',
                              'amount': amount_invested, 'round_id': rid}),
                   origin, company_id=company_id)
        conn.commit()
    except Exception:
        conn.rollback()
        conn.close()
        raise
    conn.close()
    return rid

def update_round(round_id, origin='app', **kwargs):
    if not kwargs:
        return
    sr = kwargs.get('shares_received')
    ts = kwargs.get('total_shares_outstanding')
    if sr and ts and 'ownership_pct' not in kwargs:
        kwargs['ownership_pct'] = (sr / ts) * 100
    conn = get_conn()
    try:
        old = conn.execute("SELECT * FROM funding_rounds WHERE id=?",
                           (round_id,)).fetchone()
        if not old:
            conn.close()
            return
        old = dict(old)
        fields = ', '.join(f"{k}=?" for k in kwargs)
        conn.execute(f"UPDATE funding_rounds SET {fields} WHERE id=?",
                     [*kwargs.values(), round_id])
        changes = _diff(old, kwargs)
        if changes:
            _audit(conn, 'funding_rounds', round_id, 'update', changes,
                   origin, company_id=old['company_id'])
        # write-through: keep the linked investment flow in sync
        new_amount = kwargs.get('amount_invested',
                                old.get('amount_invested'))
        new_date = kwargs.get('date', old.get('date'))
        flow = conn.execute(
            "SELECT * FROM cashflows WHERE round_id=? AND "
            "type='investment'", (round_id,)).fetchone()
        if flow and new_amount and new_amount > 0:
            flow = dict(flow)
            fl_changes = _diff(flow, {'amount': new_amount,
                                      'date': new_date or ''})
            if fl_changes:
                conn.execute(
                    "UPDATE cashflows SET amount=?, date=? WHERE id=?",
                    (new_amount, new_date or '', flow['id']))
                _audit(conn, 'cashflows', flow['id'], 'update',
                       fl_changes, origin, company_id=old['company_id'])
        elif not flow and new_amount and new_amount > 0:
            fc = conn.execute(
                "INSERT INTO cashflows (company_id, round_id, date, type, "
                "amount, note, created_at) VALUES (?,?,?,?,?,?,?)",
                (old['company_id'], round_id, new_date or '', 'investment',
                 new_amount, 'created when round gained an amount',
                 _utcnow()))
            _audit(conn, 'cashflows', fc.lastrowid, 'insert',
                   _diff({}, {'date': new_date, 'type': 'investment',
                              'amount': new_amount, 'round_id': round_id}),
                   origin, company_id=old['company_id'])
        conn.commit()
    except Exception:
        conn.rollback()
        conn.close()
        raise
    conn.close()

def clear_rounds(company_id, origin='app'):
    """Delete all funding rounds for a company (used before re-importing
    year data). Their linked investment flows go with them (write-through)."""
    conn = get_conn()
    try:
        n = conn.execute("SELECT COUNT(*) FROM funding_rounds WHERE company_id=?",
                         (company_id,)).fetchone()[0]
        nf = conn.execute(
            "SELECT COUNT(*) FROM cashflows WHERE company_id=? AND "
            "type='investment' AND round_id IS NOT NULL",
            (company_id,)).fetchone()[0]
        conn.execute(
            "DELETE FROM cashflows WHERE company_id=? AND "
            "type='investment' AND round_id IS NOT NULL", (company_id,))
        conn.execute("DELETE FROM funding_rounds WHERE company_id=?", (company_id,))
        if n:
            _audit(conn, 'funding_rounds', None, 'delete',
                   [{'field': 'rounds_deleted', 'old': n, 'new': None},
                    {'field': 'linked_flows_deleted', 'old': nf, 'new': None}],
                   origin, company_id=company_id)
        conn.commit()
    except Exception:
        conn.rollback()
        conn.close()
        raise
    conn.close()

def delete_round(round_id, origin='app'):
    conn = get_conn()
    try:
        old = conn.execute("SELECT * FROM funding_rounds WHERE id=?",
                           (round_id,)).fetchone()
        if not old:
            conn.close()
            return
        old = dict(old)
        # write-through: the linked investment flow leaves with the round
        flow = conn.execute(
            "SELECT id FROM cashflows WHERE round_id=? AND "
            "type='investment'", (round_id,)).fetchone()
        if flow:
            conn.execute("DELETE FROM cashflows WHERE id=?", (flow['id'],))
            _audit(conn, 'cashflows', flow['id'], 'delete',
                   [{'field': 'linked_to_round', 'old': round_id,
                     'new': None}],
                   origin, company_id=old['company_id'])
        conn.execute("DELETE FROM funding_rounds WHERE id=?", (round_id,))
        _audit(conn, 'funding_rounds', round_id, 'delete',
               [{'field': k, 'old': _trunc(v), 'new': None}
                for k, v in old.items()
                if k not in ('id', 'company_id') and v not in (None, '')],
               origin, company_id=old['company_id'])
        conn.commit()
    except Exception:
        conn.rollback()
        conn.close()
        raise
    conn.close()

# ── Cash-flow ledger ──────────────────────────────────────────────────────────
# ALL money movement lives here (single source of truth). Amounts stored
# POSITIVE; direction derives from type via metrics.signed_amount().
# Investment flows are round-linked and write-through: the round mutators
# above/below keep exactly one linked flow in the SAME transaction —
# public cashflow functions refuse to touch round-linked rows.

CASHFLOW_TYPES = ('investment', 'follow_on', 'exit_proceeds',
                  'partial_sale', 'dividend', 'distribution', 'fee',
                  'other_in', 'other_out')


def get_cashflows(company_id):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM cashflows WHERE company_id=? ORDER BY date, id",
        (company_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_cashflow(cashflow_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM cashflows WHERE id=?",
                       (cashflow_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_cashflows_by_company() -> dict:
    """{company_id: [flow, ...]} in one query — for dashboards/exports."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM cashflows ORDER BY date, id").fetchall()
    conn.close()
    out: dict = {}
    for r in rows:
        out.setdefault(r['company_id'], []).append(dict(r))
    return out


def get_cashflow_for_round(round_id):
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM cashflows WHERE round_id=? AND type='investment'",
        (round_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def shares_held(company_id) -> float:
    """Shares currently held = Σ shares_received from rounds
    + Σ shares_delta from flows (sales carry negative deltas)."""
    conn = get_conn()
    from_rounds = conn.execute(
        "SELECT COALESCE(SUM(shares_received), 0) FROM funding_rounds "
        "WHERE company_id=?", (company_id,)).fetchone()[0]
    from_flows = conn.execute(
        "SELECT COALESCE(SUM(shares_delta), 0) FROM cashflows "
        "WHERE company_id=?", (company_id,)).fetchone()[0]
    conn.close()
    return (from_rounds or 0) + (from_flows or 0)


def add_cashflow(company_id, date, type, amount, round_id=None,
                 shares_delta=None, note='', origin='app'):
    if type not in CASHFLOW_TYPES:
        raise ValueError(f'unknown cashflow type: {type!r}')
    if not amount or amount <= 0:
        raise ValueError('amount must be positive; direction comes from '
                         'the type (see CLAUDE.md: SIGN CONVENTION)')
    if type == 'partial_sale' and shares_delta:
        held = shares_held(company_id)
        if -shares_delta > held + 1e-9:
            raise ValueError(
                f'cannot sell {-shares_delta:,.0f} shares — only '
                f'{held:,.0f} held')
    conn = get_conn()
    try:
        c = conn.execute(
            "INSERT INTO cashflows (company_id, round_id, date, type, "
            "amount, shares_delta, note, created_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (company_id, round_id, date, type, amount, shares_delta,
             note, _utcnow()))
        fid = c.lastrowid
        _audit(conn, 'cashflows', fid, 'insert',
               _diff({}, {'date': date, 'type': type, 'amount': amount,
                          'shares_delta': shares_delta, 'note': note,
                          'round_id': round_id}),
               origin, company_id=company_id)
        conn.commit()
    except Exception:
        conn.rollback()
        conn.close()
        raise
    conn.close()
    return fid


def update_cashflow(cashflow_id, origin='app', **kwargs):
    if not kwargs:
        return
    if 'type' in kwargs and kwargs['type'] not in CASHFLOW_TYPES:
        raise ValueError(f"unknown cashflow type: {kwargs['type']!r}")
    conn = get_conn()
    try:
        old = conn.execute("SELECT * FROM cashflows WHERE id=?",
                           (cashflow_id,)).fetchone()
        if not old:
            conn.close()
            return
        old = dict(old)
        if old['round_id'] is not None:
            raise ValueError(
                'this flow is linked to a funding round — edit the round '
                'instead, and the flow follows automatically')
        fields = ', '.join(f"{k}=?" for k in kwargs)
        conn.execute(f"UPDATE cashflows SET {fields} WHERE id=?",
                     [*kwargs.values(), cashflow_id])
        changes = _diff(old, kwargs)
        if changes:
            _audit(conn, 'cashflows', cashflow_id, 'update', changes,
                   origin, company_id=old['company_id'])
        conn.commit()
    except Exception:
        conn.rollback()
        conn.close()
        raise
    conn.close()


def delete_cashflow(cashflow_id, origin='app'):
    conn = get_conn()
    try:
        old = conn.execute("SELECT * FROM cashflows WHERE id=?",
                           (cashflow_id,)).fetchone()
        if not old:
            conn.close()
            return
        old = dict(old)
        if old['round_id'] is not None:
            raise ValueError(
                'this flow is linked to a funding round — delete the '
                'round instead (its flow is removed with it)')
        conn.execute("DELETE FROM cashflows WHERE id=?", (cashflow_id,))
        _audit(conn, 'cashflows', cashflow_id, 'delete',
               [{'field': k, 'old': _trunc(v), 'new': None}
                for k, v in old.items()
                if k not in ('id', 'company_id') and v not in (None, '')],
               origin, company_id=old['company_id'])
        conn.commit()
    except Exception:
        conn.rollback()
        conn.close()
        raise
    conn.close()


# ── Company journal (dated qualitative updates) ───────────────────────────────

def get_company_updates(company_id):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM company_updates WHERE company_id=? "
        "ORDER BY date DESC, id DESC", (company_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_company_update(company_id, date, text, period_label=None,
                       title=None, origin='app'):
    if not (text or '').strip():
        raise ValueError('a journal entry needs text')
    conn = get_conn()
    try:
        c = conn.execute(
            "INSERT INTO company_updates (company_id, date, period_label, "
            "title, text, created_at) VALUES (?,?,?,?,?,?)",
            (company_id, date, period_label, title, text.strip(),
             _utcnow()))
        uid = c.lastrowid
        _audit(conn, 'company_updates', uid, 'insert',
               _diff({}, {'date': date, 'period_label': period_label,
                          'title': title, 'text': text.strip()}),
               origin, company_id=company_id)
        conn.commit()
    except Exception:
        conn.rollback()
        conn.close()
        raise
    conn.close()
    return uid


def update_company_update(update_id, origin='app', **kwargs):
    if not kwargs:
        return
    conn = get_conn()
    try:
        old = conn.execute("SELECT * FROM company_updates WHERE id=?",
                           (update_id,)).fetchone()
        if not old:
            conn.close()
            return
        old = dict(old)
        fields = ', '.join(f"{k}=?" for k in kwargs)
        conn.execute(f"UPDATE company_updates SET {fields} WHERE id=?",
                     [*kwargs.values(), update_id])
        changes = _diff(old, kwargs)
        if changes:
            _audit(conn, 'company_updates', update_id, 'update', changes,
                   origin, company_id=old['company_id'])
        conn.commit()
    except Exception:
        conn.rollback()
        conn.close()
        raise
    conn.close()


def delete_company_update(update_id, origin='app'):
    conn = get_conn()
    try:
        old = conn.execute("SELECT * FROM company_updates WHERE id=?",
                           (update_id,)).fetchone()
        if not old:
            conn.close()
            return
        old = dict(old)
        conn.execute("DELETE FROM company_updates WHERE id=?", (update_id,))
        _audit(conn, 'company_updates', update_id, 'delete',
               [{'field': k, 'old': _trunc(v), 'new': None}
                for k, v in old.items()
                if k not in ('id', 'company_id') and v not in (None, '')],
               origin, company_id=old['company_id'])
        conn.commit()
    except Exception:
        conn.rollback()
        conn.close()
        raise
    conn.close()


def get_valuations_by_company() -> dict:
    """{company_id: [valuation, ...]} in one query — for time series."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM valuations ORDER BY as_of_date, id").fetchall()
    conn.close()
    out: dict = {}
    for r in rows:
        out.setdefault(r['company_id'], []).append(dict(r))
    return out


def timeseries_inputs(entity=None, company_id=None) -> list:
    """[(company, rounds, valuations, cashflows), ...] — the shape
    metrics.nav_series consumes. Scope: everything, one entity, or one
    company."""
    companies = get_all_companies()
    if entity:
        companies = [c for c in companies if (c.get('entity') or '') == entity]
    if company_id:
        companies = [c for c in companies if c['id'] == company_id]
    flows_by = get_cashflows_by_company()
    vals_by = get_valuations_by_company()
    return [(c, get_rounds(c['id']), vals_by.get(c['id'], []),
             flows_by.get(c['id'], [])) for c in companies]


# ── Documents ─────────────────────────────────────────────────────────────────

def get_documents(company_id=None, round_id=None):
    conn = get_conn()
    if round_id:
        rows = conn.execute("SELECT * FROM documents WHERE round_id=?", (round_id,)).fetchall()
    elif company_id:
        rows = conn.execute(
            "SELECT * FROM documents WHERE company_id=? AND round_id IS NULL", (company_id,)
        ).fetchall()
    else:
        rows = []
    conn.close()
    return [dict(r) for r in rows]

def get_document_detail(doc_id):
    conn = get_conn()
    row = conn.execute("""
        SELECT d.*, c.name AS company_name, r.round_name
        FROM documents d
        LEFT JOIN companies c ON d.company_id = c.id
        LEFT JOIN funding_rounds r ON d.round_id = r.id
        WHERE d.id = ?
    """, (doc_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def add_document(src_path, doc_type, company_id=None, round_id=None):
    docs_dir = get_docs_dir()
    filename = os.path.basename(src_path)
    stored = filename
    dest = os.path.join(docs_dir, stored)
    counter = 1
    while os.path.exists(dest):
        name, ext = os.path.splitext(filename)
        stored = f"{name}_{counter}{ext}"
        dest = os.path.join(docs_dir, stored)
        counter += 1
    shutil.copy2(src_path, dest)
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "INSERT INTO documents (company_id,round_id,doc_type,original_filename,stored_filename,added_date) VALUES (?,?,?,?,?,?)",
        (company_id, round_id, doc_type, filename, stored, date.today().isoformat())
    )
    conn.commit()
    did = c.lastrowid
    conn.close()
    return did

def delete_document(doc_id):
    conn = get_conn()
    row = conn.execute("SELECT stored_filename FROM documents WHERE id=?", (doc_id,)).fetchone()
    if row:
        path = os.path.join(get_docs_dir(), row['stored_filename'])
        if os.path.exists(path):
            os.remove(path)
        conn.execute("DELETE FROM documents WHERE id=?", (doc_id,))
        conn.commit()
    conn.close()

def get_document_path(doc_id):
    conn = get_conn()
    row = conn.execute("SELECT stored_filename FROM documents WHERE id=?", (doc_id,)).fetchone()
    conn.close()
    if row:
        return os.path.join(get_docs_dir(), row['stored_filename'])
    return None

# ── Settings ──────────────────────────────────────────────────────────────────

def get_setting(key, default=''):
    conn = get_conn()
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    conn.close()
    return row['value'] if row else default

def set_setting(key, value):
    conn = get_conn()
    conn.execute("INSERT OR REPLACE INTO settings (key,value) VALUES (?,?)", (key, value))
    conn.commit()
    conn.close()

def backup_db(dest_path):
    shutil.copy2(get_db_path(), dest_path)

def restore_db(src_path):
    shutil.copy2(src_path, get_db_path())

def export_portable_zip(dest_path):
    import zipfile
    db_path   = get_db_path()
    docs_dir  = get_docs_dir()
    with zipfile.ZipFile(dest_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.write(db_path, 'investments.db')
        if os.path.isdir(docs_dir):
            for fname in os.listdir(docs_dir):
                zf.write(os.path.join(docs_dir, fname), f'documents/{fname}')

def import_portable_zip(src_path):
    import zipfile
    base     = _base()
    db_path  = get_db_path()
    docs_dir = get_docs_dir()
    with zipfile.ZipFile(src_path, 'r') as zf:
        names = zf.namelist()
        if 'investments.db' not in names:
            raise ValueError("Not a valid FamiljeInvesteringar backup (missing investments.db)")
        zf.extract('investments.db', base)
        for name in names:
            if name.startswith('documents/') and name != 'documents/':
                zf.extract(name, base)

# ── Thesis column migration (called from init_db) ─────────────────────────────

def _run_thesis_migration():
    conn = get_conn()
    try:
        conn.execute("ALTER TABLE companies ADD COLUMN thesis TEXT DEFAULT ''")
        conn.commit()
    except Exception:
        pass
    conn.close()

# ── Snapshot / delta tracking ─────────────────────────────────────────────────

def get_snapshot():
    import json
    from datetime import date as _date
    from metrics import OUTFLOW_TYPES   # money movement comes from the ledger
    companies = get_all_companies()
    flows_by = get_cashflows_by_company()
    snap_companies = {}
    total_inv_known = 0.0
    total_val_known = 0.0

    for c in companies:
        rounds = get_rounds(c['id'])
        invested = sum(f['amount'] for f in flows_by.get(c['id'], [])
                       if f['type'] in OUTFLOW_TYPES)
        val = c.get('current_valuation')

        current_value = None
        if val is not None:
            for r in sorted(rounds, key=lambda x: x.get('date') or '', reverse=True):
                if r.get('ownership_pct') is not None:
                    current_value = (r['ownership_pct'] / 100) * val
                    total_inv_known += invested
                    total_val_known += current_value
                    break

        snap_companies[str(c['id'])] = {
            'name': c['name'],
            'valuation': val,
            'invested': invested,
            'current_value': current_value,
            'docs': len(get_documents(company_id=c['id'])),
        }

    return {
        'date': _date.today().isoformat(),
        'portfolio_moic': (total_val_known / total_inv_known if total_inv_known > 0 else None),
        'companies': snap_companies,
    }

def load_last_snapshot():
    import json
    raw = get_setting('last_snapshot', '')
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None

def save_snapshot(snap):
    import json
    set_setting('last_snapshot', json.dumps(snap))
