from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QPushButton, QDialogButtonBox,
    QRadioButton, QMessageBox
)
import excel_io


class ImportPreviewDialog(QDialog):
    def __init__(self, parent=None, path=''):
        super().__init__(parent)
        self.setWindowTitle("Import Preview — Excel")
        self.setMinimumSize(920, 520)
        self._path = path
        self._rows = []
        self._build()
        self._load()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        self._info = QLabel()
        layout.addWidget(self._info)

        # honest scope statement — no silent data loss on a round-trip
        scope = QLabel(
            "ℹ  This import covers companies and rounds only. Cash flows "
            "(dividends, exits, partial sales, fees) are NOT imported — "
            "flows already recorded in the app stay untouched, and the "
            "Cashflows sheet in exports is for reading, not re-importing.")
        scope.setWordWrap(True)
        scope.setStyleSheet("color: #FBBF24; font-size: 9pt;")
        layout.addWidget(scope)

        conflict_row = QHBoxLayout()
        conflict_row.addWidget(QLabel("If a round already exists:"))
        self._update_rb = QRadioButton("Update existing")
        self._skip_rb   = QRadioButton("Skip / leave unchanged")
        self._update_rb.setChecked(True)
        conflict_row.addWidget(self._update_rb)
        conflict_row.addWidget(self._skip_rb)
        conflict_row.addStretch()
        layout.addLayout(conflict_row)

        self._table = QTableWidget()
        self._table.setAlternatingRowColors(True)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        layout.addWidget(self._table)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.button(QDialogButtonBox.StandardButton.Ok).setText("Import")
        btns.accepted.connect(self._do_import)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _load(self):
        try:
            self._rows = excel_io.parse_excel(self._path)
        except Exception as e:
            self._info.setText(f"Error reading file: {e}")
            return

        self._info.setText(
            f"Found {len(self._rows)} data row(s). Review below, then click Import."
        )

        cols = ["Company", "Round", "Date", "Amount Invested", "Pre-Money",
                "Post-Money", "Shares", "Price/Share", "Ownership %", "Current Valuation"]
        self._table.setColumnCount(len(cols))
        self._table.setHorizontalHeaderLabels(cols)
        self._table.setRowCount(len(self._rows))

        for ri, row in enumerate(self._rows):
            vals = [
                row.get('company', ''),
                row.get('round', ''),
                row.get('date', ''),
                f"{row['amount_invested']:,.0f}"       if row.get('amount_invested')       else '',
                f"{row['pre_money_valuation']:,.0f}"   if row.get('pre_money_valuation')   else '',
                f"{row['post_money_valuation']:,.0f}"  if row.get('post_money_valuation')  else '',
                f"{row['shares']:,.0f}"                if row.get('shares')                else '',
                f"{row['price_per_share']:,.4f}"       if row.get('price_per_share')       else '',
                f"{row['ownership_pct']:.2f}%"         if row.get('ownership_pct')         else '',
                f"{row['current_valuation']:,.0f}"     if row.get('current_valuation')     else '',
            ]
            for ci, val in enumerate(vals):
                self._table.setItem(ri, ci, QTableWidgetItem(str(val)))

        self._table.resizeColumnsToContents()

    def _do_import(self):
        if not self._rows:
            self.reject()
            return
        conflict = 'update' if self._update_rb.isChecked() else 'skip'
        try:
            excel_io.import_rows(self._rows, on_conflict=conflict)
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Import Error", str(e))
