"""Session 3 tests: sign convention, round↔flow write-through, backfill,
multiple identities (MOIC = TVPI = DPI + RVPI), XIRR against an
independent solver, oversell guard, ownership after partial sales."""

from datetime import date

import pytest

import metrics
import models


# ── Sign convention: table-driven over ALL types ─────────────────────────────

@pytest.mark.parametrize('flow_type,expected_sign', [
    ('investment', -1), ('follow_on', -1), ('fee', -1), ('other_out', -1),
    ('exit_proceeds', 1), ('partial_sale', 1), ('dividend', 1),
    ('distribution', 1), ('other_in', 1),
])
def test_signed_amount(flow_type, expected_sign):
    assert metrics.signed_amount(flow_type, 100) == 100 * expected_sign


def test_signed_amount_rejects_unknown():
    with pytest.raises(ValueError):
        metrics.signed_amount('bribe', 100)


def test_type_sets_partition_the_storage_whitelist():
    both = metrics.OUTFLOW_TYPES | metrics.INFLOW_TYPES
    assert both == set(models.CASHFLOW_TYPES)
    assert not (metrics.OUTFLOW_TYPES & metrics.INFLOW_TYPES)


# ── Write-through: rounds own their investment flow ───────────────────────────

def test_round_creates_exactly_one_linked_flow(temp_db):
    cid = models.add_company('C')
    rid = models.add_round(cid, 'Seed', '2024-01-01', 500)
    flows = models.get_cashflows(cid)
    assert len(flows) == 1
    f = flows[0]
    assert (f['type'], f['amount'], f['date'], f['round_id']) == \
        ('investment', 500, '2024-01-01', rid)


def test_round_edit_updates_the_linked_flow(temp_db):
    cid = models.add_company('C')
    rid = models.add_round(cid, 'Seed', '2024-01-01', 500)
    models.update_round(rid, amount_invested=750, date='2024-02-01')
    flows = models.get_cashflows(cid)
    assert len(flows) == 1, 'no duplicates'
    assert flows[0]['amount'] == pytest.approx(750)
    assert flows[0]['date'] == '2024-02-01'


def test_round_delete_removes_the_linked_flow(temp_db):
    cid = models.add_company('C')
    rid = models.add_round(cid, 'Seed', '2024-01-01', 500)
    models.add_cashflow(cid, '2024-06-01', 'dividend', 50)
    models.delete_round(rid)
    flows = models.get_cashflows(cid)
    assert [f['type'] for f in flows] == ['dividend'], 'no orphans'


def test_clear_rounds_removes_linked_flows_only(temp_db):
    cid = models.add_company('C')
    models.add_round(cid, 'Seed', '2024-01-01', 500)
    models.add_round(cid, 'A', '2025-01-01', 800)
    models.add_cashflow(cid, '2024-06-01', 'dividend', 50)
    models.clear_rounds(cid)
    assert [f['type'] for f in models.get_cashflows(cid)] == ['dividend']


def test_ledger_blocks_direct_edits_of_round_linked_flows(temp_db):
    cid = models.add_company('C')
    models.add_round(cid, 'Seed', '2024-01-01', 500)
    flow = models.get_cashflows(cid)[0]
    with pytest.raises(ValueError):
        models.update_cashflow(flow['id'], amount=999)
    with pytest.raises(ValueError):
        models.delete_cashflow(flow['id'])


def test_backfill_one_flow_per_round(v1_db):
    conn = models.get_conn()
    for i in range(2, 5):
        conn.execute(
            "INSERT INTO funding_rounds (company_id, round_name, date, "
            "amount_invested) VALUES (1, ?, ?, ?)",
            (f'R{i}', f'202{i}-01-01', i * 100))
    conn.commit()
    conn.close()
    models.init_db()
    flows = models.get_cashflows(1)
    rounds = models.get_rounds(1)
    inv = [f for f in flows if f['type'] == 'investment']
    assert len(inv) == len(rounds) == 4
    by_round = {f['round_id']: f for f in inv}
    for r in rounds:
        assert by_round[r['id']]['amount'] == pytest.approx(
            r['amount_invested'])
        assert by_round[r['id']]['date'] == r['date']


# ── Multiple identities ───────────────────────────────────────────────────────

def _flows(*triples):
    return [{'date': d, 'type': t, 'amount': a, 'shares_delta': None}
            for d, t, a in triples]


def test_moic_equals_tvpi_and_dpi_plus_rvpi(temp_db):
    cid = models.add_company('C')
    rid = models.add_round(cid, 'Seed', '2020-01-01', 1000,
                           ownership_pct=10)
    models.add_valuation(cid, '2024-01-01', 30000, 'internal_estimate')
    models.add_cashflow(cid, '2022-06-01', 'dividend', 200)
    models.add_cashflow(cid, '2023-06-01', 'fee', 100)
    c = models.get_company(cid)
    met = metrics.company_metrics_for(c, models.get_rounds(cid),
                                      models.get_cashflows(cid))
    # invested 1100 (round + fee), realized 200, unrealized 3000
    assert met['total_invested'] == pytest.approx(1100)
    assert met['realized'] == pytest.approx(200)
    assert met['current_value'] == pytest.approx(3000)
    assert met['dpi'] == pytest.approx(200 / 1100)
    assert met['rvpi'] == pytest.approx(3000 / 1100)
    assert met['tvpi'] == pytest.approx(met['dpi'] + met['rvpi'])
    assert met['moic'] == pytest.approx(met['tvpi'])


def test_closed_company_has_zero_unrealized(temp_db):
    cid = models.add_company('C', notes='Status: Exited')
    models.add_round(cid, 'Seed', '2020-01-01', 1000, ownership_pct=10)
    models.add_valuation(cid, '2024-01-01', 50000, 'exit')
    models.add_cashflow(cid, '2024-06-01', 'exit_proceeds', 3500)
    c = models.get_company(cid)
    met = metrics.company_metrics_for(c, models.get_rounds(cid),
                                      models.get_cashflows(cid))
    assert met['current_value'] == 0.0
    assert met['moic'] == pytest.approx(3.5)
    assert met['dpi'] == pytest.approx(3.5)
    assert met['rvpi'] == pytest.approx(0.0)


# ── XIRR against an independent solver ────────────────────────────────────────

def _independent_xirr(flows, lo=-0.99, hi=25.0):
    """Plain bisection on NPV with actual/365.25 — written independently
    of metrics.irr so the two implementations check each other."""
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


@pytest.mark.parametrize('flows', [
    # single invest + single exit
    [('2020-01-01', -1000), ('2024-01-01', 2500)],
    # invest + dividends + exit
    [('2020-01-01', -1000), ('2021-06-01', 80), ('2022-06-01', 90),
     ('2024-01-01', 1800)],
    # partial sale mid-life + terminal value
    [('2020-01-01', -2000), ('2022-06-01', 900), ('2025-01-01', 2400)],
])
def test_xirr_matches_independent_solver(flows):
    ours = metrics.irr(flows, date(2025, 6, 1))
    theirs = _independent_xirr(flows)
    assert ours is not None and theirs is not None
    assert ours == pytest.approx(theirs, abs=1e-6)


def test_xirr_unrealized_only_case():
    flows = [('2020-01-01', -1000), ('2025-01-01', 1600)]
    ours = metrics.irr(flows, date(2025, 1, 1))
    assert ours == pytest.approx(_independent_xirr(flows), abs=1e-6)


def test_xirr_multi_sign_change_falls_back_to_bisection():
    # -1000, +2550, -1600: two distinct mathematical roots (≈11.5% and
    # ≈43.5%); the bracket scan must still return a rate that zeroes NPV
    flows = [('2020-01-01', -1000), ('2021-01-01', 2550),
             ('2022-01-01', -1600)]
    r = metrics.irr(flows, date(2022, 1, 1))
    assert r is not None
    base = date(2020, 1, 1)
    npv = sum(a / (1 + r) ** ((date.fromisoformat(d) - base).days / 365.25)
              for d, a in flows)
    assert abs(npv) < 1e-3, 'returned rate must actually zero the NPV'


def test_irr_none_without_sign_change():
    assert metrics.irr([('2020-01-01', -100), ('2021-01-01', -50)],
                       date(2021, 1, 1)) is None
    assert metrics.irr([('2020-01-01', -100)], date(2021, 1, 1)) is None


# ── Shares: oversell guard + ownership after partial sale ─────────────────────

def test_oversell_guard(temp_db):
    cid = models.add_company('C')
    models.add_round(cid, 'Seed', '2020-01-01', 1000, shares_received=10000,
                     total_shares_outstanding=100000)
    with pytest.raises(ValueError):
        models.add_cashflow(cid, '2024-01-01', 'partial_sale', 500,
                            shares_delta=-15000)
    models.add_cashflow(cid, '2024-01-01', 'partial_sale', 500,
                        shares_delta=-4000)
    assert models.shares_held(cid) == pytest.approx(6000)
    with pytest.raises(ValueError):
        models.add_cashflow(cid, '2024-06-01', 'partial_sale', 500,
                            shares_delta=-7000)


def test_ownership_scales_down_after_partial_sale(temp_db):
    cid = models.add_company('C')
    models.add_round(cid, 'Seed', '2020-01-01', 1000, shares_received=10000,
                     total_shares_outstanding=100000, ownership_pct=10)
    models.add_valuation(cid, '2024-01-01', 50000, 'internal_estimate')
    models.add_cashflow(cid, '2024-06-01', 'partial_sale', 3000,
                        shares_delta=-4000)
    c = models.get_company(cid)
    met = metrics.company_metrics_for(c, models.get_rounds(cid),
                                      models.get_cashflows(cid))
    # 10% × (6000/10000 still held) = 6%
    assert met['ownership'] == pytest.approx(6.0)
    assert met['current_value'] == pytest.approx(0.06 * 50000)


# ── Demo data acceptance ──────────────────────────────────────────────────────

def _demo(name, companies):
    return next(c for c in companies if c['name'] == name)


def test_demo_covers_every_new_path(demo_db):
    companies = models.get_all_companies()

    datapulse = _demo('DataPulse', companies)
    divs = [f for f in models.get_cashflows(datapulse['id'])
            if f['type'] == 'dividend']
    assert len(divs) == 2

    biovance = _demo('BioVance', companies)
    sales = [f for f in models.get_cashflows(biovance['id'])
             if f['type'] == 'partial_sale']
    assert len(sales) == 1 and sales[0]['shares_delta'] == -5000

    wintex = _demo('Wintex Payments', companies)
    met = metrics.company_metrics_for(
        wintex, models.get_rounds(wintex['id']),
        models.get_cashflows(wintex['id']))
    assert met['closed'] and met['current_value'] == 0.0
    assert met['realized'] == pytest.approx(26520)
    assert met['dpi'] == pytest.approx(26520 / 7500)


def test_demo_exited_irr_matches_independent_solver(demo_db):
    companies = models.get_all_companies()
    wintex = _demo('Wintex Payments', companies)
    met = metrics.company_metrics_for(
        wintex, models.get_rounds(wintex['id']),
        models.get_cashflows(wintex['id']))
    flows = [('2020-05-01', -3000), ('2022-01-15', -4500),
             ('2024-06-30', 26520)]
    expected = _independent_xirr(flows)
    assert met['irr'] == pytest.approx(expected, abs=1e-6)


def test_portfolio_metrics_separates_realized(demo_db):
    companies = models.get_all_companies()
    rounds_by = {c['id']: models.get_rounds(c['id']) for c in companies}
    flows_by = models.get_cashflows_by_company()
    pm = metrics.portfolio_metrics(companies, rounds_by,
                                   flows_by_company=flows_by)
    assert pm['total_realized'] == pytest.approx(26520 + 120 + 150 + 1600)
    assert pm['tvpi'] == pytest.approx(pm['dpi'] + pm['rvpi'])
