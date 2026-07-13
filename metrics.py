"""Financial metrics: ROI, MOIC, IRR, company/portfolio aggregates.

Run this file directly to execute unit tests:
    python metrics.py
"""

from datetime import date, datetime
from typing import List, Tuple, Optional


def _parse_date(d) -> Optional[date]:
    if not d:
        return None
    if isinstance(d, date):
        return d
    try:
        return datetime.strptime(str(d)[:10], "%Y-%m-%d").date()
    except Exception:
        return None


def roi(invested: float, current_value: float) -> Optional[float]:
    """Return on Investment as a percentage."""
    if not invested:
        return None
    return (current_value - invested) / invested * 100


def moic(invested: float, current_value: float) -> Optional[float]:
    """Multiple on Invested Capital."""
    if not invested:
        return None
    return current_value / invested


def _npv(rate: float, timed_flows: List[Tuple[float, float]]) -> float:
    """Net present value. timed_flows = [(years, amount), ...]"""
    if rate <= -1:
        return float('inf')
    return sum(cf / (1 + rate) ** t for t, cf in timed_flows)


def irr(dated_flows: List[Tuple[str, float]], today: Optional[date] = None) -> Optional[float]:
    """
    Annualised IRR as a decimal (e.g. 0.25 = 25%).
    dated_flows = [(date_str, amount)] where investments are negative.
    Returns None when IRR cannot be determined.
    Uses Newton's method with bisection fallback.
    """
    if today is None:
        today = date.today()

    parsed = []
    for d, amt in dated_flows:
        dt = _parse_date(d) or today
        parsed.append((dt, amt))

    if len(parsed) < 2:
        return None

    base = min(dt for dt, _ in parsed)
    flows = [((dt - base).days / 365.25, amt) for dt, amt in parsed]

    if not any(a < 0 for _, a in flows) or not any(a > 0 for _, a in flows):
        return None

    def f(r):
        return _npv(r, flows)

    # Newton's method
    r = 0.1
    for _ in range(150):
        fr = f(r)
        dr = 1e-7
        dfr = (f(r + dr) - fr) / dr
        if abs(dfr) < 1e-15:
            break
        step = fr / dfr
        r -= step
        if r < -0.9999:
            r = -0.5
        if abs(step) < 1e-9:
            break

    if abs(f(r)) < 1e-4:
        return r

    # Bisection fallback
    lo, hi = -0.9999, 20.0
    if f(lo) * f(hi) > 0:
        return None
    for _ in range(300):
        mid = (lo + hi) / 2
        if f(lo) * f(mid) <= 0:
            hi = mid
        else:
            lo = mid
        if hi - lo < 1e-9:
            break
    r = (lo + hi) / 2

    return r if abs(f(r)) < 1e-3 else None


def company_metrics(rounds: list, current_valuation: Optional[float],
                    today: Optional[date] = None) -> dict:
    """Compute aggregated metrics for one company."""
    if today is None:
        today = date.today()

    total_invested = sum((r.get('amount_invested') or 0) for r in rounds)

    # Most recent round that has an ownership figure
    ownership = None
    for r in sorted(rounds, key=lambda x: x.get('date') or '', reverse=True):
        if r.get('ownership_pct') is not None:
            ownership = r['ownership_pct']
            break

    current_value = None
    if ownership is not None and current_valuation is not None:
        current_value = (ownership / 100) * current_valuation

    gain = roi_val = moic_val = irr_val = None
    if current_value is not None and total_invested > 0:
        gain = current_value - total_invested
        roi_val = roi(total_invested, current_value)
        moic_val = moic(total_invested, current_value)

        flows = [(r.get('date') or today.isoformat(), -(r.get('amount_invested') or 0))
                 for r in rounds if r.get('amount_invested')]
        flows.append((today.isoformat(), current_value))
        irr_val = irr(flows, today)

    return {
        'total_invested': total_invested,
        'current_value': current_value,
        'gain': gain,
        'roi': roi_val,
        'moic': moic_val,
        'irr': irr_val,
        'ownership': ownership,
    }


def portfolio_metrics(companies: list, rounds_by_company: dict,
                      today: Optional[date] = None) -> dict:
    """Aggregate metrics across the whole portfolio."""
    if today is None:
        today = date.today()

    all_flows: List[Tuple[str, float]] = []
    total_invested = 0.0
    total_current = 0.0
    has_current = False

    for c in companies:
        rounds = rounds_by_company.get(c['id'], [])
        met = company_metrics(rounds, c.get('current_valuation'), today)
        total_invested += met['total_invested']
        if met['current_value'] is not None:
            total_current += met['current_value']
            has_current = True
        for r in rounds:
            amt = r.get('amount_invested')
            if amt:
                all_flows.append((r.get('date') or today.isoformat(), -amt))

    if has_current:
        all_flows.append((today.isoformat(), total_current))

    irr_val = irr(all_flows, today) if len(all_flows) >= 2 else None

    return {
        'total_invested': total_invested,
        'total_current': total_current if has_current else None,
        'gain': (total_current - total_invested) if has_current else None,
        'roi': roi(total_invested, total_current) if has_current and total_invested else None,
        'moic': moic(total_invested, total_current) if has_current and total_invested else None,
        'irr': irr_val,
    }


# ── Unit tests ────────────────────────────────────────────────────────────────

def _run_tests():
    print("Running metrics unit tests...")

    assert abs(roi(100, 150) - 50.0) < 1e-6,       "ROI +50% failed"
    assert abs(roi(100, 50) - (-50.0)) < 1e-6,      "ROI -50% failed"
    assert roi(0, 100) is None,                      "ROI zero-denom should be None"

    assert abs(moic(100, 250) - 2.5) < 1e-6,        "MOIC 2.5× failed"
    assert abs(moic(200, 200) - 1.0) < 1e-6,        "MOIC 1.0× failed"
    assert moic(0, 100) is None,                     "MOIC zero-denom should be None"

    # invest 100 on day 0, receive 121 after exactly 2 years → IRR ≈ 10%
    d0 = date(2022, 1, 1)
    d2 = date(2024, 1, 1)
    r = irr([(d0.isoformat(), -100), (d2.isoformat(), 121)], d0)
    assert r is not None and abs(r - 0.10) < 0.005, f"IRR 10% failed: {r}"

    # invest 100, get back 200 after ~3.5 years → IRR ≈ 19%
    d3 = date(2025, 7, 1)
    r2 = irr([(d0.isoformat(), -100), (d3.isoformat(), 200)], d0)
    assert r2 is not None and 0.15 < r2 < 0.25,     f"IRR ~19% failed: {r2}"

    # Single flow → None
    assert irr([(d0.isoformat(), -100)], d0) is None, "Single-flow IRR should be None"

    # All negative → None
    assert irr([(d0.isoformat(), -100), (d2.isoformat(), -50)], d0) is None

    print("All tests passed.")


if __name__ == "__main__":
    _run_tests()
