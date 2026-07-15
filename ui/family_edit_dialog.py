"""
FamilyEditDialog — edit all family-fund companies in a single spreadsheet-like table.
Changes can be saved to the database and/or exported back to Excel.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QMessageBox, QFileDialog, QComboBox,
    QHeaderView, QFrame, QApplication
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont

import models
import excel_io
from ui.styles import (
    ACCENT, MUTED, GREEN_SOFT, RED_SOFT,
    INFO_BG, INFO_BORDER, INFO_TEXT,
)

_YEARS        = [2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026]
_ENTITIES     = ['Portfolio A', 'Portfolio B']
_STATUSES     = ['Active', 'Exited', 'Bankrupt']
_INVEST_TYPES = ['Startup', 'ViFi Fund', 'Private Equity Fund', 'Listed Stock', 'Loan', 'Real Estate', 'Other']

# Column indices
_C_NAME   = 0
_C_ENTITY = 1
_C_SECTOR = 2
_C_Y0     = 3                        # first year column (2018)
_C_YEND   = _C_Y0 + len(_YEARS) - 1 # last  year column (2026)
_C_CURVAL = _C_YEND + 1
_C_EXITYR = _C_CURVAL + 1
_C_MULT   = _C_EXITYR + 1
_C_STATUS = _C_MULT + 1
_C_WEB    = _C_STATUS + 1
_C_DESC   = _C_WEB + 1
_C_TYPE   = _C_DESC + 1
_N_COLS   = _C_TYPE + 1

_HEADERS = (
    ['Company', 'Portfolio', 'Sector']
    + [str(y) for y in _YEARS]
    + ['Current Val\n(TKR)', 'Exit Year', 'Target ×', 'Status', 'Website', 'Description', 'Type']
)

_ID_ROLE = Qt.ItemDataRole.UserRole   # stores company DB id in col 0 item


def _num(text: str):
    """Parse a number from cell text; return float or None."""
    s = str(text).strip().replace(',', '').replace(' ', '')
    try:
        v = float(s)
        return v if v != 0 else None
    except ValueError:
        return None


class FamilyEditDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Family Data")
        self.setMinimumSize(1200, 640)
        self._deleted_ids: list[int] = []   # company IDs removed from table
        self._build()
        self._load()

    # ── Build UI ──────────────────────────────────────────────────────────────

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # Info banner
        info = QLabel(
            "Edit company data below. "
            "Each year column is the amount invested in that year (TKR). "
            "Changes only take effect when you click Save."
        )
        info.setWordWrap(True)
        info.setStyleSheet(
            f"background:{INFO_BG}; border:1px solid {INFO_BORDER}; border-radius:6px; "
            f"padding:8px 12px; color:{INFO_TEXT}; font-size:9pt;"
        )
        layout.addWidget(info)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)

        add_btn = QPushButton("+ Add Company")
        add_btn.clicked.connect(self._add_row)
        add_btn.setStyleSheet(
            f"QPushButton {{ background:{ACCENT}; color:white; border:none; }}"
            "QPushButton { "
            "border-radius:5px; padding:5px 14px; font-weight:bold; }"
            "QPushButton:hover { background:#1D4ED8; }"
        )

        del_btn = QPushButton("✕ Remove Selected")
        del_btn.clicked.connect(self._remove_row)
        del_btn.setStyleSheet(
            "QPushButton { background:#DC2626; color:white; border:none; "
            "border-radius:5px; padding:5px 14px; }"
            "QPushButton:hover { background:#B91C1C; }"
        )

        toolbar.addWidget(add_btn)
        toolbar.addWidget(del_btn)
        toolbar.addStretch()

        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet(f"color:{MUTED}; font-size:9pt;")
        toolbar.addWidget(self._status_lbl)

        layout.addLayout(toolbar)

        # Table
        self._table = QTableWidget(0, _N_COLS)
        self._table.setHorizontalHeaderLabels(_HEADERS)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self._table.horizontalHeader().setSectionResizeMode(
            _C_NAME, QHeaderView.ResizeMode.Stretch
        )
        self._table.setMinimumHeight(400)
        layout.addWidget(self._table)

        # Bottom buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        save_btn = QPushButton("Save to Database")
        save_btn.setStyleSheet(
            "QPushButton { background:#16A34A; color:white; border:none; "
            "border-radius:5px; padding:6px 18px; font-weight:bold; }"
            "QPushButton:hover { background:#15803D; }"
        )
        save_btn.clicked.connect(self._save)

        export_btn = QPushButton("Save + Export to Excel…")
        export_btn.setStyleSheet(
            f"QPushButton {{ background:{ACCENT}; color:white; border:none; }}"
            "QPushButton { "
            "border-radius:5px; padding:6px 18px; font-weight:bold; }"
            "QPushButton:hover { background:#1D4ED8; }"
        )
        export_btn.clicked.connect(self._save_and_export)

        resync_btn = QPushButton("Re-sync from Excel file…")
        resync_btn.setStyleSheet(
            "QPushButton { background:#7C3AED; color:white; border:none; "
            "border-radius:5px; padding:6px 18px; }"
            "QPushButton:hover { background:#6D28D9; }"
        )
        resync_btn.clicked.connect(self._resync)

        cancel_btn = QPushButton("Close")
        cancel_btn.clicked.connect(self.reject)

        btn_row.addWidget(save_btn)
        btn_row.addWidget(export_btn)
        btn_row.addWidget(resync_btn)
        btn_row.addStretch()
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

    # ── Load data from DB ─────────────────────────────────────────────────────

    def _load(self):
        self._table.setRowCount(0)
        self._deleted_ids.clear()

        companies = models.get_all_companies()
        # Sort: alphabetically by entity, then by company name
        companies.sort(key=lambda c: (c.get('entity') or '', c['name']))

        self._table.setRowCount(len(companies))

        for ri, c in enumerate(companies):
            rounds = models.get_rounds(c['id'])
            yr_amt: dict[int, float] = {}
            for r in rounds:
                yr_str = (r.get('date') or '')[:4]
                try:
                    yr = int(yr_str)
                    if yr in _YEARS:
                        yr_amt[yr] = yr_amt.get(yr, 0) + (r.get('amount_invested') or 0)
                except ValueError:
                    pass

            notes = c.get('notes') or ''
            exit_yr = ''
            multiple = ''
            for line in notes.splitlines():
                if line.startswith('Exit year:'):
                    exit_yr = line.split(':', 1)[1].strip()
                elif line.startswith('Target multiple:'):
                    multiple = line.split(':', 1)[1].replace('×', '').strip()

            # Determine status from notes
            nl = notes.lower()
            if 'bankrupt' in nl:
                status = 'Bankrupt'
            elif 'status: exited' in nl:
                status = 'Exited'
            else:
                status = 'Active'

            self._set_row(ri, {
                'id':             c['id'],
                'name':           c['name'],
                'entity':         c.get('entity') or '',
                'sector':         c.get('sector') or '',
                'yr_amt':         yr_amt,
                'curval':         c.get('current_valuation'),
                'exit_yr':        exit_yr,
                'multiple':       multiple,
                'status':         status,
                'website':        c.get('website') or '',
                'description':    c.get('description') or '',
                'investment_type': c.get('investment_type') or '',
            })

        self._update_status()

    def _set_row(self, ri: int, data: dict):
        """Populate a single table row from a data dict."""

        def _item(txt, editable=True, align=Qt.AlignmentFlag.AlignLeft):
            it = QTableWidgetItem(str(txt) if txt is not None else '')
            if not editable:
                it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
            it.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | align)
            return it

        # Col 0: company name (stores DB id in UserRole)
        name_item = _item(data['name'])
        name_item.setData(_ID_ROLE, data.get('id'))
        self._table.setItem(ri, _C_NAME, name_item)

        # Col 1: entity — combobox
        entity_cb = QComboBox()
        entity_cb.addItems(_ENTITIES)
        entity_cb.setEditable(True)
        entity_cb.setCurrentText(data.get('entity') or '')
        self._table.setCellWidget(ri, _C_ENTITY, entity_cb)

        # Col 2: sector
        self._table.setItem(ri, _C_SECTOR, _item(data.get('sector') or ''))

        # Year columns
        for ci, yr in enumerate(_YEARS, _C_Y0):
            val = data['yr_amt'].get(yr)
            txt = f"{val:,.0f}" if val else ''
            it = _item(txt, align=Qt.AlignmentFlag.AlignRight)
            self._table.setItem(ri, ci, it)

        # Current valuation
        cv = data.get('curval')
        self._table.setItem(ri, _C_CURVAL,
            _item(f"{cv:,.0f}" if cv is not None else '',
                  align=Qt.AlignmentFlag.AlignRight))

        # Exit year
        self._table.setItem(ri, _C_EXITYR, _item(data.get('exit_yr') or ''))

        # Target multiple
        self._table.setItem(ri, _C_MULT,
            _item(data.get('multiple') or '',
                  align=Qt.AlignmentFlag.AlignRight))

        # Status — combobox
        status_cb = QComboBox()
        status_cb.addItems(_STATUSES)
        status_cb.setCurrentText(data.get('status') or 'Active')
        self._table.setCellWidget(ri, _C_STATUS, status_cb)

        # Website
        self._table.setItem(ri, _C_WEB,  _item(data.get('website') or ''))

        # Description
        self._table.setItem(ri, _C_DESC, _item(data.get('description') or ''))

        # Investment type — combobox
        type_cb = QComboBox()
        type_cb.addItems([''] + _INVEST_TYPES)
        type_cb.setEditable(True)
        type_cb.setCurrentText(data.get('investment_type') or '')
        self._table.setCellWidget(ri, _C_TYPE, type_cb)

        # Color the row by status
        self._color_row(ri, data.get('status') or 'Active')

    def _color_row(self, ri: int, status: str):
        bg = None
        if status == 'Bankrupt':
            bg = QColor(RED_SOFT)
        elif status == 'Exited':
            bg = QColor(GREEN_SOFT)
        if bg:
            for ci in range(_N_COLS):
                item = self._table.item(ri, ci)
                if item:
                    item.setBackground(bg)

    # ── Add / remove rows ─────────────────────────────────────────────────────

    def _add_row(self):
        ri = self._table.rowCount()
        self._table.insertRow(ri)
        self._set_row(ri, {
            'id': None, 'name': 'New Company', 'entity': _ENTITIES[0],
            'sector': '', 'yr_amt': {}, 'curval': None,
            'exit_yr': '', 'multiple': '', 'status': 'Active',
            'website': '', 'description': '', 'investment_type': '',
        })
        self._table.scrollToBottom()
        self._table.editItem(self._table.item(ri, _C_NAME))
        self._update_status()

    def _remove_row(self):
        rows = sorted({idx.row() for idx in self._table.selectedIndexes()},
                      reverse=True)
        if not rows:
            QMessageBox.information(self, "Nothing selected",
                                    "Click a row to select it, then click Remove.")
            return

        names = [self._table.item(r, _C_NAME).text() for r in rows]
        reply = QMessageBox.question(
            self, "Remove companies",
            f"Remove {len(rows)} company/companies?\n\n" + '\n'.join(names) +
            "\n\nThis will delete them from the database when you Save.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        for ri in rows:
            cid = self._table.item(ri, _C_NAME).data(_ID_ROLE)
            if cid:
                self._deleted_ids.append(cid)
            self._table.removeRow(ri)

        self._update_status()

    # ── Parse table → list of dicts ───────────────────────────────────────────

    def _parse_table(self) -> list[dict]:
        rows = []
        for ri in range(self._table.rowCount()):
            name_item = self._table.item(ri, _C_NAME)
            if not name_item:
                continue
            name = name_item.text().strip()
            if not name:
                continue

            entity_cb = self._table.cellWidget(ri, _C_ENTITY)
            entity = entity_cb.currentText().strip() if entity_cb else ''

            status_cb = self._table.cellWidget(ri, _C_STATUS)
            status = status_cb.currentText() if status_cb else 'Active'

            yr_amt: dict[int, float] = {}
            for ci, yr in enumerate(_YEARS, _C_Y0):
                item = self._table.item(ri, ci)
                v = _num(item.text() if item else '')
                if v and v > 0:
                    yr_amt[yr] = v

            cv_item = self._table.item(ri, _C_CURVAL)
            curval  = _num(cv_item.text() if cv_item else '')

            ey_item  = self._table.item(ri, _C_EXITYR)
            exit_yr  = (ey_item.text().strip() if ey_item else '')

            mul_item = self._table.item(ri, _C_MULT)
            multiple = _num(mul_item.text() if mul_item else '')

            sec_item = self._table.item(ri, _C_SECTOR)
            sector   = (sec_item.text().strip() if sec_item else '')

            web_item  = self._table.item(ri, _C_WEB)
            website   = (web_item.text().strip() if web_item else '')

            desc_item = self._table.item(ri, _C_DESC)
            desc      = (desc_item.text().strip() if desc_item else '')

            type_cb = self._table.cellWidget(ri, _C_TYPE)
            inv_type = type_cb.currentText().strip() if type_cb else ''

            rows.append({
                'id':              name_item.data(_ID_ROLE),
                'name':            name,
                'entity':          entity,
                'sector':          sector,
                'yr_amt':          yr_amt,
                'curval':          curval if (curval and curval >= 0) else None,
                'exit_yr':         exit_yr,
                'multiple':        multiple,
                'status':          status,
                'website':         website,
                'description':     desc,
                'investment_type': inv_type,
            })
        return rows

    # ── Save to database ──────────────────────────────────────────────────────

    @models.with_origin('ui.family_edit')
    def _commit(self) -> int:
        """Write current table state to DB. Returns number of companies saved."""
        rows = self._parse_table()

        # Delete removed companies
        for cid in self._deleted_ids:
            models.delete_company(cid)
        self._deleted_ids.clear()

        saved = 0
        for row in rows:
            notes_parts: list[str] = []
            if row['status'] == 'Exited':
                notes_parts.append('Status: Exited')
            elif row['status'] == 'Bankrupt':
                notes_parts.append('Status: Bankrupt (written off)')
            if row['exit_yr']:
                notes_parts.append(f"Exit year: {row['exit_yr']}")
            if row['multiple']:
                notes_parts.append(f"Target multiple: {row['multiple']}×")
            notes = '\n'.join(notes_parts)

            first_yr = min(row['yr_amt'].keys()) if row['yr_amt'] else None

            if row['id']:
                # Update existing
                models.update_company(
                    row['id'],
                    name=row['name'],
                    entity=row['entity'],
                    sector=row['sector'],
                    current_valuation=row['curval'],
                    notes=notes,
                    website=row.get('website', ''),
                    description=row.get('description', ''),
                    investment_type=row.get('investment_type', ''),
                )
                models.clear_rounds(row['id'])
                cid = row['id']
            else:
                # Create new
                cid = models.add_company(
                    name=row['name'],
                    entity=row['entity'],
                    sector=row['sector'],
                    country='',
                    first_investment_date=f"{first_yr}-01-01" if first_yr else '',
                    current_valuation=row['curval'],
                    notes=notes,
                    website=row.get('website', ''),
                    description=row.get('description', ''),
                    investment_type=row.get('investment_type', ''),
                )
                # Store the new id back into the table so a second save works
                name_item = self._table.item(
                    [i for i in range(self._table.rowCount())
                     if self._table.item(i, _C_NAME)
                     and self._table.item(i, _C_NAME).text() == row['name']][0],
                    _C_NAME
                )
                if name_item and name_item.data(_ID_ROLE) is None:
                    name_item.setData(_ID_ROLE, cid)

            for yr in sorted(row['yr_amt']):
                models.add_round(
                    company_id=cid,
                    round_name=str(yr),
                    date=f"{yr}-07-01",
                    amount_invested=row['yr_amt'][yr],
                    ownership_pct=100.0,
                    status='Closed',
                )
            if not row['yr_amt'] and row['curval'] and row['curval'] > 0:
                models.add_round(
                    company_id=cid,
                    round_name='Investment',
                    date=f"{first_yr or 2023}-07-01",
                    amount_invested=row['curval'],
                    ownership_pct=100.0,
                    status='Closed',
                )
            saved += 1

        return saved

    def _save(self):
        try:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            n = self._commit()
            QApplication.restoreOverrideCursor()
            QMessageBox.information(self, "Saved",
                f"{n} companies saved to database.")
            self._update_status()
        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, "Save error", str(e))

    def _save_and_export(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Family Data to Excel",
            "family_portfolio.xlsx", "Excel Files (*.xlsx)"
        )
        if not path:
            return
        try:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            n = self._commit()
            excel_io.export_family_excel(path)
            QApplication.restoreOverrideCursor()
            QMessageBox.information(self, "Saved & Exported",
                f"{n} companies saved to database.\nExcel written to:\n{path}")
            self._update_status()
        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, "Error", str(e))

    # ── Re-sync from external Excel ───────────────────────────────────────────

    def _resync(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Excel File to Re-sync From", "",
            "Excel Files (*.xlsx *.xls);;All Files (*)"
        )
        if not path:
            return
        try:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            parsed = excel_io.parse_family_excel(path)
            count  = excel_io.import_family_data(parsed)
            QApplication.restoreOverrideCursor()
            QMessageBox.information(
                self, "Re-sync complete",
                f"Imported {count} new companies, updated existing ones.\n"
                "The table has been refreshed."
            )
            self._load()   # reload table from DB
        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, "Re-sync error", str(e))

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _update_status(self):
        n = self._table.rowCount()
        self._status_lbl.setText(f"{n} companies  |  {len(self._deleted_ids)} pending deletion")
