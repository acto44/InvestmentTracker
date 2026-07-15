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
formatting.py            shared display formatters (MONEY invariant) +
                         sanitize_filename
version.py               APP_NAME / APP_VERSION (quoted in report headers)
reporting/               report pipeline, three strict layers:
                         builder.py (pure as-of-correct model, raw+fmt),
                         charts.py (matplotlib Agg → PNG at 2×, print-light
                         palette, generic for session 6),
                         render.py (model → QTextDocument-safe HTML; see
                         REPORT_STYLE_NOTES; named image placeholders),
                         export.py (write_html inlines base64; write_pdf
                         registers QTextDocument resources + QPrinter A4).
                         Named `reporting/` NOT `reports/` — reports/ is
                         the gitignored OUTPUT dir for generated files and
                         the package must never collide with it.
                         Templates are Python string constants: nothing new
                         to bundle for the .exe (if template FILES are ever
                         added they must load via a resource_path() helper
                         and be listed in the spec's datas).
ai/                      AI plumbing (session 7), NO features yet — rails
                         session 8 builds on:
                         __init__.py (is_ai_enabled() master gate +
                         get_provider factory), base.py (AIProvider
                         protocol + typed AIError exceptions — nothing
                         outside ai/ touches subprocess/HTTP),
                         claude_cli.py (Claude Code CLI: PATH or VS Code
                         extension; prompt via STDIN never argv; --tools ""
                         --no-session-persistence; NOT --bare, it breaks
                         OAuth), openai_api.py (urllib POST, no SDK; key
                         scrubbed from all errors), contract.py (task
                         contracts; validate_response clamps + escapes —
                         the ONLY door to the UI), consent.py (per-action
                         modal, exact payload, Cancel default),
                         service.py (send_request: gate → consent →
                         QThread → validate → ai_activity log; the ONE
                         pipeline features call), keystore.py (DPAPI
                         at-rest key encryption, obfuscation fallback
                         with UI warning; key never in the DB),
                         context.py (session 8: whitelisted context
                         packs from the report models — documents/paths
                         never included — + in-memory Pseudonymizer)
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
ui/dialogs.py            add/edit company, round & valuation dialogs;
                         tabbed SettingsDialog (General / AI)
ui/ai_settings.py        Settings → AI page: master switch (default OFF),
                         provider pick + live status, DPAPI key entry,
                         Test connection through the FULL pipeline
ui/ai_card.py            AICard — THE labeling primitive: every AI-visible
                         thing renders inside it (provenance header +
                         "verify before decisions" footer)
ui/ai_company.py         session 8: generate_for_company() — the ONE
                         generation flow (model → pack → consent →
                         validate → persist) shared by the Overview
                         AI block (cards, regenerate/remove, typed
                         errors + Retry) and the report dialog's
                         generate-first offer
ui/ai_qa.py              session 8: Ask-AI dialog (portfolio/company
                         scope, per-question consent, session-only
                         history — never persisted)
ui/history_dialog.py     read-only audit-trail view (global + per company)
ui/report_dialog.py      per-company report dialog (quick path from the
                         tree/detail panel); folder rules shared with the
                         Report Center: default Documents/<AppName>
                         Reports, QSettings, repo-dir warning
ui/report_center.py      Report Center (toolbar): Company / Portfolio /
                         Entity + batch all-companies/all-entities with
                         progress + cancel; same reporting.export code
                         path as everything else
ui/compare_dialog.py     side-by-side company comparison
ui/import_dialog.py, ui/family_import_dialog.py, ui/family_edit_dialog.py
                         Excel import + entity management
tests/                   pytest suite: conftest (temp_db/demo_db + autouse
                         no_network ban — the suite CANNOT call a real
                         API), repo hygiene guard, metrics, fixtures,
                         UI smoke, AI contract/provider/flow tests
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
- **AI SAFETY MODEL** (sessions 7–8): opt-in and consent are the
  product, not friction.
  - `ai.is_ai_enabled()` is the SINGLE gate, default OFF; while off, no
    AI affordance exists anywhere outside Settings → AI — no Overview
    block, no Ask-AI action, no report checkboxes (all tested).
  - Every send goes through `ai.service.send_request` — nothing else may
    call a provider. It shows the consent dialog with the EXACT payload
    before anything leaves the machine; there is no "always allow".
    Zero AI calls happen at app start, during report export, or in any
    background path (call-counter tested).
  - The AI sees ONLY report-model data: payloads are context packs
    (ai/context.py) built from the session-5/6 report models by explicit
    field picks — what the AI reads is exactly what a report shows.
  - NEVER leaves the machine: the raw database; document contents AND
    document names; file paths; API keys; real company/entity names
    when pseudonymization is on (Settings → AI toggle, default off,
    state always shown in the consent dialog; the alias mapping lives
    in memory for one round-trip and is never persisted or sent).
  - The prompt (the data-bearing part) goes to the Claude CLI via STDIN,
    never argv; `system` is reserved for fixed instruction strings from
    ai/contract.py — user/database content never goes in `system`.
  - Fixed contracts (ai/contract.py): 'ping', 'narrative' (sections +
    caveats), 'risk_flags' (severity/title/rationale/based_on, empty
    list valid), 'qa' (answer paragraphs + used_fields + follow-ups).
    Nothing renders un-validated: every reply passes
    `contract.validate_response` (parse, type-check, enum-check, clamp
    lengths/list sizes, HTML-escape, drop unknown fields) and every
    AI-visible thing renders inside `ui.ai_card.AICard` or a report
    section with a provenance line. On validation failure the UI says
    so with the structured reason and offers Retry — raw output is
    never shown.
  - Persisted vs session-only: narratives and risk flags live in
    ai_outputs (v6, one CURRENT row per company+task, validated JSON
    with provenance) so reports REUSE them — export never re-calls an
    API, and if nothing is stored the report dialog offers to generate
    first (full consent flow). Q&A is session-only: history dies with
    the panel, the schema itself refuses task='qa', scan-tested.
    ai_activity (v5) stores provider/model/task/payload SIZE/outcome —
    never bodies, never keys (scan-tested). The OpenAI key lives
    DPAPI-encrypted in a user-profile file, never in the database and
    never in logs or exception texts.
  - The test suite is physically unable to reach a real API (autouse
    no_network fixture); providers are tested against fakes.
  - Manual checks each release (CI has no accounts) — last run
    2026-07-15 on the owner's machine:
    1. Settings → AI → Test connection via Claude CLI end-to-end
       (consent → CLI → validated → AICard shows "pong"). PASSED.
    2. Deliberately wrong OpenAI key → typed auth error ("OpenAI
       rejected the API key (HTTP 401)…"), no stack trace, no key
       echoed. PASSED.
    3. Narrative + risk flags for a demo company via Claude CLI,
       both included in an exported PDF with provider/model/date
       provenance lines; export provably made zero AI calls. PASSED.
    4. Portfolio Q&A question answered with figures grounded in the
       payload and used_fields listed. PASSED (via Claude CLI;
       the OpenAI leg awaits the owner's API key — the provider is
       contract-tested and its 401 path was proven in check 2).
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
| 2026-07-14 | 5 | Company reports: reporting/ package (builder → render → export; named reporting/ because reports/ is the gitignored output dir), as-of-correct pure model with raw+fmt figures via new shared formatting.py, print-light offscreen charts (matplotlib Agg, 2×), QTextDocument-safe HTML (REPORT_STYLE_NOTES) with named image placeholders, portable single-file HTML (base64) + A4 PDF (QTextDocument resources + QPrinter), footnote appendix imports metrics.py strings, CONFIDENTIAL header/footer, AI-narrative anchor slot for session 8, ReportDialog (safe default folder in Documents, QSettings, repo-folder warning) reachable from toolbar/tree context menu/detail panel; filenames sanitized (Å/ö preserved) | none |
| 2026-07-14 | 6 | Portfolio & entity reports + Report Center: _company_figures extracted so both builders share one math path (consistency portfolio == Σ company models enforced by test), build_portfolio_report_model(scope, as_of, compare_to) with pooled cash-flow IRR (FOOTNOTE_POOLED_IRR — not the average of company IRRs), NAV/sector/entity allocation (by NAV, FOOTNOTE_ALLOCATION), NAV-over-time chart, holdings + Realized positions tables, Movers (valuation changes/new investments/received) when compare_to set, aggregation notes ("N positions carried at net invested capital"); entity report = same pipeline scoped + Prepared-for header, zero forked paths; unknown scope → honest empty report (documented); donut + 3-series NAV chart helpers in charts.py; Report Center dialog (types, batch all-companies/all-entities with progress+cancel, QSettings) replaces the toolbar action — tree/detail quick dialog unchanged and on the same export functions | none |
| 2026-07-15 | 7 | Safe AI plumbing, no user-visible features yet (rails for session 8): ai/ package — AIProvider protocol + typed errors, Claude via local Claude Code CLI (flags verified against 2.1.210: -p --output-format json --tools "" --no-session-persistence; prompt via STDIN never argv; neutral cwd; --bare avoided, kills OAuth; PATH + VS Code-extension discovery), OpenAI via urllib (no SDK — stdlib-first; default gpt-4.1-mini checked against docs 2026-07-15; max_completion_tokens; key scrubbed from every error), task-contract registry with validate_response (fence-strip, parse, type-check, clamp, HTML-escape, structured rejection), per-action ConsentDialog (exact payload, Cancel default, no "always allow"), service.send_request = the one pipeline (gate → consent → QThread with relay back to caller thread → validate → log), DPAPI keystore (per-user, obfuscation fallback + visible warning); Settings tabbed General/AI (master switch default OFF, live provider status, Test connection through the full real pipeline into an AICard); AICard labeling primitive; autouse no_network test ban; AI invariant + manual account checks recorded above (both passed on owner machine 2026-07-15). 45 new tests (147 total) | v5: ai_activity |
| 2026-07-15 | 8 | The three AI capabilities on the session-7 rails: contract system gains enum choices + nested object_list validation; contracts 'narrative' (sections position_narrative/quarter_review + caveats), 'risk_flags' (severity/title/rationale/based_on, empty valid → "No flags raised."), 'qa' (answer/used_fields/follow-ups) with invent-nothing system prompts; ai/context.py whitelisted packs from the report models (documents and their NAMES excluded from every payload — tested against a company WITH documents; packs = the exact consent-preview bytes) + Pseudonymizer (Company A/Entity 1, in-memory mapping, restore on answers, state shown in consent; nothing alias-related persisted); v6 ai_outputs (one CURRENT validated output per company+task with provenance; qa refused by schema CHECK); generate_for_company() = one generation flow shared by the Overview AI block (AICards, regenerate/remove, typed errors + Retry) and the report dialog's generate-first offer; reports render ONLY persisted outputs as 'AI narrative'/'AI risk flags' sections with provenance lines (export provably zero AI calls, call-counter tested; boot too); Ask-AI toolbar action (exists only while enabled) → Q&A dialog with scope picker, per-question consent, session-only history (scan-tested absent from DB); severity chips on status-dot colors. Manual checklist 3–4 run on owner machine via real Claude CLI (PDF with labeled narrative+flags; grounded Q&A answer). 19 new tests (166 total) | v6: ai_outputs |
