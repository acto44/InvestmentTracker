from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QScrollArea, QTableWidget, QTableWidgetItem, QSizePolicy,
    QGridLayout, QPushButton, QLineEdit
)
import os

from PyQt6.QtCore import Qt, pyqtSignal
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
    """Right side of the hero banner: the stork-with-moneybag
    illustration (ui/assets/hero_art.png, transparent background,
    loaded through resource_path so the .exe finds it too). Renders
    nothing if the asset is missing — the banner must never crash."""

    def __init__(self, parent=None):
        super().__init__(parent)
        from PyQt6.QtGui import QPixmap

        from resources import resource_path
        self._pm = QPixmap(resource_path(
            os.path.join('ui', 'assets', 'hero_art.png')))

    def paintEvent(self, event):
        from PyQt6.QtGui import QPainter
        if self._pm.isNull():
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        h = self.height() - 8
        pm = self._pm.scaledToHeight(
            h, Qt.TransformationMode.SmoothTransformation)
        p.drawPixmap(self.width() - pm.width() - 8,
                     (self.height() - pm.height()) // 2, pm)
        p.end()


class _Sparkline(QWidget):
    """Tiny value-over-time polyline for holding rows. Values come from
    the REAL derived series; a constant series draws honestly flat."""

    def __init__(self, values, parent=None):
        super().__init__(parent)
        self._values = [v for v in values if v is not None]
        self.setFixedSize(92, 26)

    def paintEvent(self, event):
        from PyQt6.QtCore import QPointF
        from PyQt6.QtGui import QColor, QPainter, QPen
        from ui.styles import CHART_ACCENT
        if len(self._values) < 2:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        lo, hi = min(self._values), max(self._values)
        span = (hi - lo) or 1.0
        n = len(self._values)
        pts = [QPointF(3 + i * (self.width() - 6) / (n - 1),
                       self.height() - 5
                       - (v - lo) / span * (self.height() - 10))
               for i, v in enumerate(self._values)]
        pen = QPen(QColor(CHART_ACCENT), 1.6)
        p.setPen(pen)
        for a, b in zip(pts, pts[1:]):
            p.drawLine(a, b)
        p.end()


_AVATAR_COLORS = ('#3B82F6', '#8B5CF6', '#0EA5E9', '#10B981',
                  '#F59E0B', '#EC4899', '#64748B')


def _avatar(name: str) -> QLabel:
    """24px rounded square with the company initial — color picked by
    name hash so it is stable across refreshes."""
    lbl = QLabel((name or '?')[0].upper())
    color = _AVATAR_COLORS[hash(name) % len(_AVATAR_COLORS)]
    lbl.setFixedSize(24, 24)
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setStyleSheet(f"background:{color}; color:white; "
                      f"border-radius:6px; font-size:10pt; "
                      f"font-weight:700; border:none;")
    return lbl


class _Bar(QWidget):
    """Thin progress/indicator bar for the health sub-cards
    (green/amber/red carries the meaning)."""

    def __init__(self, fraction: float, color: str, parent=None):
        super().__init__(parent)
        self._frac = max(0.0, min(1.0, fraction))
        self._color = color
        self.setFixedHeight(5)

    def paintEvent(self, event):
        from PyQt6.QtGui import QColor, QPainter
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, 20))
        p.drawRoundedRect(0, 0, self.width(), 5, 2.5, 2.5)
        w = int(self.width() * self._frac)
        if w > 4:
            p.setBrush(QColor(self._color))
            p.drawRoundedRect(0, 0, w, 5, 2.5, 2.5)
        p.end()


class _Ring(QWidget):
    """Circular progress ring (target: 'Valuations covered')."""

    def __init__(self, pct: float, parent=None):
        super().__init__(parent)
        self._pct = max(0.0, min(100.0, pct))
        self.setFixedSize(84, 84)

    def paintEvent(self, event):
        from PyQt6.QtCore import QRectF
        from PyQt6.QtGui import QColor, QFont, QPainter, QPen
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(6, 6, self.width() - 12, self.height() - 12)
        base = QPen(QColor(148, 163, 184, 46), 8)
        base.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(base)
        p.drawArc(rect, 0, 360 * 16)
        arc = QPen(QColor(GREEN), 8)
        arc.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(arc)
        p.drawArc(rect, 90 * 16, int(-self._pct * 3.6 * 16))
        p.setPen(QColor(TEXT))
        f = QFont()
        f.setPointSize(11)
        f.setBold(True)
        p.setFont(f)
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                   f"{self._pct:.0f}%")
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


def _pill_style(active: bool, compact: bool = False) -> str:
    """THE filter-pill style — every toggle row (portfolio, type, chart
    metric/range) uses exactly this active/inactive pair. compact =
    tighter padding for fixed-width pills like 1M/3M/…/ALL."""
    from ui.styles import ACCENT_LITE, BORDER_SOFT, RADIUS_SM
    pad = "4px 8px" if compact else "4px 16px"
    if active:
        return (f"QPushButton {{ background:{ACCENT_LITE}; color:{ACCENT}; "
                f"border:1px solid rgba(59,130,246,0.45); "
                f"border-radius:{RADIUS_SM}px; padding:{pad}; "
                f"font-weight:600; font-size:9pt; }}")
    return (f"QPushButton {{ background:transparent; color:{MUTED}; "
            f"border:1px solid {BORDER_SOFT}; "
            f"border-radius:{RADIUS_SM}px; padding:{pad}; "
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

    def __init__(self, title, value, subtitle=None, value_color=None,
                 min_w=140, tooltip=None, bar=None, value_pt=16,
                 pad=None):
        super().__init__()
        from ui.styles import BORDER_SOFT, CARD_PAD, RADIUS, label_font
        pad = CARD_PAD if pad is None else pad
        self.setStyleSheet(f"""
            QFrame {{
                background: {CARD};
                border:1px solid {BORDER_SOFT}; border-radius:{RADIUS}px;
            }}
        """)
        if tooltip:
            self.setToolTip(tooltip)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(pad, 16, pad, 16)
        lay.setSpacing(4)

        t = QLabel(str(title).upper())
        t.setFont(label_font())          # letter-spacing (QSS can't)
        t.setStyleSheet(f"color:{MUTED}; font-size:8pt; "
                        f"font-weight:600; border:none;")
        lay.addWidget(t)

        v = QLabel(str(value))
        # size via stylesheet — the app-wide QSS font-size wins over QFont
        v.setStyleSheet(f"font-size:{value_pt}pt; font-weight:600; "
                        f"color:{value_color or TEXT}; border:none;")
        lay.addWidget(v)

        if bar is not None:
            lay.addWidget(_Bar(*bar))

        s = QLabel(str(subtitle) if subtitle else " ")
        s.setStyleSheet(f"color:{value_color or MUTED}; font-size:9pt; border:none;")
        lay.addWidget(s)
        lay.addStretch()

        self.setMinimumWidth(min_w)
        self.setMinimumHeight(108)
        # Ignored horizontally: the row divides space evenly and cards
        # really can shrink to min_w — long labels must not dictate the
        # layout's minimum width (they'd push the right rail off-screen)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)


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
    open_company = pyqtSignal(int)     # chevron on a holding row
    view_all = pyqtSignal()            # "View all →" on Top 5 Holdings
    show_history = pyqtSignal()        # "View all" on Recent Activity
    quick_action = pyqtSignal(str)     # right-rail Quick Actions

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

        # main column + right rail; stacks vertically when narrow
        self._content = QWidget()
        self._content_row = QHBoxLayout(self._content)
        self._content_row.setContentsMargins(0, 0, 0, 0)
        self._content_row.setSpacing(0)

        main_host = QWidget()
        self._layout = QVBoxLayout(main_host)
        self._layout.setContentsMargins(24, 20, 16, 24)
        self._layout.setSpacing(16)
        self._content_row.addWidget(main_host, 1)

        self._rail_host = QWidget()
        self._rail_host.setFixedWidth(300)
        self._rail_lay = QVBoxLayout(self._rail_host)
        self._rail_lay.setContentsMargins(0, 20, 24, 24)
        self._rail_lay.setSpacing(16)
        self._content_row.addWidget(self._rail_host)
        self._stacked = False

        scroll.setWidget(self._content)
        outer.addWidget(scroll)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        narrow = self.width() < 1280
        if narrow != self._stacked:
            self._stacked = narrow
            from PyQt6.QtWidgets import QBoxLayout
            self._content_row.setDirection(
                QBoxLayout.Direction.TopToBottom if narrow
                else QBoxLayout.Direction.LeftToRight)
            if narrow:
                self._rail_host.setMinimumWidth(0)
                self._rail_host.setMaximumWidth(16777215)
                self._rail_lay.setContentsMargins(24, 0, 24, 24)
            else:
                self._rail_host.setFixedWidth(300)
                self._rail_lay.setContentsMargins(0, 20, 24, 24)

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

        # ── Portfolio value chart + summary card (target design) ──────────
        if HAS_MPL:
            hero_row = QHBoxLayout()
            hero_row.setSpacing(16)
            hero_row.addWidget(self._value_chart_card(sym), 3)
            hero_row.addWidget(self._summary_card(sym, coverage), 1)
            self._layout.addLayout(hero_row)
            self._add_quarter_delta(sym)

        gain_color = GREEN if total_gain_known >= 0 else RED
        sign       = "+" if total_gain_known >= 0 else "−"
        gain_str   = f"{sign}{sym} {abs(total_gain_known):,.0f}"

        cards = QHBoxLayout()
        cards.setSpacing(12)

        def kpi(*a, **k):        # six cards beside the rail: tighter fit
            return _Card(*a, value_pt=15, pad=14, **k)
        cards.addWidget(kpi("Total Invested", f"{sym} {total_invested:,.0f}",
            tooltip="The total amount of money put into all companies across all funding rounds."))
        cards.addWidget(kpi("Known Current Value", f"{sym} {total_current_known:,.0f}",
                              f"({len(known)} companies)", None,
            tooltip="Current estimated value of all companies that have a valuation set.\n"
                    "Companies without a valuation are not counted here."))
        cards.addWidget(kpi("Gain / Loss (known)", gain_str,
                              f"{total_gain_known/invested_of_known*100:+.1f}% on known"
                              if invested_of_known else None,
                              gain_color,
            tooltip="Profit or loss on companies with known valuations.\n"
                    "= Current Value − Amount Invested\n"
                    "Green = profit, Red = loss."))
        cards.addWidget(kpi("Realized", f"{sym} {total_realized:,.0f}",
                              None, None,
            tooltip=m.FOOTNOTE_REALIZED + "\n"
                    "Money already back in the family's pocket — exits, "
                    "partial sales, dividends, distributions."))
        cards.addWidget(kpi("MOIC / TVPI (known)", _moic(tvpi_known),
            tooltip=m.FOOTNOTE_MOIC + "\n" + m.FOOTNOTE_TVPI + "\n"
                    "Only includes companies with a known valuation."))
        cards.addWidget(kpi("Not yet valued",
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

        # ── Top 5 Holdings (extended) + Allocation by Sector ─────────────────
        holdings_row = QHBoxLayout()
        holdings_row.setSpacing(16)
        holdings_row.addWidget(self._top5_card(companies, co_met, sym), 3)
        holdings_row.addWidget(self._sector_donut_card(companies, co_met), 2)
        self._layout.addLayout(holdings_row)

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

        # ── 3. Secondary charts ──────────────────────────────────────────────
        # (the portfolio-value chart moved to the top card in phase 3)
        if HAS_MPL:
            chart_row = QHBoxLayout()
            chart_row.setSpacing(16)
            chart_row.addWidget(self._top_holdings_chart(companies, co_met, sym), 3)
            chart_row.addWidget(self._returns_chart(known, co_met, sym), 2)
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

        # ── Right rail: activity, quick actions, alerts (phase 6) ─────────
        self._build_rail_cards(all_cos, known, rounds_by, sym)

    # ── Charts ────────────────────────────────────────────────────────────────

    METRIC_TABS = (('value', 'Total Value'), ('gain', 'Gain / Loss'),
                   ('moic', 'MOIC'), ('irr', 'IRR'))
    RANGES = (('1M', 31), ('3M', 92), ('6M', 183), ('1Y', 365),
              ('3Y', 1095), ('ALL', None))

    def _set_ts_range(self, label):
        self._ts_range = label
        self.refresh()

    def _set_ts_metric(self, key):
        self._ts_metric = key
        self.refresh()

    def _metric_values(self, series, data, metric):
        """Selected metric per grid point — pure transforms of the
        derived nav_series (CLAUDE.md: time series are derived)."""
        if metric == 'gain':
            return ([p['nav'] + p['realized_cum'] - p['invested_cum']
                     for p in series], lambda v: f"{v:+,.0f}")
        if metric == 'moic':
            return ([((p['nav'] + p['realized_cum']) / p['invested_cum'])
                     if p['invested_cum'] > 0 else None for p in series],
                    lambda v: f"{v:.2f}×")
        if metric == 'irr':
            flows = []
            for _c, _r, _v, fl in data:
                for f in fl:
                    if f.get('date'):
                        flows.append((f['date'],
                                      m.signed_amount(f['type'],
                                                      f['amount'])))
            flows.sort()
            vals = []
            for p in series:
                iso = p['date'].isoformat()
                sub = [(d, a) for d, a in flows if d <= iso]
                if p['nav'] > 0:
                    sub = sub + [(iso, p['nav'])]
                r = m.irr(sub, p['date']) if len(sub) >= 2 else None
                vals.append(r * 100 if r is not None else None)
            return vals, lambda v: f"{v:.1f}%"
        return [p['nav'] for p in series], lambda v: f"{v:,.0f}"

    def _value_chart_card(self, sym):
        """The target's centerpiece: metric tabs + range pills + orange
        area chart with a hover crosshair. Reads ONLY the derived
        series — no stored snapshots."""
        from datetime import date as _date, timedelta as _td

        from ui.styles import BORDER_SOFT, CHART_ACCENT, RADIUS

        card = QFrame()
        card.setObjectName("ChartCard")
        card.setStyleSheet(
            f"QFrame#ChartCard {{ background:{CARD}; border:1px solid "
            f"{BORDER_SOFT}; border-radius:{RADIUS}px; }}")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 14, 16, 10)
        lay.setSpacing(8)

        metric = getattr(self, '_ts_metric', 'value')
        rng = getattr(self, '_ts_range', '1Y')

        head = QHBoxLayout()
        head.setSpacing(6)
        for key, label in self.METRIC_TABS:
            b = QPushButton(label)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(_pill_style(metric == key))
            b.clicked.connect(lambda _, k=key: self._set_ts_metric(k))
            head.addWidget(b)
        head.addStretch()
        for label, _days in self.RANGES:
            b = QPushButton(label)
            b.setFixedWidth(46)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(_pill_style(rng == label, compact=True))
            b.clicked.connect(lambda _, l=label: self._set_ts_range(l))
            head.addWidget(b)
        lay.addLayout(head)

        data = models.timeseries_inputs(entity=self._entity_filter or None)
        first = m.first_flow_date(data)
        today = _date.today()
        if first is None:
            lbl = QLabel("No dated cash flows yet — the chart appears "
                         "after the first investment is recorded.")
            lbl.setStyleSheet(f"color:{MUTED}; border:none;")
            lay.addWidget(lbl)
            return card
        days = dict(self.RANGES)[rng]
        if days:
            first = max(first, today - _td(days=days))
        span = (today - first).days
        if span <= 200:                      # dense grid on short ranges
            grid = [first + _td(days=i) for i in range(span + 1)]
        elif span <= 750:
            grid = [first + _td(days=i) for i in range(0, span + 1, 7)]
            if grid[-1] != today:
                grid.append(today)
        else:
            grid = m.month_end_grid(first, today)
        series = m.nav_series(data, grid)
        ys, y_fmt = self._metric_values(series, data, metric)

        fig = Figure(figsize=(8.6, 3.1), facecolor=CARD)
        ax = fig.add_subplot(111)
        _style_axes(ax)
        pts = [(p['date'], y) for p, y in zip(series, ys) if y is not None]
        canvas = FigureCanvasQTAgg(fig)
        if pts:
            px = [a for a, _ in pts]
            py = [b for _, b in pts]
            ax.plot(px, py, color=CHART_ACCENT, linewidth=2.2)
            if metric in ('value', 'gain'):
                ax.fill_between(px, py, 0, color=CHART_ACCENT, alpha=0.09)
            est = [(p['date'], y) for p, y in zip(series, ys)
                   if y is not None and p['is_estimate']]
            if est:
                stride = max(1, len(est) // 24)   # keep the flag readable,
                est = est[::stride]               # not a dashed-line effect
                ax.plot([a for a, _ in est], [b for _, b in est], 'o',
                        color=MUTED, markersize=2.5)
            if metric == 'value':
                ax.yaxis.set_major_formatter(
                    matplotlib.ticker.FuncFormatter(
                        lambda v, _: f"{int(v / 1000)}K"
                        if abs(v) >= 1000 else str(int(v))))
            ax.tick_params(axis='both', labelsize=8)
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.margins(x=0.01)
            fig.tight_layout(pad=1.0)

            # hover crosshair + tooltip
            import matplotlib.dates as mdates
            xnums = mdates.date2num(px)
            vline = ax.axvline(px[0], color=MUTED, linewidth=0.8, alpha=0)
            dot, = ax.plot([], [], 'o', color=CHART_ACCENT, markersize=5)
            annot = ax.annotate(
                '', xy=(px[0], py[0]), xytext=(12, 14),
                textcoords='offset points', color=TEXT, fontsize=8,
                bbox=dict(boxstyle='round,pad=0.45', fc=CARD_ALT,
                          ec=BORDER, lw=1))
            annot.set_visible(False)

            def _on_move(event):
                if event.inaxes != ax or event.xdata is None:
                    if annot.get_visible():
                        annot.set_visible(False)
                        vline.set_alpha(0)
                        dot.set_data([], [])
                        canvas.draw_idle()
                    return
                i = min(range(len(xnums)),
                        key=lambda k: abs(xnums[k] - event.xdata))
                vline.set_xdata([px[i], px[i]])
                vline.set_alpha(0.55)
                dot.set_data([px[i]], [py[i]])
                annot.xy = (px[i], py[i])
                annot.set_text(f"{px[i].isoformat()}\n{y_fmt(py[i])}")
                annot.set_visible(True)
                canvas.draw_idle()

            canvas.mpl_connect('motion_notify_event', _on_move)
        else:
            ax.text(0.5, 0.5, 'not computable for this range',
                    transform=ax.transAxes, ha='center', color=MUTED,
                    fontsize=9)
        canvas.setMinimumHeight(250)
        # the figure's pixel size must not dictate layout minimums —
        # the canvas re-renders at whatever width the card gives it
        canvas.setSizePolicy(QSizePolicy.Policy.Ignored,
                             QSizePolicy.Policy.Preferred)
        canvas.setMinimumWidth(320)
        lay.addWidget(canvas)
        return card

    def _summary_card(self, sym, coverage_pct):
        """Total Portfolio Value + %-vs-last-year + coverage ring."""
        from datetime import date as _date, timedelta as _td

        from ui.styles import BORDER_SOFT, RADIUS, label_font

        card = QFrame()
        card.setObjectName("SummaryCard")
        card.setStyleSheet(
            f"QFrame#SummaryCard {{ background:{CARD}; border:1px solid "
            f"{BORDER_SOFT}; border-radius:{RADIUS}px; }}")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(6)

        t = QLabel("TOTAL PORTFOLIO VALUE")
        t.setFont(label_font())
        t.setStyleSheet(f"color:{MUTED}; font-size:8pt; "
                        f"font-weight:600; border:none;")
        lay.addWidget(t)

        data = models.timeseries_inputs(entity=self._entity_filter or None)
        first = m.first_flow_date(data)
        today = _date.today()
        nav_now, prev = 0.0, None
        is_est = False
        if first is not None:
            series = m.nav_series(data, [today - _td(days=365), today])
            nav_now = series[-1]['nav']
            is_est = series[-1]['is_estimate']
            if first <= today - _td(days=365):
                prev = series[0]['nav']

        v = QLabel(f"{sym} {nav_now:,.0f}")
        v.setStyleSheet(f"font-size:21pt; font-weight:700; color:{TEXT}; "
                        f"border:none;")
        lay.addWidget(v)

        if prev:
            pct = (nav_now - prev) / prev * 100
            color = GREEN if pct >= 0 else RED
            d = QLabel(f"{'▲' if pct >= 0 else '▼'} {pct:+.1f}% "
                       f"vs. last year")
            d.setStyleSheet(f"color:{color}; font-size:9.5pt; "
                            f"border:none;")
            lay.addWidget(d)
        if is_est:
            e = QLabel("contains estimated positions")
            e.setStyleSheet(f"color:{MUTED}; font-size:8pt; border:none;")
            lay.addWidget(e)
        lay.addStretch()

        ring_row = QHBoxLayout()
        ring_row.setSpacing(12)
        ring_row.addWidget(_Ring(coverage_pct))
        rl = QLabel("Valuations\ncovered")
        rl.setStyleSheet(f"color:{MUTED}; font-size:9pt; border:none;")
        ring_row.addWidget(rl)
        ring_row.addStretch()
        lay.addLayout(ring_row)
        return card

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

    def _top5_card(self, companies, co_met, sym):
        """Top 5 Holdings, extended per the target: avatar, invested,
        current value, MOIC (green ≥1× / red below), ownership %,
        % of total, sparkline from the real derived series, chevron."""
        from datetime import date as _date, timedelta as _td

        from PyQt6.QtWidgets import QGridLayout

        from ui.styles import BORDER_SOFT, RADIUS, label_font

        card = QFrame()
        card.setObjectName("Top5Card")
        card.setStyleSheet(
            f"QFrame#Top5Card {{ background:{CARD}; border:1px solid "
            f"{BORDER_SOFT}; border-radius:{RADIUS}px; }}")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(10)

        head = QHBoxLayout()
        title = QLabel("Top 5 Holdings "
                       f"<span style='color:{MUTED}; font-size:9pt;'>"
                       f"(% of invested capital)</span>")
        title.setStyleSheet(f"font-weight:bold; font-size:11pt; "
                            f"color:{TEXT}; border:none;")
        head.addWidget(title)
        head.addStretch()
        view_all = QPushButton("View all →")
        view_all.setCursor(Qt.CursorShape.PointingHandCursor)
        view_all.setStyleSheet(
            f"QPushButton {{ background:transparent; color:{ACCENT}; "
            f"border:none; font-weight:600; font-size:9pt; }}")
        view_all.clicked.connect(self.view_all.emit)
        head.addWidget(view_all)
        lay.addLayout(head)

        total_invested = sum(co_met[c['id']]['total_invested']
                             for c in companies) or 1.0
        top5 = sorted(companies,
                      key=lambda c: co_met[c['id']]['total_invested'],
                      reverse=True)[:5]
        by_id = {c['id']: (c, r, v, f) for c, r, v, f in
                 models.timeseries_inputs(entity=self._entity_filter
                                          or None)}
        today = _date.today()
        grid_dates = m.month_end_grid(today - _td(days=365), today)

        g = QGridLayout()
        g.setHorizontalSpacing(14)
        g.setVerticalSpacing(8)
        headers = ("Company", "Invested", "Current Value", "MOIC",
                   "Ownership", "% of total", "", "")
        for ci, h in enumerate(headers):
            hl = QLabel(h.upper())
            hl.setFont(label_font())
            hl.setStyleSheet(f"color:{MUTED}; font-size:7.5pt; "
                             f"font-weight:600; border:none;")
            if 1 <= ci <= 5:
                hl.setAlignment(Qt.AlignmentFlag.AlignRight)
            g.addWidget(hl, 0, ci)

        def cell(text, color=None, right=True):
            l = QLabel(str(text))
            l.setStyleSheet(f"color:{color or TEXT}; font-size:9.5pt; "
                            f"border:none;")
            if right:
                l.setAlignment(Qt.AlignmentFlag.AlignRight
                               | Qt.AlignmentFlag.AlignVCenter)
            return l

        for ri, c in enumerate(top5, start=1):
            met = co_met[c['id']]
            inv = met['total_invested']
            cur = met.get('current_value')
            moic = met.get('moic')
            name_row = QHBoxLayout()
            name_row.setSpacing(8)
            name_row.addWidget(_avatar(c['name']))
            nm = QLabel(c['name'])
            nm.setStyleSheet(f"color:{TEXT}; font-size:9.5pt; "
                             f"font-weight:600; border:none;")
            name_row.addWidget(nm)
            name_row.addStretch()
            nw = QWidget()
            nw.setLayout(name_row)
            g.addWidget(nw, ri, 0)

            g.addWidget(cell(f"{sym} {inv:,.0f}"), ri, 1)
            g.addWidget(cell(f"{sym} {cur:,.0f}" if cur is not None
                             else "—", None if cur else MUTED), ri, 2)
            if moic is None:
                g.addWidget(cell("n/a", MUTED), ri, 3)
            else:
                g.addWidget(cell(f"{moic:.2f}×",
                                 GREEN if moic >= 1.0 else RED), ri, 3)

            tpl = by_id.get(c['id'])
            own = (m.ownership_at(tpl[1], tpl[3], today)
                   if tpl else None)
            g.addWidget(cell(f"{own:.1f}%" if own is not None else "n/a",
                             None if own is not None else MUTED), ri, 4)
            g.addWidget(cell(f"{inv / total_invested * 100:.1f}%"), ri, 5)

            spark_vals = []
            if tpl:
                spark_vals = [p['nav'] for p in
                              m.nav_series([tpl], grid_dates)]
            g.addWidget(_Sparkline(spark_vals), ri, 6)

            ch = QPushButton("›")
            ch.setFixedSize(24, 24)
            ch.setCursor(Qt.CursorShape.PointingHandCursor)
            ch.setStyleSheet(
                f"QPushButton {{ background:transparent; color:{MUTED}; "
                f"border:none; font-size:13pt; }} "
                f"QPushButton:hover {{ color:{ACCENT}; }}")
            ch.clicked.connect(
                lambda _, cid=c['id']: self.open_company.emit(cid))
            g.addWidget(ch, ri, 7)

        g.setColumnStretch(0, 3)
        lay.addLayout(g)
        # the grid's text metrics must not dictate the page's minimum
        # width (they'd push the right rail off-screen)
        card.setMinimumWidth(460)
        card.setSizePolicy(QSizePolicy.Policy.Ignored,
                           QSizePolicy.Policy.Preferred)
        return card

    def _sector_donut_card(self, companies, co_met):
        """Allocation by Sector: donut + side legend. Same bucketing as
        the old sector chart (invested capital, top 6 + Other) so the
        figures are identical."""
        from ui.styles import BORDER_SOFT, RADIUS

        card = QFrame()
        card.setObjectName("SectorCard")
        card.setStyleSheet(
            f"QFrame#SectorCard {{ background:{CARD}; border:1px solid "
            f"{BORDER_SOFT}; border-radius:{RADIUS}px; }}")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(8)
        title = QLabel("Allocation by Sector")
        title.setStyleSheet(f"font-weight:bold; font-size:11pt; "
                            f"color:{TEXT}; border:none;")
        lay.addWidget(title)

        by_sector: dict[str, float] = {}
        for c in companies:
            sector = (c.get('sector') or '').strip() or 'Other'
            by_sector[sector] = (by_sector.get(sector, 0)
                                 + co_met[c['id']]['total_invested'])
        by_sector = {k: v for k, v in by_sector.items() if v > 0}
        if not by_sector:
            e = QLabel("No sector data yet.")
            e.setStyleSheet(f"color:{MUTED}; border:none;")
            lay.addWidget(e)
            return card

        ranked = sorted(by_sector.items(), key=lambda kv: kv[1],
                        reverse=True)
        merged = dict(ranked[:6])
        if ranked[6:]:
            merged['Other'] = (merged.get('Other', 0)
                               + sum(v for _, v in ranked[6:]))
        pairs = sorted(((k, v) for k, v in merged.items()
                        if k != 'Other'),
                       key=lambda kv: kv[1], reverse=True)
        if 'Other' in merged:
            pairs.append(('Other', merged['Other']))
        names = [k for k, _ in pairs]
        values = [v for _, v in pairs]
        total = sum(values)
        palette = ['#3B82F6', '#8B5CF6', '#0EA5E9', '#10B981',
                   '#F59E0B', '#EC4899']
        colors = [palette[i % len(palette)] for i in range(len(names))]
        if names[-1] == 'Other':
            colors[-1] = '#64748B'

        row = QHBoxLayout()
        row.setSpacing(12)
        if HAS_MPL:
            fig = Figure(figsize=(2.3, 2.3), facecolor=CARD)
            ax = fig.add_subplot(111)
            ax.set_facecolor(CARD)
            ax.pie(values, colors=colors, startangle=90,
                   counterclock=False,
                   wedgeprops={'width': 0.36, 'edgecolor': CARD,
                               'linewidth': 2})
            fig.tight_layout(pad=0.2)
            canvas = FigureCanvasQTAgg(fig)
            canvas.setFixedSize(170, 170)
            row.addWidget(canvas)
        legend = QVBoxLayout()
        legend.setSpacing(6)
        legend.addStretch()
        for n, v, col in zip(names, values, colors):
            lr = QHBoxLayout()
            lr.setSpacing(8)
            dot = QLabel("●")
            dot.setStyleSheet(f"color:{col}; font-size:9pt; border:none;")
            lr.addWidget(dot)
            nl = QLabel(n)
            nl.setStyleSheet(f"color:{TEXT}; font-size:9pt; border:none;")
            lr.addWidget(nl, 1)
            pl = QLabel(f"{v / total * 100:.0f}%")
            pl.setStyleSheet(f"color:{MUTED}; font-size:9pt; "
                             f"border:none;")
            lr.addWidget(pl)
            legend.addLayout(lr)
        legend.addStretch()
        row.addLayout(legend, 1)
        lay.addLayout(row)
        card.setMinimumWidth(280)
        card.setSizePolicy(QSizePolicy.Policy.Ignored,
                           QSizePolicy.Policy.Preferred)
        return card

    def _build_health_section(self, companies, co_met, rounds_by, sym):
        from datetime import date, timedelta

        total_invested   = sum(co_met[c['id']]['total_invested'] for c in companies)
        known            = [c for c in companies if c.get('current_valuation') is not None]
        invested_of_known = sum(co_met[c['id']]['total_invested'] for c in known)

        coverage_pct = invested_of_known / total_invested * 100 if total_invested else 0
        coverage_conf = "high" if coverage_pct >= 70 else ("medium" if coverage_pct >= 40 else "low")
        cov_color    = GREEN if coverage_pct >= 70 else (AMBER if coverage_pct >= 40 else RED)

        sorted_co   = sorted(companies, key=lambda c: co_met[c['id']]['total_invested'], reverse=True)
        top3_inv    = sum(co_met[c['id']]['total_invested'] for c in sorted_co[:3])
        conc_pct    = top3_inv / total_invested * 100 if total_invested else 0
        conc_label  = "high" if conc_pct >= 60 else ("medium" if conc_pct >= 40 else "low")
        conc_color  = RED if conc_label == "high" else (AMBER if conc_label == "medium" else GREEN)

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
        win_color   = RED if winners_dep > 80 else (AMBER if winners_dep > 60 else GREEN)

        from ui.styles import BORDER_SOFT, RADIUS
        frame = QFrame()
        frame.setObjectName("HealthCard")
        frame.setStyleSheet(
            f"QFrame#HealthCard {{ background:{CARD}; border:1px solid "
            f"{BORDER_SOFT}; border-radius:{RADIUS}px; }}"
        )
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(10)

        hdr = QLabel(f"<span style='color:{ACCENT};'>⌁</span>&nbsp; "
                     f"Portfolio Health")
        hdr.setStyleSheet(f"font-weight:bold; font-size:11pt; color:{TEXT}; border:none;")
        lay.addWidget(hdr)

        badge_row = QHBoxLayout()
        badge_row.setSpacing(12)
        badge_row.addWidget(_Card("Valuation coverage", f"{coverage_pct:.0f}%",
                                  f"{coverage_conf} confidence", cov_color,
            bar=(coverage_pct / 100, cov_color),
            tooltip="What percentage of your invested capital has a current valuation.\n"
                    "High (70%+) = good picture of portfolio value.\n"
                    "Low = many companies unvalued, so total figures are estimates."))
        badge_row.addWidget(_Card("Concentration risk", conc_label.capitalize(),
                                  f"Top 3 = {conc_pct:.0f}% of capital", conc_color,
            bar=(conc_pct / 100, conc_color),
            tooltip="How much of your total invested capital is concentrated in just the top 3 companies.\n"
                    "High (60%+) = if those companies struggle, the whole portfolio is affected.\n"
                    "Low = capital spread more evenly, less risk from any single company."))
        badge_row.addWidget(_Card("Loss exposure", f"{sym} {loss_exp:,.0f}",
                                  "in holdings below 0.5× MOIC", loss_color,
            bar=((loss_exp / total_invested) if total_invested else 0,
                 loss_color),
            tooltip="Total capital invested in companies currently worth less than half what was put in.\n"
                    "MOIC below 0.5× means you'd get back less than 50 cents per krona invested.\n"
                    "Zero is best — means no companies are deeply underwater."))
        badge_row.addWidget(_Card("Winners dependency", f"{winners_dep:.0f}%",
                                  "of gains from top 3 holdings", win_color,
            bar=(winners_dep / 100, win_color),
            tooltip="How much of the portfolio's total profit comes from just the top 3 best performers.\n"
                    "Very high (80%+) = the portfolio's success depends heavily on a few companies.\n"
                    "Lower = gains are spread across more companies, a healthier sign."))
        lay.addLayout(badge_row)

        # (top-5 table and the stale list both moved out — phases 5/6)
        return frame

    # ── Right rail (phase 6) ─────────────────────────────────────────────────

    _ACTIVITY_LABELS = {
        ('insert', 'companies'): ('＋', 'New company'),
        ('update', 'companies'): ('✎', 'Updated company'),
        ('delete', 'companies'): ('✕', 'Removed company'),
        ('insert', 'valuations'): ('↗', 'Added valuation'),
        ('update', 'valuations'): ('✎', 'Updated valuation'),
        ('delete', 'valuations'): ('✕', 'Removed valuation'),
        ('insert', 'funding_rounds'): ('＋', 'Added round'),
        ('insert', 'cashflows'): ('◈', 'Added cash flow'),
        ('insert', 'company_updates'): ('✎', 'Journal entry'),
        ('migration', 'schema'): ('⚙', 'Schema upgraded'),
    }

    def _rail_card(self, title, badge=None):
        from ui.styles import AMBER_SOFT, BORDER_SOFT, RADIUS
        card = QFrame()
        card.setObjectName("RailCard")
        card.setStyleSheet(
            f"QFrame#RailCard {{ background:{CARD}; border:1px solid "
            f"{BORDER_SOFT}; border-radius:{RADIUS}px; }}")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 13, 16, 14)
        lay.setSpacing(9)
        head = QHBoxLayout()
        t = QLabel(title)
        t.setStyleSheet(f"font-weight:bold; font-size:10.5pt; "
                        f"color:{TEXT}; border:none;")
        head.addWidget(t)
        if badge is not None:
            b = QLabel(str(badge))
            b.setStyleSheet(f"background:{AMBER_SOFT}; color:{AMBER}; "
                            f"border-radius:8px; padding:1px 8px; "
                            f"font-size:8pt; font-weight:700; "
                            f"border:none;")
            head.addWidget(b)
        head.addStretch()
        lay.addLayout(head)
        return card, lay, head

    def _build_rail_cards(self, all_cos, known, rounds_by, sym):
        from ui.styles import ACCENT_LITE, AMBER_SOFT
        names = {c['id']: c['name'] for c in all_cos}

        # ── Recent Activity ────────────────────────────────────────────
        card, lay, head = self._rail_card("Recent Activity")
        va = QPushButton("View all")
        va.setCursor(Qt.CursorShape.PointingHandCursor)
        va.setStyleSheet(
            f"QPushButton {{ background:transparent; color:{ACCENT}; "
            f"border:none; font-weight:600; font-size:8.5pt; }}")
        va.clicked.connect(self.show_history.emit)
        head.addWidget(va)
        events = [e for e in models.get_audit_log(limit=12)
                  if e.get('origin') != 'migration'][:4]
        if not events:
            e = QLabel("No activity recorded yet.")
            e.setStyleSheet(f"color:{MUTED}; font-size:9pt; border:none;")
            lay.addWidget(e)
        for ev in events:
            icon, label = self._ACTIVITY_LABELS.get(
                (ev['action'], ev['table_name']),
                ('•', f"{ev['action']} {ev['table_name']}"))
            row = QHBoxLayout()
            row.setSpacing(9)
            ic = QLabel(icon)
            ic.setFixedSize(26, 26)
            ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ic.setStyleSheet(f"background:{ACCENT_LITE}; color:{ACCENT}; "
                             f"border-radius:7px; font-size:10pt; "
                             f"border:none;")
            row.addWidget(ic)
            col = QVBoxLayout()
            col.setSpacing(0)
            l1 = QLabel(label)
            l1.setStyleSheet(f"color:{TEXT}; font-size:9pt; "
                             f"font-weight:600; border:none;")
            subject = names.get(ev.get('company_id'), '')
            l2 = QLabel(subject or '—')
            l2.setStyleSheet(f"color:{MUTED}; font-size:8.5pt; "
                             f"border:none;")
            col.addWidget(l1)
            col.addWidget(l2)
            row.addLayout(col, 1)
            try:
                from datetime import datetime
                d = datetime.fromisoformat(
                    ev['ts_utc'].replace('Z', '')).strftime('%b %d')
            except (ValueError, AttributeError):
                d = (ev.get('ts_utc') or '')[:10]
            dl = QLabel(d)
            dl.setStyleSheet(f"color:{MUTED}; font-size:8pt; "
                             f"border:none;")
            row.addWidget(dl)
            lay.addLayout(row)
        self._rail_lay.addWidget(card)

        # ── Quick Actions ──────────────────────────────────────────────
        card, lay, _head = self._rail_card("Quick Actions")
        for icon, label, key in (("＋", "Add Company", 'add'),
                                 ("⬇", "Import Data", 'import'),
                                 ("📄", "Generate Report", 'report'),
                                 ("⇄", "Compare Portfolios", 'compare')):
            b = QPushButton(f"{icon}   {label}")
            b.setObjectName("QuickBtn")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(
                f"QPushButton {{ background:{CARD_ALT}; color:{TEXT}; "
                f"border:1px solid rgba(255,255,255,0.06); "
                f"border-radius:8px; padding:9px 12px; "
                f"text-align:left; font-weight:600; font-size:9pt; }} "
                f"QPushButton:hover {{ background:{HOVER}; }}")
            b.clicked.connect(lambda _, k=key: self.quick_action.emit(k))
            lay.addWidget(b)
        self._rail_lay.addWidget(card)

        # ── Alerts & Reminders (same companies as the old stale list) ─
        stale = self._stale_companies(known, rounds_by)
        card, lay, _head = self._rail_card("Alerts & Reminders",
                                           badge=len(stale) or None)
        if not stale:
            ok = QLabel("✓  No alerts — all valuations are recent")
            ok.setStyleSheet(f"color:{GREEN}; font-size:9pt; "
                             f"border:none;")
            lay.addWidget(ok)
        for name in stale[:5]:
            row = QLabel(f"⚠  <b>{name}</b><br>"
                         f"<span style='color:{MUTED};'>Stale valuation "
                         f"(&gt;12 months)</span>")
            row.setStyleSheet(f"color:{AMBER}; font-size:8.5pt; "
                              f"border:none; background:{AMBER_SOFT}; "
                              f"border-radius:7px; padding:6px 9px;")
            lay.addWidget(row)
        if len(stale) > 5:
            more = QPushButton(f"View all alerts ({len(stale)})")
            more.setCursor(Qt.CursorShape.PointingHandCursor)
            more.setStyleSheet(
                f"QPushButton {{ background:transparent; "
                f"color:{ACCENT}; border:1px solid "
                f"rgba(255,255,255,0.08); border-radius:8px; "
                f"padding:7px; font-weight:600; font-size:8.5pt; }}")
            more.clicked.connect(lambda: self._show_all_alerts(stale))
            lay.addWidget(more)
        self._rail_lay.addWidget(card)
        self._rail_lay.addStretch()

    def _show_all_alerts(self, stale):
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(
            self, "Alerts & Reminders",
            "Stale valuations (not updated in 12+ months):\n\n"
            + "\n".join(f"⚠  {n}" for n in stale))

    def _stale_companies(self, known, rounds_by):
        """EXACTLY the list the old health-card panel showed: valued
        companies whose latest dated round is older than 12 months (or
        undated)."""
        from datetime import date, timedelta
        cutoff = (date.today() - timedelta(days=365)).isoformat()
        stale = []
        for c in known:
            rds = rounds_by.get(c['id'], [])
            dated = [r.get('date') or '' for r in rds if r.get('date')]
            last = max(dated) if dated else ''
            if not last or last < cutoff:
                stale.append(c['name'])
        return stale

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _clear(self):
        self._clear_layout(self._rail_lay)
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
