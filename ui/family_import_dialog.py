from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QPushButton, QDialogButtonBox, QMessageBox,
    QHeaderView, QFrame
)
from PyQt6.QtGui import QColor
from PyQt6.QtCore import Qt
import excel_io
from ui.styles import (
    GREEN, RED, MUTED, BORDER,
    GREEN_SOFT, RED_SOFT, INFO_BG, INFO_BORDER,
)


class FamilyImportDialog(QDialog):
    def __init__(self, parent=None, path=''):
        super().__init__(parent)
        self.setWindowTitle("Import — Family Fund Spreadsheet (KSEK)")
        self.setMinimumSize(980, 560)
        self._path   = path
        self._parsed = []
        self._build()
        self._load()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Info banner
        banner = QFrame()
        banner.setStyleSheet(
            f"background:{INFO_BG}; border:1px solid {INFO_BORDER}; border-radius:6px; padding:8px;"
        )
        bl = QHBoxLayout(banner)
        bl.setContentsMargins(10, 6, 10, 6)
        info = QLabel(
            "Detected family-fund format (Investerat belopp — amounts in TKR = thousands of SEK).\n"
            "Each investment year becomes a separate round. "
            "Current valuations are read from the 'Värdering' column where available.\n"
            "You can update ownership % and exact valuations after import."
        )
        info.setWordWrap(True)
        bl.addWidget(info)
        layout.addWidget(banner)

        self._status = QLabel("Loading…")
        layout.addWidget(self._status)

        self._table = QTableWidget()
        self._table.setAlternatingRowColors(True)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self._table)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.button(QDialogButtonBox.StandardButton.Ok).setText("Import All")
        btns.accepted.connect(self._do_import)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _load(self):
        try:
            self._parsed = excel_io.parse_family_excel(self._path)
        except Exception as e:
            self._status.setText(f"Error: {e}")
            return

        n = len(self._parsed)
        self._status.setText(
            f"Found {n} compan{'y' if n == 1 else 'ies'}. "
            "Review below — green = has current valuation, grey = valuation unknown."
        )

        cols = ["Company", "Entity", "Status", "Sector", "Years invested",
                "Total invested (TKR)", "Current valuation (TKR)",
                "Target ×", "Exit year"]
        self._table.setColumnCount(len(cols))
        self._table.setHorizontalHeaderLabels(cols)
        self._table.setRowCount(n)

        for ri, co in enumerate(self._parsed):
            years_str = ', '.join(
                f"{yr}: {amt:,.0f}" for yr, amt in sorted(co['year_amounts'].items())
            ) if co['year_amounts'] else '—'
            val   = co.get('current_valuation')
            mult  = co.get('multiple')

            if co.get('is_bankrupt'):
                status = 'Bankrupt'
                row_color = QColor(RED_SOFT)
            elif co.get('is_exited'):
                status = 'Exited'
                row_color = QColor(GREEN_SOFT)
            else:
                status = 'Active'
                row_color = None

            vals = [
                co['name'],
                co['entity'],
                status,
                co.get('sector', ''),
                years_str,
                f"{co['total_invested']:,.0f}" if co['total_invested'] else '—',
                f"{val:,.0f}" if val is not None else "—",
                f"{mult:.1f}×" if mult else "—",
                co.get('exit_year', '') or '—',
            ]
            for ci, v in enumerate(vals):
                item = QTableWidgetItem(str(v))
                if row_color:
                    item.setBackground(row_color)
                if ci == 6 and val is None:
                    item.setForeground(QColor(MUTED))
                elif ci == 6 and val is not None:
                    item.setForeground(QColor(GREEN))
                self._table.setItem(ri, ci, item)

        self._table.resizeColumnsToContents()

    def _do_import(self):
        if not self._parsed:
            self.reject()
            return
        try:
            count = excel_io.import_family_data(self._parsed)
            QMessageBox.information(
                self, "Import complete",
                f"Imported {count} new compan{'y' if count == 1 else 'ies'} "
                f"({len(self._parsed) - count} already existed and were updated).\n\n"
                "Tip: open each company in the Portfolio tab to set accurate\n"
                "ownership % and current valuations for precise metrics."
            )
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Import error", str(e))
