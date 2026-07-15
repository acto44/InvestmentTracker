"""Session 6 tests: consistency guarantee (portfolio == Σ company models),
entity scoping, pooled IRR hand case, movers across a quarter boundary,
batch generation, empty-scope honesty."""

import os
from datetime import date

import pytest

import metrics
import models
from reporting.builder import (build_company_report_model,
                               build_portfolio_report_model)
from reporting.charts import build_portfolio_chart_images
from reporting.export import (generate_all_company_reports,
                              generate_all_entity_reports,
                              generate_portfolio_report)
from reporting.render import render_portfolio_report_html


# ── The consistency guarantee ─────────────────────────────────────────────────

def test_portfolio_totals_equal_summed_company_models(demo_db):
    pm = build_portfolio_report_model()
    companies = models.get_all_companies()
    inv = real = nav = 0.0
    for c in companies:
        cm = build_company_report_model(c['id'])
        inv += cm['position']['invested']['raw']
        real += cm['position']['realized']['raw']
        nav += cm['position']['current_value']['raw']
    o = pm['overview']
    assert o['invested']['raw'] == pytest.approx(inv)
    assert o['realized']['raw'] == pytest.approx(real)
    assert o['nav']['raw'] == pytest.approx(nav)


def test_active_and_exited_counts(demo_db):
    pm = build_portfolio_report_model()
    o = pm['overview']
    # Wintex (exited) and Cloudburst (bankrupt, written off) are closed
    assert o['n_exited'] == 2
    assert o['n_active'] == 8
    exited_names = {r['name'] for r in pm['holdings']['exited']}
    assert exited_names == {'Wintex Payments', 'Cloudburst Storage'}


# ── Entity scoping ────────────────────────────────────────────────────────────

def test_entity_report_contains_only_its_holdings(demo_db):
    pm_a = build_portfolio_report_model(scope='Portfolio A')
    names = {r['name'] for r in pm_a['holdings']['active']}
    names |= {r['name'] for r in pm_a['holdings']['exited']}
    assert 'NovaTech AI' in names and 'Wintex Payments' in names
    assert 'BioVance' not in names and 'SolarGrid Capital' not in names

    pm_b = build_portfolio_report_model(scope='Portfolio B')
    pm_all = build_portfolio_report_model()
    assert (pm_a['overview']['nav']['raw'] + pm_b['overview']['nav']['raw']
            == pytest.approx(pm_all['overview']['nav']['raw']))
    assert (pm_a['overview']['invested']['raw']
            + pm_b['overview']['invested']['raw']
            == pytest.approx(pm_all['overview']['invested']['raw']))
    # entity-scoped reports skip the by-entity allocation
    assert pm_a['allocation']['by_entity'] is None
    assert pm_all['allocation']['by_entity'] is not None
    assert pm_a['meta']['prepared_for'] == 'Portfolio A'


# ── Pooled IRR ────────────────────────────────────────────────────────────────

def _independent_xirr(flows, lo=-0.99, hi=25.0):
    base = min(date.fromisoformat(d) for d, _ in flows)

    def npv(rate):
        return sum(a / (1 + rate) **
                   ((date.fromisoformat(d) - base).days / 365.25)
                   for d, a in flows)

    if npv(lo) * npv(hi) > 0:
        return None
    for _ in range(200):
        mid = (lo + hi) / 2
        if npv(lo) * npv(mid) <= 0:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


def test_pooled_irr_two_company_hand_case(temp_db):
    a = models.add_company('A')
    models.add_round(a, 'Seed', '2020-01-01', 1000, ownership_pct=100)
    models.add_valuation(a, '2024-01-01', 1800, 'internal_estimate')
    b = models.add_company('B')
    models.add_round(b, 'Seed', '2021-01-01', 1000, ownership_pct=100)
    models.add_valuation(b, '2024-01-01', 1200, 'internal_estimate')

    as_of = date(2024, 1, 1)
    pm = build_portfolio_report_model(as_of=as_of)
    expected = _independent_xirr([('2020-01-01', -1000),
                                  ('2021-01-01', -1000),
                                  ('2024-01-01', 3000)])
    assert pm['overview']['nav']['raw'] == pytest.approx(3000)
    assert pm['overview']['irr']['raw'] == pytest.approx(expected,
                                                         abs=1e-6)
    assert metrics.FOOTNOTE_POOLED_IRR in pm['appendix']['footnotes']


# ── Movers / deltas across a known quarter boundary ──────────────────────────

def test_movers_and_deltas(temp_db):
    cid = models.add_company('Mover AB')
    models.add_round(cid, 'Seed', '2025-01-10', 1000, ownership_pct=100)
    models.add_valuation(cid, '2025-02-01', 2000, 'internal_estimate')
    models.add_valuation(cid, '2025-05-01', 3000, 'internal_estimate')
    models.add_cashflow(cid, '2025-04-15', 'dividend', 50)
    other = models.add_company('Quiet AB')
    models.add_round(other, 'Seed', '2025-05-20', 400, ownership_pct=100)

    as_of = date(2025, 6, 30)
    q1_end = date(2025, 3, 31)          # known quarter boundary
    pm = build_portfolio_report_model(as_of=as_of, compare_to=q1_end)

    d = pm['overview']['deltas']
    # NAV: (3000 + 400est) - 2000 = +1400
    assert d['nav']['raw'] == pytest.approx(1400)
    assert d['invested']['raw'] == pytest.approx(400)
    assert d['realized']['raw'] == pytest.approx(50)

    mv = pm['movers']
    vc = {r['name']: r['delta']['raw'] for r in mv['valuation_changes']}
    assert vc['Mover AB'] == pytest.approx(1000)
    assert [r['name'] for r in mv['new_investments']] == ['Quiet AB']
    assert [r['name'] for r in mv['received']] == ['Mover AB']
    assert mv['received'][0]['type'] == 'dividend'


# ── Rendering + batches ───────────────────────────────────────────────────────

def test_portfolio_html_renders_with_anchors(demo_db):
    pm = build_portfolio_report_model(
        compare_to=metrics.previous_quarter_end(date.today()))
    images = build_portfolio_chart_images(pm)
    html = render_portfolio_report_html(pm, images)
    for anchor in ('overview', 'allocation', 'timeline', 'holdings',
                   'appendix'):
        assert f'name="{anchor}"' in html, anchor
    assert 'CONFIDENTIAL' in html
    assert 'Realized positions' in html
    assert 'pooled cash-flow IRR' in html
    assert 'carried at net invested capital' in html


def test_batch_all_entities(demo_db, tmp_path):
    written = generate_all_entity_reports(formats=('html',),
                                          out_dir=str(tmp_path))
    names = sorted(os.path.basename(p) for p in written)
    today = date.today().isoformat()
    assert names == [f'Entity_Portfolio_A_{today}.html',
                     f'Entity_Portfolio_B_{today}.html']


def test_batch_all_companies(demo_db, tmp_path):
    seen = []
    written = generate_all_company_reports(
        formats=('html',), out_dir=str(tmp_path),
        progress=lambda i, n, name: seen.append((i, n, name)))
    assert len(written) == 10
    assert seen[0][1] == 10 and seen[-1][0] == 10


def test_empty_scope_is_honest_not_crashy(demo_db, tmp_path):
    """Documented decision: an unknown scope yields an honest empty
    report rather than an error (batches iterate real entities only)."""
    pm = build_portfolio_report_model(scope='Ghost Entity')
    assert pm['overview']['n_active'] == 0
    html = render_portfolio_report_html(pm, {})
    assert 'No holdings recorded' in html
    out = generate_portfolio_report(scope='Ghost Entity',
                                    formats=('html',),
                                    out_dir=str(tmp_path))
    assert os.path.isfile(out[0])
