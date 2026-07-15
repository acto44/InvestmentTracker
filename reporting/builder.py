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


def _company_figures(c, rounds_all, vals_all, flows_all,
                     as_of: date) -> dict:
    """Historically correct core figures for one company at as_of.
    Shared by the company AND portfolio builders — the consistency
    guarantee between them holds by construction (and by test)."""
    flows = [f for f in flows_all if _le(f['date'], as_of)]
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

    closed = metrics.is_closed(c.get('notes')) and unrealized == 0
    return {'invested': invested, 'realized': realized,
            'unrealized': unrealized, 'is_estimate': is_estimate,
            'moic': moic, 'dpi': dpi, 'rvpi': rvpi, 'tvpi': tvpi,
            'irr': irr, 'signed_flows': signed, 'closed': closed}


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

    fig = _company_figures(c, rounds_all, vals_all, flows_all, as_of)
    invested, realized = fig['invested'], fig['realized']
    unrealized, is_estimate = fig['unrealized'], fig['is_estimate']
    moic, dpi, rvpi, tvpi = fig['moic'], fig['dpi'], fig['rvpi'], fig['tvpi']
    irr = fig['irr']

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


# ── Portfolio / entity report model ──────────────────────────────────────────

def build_portfolio_report_model(scope: str | None = None,
                                 as_of: date | None = None,
                                 compare_to: date | None = None) -> dict:
    """scope=None → whole portfolio; scope='<entity>' → one family
    member's holdings. compare_to (optional, typically the previous
    quarter-end) adds deltas and the Movers section. An unknown/empty
    scope yields an honest empty report — batches iterate real entities,
    so that only happens for stale scope strings."""
    as_of = as_of or date.today()
    sym = models.get_setting('currency', 'TKR')
    data = models.timeseries_inputs(entity=scope)

    per_company = []
    for c, rounds, vals, flows in data:
        fig = _company_figures(c, rounds, vals, flows, as_of)
        fig['company'] = c
        per_company.append(fig)

    invested = sum(f['invested'] for f in per_company)
    realized = sum(f['realized'] for f in per_company)
    nav = sum(f['unrealized'] for f in per_company)
    n_estimates = sum(1 for f in per_company
                      if f['is_estimate'] and not f['closed'])
    active = [f for f in per_company if not f['closed'] and
              (f['invested'] > 0 or f['unrealized'] > 0)]
    exited = [f for f in per_company if f['closed'] and f['invested'] > 0]

    moic = dpi = rvpi = tvpi = None
    if invested > 0:
        dpi = realized / invested
        rvpi = nav / invested
        tvpi = dpi + rvpi
        moic = (realized + nav) / invested

    # pooled IRR: every signed ledger flow in scope + ONE terminal NAV
    # flow (the per-company terminal values are excluded and replaced)
    pooled = []
    for f in per_company:
        pooled.extend(x for x in f['signed_flows']
                      if not (x[0] == as_of.isoformat() and x[1] > 0
                              and x[1] == f['unrealized']))
    if nav > 0:
        pooled.append((as_of.isoformat(), nav))
    pooled_irr = metrics.irr(pooled, as_of) if len(pooled) >= 2 else None

    # deltas vs compare_to
    deltas = None
    if compare_to:
        prev_inv = sum(metrics.invested_to_date(fl, compare_to)
                       for _, _, _, fl in data)
        prev_real = sum(metrics.realized_to_date(fl, compare_to)
                        for _, _, _, fl in data)
        prev_nav = sum(metrics.position_value_at(c, r, v, fl,
                                                 compare_to)['value']
                       for c, r, v, fl in data)
        deltas = {
            'compare_to': compare_to.isoformat(),
            'nav': {'raw': nav - prev_nav,
                    'fmt': F.fmt_signed_money(nav - prev_nav, sym)},
            'nav_pct': {'raw': ((nav - prev_nav) / prev_nav * 100
                                if prev_nav else None),
                        'fmt': F.fmt_pct((nav - prev_nav) / prev_nav * 100
                                         if prev_nav else None)},
            'invested': {'raw': invested - prev_inv,
                         'fmt': F.fmt_signed_money(invested - prev_inv,
                                                   sym)},
            'realized': {'raw': realized - prev_real,
                         'fmt': F.fmt_signed_money(realized - prev_real,
                                                   sym)},
        }

    # allocation by NAV (closed positions carry no NAV)
    def _alloc(key_fn):
        buckets: dict = {}
        for f in per_company:
            if f['unrealized'] <= 0:
                continue
            k = key_fn(f['company']) or 'Unspecified'
            buckets[k] = buckets.get(k, 0.0) + f['unrealized']
        rows = [{'label': k, 'value': _money(v, sym),
                 'pct': {'raw': v / nav * 100 if nav else None,
                         'fmt': F.fmt_pct(v / nav * 100 if nav else None,
                                          signed=False)}}
                for k, v in sorted(buckets.items(),
                                   key=lambda kv: kv[1], reverse=True)]
        return rows

    by_sector = _alloc(lambda c: (c.get('sector') or '').strip())
    by_entity = None if scope else _alloc(
        lambda c: (c.get('entity') or '').strip())

    # NAV over time for the scope
    first = metrics.first_flow_date(data)
    series = []
    if first and first <= as_of:
        grid = metrics.month_end_grid(first, as_of)
        series = metrics.nav_series(data, grid)

    # holdings tables
    def _holding_row(f):
        c = f['company']
        return {
            'name': c['name'],
            'entity': c.get('entity') or '',
            'sector': c.get('sector') or '',
            'invested': _money(f['invested'], sym),
            'realized': _money(f['realized'], sym),
            'current': _money(f['unrealized'], sym),
            'is_estimate': f['is_estimate'],
            'moic': {'raw': f['moic'], 'fmt': F.fmt_multiple(f['moic'])},
            'irr': {'raw': f['irr'], 'fmt': F.fmt_irr(f['irr'])},
            'pct_nav': {'raw': (f['unrealized'] / nav * 100
                                if nav else None),
                        'fmt': F.fmt_pct(f['unrealized'] / nav * 100
                                         if nav else None, signed=False)},
        }

    active_rows = [_holding_row(f) for f in
                   sorted(active, key=lambda x: x['unrealized'],
                          reverse=True)]
    exited_rows = [{
        'name': f['company']['name'],
        'entity': f['company'].get('entity') or '',
        'invested': _money(f['invested'], sym),
        'realized': _money(f['realized'], sym),
        'multiple': {'raw': f['dpi'], 'fmt': F.fmt_multiple(f['dpi'])},
        'irr': {'raw': f['irr'], 'fmt': F.fmt_irr(f['irr'])},
    } for f in sorted(exited, key=lambda x: x['realized'], reverse=True)]

    # movers (only with compare_to)
    movers = None
    if compare_to:
        val_changes = []
        for c, rounds, vals, flows in data:
            now = metrics.position_value_at(c, rounds, vals, flows, as_of)
            then = metrics.position_value_at(c, rounds, vals, flows,
                                             compare_to)
            d = now['value'] - then['value']
            if abs(d) > 1e-9:
                val_changes.append({
                    'name': c['name'],
                    'from': _money(then['value'], sym),
                    'to': _money(now['value'], sym),
                    'delta': {'raw': d, 'fmt': F.fmt_signed_money(d, sym)},
                    'is_estimate': now['is_estimate'] or
                                   then['is_estimate'],
                })
        val_changes.sort(key=lambda r: abs(r['delta']['raw']),
                         reverse=True)

        def _period_flows(types):
            rows = []
            for c, _, _, flows in data:
                for f in flows:
                    d = metrics._parse_date(f.get('date'))
                    if (d and compare_to < d <= as_of
                            and f['type'] in types):
                        rows.append({'date': f['date'],
                                     'name': c['name'],
                                     'type': f['type'].replace('_', ' '),
                                     'amount': _money(f['amount'], sym),
                                     'note': f.get('note') or ''})
            rows.sort(key=lambda r: r['date'])
            return rows

        movers = {
            'valuation_changes': val_changes[:10],
            'new_investments': _period_flows(metrics.OUTFLOW_TYPES),
            'received': _period_flows(metrics.INFLOW_TYPES),
        }

    footnotes = [
        metrics.VALUATION_MEANING_FOOTNOTE,
        metrics.FOOTNOTE_INVESTED,
        metrics.FOOTNOTE_REALIZED,
        metrics.FOOTNOTE_MOIC,
        metrics.FOOTNOTE_DPI,
        metrics.FOOTNOTE_RVPI,
        metrics.FOOTNOTE_TVPI,
        metrics.FOOTNOTE_POOLED_IRR,
        metrics.FOOTNOTE_ALLOCATION,
        metrics.FOOTNOTE_CLOSED,
    ]
    aggregation_notes = [f'All figures as of {as_of.isoformat()}.']
    if n_estimates:
        aggregation_notes.append(
            f'{n_estimates} position{"s" if n_estimates != 1 else ""} '
            'without a recorded valuation '
            f'{"are" if n_estimates != 1 else "is"} carried at net '
            'invested capital (estimate).')
        footnotes.append(metrics.FOOTNOTE_ESTIMATE)

    title = (f'Entity Report — {scope}' if scope
             else 'Portfolio Report')
    return {
        'meta': {
            'title': title,
            'prepared_for': scope or '',
            'scope': scope,
            'as_of': as_of.isoformat(),
            'compare_to': compare_to.isoformat() if compare_to else None,
            'report_date': date.today().isoformat(),
            'app': f'{APP_NAME} {APP_VERSION}',
            'currency': sym,
        },
        'overview': {
            'nav': _money(nav, sym),
            'invested': _money(invested, sym),
            'realized': _money(realized, sym),
            'moic': {'raw': moic, 'fmt': F.fmt_multiple(moic)},
            'dpi': {'raw': dpi, 'fmt': F.fmt_multiple(dpi)},
            'tvpi': {'raw': tvpi, 'fmt': F.fmt_multiple(tvpi)},
            'irr': {'raw': pooled_irr, 'fmt': F.fmt_irr(pooled_irr)},
            'n_active': len(active),
            'n_exited': len(exited),
            'n_estimates': n_estimates,
            'deltas': deltas,
        },
        'allocation': {'by_sector': by_sector, 'by_entity': by_entity,
                       'sector_chart': 'chart-alloc-sector',
                       'entity_chart': 'chart-alloc-entity'},
        'nav_chart': 'chart-nav',
        'series': series,
        'holdings': {'active': active_rows, 'exited': exited_rows},
        'movers': movers,
        'appendix': {
            'footnotes': footnotes,
            'aggregation_notes': aggregation_notes,
            'currency_note': (f'All figures in {sym}; no FX conversion '
                              'applied.'),
            'estimate_note': (metrics.FOOTNOTE_ESTIMATE if n_estimates
                              else None),
        },
    }
