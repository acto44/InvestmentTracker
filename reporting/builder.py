"""Report model builder — pure Python, no Qt, fully unit-testable.

build_company_report_model(company_id, as_of=None) returns a plain dict
tree. Every figure appears raw AND pre-formatted (via formatting.py).
An earlier as_of produces historically correct numbers through the
session-4 series functions (position_value_at etc.) — never through the
"current" convenience values on the company dict.
"""

from __future__ import annotations

from datetime import date

import formatting as F
import metrics
import models
from version import APP_NAME, APP_VERSION

SOURCE_LABELS = {
    'internal_estimate': 'Internal estimate',
    'external_valuation': 'External valuation',
    'offer': 'Offer received',
    'exit': 'Exit / sale',
    'round_post_money': 'Round post-money',
    'legacy_migration': 'Carried over (legacy)',
}

FLOW_LABELS = {
    'investment': 'Investment', 'follow_on': 'Follow-on',
    'exit_proceeds': 'Exit proceeds', 'partial_sale': 'Partial sale',
    'dividend': 'Dividend', 'distribution': 'Distribution',
    'fee': 'Fee', 'other_in': 'Other (in)', 'other_out': 'Other (out)',
}


def _le(dstr, as_of: date) -> bool:
    d = metrics._parse_date(dstr)
    return d is not None and d <= as_of


def _money(v, sym):
    return {'raw': v, 'fmt': F.fmt_money(v, sym)}


def build_company_report_model(company_id, as_of: date | None = None) -> dict:
    as_of = as_of or date.today()
    sym = models.get_setting('currency', 'TKR')

    c = models.get_company(company_id)
    if not c:
        raise ValueError(f'no company with id {company_id}')
    rounds_all = models.get_rounds(company_id)
    vals_all = models.get_valuations(company_id)      # newest first
    flows_all = models.get_cashflows(company_id)      # date ascending

    rounds = [r for r in rounds_all if not r.get('date') or _le(r['date'], as_of)]
    vals = [v for v in vals_all if _le(v['as_of_date'], as_of)]
    flows = [f for f in flows_all if _le(f['date'], as_of)]

    # ── position figures, historically correct at as_of ──────────────────
    invested = metrics.invested_to_date(flows_all, as_of)
    realized = metrics.realized_to_date(flows_all, as_of)
    pv = metrics.position_value_at(c, rounds_all, vals_all, flows_all, as_of)
    unrealized = pv['value']
    is_estimate = pv['is_estimate']

    moic = dpi = rvpi = tvpi = None
    if invested > 0:
        dpi = realized / invested
        rvpi = unrealized / invested
        tvpi = dpi + rvpi
        moic = (realized + unrealized) / invested

    signed = [(f['date'] or as_of.isoformat(),
               metrics.signed_amount(f['type'], f['amount'])) for f in flows]
    if unrealized > 0:
        signed.append((as_of.isoformat(), unrealized))
    irr = metrics.irr(signed, as_of) if len(signed) >= 2 else None

    latest_val = vals[0] if vals else None
    val_as_of = latest_val['as_of_date'] if latest_val else None
    val_source = (SOURCE_LABELS.get(latest_val['source'], latest_val['source'])
                  if latest_val else None)

    # ── valuation table (newest first) with Δ% vs previous ───────────────
    val_rows = []
    for i, v in enumerate(vals):
        prev = vals[i + 1] if i + 1 < len(vals) else None
        delta = ((v['value'] - prev['value']) / prev['value'] * 100
                 if prev and prev['value'] else None)
        val_rows.append({
            'date': v['as_of_date'],
            'value': _money(v['value'], sym),
            'source': SOURCE_LABELS.get(v['source'], v['source']),
            'note': v.get('note') or '',
            'delta_pct': {'raw': delta, 'fmt': F.fmt_pct(delta)},
        })

    # ── rounds table ──────────────────────────────────────────────────────
    round_rows = []
    for r in sorted(rounds, key=lambda x: x.get('date') or ''):
        round_rows.append({
            'name': r.get('round_name') or '',
            'date': r.get('date') or '',
            'amount': _money(r.get('amount_invested'), sym),
            'pre_money': _money(r.get('pre_money_valuation'), sym),
            'post_money': _money(r.get('post_money_valuation'), sym),
            'shares': {'raw': r.get('shares_received'),
                       'fmt': F.fmt_shares(r.get('shares_received'))},
            'pps': {'raw': r.get('price_per_share'),
                    'fmt': (F.fmt_money(r.get('price_per_share'), sym, dec=2)
                            if r.get('price_per_share') else 'n/a')},
            'ownership_pct': {'raw': r.get('ownership_pct'),
                              'fmt': F.fmt_pct(r.get('ownership_pct'),
                                               signed=False)},
        })

    # ── ledger with running totals ────────────────────────────────────────
    ledger_rows = []
    run_inv = run_real = 0.0
    for f in flows:
        s = metrics.signed_amount(f['type'], f['amount'])
        if s < 0:
            run_inv += -s
        else:
            run_real += s
        note = f.get('note') or ''
        if f.get('shares_delta'):
            note = (f"{f['shares_delta']:+,.0f} shares · {note}").strip(' ·')
        ledger_rows.append({
            'date': f.get('date') or '—',
            'type': FLOW_LABELS.get(f['type'], f['type']),
            'signed': {'raw': s, 'fmt': F.fmt_signed_money(s, sym)},
            'run_invested': _money(run_inv, sym),
            'run_realized': _money(run_real, sym),
            'note': note,
        })

    # ── ownership & shares ────────────────────────────────────────────────
    own = metrics.ownership_at(rounds_all, flows_all, as_of)
    shares_now = (sum((r.get('shares_received') or 0) for r in rounds)
                  + sum((f.get('shares_delta') or 0) for f in flows))
    basis = 'no total-shares figure recorded'
    for r in sorted(rounds, key=lambda x: x.get('date') or '', reverse=True):
        if r.get('total_shares_outstanding'):
            basis = (f"total shares outstanding "
                     f"{r['total_shares_outstanding']:,.0f} as reported in "
                     f"the {r.get('round_name') or '?'} round "
                     f"({r.get('date') or 'undated'})")
            break

    # ── thesis + journal (latest 4 at as_of) ──────────────────────────────
    journal = [u for u in models.get_company_updates(company_id)
               if _le(u['date'], as_of)][:4]

    # ── documents (names + dates only — never contents or full paths) ─────
    docs = [{'filename': d['original_filename'],
             'doc_type': d.get('doc_type') or '',
             'added': d.get('added_date') or ''}
            for d in models.get_documents(company_id=company_id)
            if not d.get('added_date') or _le(d['added_date'], as_of)]

    # ── chart series (single-company scope) ───────────────────────────────
    data = [(c, rounds_all, vals_all, flows_all)]
    first = metrics.first_flow_date(data)
    series = []
    if first and first <= as_of:
        grid = metrics.month_end_grid(first, as_of)
        series = metrics.nav_series(data, grid)
    markers = [{'date': f['date'],
                'signed': metrics.signed_amount(f['type'], f['amount']),
                'label': FLOW_LABELS.get(f['type'], f['type']),
                'note': f.get('note') or ''}
               for f in flows if f.get('date')]

    estimate_any = is_estimate or any(p['is_estimate'] for p in series)

    # ── appendix: footnotes come from metrics.py, never restated ──────────
    footnotes = [
        metrics.VALUATION_MEANING_FOOTNOTE,
        metrics.FOOTNOTE_INVESTED,
        metrics.FOOTNOTE_REALIZED,
        metrics.FOOTNOTE_MOIC,
        metrics.FOOTNOTE_DPI,
        metrics.FOOTNOTE_RVPI,
        metrics.FOOTNOTE_TVPI,
        metrics.FOOTNOTE_IRR.format(as_of=val_as_of or as_of.isoformat()),
    ]
    if latest_val:
        footnotes.append(metrics.UNREALIZED_VALUE_FOOTNOTE.format(
            date=latest_val['as_of_date'], source=val_source))
    closed_now = metrics.is_closed(c.get('notes')) and any(
        f['type'] in ('exit_proceeds', 'partial_sale') for f in flows)
    if closed_now or (metrics.is_closed(c.get('notes')) and unrealized == 0):
        footnotes.append(metrics.FOOTNOTE_CLOSED)
    if any(f.get('shares_delta') for f in flows):
        footnotes.append(metrics.FOOTNOTE_OWNERSHIP_AFTER_SALE)
    if estimate_any:
        footnotes.append(metrics.FOOTNOTE_ESTIMATE)

    return {
        'meta': {
            'company_name': c['name'],
            'sector': c.get('sector') or '',
            'country': c.get('country') or '',
            'entity': c.get('entity') or '',
            'description': c.get('description') or '',
            'as_of': as_of.isoformat(),
            'report_date': date.today().isoformat(),
            'app': f'{APP_NAME} {APP_VERSION}',
            'currency': sym,
        },
        'position': {
            'invested': _money(invested, sym),
            'realized': _money(realized, sym),
            'current_value': _money(unrealized, sym),
            'is_estimate': is_estimate,
            'val_as_of': val_as_of,
            'val_source': val_source,
            'moic': {'raw': moic, 'fmt': F.fmt_multiple(moic)},
            'dpi': {'raw': dpi, 'fmt': F.fmt_multiple(dpi)},
            'rvpi': {'raw': rvpi, 'fmt': F.fmt_multiple(rvpi)},
            'tvpi': {'raw': tvpi, 'fmt': F.fmt_multiple(tvpi)},
            'irr': {'raw': irr, 'fmt': F.fmt_irr(irr)},
        },
        'valuations': {'rows': val_rows, 'chart': 'chart-valuation'},
        'rounds': {'rows': round_rows},
        'ledger': {'rows': ledger_rows,
                   'invested_total': _money(invested, sym),
                   'realized_total': _money(realized, sym)},
        'ownership': {
            'shares_held': {'raw': shares_now,
                            'fmt': F.fmt_shares(shares_now)},
            'ownership_pct': {'raw': own,
                              'fmt': F.fmt_pct(own, signed=False)},
            'basis': basis,
        },
        'thesis': {'text': (c.get('thesis') or '').strip(),
                   'journal': journal,
                   'ai_slot': 'ai-narrative'},
        'documents': {'rows': docs},
        'series': series,
        'markers': markers,
        'appendix': {
            'footnotes': footnotes,
            'currency_note': (f'All figures in {sym}; no FX conversion '
                              'applied.'),
            'estimate_note': (metrics.FOOTNOTE_ESTIMATE if estimate_any
                              else None),
        },
    }
