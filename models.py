import sqlite3
import os
import shutil
from datetime import date

def _base():
    if getattr(__import__('sys'), 'frozen', False):
        return os.path.dirname(__import__('sys').executable)
    return os.path.dirname(os.path.abspath(__file__))

def get_db_path():
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

def init_db():
    conn = get_conn()
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
    conn.close()

# ── Companies ────────────────────────────────────────────────────────────────

def get_all_companies():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM companies ORDER BY entity, name").fetchall()
    conn.close()
    return [dict(r) for r in rows]

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
    conn.close()
    return dict(row) if row else None

def add_company(name, entity='', sector='', country='', first_investment_date='',
                current_valuation=None, notes='', website='', description=''):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "INSERT INTO companies (name,entity,sector,country,first_investment_date,current_valuation,notes,website,description) VALUES (?,?,?,?,?,?,?,?,?)",
        (name, entity, sector, country, first_investment_date, current_valuation, notes, website, description)
    )
    conn.commit()
    cid = c.lastrowid
    conn.close()
    return cid

def update_company(company_id, **kwargs):
    if not kwargs:
        return
    fields = ', '.join(f"{k}=?" for k in kwargs)
    conn = get_conn()
    conn.execute(f"UPDATE companies SET {fields} WHERE id=?", [*kwargs.values(), company_id])
    conn.commit()
    conn.close()

def delete_company(company_id):
    conn = get_conn()
    conn.execute("DELETE FROM companies WHERE id=?", (company_id,))
    conn.commit()
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
              total_shares_outstanding=None, ownership_pct=None, status='Closed'):
    if ownership_pct is None and shares_received and total_shares_outstanding:
        ownership_pct = (shares_received / total_shares_outstanding) * 100
    conn = get_conn()
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
    conn.commit()
    rid = c.lastrowid
    conn.close()
    return rid

def update_round(round_id, **kwargs):
    if not kwargs:
        return
    sr = kwargs.get('shares_received')
    ts = kwargs.get('total_shares_outstanding')
    if sr and ts and 'ownership_pct' not in kwargs:
        kwargs['ownership_pct'] = (sr / ts) * 100
    fields = ', '.join(f"{k}=?" for k in kwargs)
    conn = get_conn()
    conn.execute(f"UPDATE funding_rounds SET {fields} WHERE id=?", [*kwargs.values(), round_id])
    conn.commit()
    conn.close()

def clear_rounds(company_id):
    """Delete all funding rounds for a company (used before re-importing year data)."""
    conn = get_conn()
    conn.execute("DELETE FROM funding_rounds WHERE company_id=?", (company_id,))
    conn.commit()
    conn.close()

def delete_round(round_id):
    conn = get_conn()
    conn.execute("DELETE FROM funding_rounds WHERE id=?", (round_id,))
    conn.commit()
    conn.close()

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
    companies = get_all_companies()
    snap_companies = {}
    total_inv_known = 0.0
    total_val_known = 0.0

    for c in companies:
        rounds = get_rounds(c['id'])
        invested = sum((r.get('amount_invested') or 0) for r in rounds)
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
