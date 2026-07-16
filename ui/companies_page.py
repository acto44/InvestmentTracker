"""Companies page (session 11 shell): a flat, sortable table of every
company — read-only composition of existing data, zero new logic.
Double-click (or the chevron column) opens the company in the Portfolio
view via the open_company signal."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QFrame, QLabel, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

import metrics as m
import models
from ui.styles import GREEN, GREEN_SOFT, MUTED, RED, RED_SOFT

HEADERS = ["Company", "Portfolio", "Type", "Sector", "Invested",
           "Current Value", "Gain / Loss", "MOIC"]
NUMERIC_FROM = 4


class CompaniesPage(QWidget):
    open_company = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 24)
        lay.setSpacing(16)
        title = QLabel("Companies")
        title.setStyleSheet("font-size:14pt; font-weight:700;")
        lay.addWidget(title)
        self._hint = QLabel("Double-click a row to open the company.")
        self._hint.setStyleSheet(f"color:{MUTED}; font-size:9pt;")
        lay.addWidget(self._hint)
        self._table_slot = QVBoxLayout()
        lay.addLayout(self._table_slot, 1)
        self._tbl = None

    def refresh(self):
        if self._tbl is not None:
            self._tbl.setParent(None)
            self._tbl.deleteLater()
        sym = models.get_setting('currency', 'TKR')
        companies = models.get_all_companies()
        flows_by = models.get_cashflows_by_company()

        tbl = QTableWidget(len(companies), len(HEADERS))
        tbl.setHorizontalHeaderLabels(HEADERS)
        tbl.setAlternatingRowColors(True)
        tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        tbl.verticalHeader().setVisible(False)
        tbl.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        tbl.horizontalHeader().setStretchLastSection(True)
        tbl.setFrameShape(QFrame.Shape.NoFrame)
        right = Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight
        for ci in range(NUMERIC_FROM, len(HEADERS)):
            it = tbl.horizontalHeaderItem(ci)
            if it:
                it.setTextAlignment(right)

        rows = sorted(companies, key=lambda c: c['name'].lower())
        for ri, c in enumerate(rows):
            met = m.company_metrics_for(
                c, models.get_rounds(c['id']),
                flows_by.get(c['id'], []))
            cur = met.get('current_value')
            gain = (cur - met['total_invested']) if cur is not None else None
            notes = (c.get('notes') or '').lower()

            def item(txt, color=None, numeric=False, cid=None):
                it = QTableWidgetItem(str(txt))
                if numeric:
                    it.setTextAlignment(right)
                if color:
                    it.setForeground(QColor(color))
                if cid is not None:
                    it.setData(Qt.ItemDataRole.UserRole, cid)
                return it

            name_item = item(c['name'], cid=c['id'])
            if 'bankrupt' in notes:
                name_item.setBackground(QColor(RED_SOFT))
            elif 'status: exited' in notes:
                name_item.setBackground(QColor(GREEN_SOFT))

            gain_str, gain_col = "—", None
            if gain is not None:
                gain_str = f"{'+' if gain >= 0 else '−'}{sym} {abs(gain):,.0f}"
                gain_col = GREEN if gain >= 0 else RED
            moic = met.get('moic')

            tbl.setItem(ri, 0, name_item)
            tbl.setItem(ri, 1, item(c.get('entity') or ''))
            tbl.setItem(ri, 2, item(c.get('investment_type') or ''))
            tbl.setItem(ri, 3, item(c.get('sector') or ''))
            tbl.setItem(ri, 4, item(f"{sym} {met['total_invested']:,.0f}",
                                    numeric=True))
            tbl.setItem(ri, 5, item(
                f"{sym} {cur:,.0f}" if cur is not None else "—",
                None if cur else MUTED, numeric=True))
            tbl.setItem(ri, 6, item(gain_str, gain_col, numeric=True))
            tbl.setItem(ri, 7, item(
                f"{moic:.2f}×" if moic is not None else "n/a",
                numeric=True))

        # sorting only AFTER the fill — enabling it first makes every
        # setItem re-sort mid-fill and cells land in the wrong rows
        tbl.setSortingEnabled(True)
        tbl.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        tbl.resizeColumnsToContents()
        tbl.itemDoubleClicked.connect(self._open)
        self._tbl = tbl
        self._table_slot.addWidget(tbl)

    def _open(self, item):
        cid = self._tbl.item(item.row(), 0).data(Qt.ItemDataRole.UserRole)
        if cid is not None:
            self.open_company.emit(int(cid))
