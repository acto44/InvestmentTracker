"""Shared display formatters (CLAUDE.md: MONEY — rounding happens only at
display time, through these helpers). Pure Python, safe everywhere."""

from __future__ import annotations

import re


def fmt_money(v, sym='TKR', dec=0) -> str:
    if v is None:
        return 'n/a'
    return f"{sym} {v:,.{dec}f}"


def fmt_signed_money(v, sym='TKR', dec=0) -> str:
    if v is None:
        return 'n/a'
    sign = '+' if v >= 0 else '−'
    return f"{sign}{sym} {abs(v):,.{dec}f}"


def fmt_multiple(v) -> str:
    return f"{v:.2f}×" if v is not None else 'n/a'


def fmt_pct(v, signed=True) -> str:
    if v is None:
        return 'n/a'
    return f"{v:+.1f}%" if signed else f"{v:.1f}%"


def fmt_irr(v) -> str:
    """v is a decimal rate (0.25 = 25%)."""
    return f"{v * 100:.1f}%" if v is not None else 'n/a'


def fmt_shares(v) -> str:
    return f"{v:,.0f}" if v else 'n/a'


def sanitize_filename(name: str, fallback='company', max_len=60) -> str:
    """Safe cross-platform file stem: unicode letters/digits (Å/ö stay),
    dash, underscore — everything else dropped, repeats collapsed."""
    s = re.sub(r'\s+', '_', (name or '').strip())
    s = re.sub(r'[^\w\-]', '', s, flags=re.UNICODE)
    s = re.sub(r'_+', '_', s)
    s = s.strip('_-')[:max_len]
    return s or fallback
