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
metrics.py               financial math: ROI, MOIC/DPI/RVPI/TVPI, date-true
                         XIRR (Newton + bracket-scan bisection,
                         actual/365.25), signed_amount() sign convention,
                         pure time series (position_value_at, nav_series,
                         quarter helpers, nav_quarter_delta), footnote
                         strings; keeps its own self-test
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
- **SIGN CONVENTION**: cash-flow amounts are STORED positive; direction
  derives from the type in exactly one place — metrics.signed_amount().
  Outflows from the family ('investment','follow_on','fee','other_out')
  are negative; inflows ('exit_proceeds','partial_sale','dividend',
  'distribution','other_in') are positive. Every computation and every
  display goes through that helper.
- **LEDGER**: ALL money movement lives in the cashflows table. Investment
  flows are round-linked and write-through: the round mutators create/
  update/delete the linked flow in the SAME transaction; public cashflow
  functions refuse to touch round-linked rows. Metrics read ONLY
  cashflows — never round.amount_invested directly.
- **VALUATION MEANING**: a recorded valuation is the WHOLE company's
  value. Position value = valuation × our ownership %. Ownership comes
  from the most recent round that has a figure, scaled down after partial
  sales by the share of originally received shares still held. Companies
  whose status is Exited or Bankrupt are CLOSED: unrealized value is 0 by
  definition and only realized proceeds count (the valuation history
  keeps the record).
- **TIME SERIES ARE DERIVED, NOT STORED**: periodic NAV/snapshot values
  are computed on demand from the dated valuations and cashflows via the
  pure series functions in metrics.py. Reasoning: dated source data plus
  deterministic functions cannot go stale; stored snapshot copies can and
  do. Reports take an as-of parameter instead of reading frozen rows.
  Rules the series follow (all tested):
  - stepwise: a valuation applies from its as_of_date (inclusive) until
    the next one
  - same-day ordering: when a valuation and a flow share a date, the flow
    counts in the cumulative sums AND the valuation sets the NAV
  - closed positions contribute 0 from the date of their last exit-type
    flow (inclusive — the proceeds replace the position, no double
    count); write-offs with no exit flow contribute 0 after their last
    recorded activity
  - before the first valuation a position is shown at net invested
    capital with is_estimate=True — every consumer must surface that flag
    (dashed line, marker, or "contains estimates" note)
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

# demo data (REPLACES the current db's contents; a populated default-path
# database is refused unless you add --yes — the guard exists because of
# a near-miss, do not remove it)
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

## Future ideas (parked deliberately)
- "View the whole dashboard as of an arbitrary past date" — the derived
  series make it possible; out of scope until someone actually needs it.

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
| 2026-07-14 | 3 | Cash-flow ledger: cashflows table (backfilled 1 investment flow per round), round↔flow write-through in the same transaction, signed_amount() sign convention, DPI/RVPI/TVPI + realized/unrealized split, date-true XIRR with terminal-value assumption + bracket-scan bisection for multi-sign-change cases, closed-position rule (Exited/Bankrupt ⇒ unrealized 0), shares_held + oversell guard + ownership scaling after partial sales, ledger UI in Rounds & Cash flows tab, CashflowDialog, exit-status offer, dashboard Realized + MOIC/TVPI cards, Excel Cashflows sheet + explicit no-flow-import notes, demo data gains dividends/partial sale/full exit. Incident note: the seeder was accidentally run against the repo-root db (which holds demo data; the real family db in dist/ was never touched) — the session-2 pre-migration backup restored it, and seed_demo_data now refuses a populated default-path db without --yes | v3: cashflows |
| 2026-07-14 | 4 | Time axis: pure derived series in metrics.py (position_value_at with net-invested estimate fallback + is_estimate flag, invested/realized_to_date, month_end_grid, nav_series, quarter helpers, nav_quarter_delta) — derived-not-stored decision + same-day/closed-zero rules recorded as invariant; dashboard Portfolio-over-time chart (NAV/invested/realized steps, 1Y/3Y/All, estimate markers) + quarter-delta KPI; company position-value chart with ▲/▼ flow markers, hover tooltips, dashed estimate segments; company_updates journal (v4) with audited CRUD, Journal tab, demo entries | v4: company_updates |
