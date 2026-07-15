"""Financial math under pytest.

metrics.py keeps its original self-test (single source of truth for the
core cases); this file runs it inside the suite and adds pytest.approx
checks per the MONEY invariant (never compare floats with ==).
"""

from datetime import date

import pytest

import metrics


def test_original_metrics_suite_passes():
    metrics._run_tests()


def test_roi_uses_percent():
    assert metrics.roi(100, 150) == pytest.approx(50.0)
    assert metrics.roi(80, 60) == pytest.approx(-25.0)
    assert metrics.roi(0, 100) is None


def test_moic():
    assert metrics.moic(100, 250) == pytest.approx(2.5)
    assert metrics.moic(0, 1) is None


def test_irr_two_flow_case():
    d0, d2 = date(2022, 1, 1), date(2024, 1, 1)
    r = metrics.irr([(d0.isoformat(), -100), (d2.isoformat(), 121)], d0)
    assert r == pytest.approx(0.10, abs=0.005)


def test_company_metrics_on_demo_shape(demo_db):
    import models
    companies = models.get_all_companies()
    nova = next(c for c in companies if c['name'] == 'NovaTech AI')
    met = metrics.company_metrics(models.get_rounds(nova['id']),
                                  nova['current_valuation'])
    assert met['total_invested'] == pytest.approx(6300)
    # stake = 7.1% of 220,000 = 15,620 -> MOIC ~2.48x
    assert met['moic'] == pytest.approx(2.48, abs=0.02)
