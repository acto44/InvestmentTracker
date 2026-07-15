from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QScrollArea, QTableWidget, QTableWidgetItem, QSizePolicy,
    QGridLayout, QPushButton, QLineEdit
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont

import models
import metrics as m
from ui.styles import (
    GREEN, RED, ACCENT, MUTED, CARD, BORDER, TEXT, AMBER,
    CARD_ALT, HOVER, GREEN_SOFT, RED_SOFT,
    INFO_BG, INFO_BORDER, INFO_TEXT,
)


def _style_axes(ax):
    """Apply the dark theme to a matplotlib axes."""
    ax.set_facecolor(CARD)
    ax.tick_params(colors=MUTED, labelcolor=MUTED)
    for spine in ax.spines.values():
        spine.set_color(BORDER)
    ax.xaxis.label.set_color(MUTED)
    ax.yaxis.label.set_color(MUTED)
    ax.title.set_color(TEXT)

try:
    import matplotlib
    import matplotlib.ticker
    matplotlib.use('QtAgg')
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
    from matplotlib.figure import Figure
    HAS_MPL = True
except Exception:
    HAS_MPL = False


class _HeroArt(QWidget):
    """Decorative right side of the hero banner — painted shapes only
    (target mockup shows an abstract dial + beams), no image assets."""

    def paintEvent(self, event):
        from PyQt6.QtCore import QPointF
        from PyQt6.QtGui import QColor, QPainter, QPen, QPolygonF
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        # diagonal beams sweeping in from the right
        p.setPen(Qt.PenStyle.NoPen)
        for i, alpha in ((0, 16), (1, 10), (2, 6)):
            x = w - 40 - i * 85
            p.setBrush(QColor(255, 255, 255, alpha))
            p.drawPolygon(QPolygonF([
                QPointF(x, h), QPointF(x + 46, h),
                QPointF(x + 120, -10), QPointF(x + 74, -10)]))
        # big soft dial
        cx, cy, r = w - 170, h * 0.55, 74
        p.setBrush(QColor(148, 163, 184, 46))
        p.drawEllipse(int(cx - r), int(cy - r), int(r * 2), int(r * 2))
        pen = QPen(QColor(230, 234, 243, 60))
        pen.setWidthF(1.2)
        p.setPen(pen)
        p.drawLine(int(cx - r), int(cy), int(cx + r), int(cy))
        p.drawLine(int(cx), int(cy - r), int(cx), int(cy + r))
        p.setBrush(QColor(249, 115, 22, 200))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(int(cx - 3), int(cy - 3), 6, 6)
        p.end()


class _HeroBanner(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        from ui.styles import (BORDER_SOFT, CHART_ACCENT, RADIUS,
                               label_font)
        self.setObjectName("Hero")
        self.setFixedHeight(148)
        self.setStyleSheet(f"""
            QFrame#Hero {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #141C36, stop:0.55 #111A30, stop:1 #0D1526);
                border: 1px solid {BORDER_SOFT};
                border-radius: {RADIUS}px;
            }}
        """)
        row = QHBoxLayout(self)
        row.setContentsMargins(28, 22, 20, 22)
        col = QVBoxLayout()
        col.setSpacing(8)
        eyebrow = QLabel("PORTFOLIO OVERVIEW")
        eyebrow.setFont(label_font())
        eyebrow.setStyleSheet(f"color:{CHART_ACCENT}; font-size:8.5pt; "
                              f"font-weight:600; border:none;")
        col.addWidget(eyebrow)
        headline = QLabel("Build Long-Term\nCompound Growth")
        headline.setStyleSheet(f"color:{TEXT}; font-size:20pt; "
                               f"font-weight:400; border:none;")
        col.addWidget(headline)
        col.addStretch()
        row.addLayout(col)
        row.addStretch()
        art = _HeroArt()
        art.setFixedWidth(360)
        art.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        row.addWidget(art)


def _pill_style(active: bool) -> str:
    """THE filter-pill style — every toggle row (portfolio, type, chart
    range) uses exactly this active/inactive pair."""
    from ui.styles import ACCENT_LITE, BORDER_SOFT, RADIUS_SM
    if active:
        return (f"QPushButton {{ background:{ACCENT_LITE}; color:{ACCENT}; "
                f"border:1px solid rgba(59,130,246,0.45); "
                f"border-radius:{RADIUS_SM}px; padding:4px 16px; "
                f"font-weight:600; font-size:9pt; }}")
    return (f"QPushButton {{ background:transparent; color:{MUTED}; "
            f"border:1px solid {BORDER_SOFT}; "
            f"border-radius:{RADIUS_SM}px; padding:4px 16px; "
            f"font-weight:600; font-size:9pt; }}"
            f"QPushButton:hover {{ background:{HOVER}; color:{TEXT}; }}")


def _sym():
    return models.get_setting('currency', 'TKR')

def _fmt(val, sym='TKR', dec=0):
    if val is None:
        return "n/a"
    return f"{sym} {val:,.{dec}f}"

def _moic(val):
    return f"{val:.2f}×" if val is not None else "n/a"

def _pct(val):
    return f"{val:+.1f}%" if val is not None else "n/a"


# ── Small reusable widgets ────────────────────────────────────────────────────

class _Card(QFrame):
    """KPI card. IDENTICAL structure everywhere — label / value / subtext
    (subtext always exists, blank if unused) — so a row of cards shares
    heights and baselines by construction."""

    def __init__(self, title, value, subtitle=None, value_color=None, min_w=160, tooltip=None):
        super().__init__()
        from ui.styles import BORDER_SOFT, CARD_PAD, RADIUS, label_font
        self.setStyleSheet(f"""
            QFrame {{
                background: {CARD};
                border:1px solid {BORDER_SOFT}; border-radius:{RADIUS}px;
            }}
        """)
        if tooltip:
            self.setToolTip(tooltip)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(CARD_PAD, 16, CARD_PAD, 16)
        lay.setSpacing(4)

        t = QLabel(str(title).upper())
        t.setFont(label_font())          # letter-spacing (QSS can't)
        t.setStyleSheet(f"color:{MUTED}; font-size:8pt; "
                        f"font-weight:600; border:none;")
        lay.addWidget(t)

        v = QLabel(str(value))
        # size via stylesheet — the app-wide QSS font-size wins over QFont
        # (16pt: six cards must fit beside the 230px rail at min width)
        v.setStyleSheet(f"font-size:16pt; font-weight:600; "
                        f"color:{value_color or TEXT}; border:none;")
        lay.addWidget(v)

        s = QLabel(str(subtitle) if subtitle else " ")
        s.setStyleSheet(f"color:{value_color or MUTED}; font-size:9pt; border:none;")
        lay.addWidget(s)
        lay.addStretch()

        self.setMinimumWidth(min_w)
        self.setMinimumHeight(108)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)


class _SectionTitle(QLabel):
    """THE section header style: 8pt uppercase, letter-spaced, muted —
    hierarchy from type, not decoration (matches detail_panel and
    dialogs)."""

    def __init__(self, text):
        super().__init__(str(text).upper())
        from ui.styles import label_font
        self.setFont(label_font())       # letter-spacing (QSS can't)
        self.setStyleSheet(f"color:{MUTED}; font-size:8pt; "
                           f"font-weight:600; margin-top:24px;")


class _MiniTable(QFrame):
    """Compact read-only table for top/worst lists. Numeric columns
    (everything but the first) are right-aligned; the widget is sized to
    EXACTLY header + rows so no empty viewport strip can show below the
    last row."""

    _ROW_H = 34
    _HEADER_H = 32

    def __init__(self, headers, rows, col_colors=None):
        super().__init__()
        from ui.styles import BORDER_SOFT, RADIUS
        self.setStyleSheet(
            f"QFrame {{background:{CARD}; border:1px solid {BORDER_SOFT}; "
            f"border-radius:{RADIUS}px;}}"
        )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        tbl = QTableWidget(len(rows), len(headers))
        tbl.setHorizontalHeaderLabels(headers)
        tbl.setAlternatingRowColors(True)
        tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        tbl.verticalHeader().setVisible(False)
        tbl.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        tbl.horizontalHeader().setStretchLastSection(True)
        tbl.setFrameShape(QFrame.Shape.NoFrame)
        tbl.setStyleSheet("QTableWidget { border: none; }")
        tbl.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        right = (Qt.AlignmentFlag.AlignVCenter
                 | Qt.AlignmentFlag.AlignRight)
        left = Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
        for ci in range(1, len(headers)):
            it = tbl.horizontalHeaderItem(ci)
            if it:
                it.setTextAlignment(right)
        for ri, row_data in enumerate(rows):
            tbl.setRowHeight(ri, self._ROW_H)
            for ci, val in enumerate(row_data):
                item = QTableWidgetItem(str(val))
                item.setTextAlignment(left if ci == 0 else right)
                if col_colors and ci < len(col_colors) and col_colors[ci]:
                    fg = col_colors[ci](val) if callable(col_colors[ci]) else col_colors[ci]
                    if fg:
                        item.setForeground(QColor(fg))
                tbl.setItem(ri, ci, item)

        tbl.resizeColumnsToContents()
        exact = self._HEADER_H + self._ROW_H * len(rows) + 10
        tbl.setFixedHeight(exact)
        self.setFixedHeight(exact + 2)
        lay.addWidget(tbl)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)


# ── Main dashboard ────────────────────────────────────────────────────────────

class DashboardTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._entity_filter: str | None = None
        self._type_filter:   str | None = None
        self._search_text   = ''
        self._holdings_tbl  = None
        self._session_snapshot_taken = False
        self._session_deltas: list = []
        self._session_last_date: str = ''

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        self._content = QWidget()
        self._layout  = QVBoxLayout(self._content)
        self._layout.setContentsMargins(24, 20, 24, 24)
        self._layout.setSpacing(16)

        scroll.setWidget(self._content)
        outer.addWidget(scroll)

    # ── Refresh ───────────────────────────────────────────────────────────────

    def refresh(self):
        self._clear()
        sym         = _sym()
        all_cos     = models.get_all_companies()

        # Hero banner (target design), then the type filter bar
        self._layout.addWidget(_HeroBanner())
        self._layout.addWidget(self._filter_bar(all_cos))

        # Apply entity + type filters
        companies = [
            c for c in all_cos
            if (not self._entity_filter or c.get('entity') == self._entity_filter)
            and (not self._type_filter   or c.get('investment_type') == self._type_filter)
        ]

        subtitle = self._entity_filter or "All Portfolios"
        title = _SectionTitle(f"Dashboard — {subtitle}")
        self._layout.addWidget(title)

        if not companies:
            empty = QLabel(
                "No investments yet.\n\nUse File → Import from family spreadsheet to get started."
            )
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet(f"color:{MUTED}; font-size:12pt; margin:60px;")
            self._layout.addWidget(empty)
            return

        rounds_by = {c['id']: models.get_rounds(c['id']) for c in companies}
        flows_by  = models.get_cashflows_by_company()
        co_met    = {c['id']: m.company_metrics_for(
                         c, rounds_by[c['id']], flows_by.get(c['id'], []))
                     for c in companies}

        # Split: companies with known valuation vs unknown
        known   = [c for c in companies if c.get('current_valuation') is not None]
        unknown = [c for c in companies if c.get('current_valuation') is None]

        total_invested      = sum(co_met[c['id']]['total_invested'] for c in companies)
        invested_of_known   = sum(co_met[c['id']]['total_invested'] for c in known)
        total_current_known = sum((co_met[c['id']]['current_value'] or 0) for c in known)
        total_realized      = sum(co_met[c['id']]['realized'] for c in companies)
        realized_of_known   = sum(co_met[c['id']]['realized'] for c in known)
        total_gain_known    = (total_current_known + realized_of_known) - invested_of_known
        coverage            = invested_of_known / total_invested * 100 if total_invested else 0
        moic_known          = ((total_current_known + realized_of_known) / invested_of_known
                               if invested_of_known else None)
        tvpi_known          = moic_known    # TVPI = DPI + RVPI = MOIC (see metrics.py)

        # ── Since last update (all-portfolios view only) ──────────────────────
        if not self._entity_filter:
            self._ensure_snapshot(sym)
            delta_w = self._build_delta_section(sym)
            if delta_w:
                self._layout.addWidget(delta_w)

        # ── 1. Headline cards ─────────────────────────────────────────────────
        self._layout.addWidget(
            QLabel(f"<span style='color:{MUTED}; font-size:9pt;'>"
                   f"Valuation coverage: {len(known)} of {len(companies)} companies "
                   f"({coverage:.0f}% of invested capital)</span>")
        )

        gain_color = GREEN if total_gain_known >= 0 else RED
        sign       = "+" if total_gain_known >= 0 else "−"
        gain_str   = f"{sign}{sym} {abs(total_gain_known):,.0f}"

        cards = QHBoxLayout()
        cards.setSpacing(12)
        cards.addWidget(_Card("Total Invested", f"{sym} {total_invested:,.0f}",
            tooltip="The total amount of money put into all companies across all funding rounds."))
        cards.addWidget(_Card("Known Current Value", f"{sym} {total_current_known:,.0f}",
                              f"({len(known)} companies)", None,
            tooltip="Current estimated value of all companies that have a valuation set.\n"
                    "Companies without a valuation are not counted here."))
        cards.addWidget(_Card("Gain / Loss (known)", gain_str,
                              f"{total_gain_known/invested_of_known*100:+.1f}% on known"
                              if invested_of_known else None,
                              gain_color,
            tooltip="Profit or loss on companies with known valuations.\n"
                    "= Current Value − Amount Invested\n"
                    "Green = profit, Red = loss."))
        cards.addWidget(_Card("Realized", f"{sym} {total_realized:,.0f}",
                              None, None,
            tooltip=m.FOOTNOTE_REALIZED + "\n"
                    "Money already back in the family's pocket — exits, "
                    "partial sales, dividends, distributions."))
        cards.addWidget(_Card("MOIC / TVPI (known)", _moic(tvpi_known),
            tooltip=m.FOOTNOTE_MOIC + "\n" + m.FOOTNOTE_TVPI + "\n"
                    "Only includes companies with a known valuation."))
        cards.addWidget(_Card("Not yet valued",
                              f"{sym} {total_invested - invested_of_known:,.0f}",
                              f"{len(unknown)} companies", MUTED,
            tooltip="Capital invested in companies where no current valuation has been set.\n"
                    "These are not counted in MOIC or Gain/Loss — "
                    "the true portfolio performance may be higher or lower."))
        self._layout.addLayout(cards)

        # ── Portfolio Health ──────────────────────────────────────────────────
        self._layout.addWidget(
            self._build_health_section(companies, co_met, rounds_by, sym)
        )

        # ── 2. Entity breakdown (only shown in combined "All" view) ──────────
        if not self._entity_filter:
            self._layout.addWidget(_SectionTitle("By Portfolio"))
            entity_row = QHBoxLayout()
            entity_row.setSpacing(12)
            entities = {}
            for c in all_cos:
                e = c.get('entity') or 'Unassigned'
                entities.setdefault(e, []).append(c)
            all_co_met = {c['id']: m.company_metrics_for(
                              c, models.get_rounds(c['id']),
                              flows_by.get(c['id'], []))
                          for c in all_cos}

            for ename, elist in sorted(entities.items()):
                e_inv  = sum(all_co_met[c['id']]['total_invested'] for c in elist)
                e_cur  = sum((all_co_met[c['id']]['current_value'] or 0)
                             for c in elist if c.get('current_valuation') is not None)
                e_n    = len(elist)
                e_kn   = sum(1 for c in elist if c.get('current_valuation') is not None)
                e_gain = e_cur - sum(all_co_met[c['id']]['total_invested']
                                     for c in elist if c.get('current_valuation') is not None)
                g_col  = GREEN if e_gain >= 0 else RED
                entity_row.addWidget(_Card(
                    ename,
                    f"{sym} {e_inv:,.0f} invested",
                    f"{sym} {e_cur:,.0f} known value  |  {e_kn}/{e_n} valued  |  "
                    f"gain {'+' if e_gain>=0 else ''}{sym} {e_gain:,.0f}",
                    g_col, min_w=200
                ))
            self._layout.addLayout(entity_row)

        # ── 3. Charts ─────────────────────────────────────────────────────────
        if HAS_MPL:
            self._layout.addWidget(_SectionTitle("Portfolio Over Time"))
            self._add_quarter_delta(sym)
            range_row = QHBoxLayout()
            for label in ('1Y', '3Y', 'All'):
                b = QPushButton(label)
                b.setFixedWidth(48)
                active = getattr(self, '_ts_range', 'All') == label
                b.setStyleSheet(_pill_style(active))
                b.clicked.connect(lambda _, l=label: self._set_ts_range(l))
                range_row.addWidget(b)
            range_row.addStretch()
            self._layout.addLayout(range_row)
            self._layout.addWidget(self._timeline_chart(sym))

            chart_row = QHBoxLayout()
            chart_row.setSpacing(12)
            chart_row.addWidget(self._top_holdings_chart(companies, co_met, sym), 3)
            chart_row.addWidget(self._returns_chart(known, co_met, sym), 2)
            chart_row.addWidget(self._sector_chart(companies, co_met, sym), 2)
            self._layout.addLayout(chart_row)

        # ── 4. Top contributors / Worst performers ────────────────────────────
        ranker_row = QHBoxLayout()
        ranker_row.setSpacing(12)

        top5, worst5 = self._rank_companies(known, co_met, sym)

        left_col = QVBoxLayout()
        left_col.setSpacing(6)
        left_col.addWidget(_SectionTitle("Top Contributors"))
        left_col.addWidget(_MiniTable(
            ["Company", "Invested", "Current Value", "Gain", "MOIC"],
            top5,
            col_colors=[
                None, None, None,
                lambda v: GREEN if v.startswith('+') else (RED if v.startswith('−') else None),
                None,
            ]
        ))
        ranker_row.addLayout(left_col)

        right_col = QVBoxLayout()
        right_col.setSpacing(6)
        right_col.addWidget(_SectionTitle("Worst Performers"))
        right_col.addWidget(_MiniTable(
            ["Company", "Invested", "Current Value", "Gain", "MOIC"],
            worst5,
            col_colors=[
                None, None, None,
                lambda v: RED if v.startswith('−') else (GREEN if v.startswith('+') else None),
                None,
            ]
        ))
        ranker_row.addLayout(right_col)

        self._layout.addLayout(ranker_row)

        # ── 5. Search bar + full company table ───────────────────────────────
        self._layout.addWidget(_SectionTitle("All Holdings"))

        search_row = QHBoxLayout()
        search_row.setSpacing(8)
        search_bar = QLineEdit()
        search_bar.setPlaceholderText("🔍  Search by company name, portfolio or sector…")
        search_bar.setText(self._search_text)
        search_bar.setClearButtonEnabled(True)
        search_bar.setStyleSheet(
            f"QLineEdit {{ border:1px solid {BORDER}; border-radius:7px; "
            f"padding:6px 12px; font-size:10pt; background:{CARD}; }}"
            f"QLineEdit:focus {{ border-color:{ACCENT}; }}"
        )
        search_row.addWidget(search_bar)
        self._layout.addLayout(search_row)

        tbl = self._full_table(companies, co_met, sym)
        self._holdings_tbl = tbl
        self._apply_search(self._search_text)   # restore previous filter

        search_bar.textChanged.connect(self._on_search)
        self._layout.addWidget(tbl)
        self._layout.addStretch()

    # ── Charts ────────────────────────────────────────────────────────────────

    def _set_ts_range(self, label):
        self._ts_range = label
        self.refresh()

    def _add_quarter_delta(self, sym):
        """Small KPI: NAV now vs previous quarter-end (metrics does the
        math so a test can hand-check it)."""
        data = models.timeseries_inputs(entity=self._entity_filter or None)
        qd = m.nav_quarter_delta(data)
        if not qd:
            return
        color = GREEN if qd['delta'] >= 0 else RED
        sign = '+' if qd['delta'] >= 0 else '−'
        pct = f" ({qd['pct']:+.1f}%)" if qd['pct'] is not None else ''
        est = '  ·  contains estimated positions' if qd['is_estimate'] else ''
        lbl = QLabel(
            f"NAV {sym} {qd['current']:,.0f}  vs  {qd['previous_quarter']} "
            f"end {sym} {qd['previous']:,.0f}   →   "
            f"<span style='color:{color};'>{sign}{sym} "
            f"{abs(qd['delta']):,.0f}{pct}</span>"
            f"<span style='color:{MUTED};'>{est}</span>")
        lbl.setStyleSheet("font-size:10pt;")
        self._layout.addWidget(lbl)

    def _timeline_chart(self, sym):
        """NAV / cumulative invested / cumulative realized over month-end
        grid — DERIVED from dated valuations and flows (see CLAUDE.md)."""
        from datetime import date as _date, timedelta as _td
        data = models.timeseries_inputs(entity=self._entity_filter or None)
        first = m.first_flow_date(data)
        today = _date.today()
        if first is None:
            lbl = QLabel("No dated cash flows yet — the timeline appears "
                         "after the first investment is recorded.")
            lbl.setStyleSheet(f"color:{MUTED};")
            return lbl
        rng = getattr(self, '_ts_range', 'All')
        if rng == '1Y':
            first = max(first, today - _td(days=365))
        elif rng == '3Y':
            first = max(first, today - _td(days=3 * 365))
        grid = m.month_end_grid(first, today)
        series = m.nav_series(data, grid)

        xs = [p['date'] for p in series]
        fig = Figure(figsize=(9.0, 3.4), facecolor=CARD)
        ax = fig.add_subplot(111)
        _style_axes(ax)
        ax.step(xs, [p['nav'] for p in series], where='post',
                color=ACCENT, linewidth=2, label='NAV')
        ax.step(xs, [p['invested_cum'] for p in series], where='post',
                color=MUTED, linewidth=1.4, linestyle='--',
                label='Invested (cum.)')
        ax.step(xs, [p['realized_cum'] for p in series], where='post',
                color=GREEN, linewidth=1.4, label='Realized (cum.)')
        est_pts = [p for p in series if p['is_estimate']]
        if est_pts:
            ax.plot([p['date'] for p in est_pts],
                    [p['nav'] for p in est_pts], 'o', color=MUTED,
                    markersize=3,
                    label='contains estimates')
        ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(
            lambda v, _: f"{int(v/1000)}K" if abs(v) >= 1000 else str(int(v))))
        ax.tick_params(axis='both', labelsize=8)
        ax.legend(fontsize=8, frameon=False, loc='upper left',
                  labelcolor=MUTED)
        ax.set_title(f'NAV, invested and realized over time ({sym})',
                     fontsize=10, fontweight='bold', pad=6)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        fig.tight_layout(pad=1.2)
        canvas = FigureCanvasQTAgg(fig)
        canvas.setMinimumHeight(260)
        return canvas

    def _top_holdings_chart(self, companies, co_met, sym):
        """Horizontal bar — top 12 holdings by invested amount."""
        sorted_co = sorted(companies, key=lambda c: co_met[c['id']]['total_invested'],
                           reverse=True)[:12]

        names    = [c['name'][:22] for c in reversed(sorted_co)]
        invested = [co_met[c['id']]['total_invested'] for c in reversed(sorted_co)]
        current  = [(co_met[c['id']]['current_value'] or 0) for c in reversed(sorted_co)]

        fig = Figure(figsize=(5.5, 3.8), facecolor=CARD)
        ax  = fig.add_subplot(111)
        _style_axes(ax)

        y = list(range(len(names)))
        h = 0.35
        ax.barh([i + h/2 for i in y], invested, h, label='Invested',
                color=ACCENT, alpha=0.9)
        ax.barh([i - h/2 for i in y], current,  h, label='Current Value',
                color=GREEN, alpha=0.9)

        ax.set_yticks(y)
        ax.set_yticklabels(names, fontsize=8)
        ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(
            lambda v, _: f"{int(v/1000)}K" if v >= 1000 else str(int(v))
        ))
        ax.tick_params(axis='x', labelsize=8)
        ax.set_title('Top 12 Holdings (TKR)', fontsize=10, fontweight='bold', pad=6)
        ax.legend(fontsize=8, frameon=False, loc='lower right', labelcolor=MUTED)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        fig.tight_layout(pad=1.2)

        canvas = FigureCanvasQTAgg(fig)
        canvas.setMinimumHeight(300)
        return canvas

    def _returns_chart(self, known_companies, co_met, sym):
        """Horizontal bar — MOIC for companies with known valuation, sorted."""
        if not known_companies:
            lbl = QLabel("No valuations set yet.\nImport your spreadsheet to see returns.")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f"color:{MUTED}; font-size:10pt;")
            return lbl

        sorted_co = sorted(known_companies,
                           key=lambda c: co_met[c['id']].get('moic') or 0,
                           reverse=True)

        names  = [c['name'][:20] for c in reversed(sorted_co)]
        moics  = [(co_met[c['id']].get('moic') or 0) for c in reversed(sorted_co)]
        colors = [GREEN if v >= 1.0 else RED for v in moics]

        fig = Figure(figsize=(3.5, 3.8), facecolor=CARD)
        ax  = fig.add_subplot(111)
        _style_axes(ax)

        y = list(range(len(names)))
        ax.barh(y, moics, color=colors, alpha=0.9)
        ax.axvline(1.0, color=MUTED, linewidth=1, linestyle='--', alpha=0.6)
        ax.set_yticks(y)
        ax.set_yticklabels(names, fontsize=8)
        ax.tick_params(axis='x', labelsize=8)
        ax.set_xlabel('MOIC (×)', fontsize=8)
        ax.set_title('Returns (valued companies)', fontsize=10, fontweight='bold', pad=6)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        fig.tight_layout(pad=1.2)

        canvas = FigureCanvasQTAgg(fig)
        canvas.setMinimumHeight(300)
        return canvas

    def _sector_chart(self, companies, co_met, sym):
        """Donut — invested capital by sector (top 6 + Other)."""
        by_sector: dict[str, float] = {}
        for c in companies:
            sector = (c.get('sector') or '').strip() or 'Unspecified'
            by_sector[sector] = by_sector.get(sector, 0) + co_met[c['id']]['total_invested']
        by_sector = {k: v for k, v in by_sector.items() if v > 0}

        if not by_sector:
            lbl = QLabel("No sector data yet.")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f"color:{MUTED}; font-size:10pt;")
            return lbl

        ranked = sorted(by_sector.items(), key=lambda kv: kv[1], reverse=True)
        top, rest = ranked[:6], ranked[6:]
        if rest:
            top.append(('Other', sum(v for _, v in rest)))

        names  = [k for k, _ in top]
        values = [v for _, v in top]
        total  = sum(values)

        # Lightness-staggered so adjacent slices stay distinct under CVD;
        # every slice also carries a direct text label (identity is never color-alone).
        palette = ['#6C8CFF', '#7A5AF8', '#22D3EE', '#4ADE80', '#FBBF24', '#F472B6']
        colors  = [palette[i % len(palette)] for i in range(len(names))]
        if names[-1] == 'Other':
            colors[-1] = '#475569'

        fig = Figure(figsize=(3.5, 3.8), facecolor=CARD)
        ax  = fig.add_subplot(111)
        ax.set_facecolor(CARD)
        ax.title.set_color(TEXT)

        labels = [f"{n}\n{v/total*100:.0f}%" for n, v in zip(names, values)]
        ax.pie(values, labels=labels, colors=colors, startangle=90,
               counterclock=False,
               wedgeprops={'width': 0.42, 'edgecolor': CARD, 'linewidth': 2},
               textprops={'fontsize': 7, 'color': MUTED},
               labeldistance=1.12)
        ax.text(0, 0, f"{sym}\n{total:,.0f}", ha='center', va='center',
                fontsize=9, fontweight='bold', color=TEXT)
        ax.set_title('Invested by Sector', fontsize=10, fontweight='bold', pad=6)
        fig.tight_layout(pad=1.2)

        canvas = FigureCanvasQTAgg(fig)
        canvas.setMinimumHeight(300)
        return canvas

    # ── Ranked lists ──────────────────────────────────────────────────────────

    def _rank_companies(self, known, co_met, sym):
        def row(c):
            met  = co_met[c['id']]
            inv  = met['total_invested']
            cur  = met['current_value'] or 0
            gain = cur - inv
            sign = '+' if gain >= 0 else '−'
            mc   = _moic(met.get('moic'))
            return [
                c['name'],
                f"{sym} {inv:,.0f}",
                f"{sym} {cur:,.0f}",
                f"{sign}{sym} {abs(gain):,.0f}",
                mc,
            ]

        by_gain = sorted(known, key=lambda c: (co_met[c['id']]['current_value'] or 0)
                         - co_met[c['id']]['total_invested'], reverse=True)
        top5   = [row(c) for c in by_gain[:5]]
        worst5 = [row(c) for c in by_gain[-5:] if
                  ((co_met[c['id']]['current_value'] or 0)
                   - co_met[c['id']]['total_invested']) < 0]
        return top5, worst5

    # ── Full table ────────────────────────────────────────────────────────────

    def _full_table(self, companies, co_met, sym):
        headers = ["Company", "Portfolio", "Type", "Sector", "Invested",
                   "Current Value", "Gain / Loss", "MOIC"]

        sorted_co = sorted(companies,
                           key=lambda c: co_met[c['id']]['total_invested'],
                           reverse=True)

        tbl = QTableWidget(len(sorted_co), len(headers))
        tbl.setHorizontalHeaderLabels(headers)
        tbl.setAlternatingRowColors(True)
        tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        tbl.verticalHeader().setVisible(False)
        tbl.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        tbl.setSortingEnabled(True)
        tbl.horizontalHeader().setStretchLastSection(True)
        tbl.setFrameShape(QFrame.Shape.NoFrame)
        for ci in range(4, len(headers)):     # numeric columns
            it = tbl.horizontalHeaderItem(ci)
            if it:
                it.setTextAlignment(Qt.AlignmentFlag.AlignVCenter
                                    | Qt.AlignmentFlag.AlignRight)

        for ri, c in enumerate(sorted_co):
            met = co_met[c['id']]
            cur = met.get('current_value')
            gain = (cur - met['total_invested']) if cur is not None else None
            notes = (c.get('notes') or '').lower()

            def _item(txt, color=None, numeric=False):
                it = QTableWidgetItem(str(txt))
                if numeric:
                    it.setTextAlignment(Qt.AlignmentFlag.AlignVCenter
                                        | Qt.AlignmentFlag.AlignRight)
                if color:
                    it.setForeground(QColor(color))
                return it

            # Status color: bankrupt = red bg, exited = green bg
            name_item = _item(c['name'])
            if 'bankrupt' in notes:
                name_item.setBackground(QColor(RED_SOFT))
            elif 'status: exited' in notes:
                name_item.setBackground(QColor(GREEN_SOFT))

            gain_str = "—"
            gain_col = None
            if gain is not None:
                sign     = "+" if gain >= 0 else "−"
                gain_str = f"{sign}{sym} {abs(gain):,.0f}"
                gain_col = GREEN if gain >= 0 else RED

            tbl.setItem(ri, 0, name_item)
            tbl.setItem(ri, 1, _item(c.get('entity') or ''))
            tbl.setItem(ri, 2, _item(c.get('investment_type') or ''))
            tbl.setItem(ri, 3, _item(c.get('sector') or ''))
            tbl.setItem(ri, 4, _item(f"{sym} {met['total_invested']:,.0f}",
                                     numeric=True))
            tbl.setItem(ri, 5, _item(f"{sym} {cur:,.0f}" if cur is not None else "—",
                                     None if cur else MUTED, numeric=True))
            tbl.setItem(ri, 6, _item(gain_str, gain_col, numeric=True))
            tbl.setItem(ri, 7, _item(_moic(met.get('moic')), numeric=True))

        tbl.resizeColumnsToContents()
        tbl.setMinimumHeight(320)
        return tbl

    # ── Filter bar ────────────────────────────────────────────────────────────

    def _filter_bar(self, all_companies):
        frame = QFrame()
        frame.setStyleSheet("QFrame { border: none; background: transparent; }")
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(0, 0, 0, 4)
        lay.setSpacing(4)

        _btn_style = _pill_style

        # The entity filter lives in the sidebar dropdown since the
        # session-11 shell (same _set_filter path the pills used).
        # Row: investment type filter (only shown if any types are set)
        types = sorted({c.get('investment_type') for c in all_companies
                        if c.get('investment_type')})
        if types:
            type_row = QHBoxLayout()
            type_row.setSpacing(6)
            lbl = QLabel("Type:")
            lbl.setStyleSheet(f"color:{MUTED}; font-size:9pt; border:none;")
            type_row.addWidget(lbl)
            for label, value in [("All Types", None)] + [(t, t) for t in types]:
                btn = QPushButton(label)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setStyleSheet(_btn_style(self._type_filter == value))
                btn.clicked.connect(lambda _, v=value: self._set_type_filter(v))
                type_row.addWidget(btn)
            type_row.addStretch()
            lay.addLayout(type_row)

        return frame

    def _set_filter(self, entity: str | None):
        self._entity_filter = entity
        self.refresh()

    def _set_type_filter(self, inv_type: str | None):
        self._type_filter = inv_type
        self.refresh()

    def _on_search(self, text: str):
        self._search_text = text
        self._apply_search(text)

    def _apply_search(self, text: str):
        if self._holdings_tbl is None:
            return
        q = text.strip().lower()
        tbl = self._holdings_tbl
        for ri in range(tbl.rowCount()):
            if not q:
                tbl.setRowHidden(ri, False)
                continue
            # Search across company name (col 0), portfolio (col 1), type (col 2), sector (col 3)
            row_text = ' '.join(
                (tbl.item(ri, ci).text() if tbl.item(ri, ci) else '')
                for ci in (0, 1, 2, 3)
            ).lower()
            tbl.setRowHidden(ri, q not in row_text)

    # ── Snapshot / delta ─────────────────────────────────────────────────────

    def _ensure_snapshot(self, sym):
        if self._session_snapshot_taken:
            return
        old_snap = models.load_last_snapshot()
        new_snap = models.get_snapshot()
        models.save_snapshot(new_snap)
        self._session_snapshot_taken = True
        self._session_last_date = old_snap.get('date', '') if old_snap else ''
        self._session_deltas = self._compute_deltas(old_snap, new_snap, sym) if old_snap else []

    def _compute_deltas(self, old_snap, new_snap, sym):
        deltas = []
        old_cos = old_snap.get('companies', {})
        new_cos = new_snap.get('companies', {})

        for k, nc in new_cos.items():
            if k not in old_cos:
                deltas.append((f"New company added: {nc['name']}", ACCENT))

        for k, nc in new_cos.items():
            oc = old_cos.get(k)
            if not oc:
                continue
            name = nc['name']
            ov, nv = oc.get('valuation'), nc.get('valuation')
            if ov != nv:
                if nv is None:
                    deltas.append((f"{name}: valuation removed", MUTED))
                elif ov is None:
                    deltas.append((f"{name}: valuation set — {sym} {nv:,.0f}", GREEN))
                else:
                    diff = nv - ov
                    sign = "+" if diff >= 0 else "−"
                    col  = GREEN if diff >= 0 else RED
                    deltas.append((
                        f"{name} valuation {sign}{sym} {abs(diff):,.0f} (→ {sym} {nv:,.0f})", col
                    ))
            nd, od = nc.get('docs', 0), oc.get('docs', 0)
            if nd > od:
                n = nd - od
                deltas.append((f"{name}: {n} new document{'s' if n > 1 else ''} added", ACCENT))

        om, nm = old_snap.get('portfolio_moic'), new_snap.get('portfolio_moic')
        if om is not None and nm is not None and abs(nm - om) >= 0.01:
            deltas.append((
                f"Portfolio MOIC changed from {om:.2f}× to {nm:.2f}×",
                GREEN if nm > om else RED
            ))

        no_val = sum(1 for nc in new_cos.values() if nc.get('valuation') is None)
        if no_val > 0:
            deltas.append((
                f"{no_val} compan{'ies' if no_val > 1 else 'y'} still missing valuation", MUTED
            ))

        return deltas

    def _build_delta_section(self, sym):
        if not self._session_deltas:
            return None
        frame = QFrame()
        frame.setStyleSheet(
            f"QFrame {{ background:{INFO_BG}; border:1px solid {INFO_BORDER}; border-radius:10px; }}"
        )
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(5)

        since = f" — since {self._session_last_date}" if self._session_last_date else ""
        hdr = QLabel(f"Since last update{since}")
        hdr.setStyleSheet(f"font-weight:bold; font-size:10pt; color:{INFO_TEXT}; border:none;")
        lay.addWidget(hdr)

        for text, color in self._session_deltas:
            row = QHBoxLayout()
            dot = QLabel("•")
            dot.setStyleSheet(f"color:{color}; font-size:12pt; border:none;")
            dot.setFixedWidth(14)
            lbl = QLabel(text)
            lbl.setStyleSheet(f"color:{color}; font-size:9pt; border:none;")
            lbl.setWordWrap(True)
            row.addWidget(dot)
            row.addWidget(lbl, 1)
            lay.addLayout(row)

        return frame

    def _build_health_section(self, companies, co_met, rounds_by, sym):
        from datetime import date, timedelta

        total_invested   = sum(co_met[c['id']]['total_invested'] for c in companies)
        known            = [c for c in companies if c.get('current_valuation') is not None]
        invested_of_known = sum(co_met[c['id']]['total_invested'] for c in known)

        coverage_pct = invested_of_known / total_invested * 100 if total_invested else 0
        coverage_conf = "high" if coverage_pct >= 70 else ("medium" if coverage_pct >= 40 else "low")
        cov_color    = GREEN if coverage_pct >= 70 else (MUTED if coverage_pct >= 40 else RED)

        sorted_co   = sorted(companies, key=lambda c: co_met[c['id']]['total_invested'], reverse=True)
        top3_inv    = sum(co_met[c['id']]['total_invested'] for c in sorted_co[:3])
        conc_pct    = top3_inv / total_invested * 100 if total_invested else 0
        conc_label  = "high" if conc_pct >= 60 else ("medium" if conc_pct >= 40 else "low")
        conc_color  = RED if conc_label == "high" else (MUTED if conc_label == "medium" else GREEN)

        loss_exp = sum(
            co_met[c['id']]['total_invested'] for c in known
            if (co_met[c['id']].get('moic') or 1.0) < 0.5
        )
        loss_color = RED if loss_exp > 0 else GREEN

        gains     = sorted(
            [(c, (co_met[c['id']].get('current_value') or 0) - co_met[c['id']]['total_invested'])
             for c in known],
            key=lambda x: x[1], reverse=True
        )
        total_gain  = sum(g for _, g in gains if g > 0)
        top3_gain   = sum(g for _, g in gains[:3] if g > 0)
        winners_dep = top3_gain / total_gain * 100 if total_gain > 0 else 0
        win_color   = RED if winners_dep > 80 else (MUTED if winners_dep > 60 else GREEN)

        frame = QFrame()
        frame.setStyleSheet(
            f"QFrame {{ background:{CARD}; border:1px solid {BORDER}; border-radius:10px; }}"
        )
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(10)

        hdr = QLabel("Portfolio Health")
        hdr.setStyleSheet(f"font-weight:bold; font-size:11pt; color:{TEXT}; border:none;")
        lay.addWidget(hdr)

        badge_row = QHBoxLayout()
        badge_row.setSpacing(10)
        badge_row.addWidget(_Card("Valuation coverage", f"{coverage_pct:.0f}%",
                                  f"{coverage_conf} confidence", cov_color,
            tooltip="What percentage of your invested capital has a current valuation.\n"
                    "High (70%+) = good picture of portfolio value.\n"
                    "Low = many companies unvalued, so total figures are estimates."))
        badge_row.addWidget(_Card("Concentration risk", conc_label.capitalize(),
                                  f"Top 3 = {conc_pct:.0f}% of capital", conc_color,
            tooltip="How much of your total invested capital is concentrated in just the top 3 companies.\n"
                    "High (60%+) = if those companies struggle, the whole portfolio is affected.\n"
                    "Low = capital spread more evenly, less risk from any single company."))
        badge_row.addWidget(_Card("Loss exposure", f"{sym} {loss_exp:,.0f}",
                                  "in holdings below 0.5× MOIC", loss_color,
            tooltip="Total capital invested in companies currently worth less than half what was put in.\n"
                    "MOIC below 0.5× means you'd get back less than 50 cents per krona invested.\n"
                    "Zero is best — means no companies are deeply underwater."))
        badge_row.addWidget(_Card("Winners dependency", f"{winners_dep:.0f}%",
                                  "of gains from top 3 holdings", win_color,
            tooltip="How much of the portfolio's total profit comes from just the top 3 best performers.\n"
                    "Very high (80%+) = the portfolio's success depends heavily on a few companies.\n"
                    "Lower = gains are spread across more companies, a healthier sign."))
        lay.addLayout(badge_row)

        details_row = QHBoxLayout()
        details_row.setSpacing(16)

        top5_rows = [
            (c['name'],
             f"{sym} {co_met[c['id']]['total_invested']:,.0f}",
             f"{co_met[c['id']]['total_invested']/total_invested*100:.1f}%")
            for c in sorted_co[:5]
        ]
        top5_col = QVBoxLayout()
        top5_col.setSpacing(4)
        t5_lbl = QLabel("Top 5 holdings (% of invested capital)")
        t5_lbl.setStyleSheet(f"color:{MUTED}; font-size:9pt; font-weight:bold; border:none;")
        top5_col.addWidget(t5_lbl)
        top5_col.addWidget(_MiniTable(["Company", "Invested", "% of total"], top5_rows))
        details_row.addLayout(top5_col, 2)

        cutoff = (date.today() - timedelta(days=365)).isoformat()
        stale  = []
        for c in known:
            rds = rounds_by.get(c['id'], [])
            dated = [r.get('date') or '' for r in rds if r.get('date')]
            last  = max(dated) if dated else ''
            if not last or last < cutoff:
                stale.append(c['name'])

        stale_col = QVBoxLayout()
        stale_col.setSpacing(4)
        sl_lbl = QLabel("Stale valuations (not updated in 12+ months)")
        sl_lbl.setStyleSheet(f"color:{MUTED}; font-size:9pt; font-weight:bold; border:none;")
        stale_col.addWidget(sl_lbl)
        if stale:
            for name in stale:
                w = QLabel(f"⚠  {name}")
                w.setStyleSheet(f"color:{AMBER}; font-size:9pt; border:none;")
                stale_col.addWidget(w)
        else:
            ok = QLabel("✓  All valuations are recent")
            ok.setStyleSheet(f"color:{GREEN}; font-size:9pt; border:none;")
            stale_col.addWidget(ok)
        stale_col.addStretch()
        details_row.addLayout(stale_col, 1)

        lay.addLayout(details_row)
        return frame

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _clear(self):
        while self._layout.count():
            item = self._layout.takeAt(0)
            w    = item.widget()
            if w:
                w.setParent(None)   # vanish NOW, not on deferred delete
                w.deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            w    = item.widget()
            if w:
                w.setParent(None)
                w.deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())
