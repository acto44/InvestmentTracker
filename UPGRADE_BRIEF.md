# FamilyInvestmentTracker — upgrade brief

Purpose of this document: give a fresh Claude session everything it needs to
write a numbered series of **professional upgrade prompts** that take this
program from "working demo" to software a family office or small investment
firm could genuinely run on. Contains NO personal data — safe to paste
anywhere.

## What the program is
A Windows desktop app (Python 3 + PyQt6, dark fintech theme) that tracks a
family's private investments: unlisted companies, the funding rounds invested
in, ownership stakes, valuations and attached documents. Local-first: one
SQLite file next to the app, no server, no accounts. Also ships as a
single-file .exe (PyInstaller) for family members without Python.

## Architecture (file by file)
```
main.py                 entry point, app + main window bootstrap
models.py               SQLite layer: schema, migrations, CRUD
metrics.py              financial math: ROI, MOIC, annualised IRR
                        (Newton + bisection), company/portfolio aggregates;
                        has its own unit tests
excel_io.py             import/export of holdings via Excel
seed_demo_data.py       fictional demo portfolio ("ViFi Fund") for the
                        public repo — never real data
ui/styles.py            design system: palette + QSS (accent #3B82F6,
                        bg #0B1220, cards #141D2E)
ui/main_window.py       toolbar, shortcuts (Ctrl+N/K/R), QSettings
                        persistence of geometry/splitters/tabs
ui/tree_panel.py        left tree: entities → companies, filter box,
                        status dots
ui/dashboard.py         portfolio dashboard: KPI cards, sector donut,
                        charts
ui/detail_panel.py      per-company tabs: Overview / Rounds / Documents
ui/quick_jump.py        Ctrl+K fuzzy jump to any company
ui/dialogs.py           add/edit company & round dialogs
ui/compare_dialog.py    side-by-side company comparison
ui/import_dialog.py,
ui/family_import_dialog.py,
ui/family_edit_dialog.py   Excel import + family/entity management
```

## Data model (SQLite)
- **companies**: name, entity (which family member/legal entity holds it),
  sector, country, first_investment_date, current_valuation (ONE number,
  no history), notes, website, description, thesis, investment_type
- **funding_rounds**: per company — round_name, date, amount_invested,
  pre/post-money valuation, shares_received, price_per_share,
  total_shares_outstanding, ownership_pct, status
- **documents**: files attached to a company/round, copied into a
  documents/ folder (no content extraction — just stored)
- **settings**: key/value (currency etc.)

## What it can already do
Portfolio dashboard with KPIs and charts; per-company detail view; ROI,
MOIC and IRR from dated cash flows; entities so each family member's
holdings are grouped; Excel import/export; document attachment; compare
two companies; fuzzy search; polished dark UI; one-file .exe distribution.

## Why it still reads as a demo (honest gaps)
1. **No report output at all** — nothing can be printed, exported or sent
   to an accountant, board or family meeting.
2. **current_valuation is a single mutable number** — no valuation history,
   no NAV over time, no audit trail of who changed what and when.
3. **No cash-flow ledger beyond investments** — exits, dividends,
   distributions, partial sales and follow-ons have no first-class home,
   so IRR misses real flows.
4. **No AI anywhere** — no analysis, no narrative, no document reading.
5. Documents are dead storage — the app never reads what's inside them.
6. Single currency assumption; no FX.
7. No periodic snapshots/quarterly view, so "how is the company going"
   cannot be answered over time.

## The owner's goals (what the prompts must build toward)
- **Individual company reports**: a professional, self-contained document
  per company — position summary, round history, valuation development,
  ROI/MOIC/IRR, thesis vs. status narrative — good enough to hand to an
  accountant or discuss at a family meeting. Portfolio-level report too.
- **AI availability — BOTH Claude and ChatGPT**: the user plugs in their
  own account (Claude Code CLI is installed on this machine; OpenAI via
  the user's own key). AI writes narrative report sections, flags risks,
  and answers questions about the portfolio. Proven pattern to copy from
  the owner's other project (FlowLens): AI runs sandboxed — fixed output
  contract, validated/clamped before display, strictly opt-in, clearly
  labeled when data leaves the machine.
- **Firm-grade professionalism**: valuation history + audit trail, a real
  cash-flow ledger (buys/sells/dividends/exits), quarterly snapshots,
  honest metric footnotes (IRR assumptions etc.), data backup/versioning.

## Hard invariants for every prompt
- Privacy is sacred: the real database, documents and Excel files contain
  a family's private finances. They are gitignored and must NEVER enter
  the public repo, screenshots, tests or fixtures. All fixtures use the
  fictional demo data. AI features are opt-in per action, use only the
  user's own accounts, and never silently transmit data.
- PyQt6 desktop, SQLite, Windows-first; the one-file .exe build must keep
  working. Prefer stdlib; each new dependency needs justification.
- Schema changes only via the existing migration pattern in models.py.
- Financial numbers must be trustworthy: every metric shown states its
  assumptions; no invented precision; tests for all financial math.
- Keep the existing dark design system (ui/styles.py) and interaction
  patterns; professional ≠ redesign.

## What to produce
A numbered series of 6–8 self-contained upgrade prompts, one per session,
each with: GOAL, CONTEXT (what already exists — do not rebuild it),
REQUIREMENTS, and ACCEPTANCE criteria. Order them so foundations come
first (start with a CLAUDE.md that locks in the invariants above, then the
data-model upgrades, then reports, then AI). Every prompt must demand
tests and end with the full suite green. Begin each prompt with:
"Read CLAUDE.md first and follow its invariants throughout. Don't forget
something might already exist in the code."
