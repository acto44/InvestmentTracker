"""Read-only audit history view (CLAUDE.md: the audit trail is
append-only — this dialog deliberately offers no edit affordances).

Opened globally from the Tools menu, or filtered per company from the
company detail panel. Timestamps are stored UTC and shown in local time.
"""

from datetime import datetime, timezone

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QHeaderView, QPushButton,
)
from PyQt6.QtCore import Qt

import models
from ui.styles import MUTED

ACTION_LABELS = {'insert': 'Added', 'update': 'Changed',
                 'delete': 'Deleted', 'migration': 'Schema migration'}
TABLE_LABELS = {'companies': 'Company', 'funding_rounds': 'Round',
                'valuations': 'Valuation', 'schema': 'Database'}


def _local_time(ts_utc: str) -> str:
    try:
        dt = datetime.strptime(ts_utc, '%Y-%m-%dT%H:%M:%SZ')
        return dt.replace(tzinfo=timezone.utc).astimezone() \
                 .strftime('%Y-%m-%d %H:%M')
    except Exception:
        return ts_utc


def _summary(entry: dict) -> str:
    parts = []
    for ch in entry.get('changes', [])[:6]:
        f, old, new = ch.get('field'), ch.get('old'), ch.get('new')
        if entry['action'] == 'insert':
            parts.append(f"{f} = {new}")
        elif entry['action'] == 'delete':
            parts.append(f"{f} was {old}")
        else:
            parts.append(f"{f}: {old} → {new}")
    more = len(entry.get('changes', [])) - 6
    if more > 0:
        parts.append(f'… +{more} more')
    return '; '.join(str(p) for p in parts)


class HistoryDialog(QDialog):
    def __init__(self, parent=None, company_id=None):
        super().__init__(parent)
        self._cid = company_id
        title = "Change History"
        if company_id:
            c = models.get_company(company_id)
            if c:
                title += f" — {c['name']}"
        self.setWindowTitle(title)
        self.resize(860, 520)

        layout = QVBoxLayout(self)
        head = QLabel(
            "Every financially meaningful change is recorded here "
            "automatically. This log is append-only — it cannot be "
            "edited, by design.")
        head.setWordWrap(True)
        head.setStyleSheet(f"color:{MUTED}; font-size:9pt;")
        layout.addWidget(head)

        entries = models.get_audit_log(company_id=company_id, limit=500)
        tbl = QTableWidget(len(entries), 4)
        tbl.setHorizontalHeaderLabels(["Time", "What", "Action", "Change"])
        tbl.verticalHeader().setVisible(False)
        tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        tbl.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        tbl.setWordWrap(False)
        for i, e in enumerate(entries):
            cells = [
                _local_time(e['ts_utc']),
                TABLE_LABELS.get(e['table_name'], e['table_name']),
                ACTION_LABELS.get(e['action'], e['action']),
                _summary(e),
            ]
            for col, text in enumerate(cells):
                item = QTableWidgetItem(str(text))
                if col == 3:
                    item.setToolTip(str(text))
                tbl.setItem(i, col, item)
        tbl.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(tbl)

        row = QHBoxLayout()
        row.addStretch()
        n = QLabel(f"{len(entries)} entr{'y' if len(entries) == 1 else 'ies'}"
                   f" (newest first, showing up to 500)")
        n.setStyleSheet(f"color:{MUTED}; font-size:9pt;")
        row.addWidget(n)
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        row.addWidget(close)
        layout.addLayout(row)
