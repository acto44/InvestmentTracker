"""Transactions page (session 11 shell): every cash flow in the ledger,
newest first — a read-only global view of the cashflows table through
the existing accessors and the ONE sign convention
(metrics.signed_amount). Zero new logic."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QFrame, QLabel, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

import metrics
import models
from reporting.builder import FLOW_LABELS
from ui.styles import GREEN, MUTED, RED

HEADERS = ["Date", "Company", "Type", "Amount", "Note"]


class TransactionsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 24)
        lay.setSpacing(16)
        title = QLabel("Transactions")
        title.setStyleSheet("font-size:14pt; font-weight:700;")
        lay.addWidget(title)
        self._summary = QLabel("")
        self._summary.setStyleSheet(f"color:{MUTED}; font-size:9pt;")
        lay.addWidget(self._summary)
        self._table_slot = QVBoxLayout()
        lay.addLayout(self._table_slot, 1)
        self._tbl = None

    def refresh(self):
        if self._tbl is not None:
            self._tbl.setParent(None)
            self._tbl.deleteLater()
        sym = models.get_setting('currency', 'TKR')
        names = {c['id']: c['name'] for c in models.get_all_companies()}
        flows = []
        for cid, rows in models.get_cashflows_by_company().items():
            for f in rows:
                flows.append((names.get(cid, '?'), f))
        flows.sort(key=lambda x: (x[1].get('date') or '', x[1]['id']),
                   reverse=True)

        n_in = sum(1 for _, f in flows
                   if f['type'] in metrics.INFLOW_TYPES)
        self._summary.setText(
            f"{len(flows)} recorded flows — {len(flows) - n_in} out, "
            f"{n_in} in. Amounts shown signed (money out is negative).")

        tbl = QTableWidget(len(flows), len(HEADERS))
        tbl.setHorizontalHeaderLabels(HEADERS)
        tbl.setAlternatingRowColors(True)
        tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        tbl.verticalHeader().setVisible(False)
        tbl.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        tbl.setSortingEnabled(True)
        tbl.horizontalHeader().setStretchLastSection(True)
        tbl.setFrameShape(QFrame.Shape.NoFrame)
        right = Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight
        hdr = tbl.horizontalHeaderItem(3)
        if hdr:
            hdr.setTextAlignment(right)

        for ri, (cname, f) in enumerate(flows):
            signed = metrics.signed_amount(f['type'], f['amount'])
            amt = QTableWidgetItem(
                f"{'+' if signed >= 0 else '−'}{sym} {abs(signed):,.0f}")
            amt.setTextAlignment(right)
            amt.setForeground(QColor(GREEN if signed >= 0 else RED))
            tbl.setItem(ri, 0, QTableWidgetItem(f.get('date') or '—'))
            tbl.setItem(ri, 1, QTableWidgetItem(cname))
            tbl.setItem(ri, 2, QTableWidgetItem(
                FLOW_LABELS.get(f['type'], f['type'])))
            tbl.setItem(ri, 3, amt)
            tbl.setItem(ri, 4, QTableWidgetItem(f.get('note') or ''))

        tbl.resizeColumnsToContents()
        self._tbl = tbl
        self._table_slot.addWidget(tbl)
