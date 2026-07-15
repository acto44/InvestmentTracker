"""Offscreen chart rendering for reports — matplotlib Agg only, no Qt.

Reports are PRINT media: light background, dark text, restrained accent.
render_series_chart_png() is generic on purpose — session 6 reuses it for
portfolio/entity charts. 2× resolution (dpi=200) for print sharpness.
"""

from __future__ import annotations

import io

# print palette (light) — deliberately NOT the app's dark theme
INK = '#1E293B'
MUTED = '#64748B'
GRID = '#E2E8F0'
ACCENT = '#2563EB'
GREEN = '#15803D'
RED = '#B91C1C'


def render_series_chart_png(series: list, markers: list | None = None,
                            sym: str = 'TKR', title: str = '',
                            width_in: float = 7.0,
                            height_in: float = 2.8) -> bytes:
    """PNG bytes for a stepwise value series.

    series  = [{'date', 'nav', 'is_estimate'}, ...] (metrics.nav_series)
    markers = [{'date', 'signed', 'label', 'note'}, ...] — drawn ▲/▼ by
              direction on the value line.
    """
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    import matplotlib.ticker as mticker

    import metrics

    fig = Figure(figsize=(width_in, height_in), facecolor='white')
    FigureCanvasAgg(fig)
    ax = fig.add_subplot(111)
    ax.set_facecolor('white')
    for spine in ax.spines.values():
        spine.set_color(GRID)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.tick_params(colors=MUTED, labelcolor=MUTED, labelsize=8)
    ax.grid(True, color=GRID, linewidth=0.6, alpha=0.7)

    # estimate segments dashed & muted, confirmed segments solid accent
    seg_x, seg_y, seg_est = [], [], None
    for p in list(series) + [None]:
        cur_est = p['is_estimate'] if p else None
        if seg_est is None:
            seg_est = cur_est
        if p is None or cur_est != seg_est:
            if seg_x:
                ax.step(seg_x, seg_y, where='post',
                        color=MUTED if seg_est else ACCENT,
                        linestyle='--' if seg_est else '-',
                        linewidth=1.8,
                        label=('estimated' if seg_est else 'value'))
            if p is not None:
                seg_x = [seg_x[-1]] if seg_x else []
                seg_y = [seg_y[-1]] if seg_y else []
                seg_est = cur_est
        if p is not None:
            seg_x.append(p['date'])
            seg_y.append(p['nav'])

    if markers:
        by_date = {p['date']: p['nav'] for p in series}
        for mk in markers:
            d = metrics._parse_date(mk['date'])
            if d is None:
                continue
            # y = value at the nearest grid point ≤ marker date
            ys = [p['nav'] for p in series if p['date'] <= d]
            y = ys[-1] if ys else 0
            up = mk['signed'] >= 0
            ax.plot([d], [y], '^' if up else 'v',
                    color=GREEN if up else RED, markersize=6, zorder=5)

    handles, labels = ax.get_legend_handles_labels()
    seen = {}
    for h, l in zip(handles, labels):
        seen.setdefault(l, h)
    if seen:
        ax.legend(seen.values(), seen.keys(), fontsize=8, frameon=False,
                  labelcolor=MUTED, loc='upper left')
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(
        lambda v, _: f"{int(v/1000)}K" if abs(v) >= 1000 else str(int(v))))
    if title:
        ax.set_title(title, fontsize=10, color=INK, fontweight='bold',
                     pad=6)
    fig.tight_layout(pad=1.0)

    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=200, facecolor='white')
    return buf.getvalue()


def build_company_chart_images(model: dict) -> dict:
    """{placeholder_name: png_bytes} for a company report model."""
    if not model.get('series'):
        return {}
    sym = model['meta']['currency']
    png = render_series_chart_png(
        model['series'], model.get('markers'), sym=sym,
        title=f"Position value over time ({sym})   ▲ money in   ▼ money out")
    return {model['valuations']['chart']: png}
