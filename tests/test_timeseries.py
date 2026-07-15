"""Session 4 tests: quarter math, position value over time (estimate
fallback, same-day ordering, closed rule), nav_series scoping and
cumulative correctness, quarter delta, journal CRUD + audit."""

from datetime import date

import pytest

import metrics
import models


# ── Quarter helpers ───────────────────────────────────────────────────────────

@pytest.mark.parametrize('d,expected', [
    (date(2026, 1, 1), date(2026, 3, 31)),
    (date(2026, 3, 31), date(2026, 3, 31)),
    (date(2026, 5, 2), date(2026, 6, 30)),
    (date(2026, 11, 15), date(2026, 12, 31)),
])
def test_quarter_end(d, expected):
    assert metrics.quarter_end(d) == expected


def test_quarter_label():
    assert metrics.quarter_label(date(2026, 5, 2)) == '2026-Q2'
    assert metrics.quarter_label(date(2026, 12, 31)) == '2026-Q4'


def test_previous_quarter_end_across_year_boundary():
    assert metrics.previous_quarter_end(date(2026, 1, 1)) == date(2025, 12, 31)
    assert metrics.previous_quarter_end(date(2026, 2, 15)) == date(2025, 12, 31)
    assert metrics.previous_quarter_end(date(2026, 7, 14)) == date(2026, 6, 30)


def test_month_end_grid_includes_last():
    g = metrics.month_end_grid(date(2026, 1, 10), date(2026, 4, 15))
    assert g == [date(2026, 1, 31), date(2026, 2, 28),
                 date(2026, 3, 31), date(2026, 4, 15)]


# ── position_value_at ─────────────────────────────────────────────────────────

def _co(notes=''):
    return {'id': 1, 'name': 'T', 'notes': notes}


ROUNDS = [{'date': '2020-01-01', 'ownership_pct': 10.0,
           'shares_received': 10000, 'amount_invested': 1000}]
FLOWS = [{'date': '2020-01-01', 'type': 'investment', 'amount': 1000,
          'shares_delta': None}]
VALS = [{'id': 1, 'as_of_date': '2021-06-01', 'value': 50000,
         'created_at': '2021-06-01T00:00:00Z'}]


def test_before_first_valuation_falls_back_to_net_invested():
    pv = metrics.position_value_at(_co(), ROUNDS, VALS, FLOWS,
                                   date(2020, 6, 1))
    assert pv['value'] == pytest.approx(1000)
    assert pv['is_estimate'] is True


def test_after_valuation_uses_position_semantics():
    pv = metrics.position_value_at(_co(), ROUNDS, VALS, FLOWS,
                                   date(2021, 7, 1))
    assert pv['value'] == pytest.approx(0.10 * 50000)
    assert pv['is_estimate'] is False


def test_stepwise_between_valuations():
    vals = VALS + [{'id': 2, 'as_of_date': '2023-01-01', 'value': 80000,
                    'created_at': '2023-01-01T00:00:00Z'}]
    mid = metrics.position_value_at(_co(), ROUNDS, vals, FLOWS,
                                    date(2022, 6, 1))
    after = metrics.position_value_at(_co(), ROUNDS, vals, FLOWS,
                                      date(2023, 1, 1))
    assert mid['value'] == pytest.approx(5000)      # still the old point
    assert after['value'] == pytest.approx(8000)    # steps on the day


def test_same_day_valuation_and_flow():
    """Ordering rule: on a shared date the flow counts in cumulatives AND
    the valuation sets the NAV — both inclusive."""
    flows = FLOWS + [{'date': '2021-06-01', 'type': 'follow_on',
                      'amount': 500, 'shares_delta': None}]
    d = date(2021, 6, 1)
    pv = metrics.position_value_at(_co(), ROUNDS, VALS, flows, d)
    assert pv['value'] == pytest.approx(5000)
    assert pv['is_estimate'] is False
    assert metrics.invested_to_date(flows, d) == pytest.approx(1500)


def test_closed_zero_from_exit_date_inclusive():
    flows = FLOWS + [{'date': '2024-06-30', 'type': 'exit_proceeds',
                      'amount': 9000, 'shares_delta': None}]
    co = _co('Status: Exited')
    on_exit = metrics.position_value_at(co, ROUNDS, VALS, flows,
                                        date(2024, 6, 30))
    before = metrics.position_value_at(co, ROUNDS, VALS, flows,
                                       date(2024, 6, 29))
    assert on_exit['value'] == 0.0, 'exit proceeds replace the position'
    assert before['value'] == pytest.approx(5000)
    assert metrics.realized_to_date(flows, date(2024, 6, 30)) == \
        pytest.approx(9000)


def test_ownership_at_respects_dated_partial_sale():
    flows = FLOWS + [{'date': '2022-01-01', 'type': 'partial_sale',
                      'amount': 800, 'shares_delta': -4000}]
    before = metrics.position_value_at(_co(), ROUNDS, VALS, flows,
                                       date(2021, 12, 31))
    after = metrics.position_value_at(_co(), ROUNDS, VALS, flows,
                                      date(2022, 1, 1))
    assert before['value'] == pytest.approx(5000)          # 10 %
    assert after['value'] == pytest.approx(3000)           # 6 %


# ── nav_series ────────────────────────────────────────────────────────────────

def test_nav_series_cumulatives_match_ledger_sums():
    flows = [
        {'date': '2020-01-01', 'type': 'investment', 'amount': 1000,
         'shares_delta': None},
        {'date': '2021-03-01', 'type': 'follow_on', 'amount': 400,
         'shares_delta': None},
        {'date': '2022-09-01', 'type': 'dividend', 'amount': 150,
         'shares_delta': None},
    ]
    data = [(_co(), ROUNDS, VALS, flows)]
    grid = metrics.month_end_grid(date(2020, 1, 1), date(2023, 1, 1))
    series = metrics.nav_series(data, grid)
    for p in series:
        assert p['invested_cum'] == pytest.approx(
            metrics.invested_to_date(flows, p['date']))
        assert p['realized_cum'] == pytest.approx(
            metrics.realized_to_date(flows, p['date']))
    # invested steps at the round dates
    assert series[0]['invested_cum'] == pytest.approx(1000)
    assert series[-1]['invested_cum'] == pytest.approx(1400)
    assert series[-1]['realized_cum'] == pytest.approx(150)
    # estimate flag before the first valuation, confirmed after
    assert series[0]['is_estimate'] is True
    assert series[-1]['is_estimate'] is False


def test_nav_series_entity_scope_excludes_others(demo_db):
    data_a = models.timeseries_inputs(entity='Portfolio A')
    data_b = models.timeseries_inputs(entity='Portfolio B')
    names_a = {c['name'] for c, _, _, _ in data_a}
    assert 'BioVance' not in names_a and 'NovaTech AI' in names_a
    grid = [date.today()]
    nav_a = metrics.nav_series(data_a, grid)[0]['nav']
    nav_b = metrics.nav_series(data_b, grid)[0]['nav']
    nav_all = metrics.nav_series(models.timeseries_inputs(), grid)[0]['nav']
    assert nav_a + nav_b == pytest.approx(nav_all)
    assert nav_a > 0 and nav_b > 0


def test_demo_timeline_tells_the_story(demo_db):
    """Invested ramps at round dates, realized jumps at the exit."""
    data = models.timeseries_inputs()
    first = metrics.first_flow_date(data)
    assert first == date(2020, 1, 15)
    grid = metrics.month_end_grid(first, date(2026, 7, 14))
    series = metrics.nav_series(data, grid)
    before_exit = next(p for p in series if p['date'] == date(2024, 5, 31))
    after_exit = next(p for p in series if p['date'] == date(2024, 6, 30))
    assert after_exit['realized_cum'] - before_exit['realized_cum'] == \
        pytest.approx(26520)
    assert series[-1]['invested_cum'] == pytest.approx(53200)


def test_quarter_delta_hand_computed():
    """NAV now vs previous quarter-end on a constructed case."""
    vals = [{'id': 1, 'as_of_date': '2026-01-15', 'value': 50000,
             'created_at': 'x'},
            {'id': 2, 'as_of_date': '2026-07-01', 'value': 80000,
             'created_at': 'x'}]
    data = [(_co(), ROUNDS, vals, FLOWS)]
    qd = metrics.nav_quarter_delta(data, today=date(2026, 7, 14))
    # prev quarter end = 2026-06-30 -> valuation of Jan 15 applies: 5000
    # today -> valuation of Jul 1 applies: 8000
    assert qd['previous_quarter'] == '2026-Q2'
    assert qd['previous'] == pytest.approx(5000)
    assert qd['current'] == pytest.approx(8000)
    assert qd['delta'] == pytest.approx(3000)
    assert qd['pct'] == pytest.approx(60.0)


# ── Journal ───────────────────────────────────────────────────────────────────

def test_journal_crud_and_audit(temp_db):
    cid = models.add_company('C')
    uid = models.add_company_update(cid, '2026-04-05', 'Going well.',
                                    period_label='2026-Q2',
                                    title='Solid quarter',
                                    origin='ui.journal')
    entries = models.get_company_updates(cid)
    assert len(entries) == 1 and entries[0]['title'] == 'Solid quarter'

    models.update_company_update(uid, text='Going very well.',
                                 origin='ui.journal')
    assert models.get_company_updates(cid)[0]['text'] == 'Going very well.'

    models.delete_company_update(uid, origin='ui.journal')
    assert models.get_company_updates(cid) == []

    log = models.get_audit_log(company_id=cid)
    kinds = [(e['table_name'], e['action']) for e in log]
    assert ('company_updates', 'insert') in kinds
    assert ('company_updates', 'update') in kinds
    assert ('company_updates', 'delete') in kinds
    assert all(e['origin'] == 'ui.journal' for e in log
               if e['table_name'] == 'company_updates')


def test_journal_requires_text(temp_db):
    cid = models.add_company('C')
    with pytest.raises(ValueError):
        models.add_company_update(cid, '2026-04-05', '   ')
