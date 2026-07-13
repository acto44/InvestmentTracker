import matplotlib
matplotlib.use('Agg')
import matplotlib.ticker
import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QSplitter, QWidget,
    QLabel, QPushButton, QCheckBox, QScrollArea, QTableWidget,
    QTableWidgetItem, QHeaderView, QLineEdit, QFrame, QMessageBox,
    QAbstractItemView
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor, QBrush

import models
from ui.styles import (
    ACCENT, MUTED, TEXT, BG, CARD, BORDER, GREEN, RED, HEADER_BG, HEADER_FG,
    GREEN_SOFT, RED_SOFT, ACCENT_LITE,
)

_COLORS = ['#3B82F6', '#4ADE80', '#F87171', '#FBBF24', '#A78BFA',
           '#22D3EE', '#F472B6', '#A3E635', '#FB923C', '#818CF8']


def _style_axes(ax):
    """Apply the dark theme to a matplotlib axes."""
    ax.set_facecolor(CARD)
    ax.tick_params(colors=MUTED, labelcolor=MUTED)
    for spine in ax.spines.values():
        spine.set_color(BORDER)
    ax.xaxis.label.set_color(MUTED)
    ax.yaxis.label.set_color(MUTED)
    ax.title.set_color(TEXT)


def _shorten(name, n=18):
    return name[:n] + '…' if len(name) > n else name


class CompareDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Compare Companies")
        self.setMinimumSize(1200, 760)
        self.resize(1440, 860)
        self._checkboxes: list[tuple[QCheckBox, int, str]] = []
        self._build()

    # ── Layout ───────────────────────────────────────────────────────────────

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        hdr = QLabel("Compare Companies")
        f = QFont(); f.setBold(True); f.setPointSize(14)
        hdr.setFont(f)
        root.addWidget(hdr)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ── LEFT: picker ─────────────────────────────────────────────────────
        left = QWidget()
        left.setFixedWidth(290)
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 10, 0)
        ll.setSpacing(6)

        lbl = QLabel("Select companies to compare:")
        lbl.setStyleSheet(f"color: {MUTED}; font-size: 9pt;")
        ll.addWidget(lbl)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search companies…")
        self._search.textChanged.connect(self._filter_list)
        ll.addWidget(self._search)

        qrow = QHBoxLayout()
        for text, fn in [("All", self._select_all), ("None", self._clear_all)]:
            b = QPushButton(text)
            b.setFixedHeight(26)
            if text == "None":
                b.setStyleSheet(f"background: {BORDER}; color: {TEXT};")
            b.clicked.connect(fn)
            qrow.addWidget(b)
        ll.addLayout(qrow)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {BORDER};")
        ll.addWidget(sep)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._list_w = QWidget()
        self._list_lay = QVBoxLayout(self._list_w)
        self._list_lay.setSpacing(2)
        self._list_lay.setContentsMargins(2, 2, 2, 2)
        self._list_lay.addStretch()
        scroll.setWidget(self._list_w)
        ll.addWidget(scroll, 1)

        cmp_btn = QPushButton("Compare Selected →")
        cmp_btn.setFixedHeight(36)
        cmp_btn.clicked.connect(self._do_compare)
        ll.addWidget(cmp_btn)

        splitter.addWidget(left)

        # ── RIGHT: results ───────────────────────────────────────────────────
        self._right = QWidget()
        self._right_lay = QVBoxLayout(self._right)
        self._right_lay.setContentsMargins(8, 0, 0, 0)
        self._right_lay.setSpacing(0)
        self._show_placeholder()
        splitter.addWidget(self._right)

        splitter.setSizes([290, 1150])
        root.addWidget(splitter, 1)

        close_btn = QPushButton("Close")
        close_btn.setStyleSheet(f"background: {BORDER}; color: {TEXT};")
        close_btn.clicked.connect(self.accept)
        brow = QHBoxLayout()
        brow.addStretch()
        brow.addWidget(close_btn)
        root.addLayout(brow)

        self._populate_list()

    def _show_placeholder(self):
        ph = QLabel("Select 2 or more companies and click  Compare Selected →")
        ph.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ph.setStyleSheet(f"color: {MUTED}; font-size: 11pt; padding: 60px;")
        self._right_lay.addWidget(ph)

    # ── Company list ─────────────────────────────────────────────────────────

    def _populate_list(self):
        while self._list_lay.count() > 1:
            item = self._list_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._checkboxes = []
        by_entity: dict[str, list] = {}
        for c in models.get_all_companies():
            key = c.get('entity') or 'Other'
            by_entity.setdefault(key, []).append(c)

        insert_pos = 0
        for entity_name in sorted(by_entity):
            lbl = QLabel(entity_name)
            lbl.setStyleSheet(
                f"color: {ACCENT}; font-weight: bold; font-size: 9pt; "
                f"margin-top: 8px; padding: 2px 0;"
            )
            self._list_lay.insertWidget(insert_pos, lbl)
            insert_pos += 1

            for c in sorted(by_entity[entity_name], key=lambda x: x['name']):
                cb = QCheckBox(c['name'])
                cb.setProperty('company_id', c['id'])
                self._list_lay.insertWidget(insert_pos, cb)
                insert_pos += 1
                self._checkboxes.append((cb, c['id'], c['name']))

    def _filter_list(self, text):
        t = text.lower()
        for cb, _, name in self._checkboxes:
            cb.setVisible(not t or t in name.lower())

    def _select_all(self):
        for cb, _, _ in self._checkboxes:
            if cb.isVisible():
                cb.setChecked(True)

    def _clear_all(self):
        for cb, _, _ in self._checkboxes:
            cb.setChecked(False)

    # ── Compare ──────────────────────────────────────────────────────────────

    def _do_compare(self):
        selected = [(cid, name) for cb, cid, name in self._checkboxes if cb.isChecked()]
        if len(selected) < 2:
            QMessageBox.information(self, "Compare",
                "Please select at least 2 companies to compare.")
            return
        self._show_comparison(selected)

    def _gather(self, cid: int, name: str) -> dict:
        c = models.get_company(cid)
        rounds = models.get_rounds(cid)
        invested = sum((r.get('amount_invested') or 0) for r in rounds)
        cur_val = c.get('current_valuation') or 0
        moic = (cur_val / invested) if invested > 0 else None
        gain = (cur_val - invested) if invested > 0 else None

        # Year amounts: round_name starts with the year (e.g. "2021")
        year_amounts: dict[int, float] = {}
        for r in rounds:
            rname = (r.get('round_name') or '')[:4]
            if rname.isdigit():
                yr = int(rname)
                year_amounts[yr] = year_amounts.get(yr, 0) + (r.get('amount_invested') or 0)

        # Parse structured notes
        notes = c.get('notes') or ''
        status, exit_yr, target_mult, potential = 'Active', None, None, None
        for line in notes.splitlines():
            if line.startswith('Status:'):
                status = line[7:].strip()
            elif line.startswith('Exit year:'):
                exit_yr = line[10:].strip()
            elif line.startswith('Target multiple:'):
                try:
                    target_mult = float(line[16:].strip().rstrip('×'))
                except ValueError:
                    pass
            elif line.startswith('Potential at exit:'):
                try:
                    potential = float(line[18:].strip())
                except ValueError:
                    pass

        return dict(
            id=cid, name=name,
            entity=c.get('entity') or '—',
            sector=c.get('sector') or '—',
            country=c.get('country') or '—',
            status=status,
            invested=invested,
            cur_val=cur_val,
            moic=moic,
            gain=gain,
            exit_yr=exit_yr or '—',
            target_mult=target_mult,
            potential=potential,
            year_amounts=year_amounts,
            n_rounds=len(rounds),
        )

    # ── Results panel ────────────────────────────────────────────────────────

    def _show_comparison(self, selected: list[tuple[int, str]]):
        self._clear_right()

        data = [self._gather(cid, name) for cid, name in selected]

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        vlay = QVBoxLayout(content)
        vlay.setSpacing(18)
        vlay.setContentsMargins(4, 4, 8, 16)

        # ── section: metrics table ────────────────────────────────────────────
        self._section_label(vlay, f"Performance Metrics — {len(data)} companies")
        vlay.addWidget(self._metrics_table(data))

        # ── section: invested vs valuation ───────────────────────────────────
        self._section_label(vlay, "Invested vs Current Valuation  &  MOIC")
        vlay.addWidget(self._valuation_chart(data))

        # ── section: year investments ─────────────────────────────────────────
        all_years = sorted({yr for d in data for yr in d['year_amounts']})
        if all_years:
            self._section_label(vlay, "Annual Investments by Company (TKR)")
            vlay.addWidget(self._year_chart(data, all_years))

        vlay.addStretch()
        scroll.setWidget(content)
        self._right_lay.addWidget(scroll)

    def _clear_right(self):
        while self._right_lay.count():
            item = self._right_lay.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    @staticmethod
    def _section_label(layout, text: str):
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"font-weight: bold; font-size: 11pt; color: {TEXT}; "
            f"border-bottom: 2px solid {ACCENT}; padding-bottom: 4px;"
        )
        layout.addWidget(lbl)

    # ── Metrics table ────────────────────────────────────────────────────────

    def _metrics_table(self, data: list[dict]) -> QTableWidget:
        def fmt_tkr(v):
            return f"TKR {v:,.0f}" if v else '—'

        def fmt_gain(d):
            g = d['gain']
            if g is None:
                return '—'
            return (f"+TKR {g:,.0f}" if g >= 0 else f"TKR {g:,.0f}")

        def fmt_moic(d):
            return f"{d['moic']:.2f}×" if d['moic'] is not None else '—'

        ROWS: list[tuple[str, callable, str | None, bool]] = [
            # (label, value_fn, best_strategy, higher_is_better)
            ("Portfolio",          lambda d: d['entity'],              None,   None),
            ("Sector",             lambda d: d['sector'],              None,   None),
            ("Country",            lambda d: d['country'],             None,   None),
            ("Status",             lambda d: d['status'],              None,   None),
            ("Total Invested",     lambda d: fmt_tkr(d['invested']),   'num',  True),
            ("Current Valuation",  lambda d: fmt_tkr(d['cur_val']),    'num',  True),
            ("Gain / Loss",        fmt_gain,                           'gain', True),
            ("MOIC",               fmt_moic,                           'moic', True),
            ("# Rounds",           lambda d: str(d['n_rounds']),       'int',  True),
            ("Exit Year",          lambda d: d['exit_yr'],             None,   None),
            ("Target Multiple",    lambda d: f"{d['target_mult']:.1f}×" if d['target_mult'] else '—',
                                                                        None,   None),
            ("Potential at Exit",  lambda d: fmt_tkr(d['potential']),  'num',  True),
        ]

        n_cols = 1 + len(data)
        tbl = QTableWidget(len(ROWS), n_cols)
        tbl.setAlternatingRowColors(True)
        tbl.verticalHeader().hide()
        tbl.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        tbl.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        tbl.setColumnWidth(0, 160)
        for i in range(1, n_cols):
            tbl.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
        tbl.setHorizontalHeaderLabels(["Metric"] + [d['name'] for d in data])
        tbl.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)

        for row_i, (label, val_fn, strategy, higher) in enumerate(ROWS):
            # Metric name cell
            name_item = QTableWidgetItem(label)
            name_item.setFont(QFont('Segoe UI', 9, QFont.Weight.Bold))
            name_item.setBackground(QBrush(QColor(HEADER_BG)))
            name_item.setForeground(QBrush(QColor(HEADER_FG)))
            name_item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            tbl.setItem(row_i, 0, name_item)

            values = [val_fn(d) for d in data]

            # Determine best index
            best_idx = None
            if strategy == 'num' and higher:
                nums = [d['cur_val'] if label == "Current Valuation"
                        else d['invested'] if label == "Total Invested"
                        else (d['potential'] or 0)
                        for d in data]
                if any(n > 0 for n in nums):
                    best_idx = max(range(len(nums)), key=lambda i: nums[i])
            elif strategy == 'gain':
                gains = [(d['gain'] or 0) for d in data]
                if any(g != 0 for g in gains):
                    best_idx = max(range(len(gains)), key=lambda i: gains[i])
            elif strategy == 'moic':
                moics = [(d['moic'] or 0) for d in data]
                if any(m > 0 for m in moics):
                    best_idx = max(range(len(moics)), key=lambda i: moics[i])
            elif strategy == 'int':
                ints = [int(v) for v in values]
                best_idx = max(range(len(ints)), key=lambda i: ints[i])

            for col_i, (val, d) in enumerate(zip(values, data)):
                cell = QTableWidgetItem(val)
                cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

                # Base colour coding
                if label == "Status":
                    if val == "Exited":
                        cell.setBackground(QBrush(QColor(GREEN_SOFT)))
                    elif val == "Bankrupt":
                        cell.setBackground(QBrush(QColor(RED_SOFT)))
                elif label == "MOIC" and d['moic'] is not None:
                    if d['moic'] >= 2.0:
                        cell.setBackground(QBrush(QColor(GREEN_SOFT)))
                        cell.setForeground(QBrush(QColor(GREEN)))
                    elif d['moic'] >= 1.0:
                        cell.setForeground(QBrush(QColor(GREEN)))
                    else:
                        cell.setBackground(QBrush(QColor(RED_SOFT)))
                        cell.setForeground(QBrush(QColor(RED)))
                elif label == "Gain / Loss" and d['gain'] is not None:
                    if d['gain'] >= 0:
                        cell.setForeground(QBrush(QColor(GREEN)))
                    else:
                        cell.setBackground(QBrush(QColor(RED_SOFT)))
                        cell.setForeground(QBrush(QColor(RED)))

                # Best-in-class badge
                if best_idx == col_i:
                    bf = QFont('Segoe UI', 9)
                    bf.setBold(True)
                    cell.setFont(bf)
                    if label not in ("Gain / Loss", "MOIC", "Status"):
                        cell.setBackground(QBrush(QColor(ACCENT_LITE)))

                tbl.setItem(row_i, col_i + 1, cell)

        tbl.setMinimumHeight(len(ROWS) * 30 + 36)
        tbl.setMaximumHeight(len(ROWS) * 30 + 36)
        return tbl

    # ── Charts ───────────────────────────────────────────────────────────────

    def _valuation_chart(self, data: list[dict]) -> FigureCanvasQTAgg:
        fig = Figure(figsize=(11, 3.8), facecolor=CARD, dpi=96)
        canvas = FigureCanvasQTAgg(fig)

        names = [_shorten(d['name']) for d in data]
        x = np.arange(len(data))
        w = 0.35

        # Left: grouped bar — invested vs current value
        ax1 = fig.add_subplot(1, 2, 1)
        _style_axes(ax1)
        ax1.bar(x - w / 2, [d['invested'] for d in data], w,
                label='Invested', color='#93C5FD', edgecolor=CARD, zorder=3)
        ax1.bar(x + w / 2, [d['cur_val'] for d in data], w,
                label='Current Val', color=ACCENT, edgecolor=CARD, zorder=3)
        ax1.set_title('Invested vs Current Valuation', fontweight='bold', fontsize=9, pad=8)
        ax1.set_xticks(x)
        ax1.set_xticklabels(names, rotation=35, ha='right', fontsize=7)
        ax1.set_ylabel('TKR', fontsize=8)
        ax1.legend(fontsize=7, labelcolor=MUTED, frameon=False)
        ax1.tick_params(axis='y', labelsize=7)
        ax1.yaxis.set_major_formatter(
            matplotlib.ticker.FuncFormatter(
                lambda v, _: f'{v/1000:.0f}k' if v >= 1000 else f'{v:.0f}'))
        ax1.grid(axis='y', alpha=0.3, zorder=0)
        ax1.spines['top'].set_visible(False)
        ax1.spines['right'].set_visible(False)

        # Right: MOIC bars
        ax2 = fig.add_subplot(1, 2, 2)
        _style_axes(ax2)
        moics = [d['moic'] if d['moic'] is not None else 0 for d in data]
        bar_colors = [GREEN if m >= 1 else RED for m in moics]
        bars = ax2.bar(x, moics, color=bar_colors, edgecolor=CARD, zorder=3)
        ax2.axhline(1.0, color=MUTED, linestyle='--', linewidth=1.2, alpha=0.7, zorder=2)
        # Value labels on bars
        for bar, val in zip(bars, moics):
            if val > 0:
                ax2.text(bar.get_x() + bar.get_width() / 2,
                         bar.get_height() + max(moics) * 0.02,
                         f'{val:.2f}×', ha='center', va='bottom', fontsize=7,
                         fontweight='bold', color=TEXT)
        ax2.set_title('MOIC (Multiple on Invested Capital)', fontweight='bold', fontsize=9, pad=8)
        ax2.set_xticks(x)
        ax2.set_xticklabels(names, rotation=35, ha='right', fontsize=7)
        ax2.set_ylabel('×', fontsize=8)
        ax2.tick_params(axis='y', labelsize=7)
        ax2.grid(axis='y', alpha=0.3, zorder=0)
        ax2.spines['top'].set_visible(False)
        ax2.spines['right'].set_visible(False)

        fig.tight_layout(pad=2.5)
        canvas.setMinimumHeight(290)
        return canvas

    def _year_chart(self, data: list[dict], all_years: list[int]) -> FigureCanvasQTAgg:
        fig = Figure(figsize=(11, 3.4), facecolor=CARD, dpi=96)
        canvas = FigureCanvasQTAgg(fig)
        ax = fig.add_subplot(1, 1, 1)
        _style_axes(ax)

        n = len(data)
        x = np.arange(len(all_years))
        w = min(0.8 / n, 0.25)

        for i, d in enumerate(data):
            vals = [d['year_amounts'].get(yr, 0) for yr in all_years]
            offset = (i - n / 2 + 0.5) * w
            label = _shorten(d['name'], 14)
            ax.bar(x + offset, vals, w, label=label,
                   color=_COLORS[i % len(_COLORS)], edgecolor=CARD, zorder=3)

        ax.set_title('Annual Investments by Company (TKR)', fontweight='bold', fontsize=9, pad=8)
        ax.set_xticks(x)
        ax.set_xticklabels([str(y) for y in all_years], fontsize=8)
        ax.set_ylabel('TKR', fontsize=8)
        ax.legend(fontsize=7, ncol=min(5, n), labelcolor=MUTED, frameon=False)
        ax.tick_params(axis='y', labelsize=7)
        ax.yaxis.set_major_formatter(
            matplotlib.ticker.FuncFormatter(
                lambda v, _: f'{v/1000:.0f}k' if v >= 1000 else f'{v:.0f}'))
        ax.grid(axis='y', alpha=0.3, zorder=0)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

        fig.tight_layout(pad=1.8)
        canvas.setMinimumHeight(240)
        return canvas
