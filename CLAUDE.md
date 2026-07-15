# CLAUDE.md — rules for working on FamilyInvestmentTracker

Read this first, every session. A family's private finances live next to
this code — the invariants below are not style preferences.

## Project map
```
main.py                  entry point: app icon (drawn in code), QSS, boot;
                         when frozen, chdir to the exe's folder
models.py                SQLite layer: schema, versioned migration runner
                         (MIGRATIONS list; auto pre-migration backup),
                         audited CRUD (audit_log written in the same
                         transaction), valuation history API
                         (get_current_valuation is THE source of current
                         value), set_db_path()/get_db_path()
backups.py               SQLite backup-API copies: pre-migration (kept
                         forever) + 24h routine (last 10 kept); backups/
                         next to the DB, override via settings 'backup_dir'
metrics.py               financial math: ROI, MOIC, annualised IRR
                         (Newton + bisection); keeps its own self-test
excel_io.py              Excel import/export (openpyxl)
seed_demo_data.py        seed(verbose=True): fictional "ViFi" demo
                         portfolio (10 companies, 2 entities) — the ONLY
                         data allowed in fixtures/screenshots/the repo
ui/styles.py             design system: palette + QSS
                         (accent #3B82F6, bg #0B1220, cards #141D2E)
ui/main_window.py        MainWindow(): toolbar, Ctrl+N/K/R shortcuts,
                         QSettings persistence
ui/tree_panel.py         entities → companies tree, filter, status dots
ui/dashboard.py          portfolio KPIs, sector donut, charts (matplotlib)
ui/detail_panel.py       per-company tabs: Overview / Rounds / Documents
ui/quick_jump.py         Ctrl+K fuzzy company search
ui/dialogs.py            add/edit company, round & valuation dialogs
ui/history_dialog.py     read-only audit-trail view (global + per company)
ui/compare_dialog.py     side-by-side company comparison
ui/import_dialog.py, ui/family_import_dialog.py, ui/family_edit_dialog.py
                         Excel import + entity management
tests/                   pytest suite: conftest (temp_db/demo_db),
                         repo hygiene guard, metrics, fixtures, UI smoke
pytest.ini               testpaths=tests — root-level scratch scripts
                         (gitignored, may reference personal paths) must
                         never be collected
```

## Invariants
- **PRIVACY**: the real database, documents/ folder, real Excel files,
  backups and generated reports contain a family's private finances. They
  are gitignored and must NEVER appear in the repo, in tests, in fixtures,
  or in screenshots. All fixtures and examples use the fictional demo data
  from seed_demo_data.py only. Tests get their database exclusively
  through the `temp_db`/`demo_db` fixtures (which call
  `models.set_db_path()` to a temp file) — never the live path.
- **STACK**: PyQt6 desktop, SQLite, Windows-first. The one-file
  PyInstaller .exe build must keep working after every session.
- **DEPENDENCIES**: stdlib and existing deps first. Any new RUNTIME
  dependency requires a written justification in the dependency register
  below before it is added. Dev-only dependencies (pytest etc.) are
  allowed but also registered.
- **SCHEMA**: changes only via the versioned migration runner in
  models.py — append a `(version, migration_fn)` pair to `MIGRATIONS`
  and the runner backs up the database first, applies it, records a
  'migration' audit entry and bumps settings.schema_version. Copy this
  exactly:
  ```python
  def _migrate_v3(conn):
      conn.executescript("CREATE TABLE IF NOT EXISTS cashflows (...);")

  MIGRATIONS = [(2, _migrate_v2), (3, _migrate_v3)]
  ```
  (The pre-versioning additive-ALTER loop in `_init_schema_v1` is frozen
  history — never extend it.) Every mutation of financial tables goes
  through models.py functions so the audit trail stays complete; new
  mutators must write their audit entry in the same transaction.
- **MONEY**: amounts are stored as REAL; never compare floats for
  equality in tests (use pytest.approx); rounding happens only at display
  time through shared formatting helpers; every metric shown to the user
  must be able to state its assumptions (footnote strings live next to
  the math in metrics.py, nowhere else).
- **UI**: keep the dark design system in ui/styles.py and existing
  interaction patterns. Professional ≠ redesign.
- **PYINSTALLER RESOURCES**: any data file bundled into the .exe
  (templates, assets) must be resolved through a single resource_path()
  helper that handles sys._MEIPASS. Never open bundled files by relative
  path. (No bundled data files exist yet — create the helper together
  with the first one, in main.py.)

## How to run
Bare `python` on this machine is a Windows Store stub — use the full path.
```
# run the app (live database — real data, be careful)
C:\Users\joelg\AppData\Local\Python\bin\python.exe main.py

# demo data instead of real data (overwrites the CURRENT db — only run
# against a copy/fresh folder, never the family's live file)
C:\Users\joelg\AppData\Local\Python\bin\python.exe seed_demo_data.py

# test dependencies (once): pip install -r requirements-dev.txt
# full test suite (uses temp databases only; safe anywhere)
C:\Users\joelg\AppData\Local\Python\bin\python.exe -m pytest

# build the one-file .exe (spec file is local, gitignored)
C:\Users\joelg\AppData\Local\Python\bin\python.exe -m PyInstaller FamilyInvestmentTracker.spec
#   (equivalent from scratch: pyinstaller --onefile --windowed
#    --icon app.ico -n FamilyInvestmentTracker main.py)
```

## Definition of Done — every session
1. Full test suite green (`pytest`).
2. The app boots against demo data (tests/test_ui_smoke.py proves it).
3. `git status` shows no real-data files staged or tracked
   (tests/test_repo_hygiene.py proves the tracked state).
4. Session Log below updated.

## Dependency register
| name       | runtime/dev | justification                          | session |
|------------|-------------|----------------------------------------|---------|
| PyQt6      | runtime     | the UI framework (pre-existing)        | pre-1   |
| matplotlib | runtime     | dashboard charts (pre-existing)        | pre-1   |
| openpyxl   | runtime     | Excel import/export (pre-existing)     | pre-1   |
| pytest     | dev         | test runner for the whole suite        | 1       |
| pytest-qt  | dev         | headless Qt harness for UI smoke tests | 1       |

## Session Log
| date       | # | what changed                                          | migrations |
|------------|---|-------------------------------------------------------|------------|
| 2026-07-14 | 1 | CLAUDE.md constitution; repo hygiene guard test; pytest foundation (temp_db/demo_db fixtures, metrics under pytest, UI smoke via pytest-qt offscreen); models.set_db_path() override; seed_demo_data wrapped in seed() (script behavior unchanged); .gitignore extended (backups/, reports/, *.sqlite*) | none |
| 2026-07-14 | 2 | Trustworthy data layer: backups.py (pre-migration via SQLite backup API + 24h routine, keep-10 rotation); valuation history replaces companies.current_valuation (honest legacy_migration backfill, column dropped, get_current_valuation + enriched company dicts keep all readers working); append-only audit trail written in-transaction by every mutator, with origins (ui.*, excel_import); round↔valuation link + ask-on-delete; Valuation block in Overview; read-only History view (toolbar + per company); metrics UNREALIZED_VALUE_FOOTNOTE | v2: valuations, audit_log, DROP companies.current_valuation |
