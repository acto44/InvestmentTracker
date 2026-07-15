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


# ── Sign convention (CLAUDE.md: SIGN CONVENTION) ─────────────────────────────
# Cash-flow amounts are STORED positive; direction derives from the type,
# here and only here. Outflows leave the family's pocket.

OUTFLOW_TYPES = frozenset({'investment', 'follow_on', 'fee', 'other_out'})
INFLOW_TYPES = frozenset({'exit_proceeds', 'partial_sale', 'dividend',
                          'distribution', 'other_in'})


def signed_amount(flow_type: str, amount: float) -> float:
    """The single place where direction is decided. Every computation and
    every display goes through this helper."""
    if flow_type in OUTFLOW_TYPES:
        return -abs(amount or 0)
    if flow_type in INFLOW_TYPES:
        return abs(amount or 0)
    raise ValueError(f'unknown cashflow type: {flow_type!r}')


def is_closed(notes: str) -> bool:
    """A company whose status is Exited or Bankrupt holds no position any
    more: unrealized value is 0 by definition (the valuation history keeps
    the record). Uses the existing notes-based status semantics."""
    n = (notes or '').lower()
    return 'status: exited' in n or 'bankrupt' in n


# ── Footnotes (CLAUDE.md: MONEY — every metric states its assumptions;
#    these strings live next to the math and nowhere else) ────────────────────
UNREALIZED_VALUE_FOOTNOTE = ("Current value = latest recorded valuation "
                             "(as of {date}, source: {source}).")
VALUATION_MEANING_FOOTNOTE = (
    "Recorded valuations are the WHOLE company's value; the position "
    "value shown = valuation × our ownership %.")
FOOTNOTE_INVESTED = ("Invested = every outflow in the ledger: rounds, "
                     "follow-ons and fees.")
FOOTNOTE_REALIZED = ("Realized = money actually received: exits, partial "
                     "sales, dividends and distributions.")
FOOTNOTE_MOIC = ("MOIC = (realized + unrealized) / invested. Equals TVPI. "
                 "Fees are included as outflows.")
FOOTNOTE_DPI = ("DPI = realized / invested — the portion of your money "
                "already back in your pocket.")
FOOTNOTE_RVPI = ("RVPI = unrealized / invested — the portion still riding "
                 "on the latest valuation.")
FOOTNOTE_TVPI = "TVPI = DPI + RVPI."
FOOTNOTE_IRR = ("IRR assumes the current valuation were realized on "
                "{as_of}. Day-count: actual/365.25. Fees are included as "
                "outflows.")
FOOTNOTE_CLOSED = ("Position closed (exited/written off): unrealized "
                   "value is 0; only realized proceeds count.")
FOOTNOTE_OWNERSHIP_AFTER_SALE = (
    "Ownership after partial sales = last recorded ownership × share of "
    "originally received shares still held.")


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

    # Bisection fallback. With multiple sign changes several mathematical
    # IRRs can exist — scan a grid ordered by |rate| and bisect the first
    # bracket found, so the root closest to zero is reported.
    grid = [0.0, 0.05, -0.05, 0.1, -0.1, 0.25, -0.25, 0.5, -0.5,
            1.0, -0.75, 2.0, -0.9, 5.0, -0.99, 10.0, 20.0]
    bracket = None
    for a, b in zip(grid, grid[1:]):
        lo, hi = min(a, b), max(a, b)
        if f(lo) * f(hi) <= 0:
            bracket = (lo, hi)
            break
    if bracket is None:
        return None
    lo, hi = bracket
    for _ in range(300):
        mid = (lo + hi) / 2
        if f(lo) * f(mid) <= 0:
            hi = mid
        else:
            lo = mid
        if hi - lo < 1e-12:
            break
    r = (lo + hi) / 2

    return r if abs(f(r)) < 1e-3 else None


def company_metrics(rounds: list, current_valuation: Optional[float],
                    today: Optional[date] = None,
                    cashflows: Optional[list] = None,
                    valuation_as_of: Optional[str] = None,
                    closed: bool = False) -> dict:
    """Aggregated metrics for one company.

    Money movement comes ONLY from `cashflows` (the ledger) — never from
    round.amount_invested directly. `current_valuation` is the WHOLE
    company's value (see VALUATION_MEANING_FOOTNOTE); `closed` means the
    position is exited/written off, so unrealized value is 0."""
    if today is None:
        today = date.today()
    cashflows = cashflows or []

    invested = sum(f['amount'] for f in cashflows
                   if f['type'] in OUTFLOW_TYPES)
    realized = sum(f['amount'] for f in cashflows
                   if f['type'] in INFLOW_TYPES)

    # Ownership: most recent round with a figure, scaled down when
    # partial sales reduced the originally received shares
    # (FOOTNOTE_OWNERSHIP_AFTER_SALE).
    ownership = None
    for r in sorted(rounds, key=lambda x: x.get('date') or '', reverse=True):
        if r.get('ownership_pct') is not None:
            ownership = r['ownership_pct']
            break
    shares_from_rounds = sum((r.get('shares_received') or 0) for r in rounds)
    shares_delta = sum((f.get('shares_delta') or 0) for f in cashflows)
    if ownership is not None and shares_from_rounds > 0 and shares_delta:
        factor = max(0.0, (shares_from_rounds + shares_delta)
                     / shares_from_rounds)
        ownership = ownership * factor

    # Unrealized position value
    if closed:
        unrealized = 0.0
    elif ownership is not None and current_valuation is not None:
        unrealized = (ownership / 100) * current_valuation
    else:
        unrealized = None

    gain = roi_val = moic_val = irr_val = None
    dpi = rvpi = tvpi = None
    if invested > 0:
        dpi = realized / invested
        if unrealized is not None:
            rvpi = unrealized / invested
            tvpi = dpi + rvpi
            moic_val = (realized + unrealized) / invested
            gain = (realized + unrealized) - invested
            roi_val = roi(invested, realized + unrealized)

    signed = [(f['date'] or today.isoformat(),
               signed_amount(f['type'], f['amount'])) for f in cashflows]
    if unrealized is not None and unrealized > 0:
        signed.append((valuation_as_of or today.isoformat(), unrealized))
    if len(signed) >= 2:
        irr_val = irr(signed, today)

    return {
        'total_invested': invested,
        'realized': realized,
        'current_value': unrealized,
        'gain': gain,
        'roi': roi_val,
        'moic': moic_val,
        'dpi': dpi,
        'rvpi': rvpi,
        'tvpi': tvpi,
        'irr': irr_val,
        'ownership': ownership,
        'closed': closed,
        'valuation_as_of': valuation_as_of,
    }


def company_metrics_for(company: dict, rounds: list, cashflows: list,
                        today: Optional[date] = None) -> dict:
    """Convenience wrapper: pulls valuation/as-of/closed from an enriched
    company dict (models.get_all_companies attaches those keys)."""
    return company_metrics(rounds, company.get('current_valuation'), today,
                           cashflows=cashflows,
                           valuation_as_of=company.get('valuation_as_of'),
                           closed=is_closed(company.get('notes')))


def portfolio_metrics(companies: list, rounds_by_company: dict,
                      today: Optional[date] = None,
                      flows_by_company: Optional[dict] = None) -> dict:
    """Aggregate metrics across the whole portfolio. Money movement comes
    from the ledger (flows_by_company); portfolio IRR is date-true over
    every signed flow plus today's total unrealized value."""
    if today is None:
        today = date.today()

    all_flows: List[Tuple[str, float]] = []
    total_invested = 0.0
    total_realized = 0.0
    total_current = 0.0
    has_current = False

    for c in companies:
        rounds = rounds_by_company.get(c['id'], [])
        flows = (flows_by_company or {}).get(c['id'], [])
        met = company_metrics(rounds, c.get('current_valuation'), today,
                              cashflows=flows,
                              valuation_as_of=c.get('valuation_as_of'),
                              closed=is_closed(c.get('notes')))
        total_invested += met['total_invested']
        total_realized += met['realized']
        if met['current_value'] is not None:
            total_current += met['current_value']
            has_current = True
        for f in flows:
            all_flows.append((f['date'] or today.isoformat(),
                              signed_amount(f['type'], f['amount'])))

    if has_current and total_current > 0:
        all_flows.append((today.isoformat(), total_current))

    irr_val = irr(all_flows, today) if len(all_flows) >= 2 else None

    dpi = (total_realized / total_invested) if total_invested else None
    rvpi = (total_current / total_invested) \
        if total_invested and has_current else None
    tvpi = (dpi + rvpi) if dpi is not None and rvpi is not None else None
    total_value = total_realized + total_current

    return {
        'total_invested': total_invested,
        'total_realized': total_realized,
        'total_current': total_current if has_current else None,
        'gain': (total_value - total_invested) if has_current else None,
        'roi': roi(total_invested, total_value) if has_current and total_invested else None,
        'moic': moic(total_invested, total_value) if has_current and total_invested else None,
        'dpi': dpi,
        'rvpi': rvpi,
        'tvpi': tvpi,
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
