import os
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QLineEdit,
    QTextEdit, QComboBox, QPushButton, QFileDialog, QMessageBox,
    QDialogButtonBox, QDoubleSpinBox, QDateEdit, QGroupBox, QScrollArea,
    QWidget, QRadioButton, QTableWidget, QTableWidgetItem, QFrame,
    QSizePolicy, QSpacerItem, QCheckBox, QTabWidget
)
from PyQt6.QtCore import QDate, Qt
from PyQt6.QtGui import QFont
import models
from ui.styles import ACCENT, ACCENT_LITE, MUTED, CARD, BORDER, TEXT

_INVEST_YEARS = [2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026]

ROUND_TYPES = ["Seed", "Pre-Seed", "Series A", "Series B", "Series C",
               "Series D", "Bridge", "Convertible Note", "SAFE", "Other"]
DOC_TYPES   = ["SHA", "Investment Agreement", "Other"]


def _section(title: str) -> QLabel:
    """THE section header style (matches SectionLabel/_SectionTitle):
    8pt uppercase letter-spaced muted."""
    from ui.styles import label_font
    lbl = QLabel(str(title).upper())
    lbl.setFont(label_font())            # letter-spacing (QSS can't)
    lbl.setStyleSheet(f"color:{MUTED}; font-size:8pt; "
                      f"font-weight:600; margin-top:16px;")
    return lbl


class CompanyDialog(QDialog):
    """
    Comprehensive add/edit dialog.
    Handles all DB writes internally — caller just checks exec() result
    and refreshes the tree.
    """

    def __init__(self, parent=None, company_id=None, default_entity=''):
        super().__init__(parent)
        self._cid           = company_id      # None = new company
        self._default_entity = default_entity
        self._year_spins: dict[int, QDoubleSpinBox] = {}
        self.setWindowTitle("Edit Company" if company_id else "Add Company")
        self.setMinimumWidth(560)
        self.setMinimumHeight(720)
        self.resize(580, 800)
        self._build()
        if company_id:
            self._populate(models.get_company(company_id),
                           models.get_rounds(company_id))

    # ── Build UI ──────────────────────────────────────────────────────────────

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Scrollable content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(10)

        # ── Section 1: Company info ───────────────────────────────────────────
        lay.addWidget(_section("Company Information"))

        f1 = QFormLayout()
        f1.setSpacing(8)
        f1.setContentsMargins(4, 4, 4, 4)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Company name  (required)")
        f1.addRow("Name *", self.name_edit)

        self.entity_edit = QComboBox()
        self.entity_edit.setEditable(True)
        self.entity_edit.addItems(
            models.get_entities() or ['Portfolio A', 'Portfolio B']
        )
        if self._default_entity:
            self.entity_edit.setCurrentText(self._default_entity)
        f1.addRow("Portfolio", self.entity_edit)

        self.status_edit = QComboBox()
        self.status_edit.addItems(['Active', 'Exited', 'Bankrupt'])
        f1.addRow("Status", self.status_edit)

        self.sector_edit = QLineEdit()
        self.sector_edit.setPlaceholderText("e.g. Healthtech, Fintech, SaaS")
        f1.addRow("Sector", self.sector_edit)

        self.country_edit = QLineEdit("")
        f1.addRow("Country", self.country_edit)

        self.website_edit = QLineEdit()
        self.website_edit.setPlaceholderText("https://")
        f1.addRow("Website", self.website_edit)

        self.description_edit = QTextEdit()
        self.description_edit.setPlaceholderText(
            "What does this company do? (shown in the portfolio view)"
        )
        self.description_edit.setFixedHeight(72)
        f1.addRow("Description", self.description_edit)

        lay.addLayout(f1)

        # ── Section 2: Investments by year ────────────────────────────────────
        lay.addWidget(_section("Investments by Year  (TKR = thousands of SEK)"))

        year_grid = QWidget()
        yg = QHBoxLayout(year_grid)
        yg.setSpacing(24)
        yg.setContentsMargins(4, 4, 4, 4)

        # Split years into two columns
        col_a = QFormLayout(); col_a.setSpacing(6)
        col_b = QFormLayout(); col_b.setSpacing(6)

        for i, yr in enumerate(_INVEST_YEARS):
            spin = QDoubleSpinBox()
            spin.setRange(0, 1_000_000)
            spin.setDecimals(1)
            spin.setSingleStep(100)
            spin.setSpecialValueText("—")
            spin.setGroupSeparatorShown(True)
            spin.setMinimumWidth(110)
            spin.valueChanged.connect(self._update_total)
            self._year_spins[yr] = spin
            lbl = QLabel(str(yr))
            lbl.setStyleSheet("font-weight:bold;")
            (col_a if i < 5 else col_b).addRow(lbl, spin)

        yg.addLayout(col_a)
        yg.addLayout(col_b)
        yg.addStretch()
        lay.addWidget(year_grid)

        total_row = QHBoxLayout()
        total_row.addStretch()
        self._total_lbl = QLabel("Total invested:  TKR 0")
        self._total_lbl.setStyleSheet(
            f"font-weight:bold; font-size:10pt; color:{ACCENT};"
        )
        total_row.addWidget(self._total_lbl)
        lay.addLayout(total_row)

        # ── Section 3: Valuation & exit ───────────────────────────────────────
        lay.addWidget(_section("Valuation & Exit"))

        f3 = QFormLayout()
        f3.setSpacing(8)
        f3.setContentsMargins(4, 4, 4, 4)

        self.valuation_edit = QDoubleSpinBox()
        self.valuation_edit.setRange(0, 1_000_000)
        self.valuation_edit.setDecimals(1)
        self.valuation_edit.setSingleStep(500)
        self.valuation_edit.setSpecialValueText("Not set")
        self.valuation_edit.setGroupSeparatorShown(True)
        f3.addRow("Current Valuation (TKR)", self.valuation_edit)

        self.exit_year_edit = QLineEdit()
        self.exit_year_edit.setPlaceholderText("e.g.  2027-IPO  or  2026")
        f3.addRow("Planned Exit Year", self.exit_year_edit)

        self.multiple_edit = QDoubleSpinBox()
        self.multiple_edit.setRange(0, 1000)
        self.multiple_edit.setDecimals(1)
        self.multiple_edit.setSingleStep(0.5)
        self.multiple_edit.setSpecialValueText("—")
        self.multiple_edit.setSuffix("  ×")
        f3.addRow("Target Multiple", self.multiple_edit)

        self.potential_edit = QDoubleSpinBox()
        self.potential_edit.setRange(0, 10_000_000)
        self.potential_edit.setDecimals(0)
        self.potential_edit.setSingleStep(1000)
        self.potential_edit.setSpecialValueText("—")
        self.potential_edit.setGroupSeparatorShown(True)
        f3.addRow("Potential Exit Value (TKR)", self.potential_edit)

        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText("Internal notes…")
        self.notes_edit.setFixedHeight(60)
        f3.addRow("Internal Notes", self.notes_edit)

        lay.addLayout(f3)
        lay.addStretch()

        scroll.setWidget(inner)
        root.addWidget(scroll, 1)

        # ── Sticky bottom buttons ─────────────────────────────────────────────
        btn_bar = QFrame()
        btn_bar.setStyleSheet(
            f"QFrame {{ background:{CARD}; border-top:1px solid {BORDER}; }}"
        )
        btn_lay = QHBoxLayout(btn_bar)
        btn_lay.setContentsMargins(20, 10, 20, 10)

        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)

        save = QPushButton("  Save Company  ")
        save.setDefault(True)
        save.setStyleSheet(
            f"QPushButton {{ background:{ACCENT}; color:white; border:none; "
            f"border-radius:7px; padding:8px 24px; font-weight:bold; font-size:10pt; }}"
            f"QPushButton:hover {{ background:#2563EB; }}"
        )
        save.clicked.connect(self._save)

        btn_lay.addWidget(cancel)
        btn_lay.addStretch()
        btn_lay.addWidget(save)
        root.addWidget(btn_bar)

    # ── Populate (edit mode) ──────────────────────────────────────────────────

    def _populate(self, c: dict, rounds: list):
        if not c:
            return

        self.name_edit.setText(c.get('name', ''))
        self.entity_edit.setCurrentText(c.get('entity', '') or '')
        self.sector_edit.setText(c.get('sector', '') or '')
        self.country_edit.setText(c.get('country', '') or '')
        self.website_edit.setText(c.get('website', '') or '')
        self.description_edit.setPlainText(c.get('description', '') or '')

        # Determine status from notes
        notes = (c.get('notes') or '').lower()
        if 'bankrupt' in notes:
            self.status_edit.setCurrentText('Bankrupt')
        elif 'status: exited' in notes:
            self.status_edit.setCurrentText('Exited')

        if c.get('current_valuation'):
            self.valuation_edit.setValue(c['current_valuation'])

        # Parse structured notes for exit year / multiple / potential
        for line in (c.get('notes') or '').splitlines():
            if line.startswith('Exit year:'):
                self.exit_year_edit.setText(line.split(':', 1)[1].strip())
            elif line.startswith('Target multiple:'):
                try:
                    self.multiple_edit.setValue(
                        float(line.split(':', 1)[1].replace('×', '').strip())
                    )
                except ValueError:
                    pass
            elif line.startswith('Potential at exit:'):
                try:
                    self.potential_edit.setValue(
                        float(line.split(':', 1)[1].replace('TKR', '').replace(',', '').strip())
                    )
                except ValueError:
                    pass
            elif not any(line.startswith(p) for p in
                         ('Status:', 'Exit year:', 'Target multiple:', 'Potential at exit:')):
                cur = self.notes_edit.toPlainText()
                if line.strip():
                    self.notes_edit.setPlainText((cur + '\n' + line).strip())

        # Populate year spinboxes from rounds
        for r in rounds:
            yr_str = (r.get('date') or '')[:4]
            try:
                yr = int(yr_str)
                if yr in self._year_spins and r.get('amount_invested'):
                    cur = self._year_spins[yr].value()
                    self._year_spins[yr].setValue(cur + r['amount_invested'])
            except ValueError:
                pass

        self._update_total()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _update_total(self):
        total = sum(
            s.value() for s in self._year_spins.values() if s.value() > 0
        )
        self._total_lbl.setText(f"Total invested:  TKR {total:,.0f}")

    # ── Save ──────────────────────────────────────────────────────────────────

    def _save(self):
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Required field", "Company name cannot be empty.")
            return

        # Build structured notes
        notes_parts = []
        status = self.status_edit.currentText()
        if status == 'Exited':
            notes_parts.append('Status: Exited')
        elif status == 'Bankrupt':
            notes_parts.append('Status: Bankrupt (written off)')

        exit_yr = self.exit_year_edit.text().strip()
        if exit_yr:
            notes_parts.append(f"Exit year: {exit_yr}")

        multiple = self.multiple_edit.value()
        if multiple > 0:
            notes_parts.append(f"Target multiple: {multiple}×")

        potential = self.potential_edit.value()
        if potential > 0:
            notes_parts.append(f"Potential at exit: {potential:,.0f} TKR")

        raw_notes = self.notes_edit.toPlainText().strip()
        if raw_notes:
            notes_parts.append(raw_notes)

        notes = '\n'.join(notes_parts)

        # Collect year investments
        year_amounts = {
            yr: spin.value()
            for yr, spin in self._year_spins.items()
            if spin.value() > 0
        }
        first_yr = min(year_amounts.keys()) if year_amounts else None

        val = self.valuation_edit.value()
        current_val = val if val > 0 else None

        company_data = dict(
            name=name,
            entity=self.entity_edit.currentText().strip(),
            sector=self.sector_edit.text().strip(),
            country=self.country_edit.text().strip(),
            first_investment_date=f"{first_yr}-01-01" if first_yr else '',
            current_valuation=current_val,
            website=self.website_edit.text().strip(),
            description=self.description_edit.toPlainText().strip(),
            notes=notes,
        )

        if self._cid:
            models.update_company(self._cid, origin='ui.company_dialog',
                                  **company_data)
            models.clear_rounds(self._cid, origin='ui.company_dialog')
            cid = self._cid
        else:
            cid = models.add_company(origin='ui.company_dialog',
                                     **company_data)

        for yr in sorted(year_amounts):
            models.add_round(
                company_id=cid,
                round_name=str(yr),
                date=f"{yr}-07-01",
                amount_invested=year_amounts[yr],
                ownership_pct=100.0,
                status='Closed',
                origin='ui.company_dialog',
            )

        self.accept()


class RoundDialog(QDialog):
    def __init__(self, parent=None, round_data=None):
        super().__init__(parent)
        self.round_data = round_data
        self.setWindowTitle("Edit Round" if round_data else "Add Funding Round")
        self.setMinimumWidth(460)
        self._build()
        if round_data:
            self._populate(round_data)

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        form = QFormLayout()
        form.setSpacing(8)

        self.round_name = QComboBox()
        self.round_name.addItems(ROUND_TYPES)
        self.round_name.setEditable(True)
        form.addRow("Round Type *", self.round_name)

        self.date_edit = QDateEdit(QDate.currentDate())
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        self.date_edit.setCalendarPopup(True)
        form.addRow("Date", self.date_edit)

        def spin(max_val=1e12, dec=2, step=10_000, suffix=''):
            s = QDoubleSpinBox()
            s.setRange(0, max_val)
            s.setDecimals(dec)
            s.setSingleStep(step)
            s.setGroupSeparatorShown(True)
            s.setSpecialValueText("Not set")
            if suffix:
                s.setSuffix(suffix)
            return s

        self.amount       = spin(dec=2, step=10_000)
        self.pre_money    = spin(dec=0, step=500_000)
        self.post_money   = spin(dec=0, step=500_000)
        self.shares       = spin(dec=0, step=1000)
        self.pps          = spin(max_val=1e9, dec=4, step=0.01)
        self.total_shares = spin(dec=0, step=10_000)
        self.ownership    = spin(max_val=100, dec=4, step=0.1, suffix='%')

        form.addRow("Amount Invested *", self.amount)
        form.addRow("Pre-Money Valuation", self.pre_money)
        form.addRow("Post-Money Valuation", self.post_money)

        # a post-money value is a valuation point — record it in the
        # valuation history unless the user opts out
        self.record_val = QCheckBox(
            "Also record a valuation point (source: round post-money)")
        self.record_val.setChecked(True)
        self.record_val.setEnabled(False)
        self.post_money.valueChanged.connect(
            lambda v: self.record_val.setEnabled(v > 0))
        form.addRow("", self.record_val)
        form.addRow("Shares Received", self.shares)
        form.addRow("Price Per Share", self.pps)
        form.addRow("Total Shares Outstanding", self.total_shares)
        form.addRow("Ownership % (0 = auto-calc)", self.ownership)

        self.status = QComboBox()
        self.status.addItems(["Closed", "Open"])
        form.addRow("Status", self.status)

        layout.addLayout(form)
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._validate)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _populate(self, r):
        idx = self.round_name.findText(r.get('round_name', ''))
        if idx >= 0:
            self.round_name.setCurrentIndex(idx)
        else:
            self.round_name.setCurrentText(r.get('round_name', ''))
        if r.get('date'):
            self.date_edit.setDate(QDate.fromString(r['date'][:10], "yyyy-MM-dd"))
        for attr, key in [
            (self.amount, 'amount_invested'), (self.pre_money, 'pre_money_valuation'),
            (self.post_money, 'post_money_valuation'), (self.shares, 'shares_received'),
            (self.pps, 'price_per_share'), (self.total_shares, 'total_shares_outstanding'),
            (self.ownership, 'ownership_pct'),
        ]:
            if r.get(key):
                attr.setValue(r[key])
        if r.get('status'):
            self.status.setCurrentText(r['status'])

    def _validate(self):
        if not self.round_name.currentText().strip():
            QMessageBox.warning(self, "Missing field", "Round type is required.")
            return
        if self.amount.value() <= 0:
            QMessageBox.warning(self, "Invalid", "Amount invested must be > 0.")
            return
        self.accept()

    def get_data(self):
        own = self.ownership.value()
        shr = self.shares.value()
        ts  = self.total_shares.value()
        if own == 0 and shr > 0 and ts > 0:
            own = (shr / ts) * 100
        return {
            'round_name':               self.round_name.currentText().strip(),
            'date':                     self.date_edit.date().toString("yyyy-MM-dd"),
            'amount_invested':          self.amount.value(),
            'pre_money_valuation':      self.pre_money.value() or None,
            'post_money_valuation':     self.post_money.value() or None,
            'shares_received':          shr or None,
            'price_per_share':          self.pps.value() or None,
            'total_shares_outstanding': ts or None,
            'ownership_pct':            own or None,
            'status':                   self.status.currentText(),
            'record_valuation':         (self.record_val.isChecked()
                                         and self.post_money.value() > 0),
        }


class ValuationDialog(QDialog):
    """Add or edit one valuation-history point (see CLAUDE.md: the
    valuation history is the single source of truth for current value)."""

    SOURCES = ['internal_estimate', 'external_valuation', 'offer', 'exit',
               'round_post_money']
    SOURCE_LABELS = {
        'internal_estimate': 'Internal estimate',
        'external_valuation': 'External valuation',
        'offer': 'Offer received',
        'exit': 'Exit / sale',
        'round_post_money': 'Round post-money',
        'legacy_migration': 'Carried over (legacy)',
    }

    def __init__(self, parent=None, valuation=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Valuation Point" if valuation
                            else "Add Valuation Point")
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(8)

        self.date_edit = QDateEdit(QDate.currentDate())
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        self.date_edit.setCalendarPopup(True)
        form.addRow("As-of date *", self.date_edit)

        self.value_edit = QDoubleSpinBox()
        self.value_edit.setRange(0, 1e12)
        self.value_edit.setDecimals(0)
        self.value_edit.setSingleStep(100_000)
        self.value_edit.setGroupSeparatorShown(True)
        form.addRow("Company valuation *", self.value_edit)

        self.source_edit = QComboBox()
        for s in self.SOURCES:
            self.source_edit.addItem(self.SOURCE_LABELS[s], s)
        form.addRow("Source", self.source_edit)

        self.note_edit = QLineEdit()
        self.note_edit.setPlaceholderText(
            "e.g. term sheet from lead investor, board estimate…")
        form.addRow("Note", self.note_edit)

        layout.addLayout(form)
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._validate)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

        if valuation:
            if valuation.get('as_of_date'):
                self.date_edit.setDate(QDate.fromString(
                    valuation['as_of_date'][:10], "yyyy-MM-dd"))
            self.value_edit.setValue(valuation.get('value') or 0)
            idx = self.source_edit.findData(valuation.get('source'))
            if idx >= 0:
                self.source_edit.setCurrentIndex(idx)
            self.note_edit.setText(valuation.get('note') or '')

    def _validate(self):
        if self.value_edit.value() <= 0:
            QMessageBox.warning(self, "Invalid",
                                "The valuation must be greater than zero.")
            return
        self.accept()

    def get_data(self):
        return {
            'as_of_date': self.date_edit.date().toString("yyyy-MM-dd"),
            'value': self.value_edit.value(),
            'source': self.source_edit.currentData(),
            'note': self.note_edit.text().strip(),
        }


class CashflowDialog(QDialog):
    """Add or edit a non-round cash flow. Amounts entered positive —
    direction comes from the type (metrics.signed_amount, see CLAUDE.md).
    Partial sales capture shares sold and refuse to oversell."""

    TYPES = ['follow_on', 'dividend', 'distribution', 'partial_sale',
             'exit_proceeds', 'fee', 'other_in', 'other_out']
    TYPE_LABELS = {
        'follow_on': 'Follow-on investment (money out)',
        'dividend': 'Dividend received (money in)',
        'distribution': 'Distribution received (money in)',
        'partial_sale': 'Partial sale of shares (money in)',
        'exit_proceeds': 'Exit proceeds (money in)',
        'fee': 'Fee paid (money out)',
        'other_in': 'Other inflow (money in)',
        'other_out': 'Other outflow (money out)',
    }

    def __init__(self, parent=None, company_id=None, flow=None):
        super().__init__(parent)
        self._cid = company_id
        self.setWindowTitle("Edit Cash Flow" if flow else "Add Cash Flow")
        self.setMinimumWidth(440)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(8)

        self.type_edit = QComboBox()
        for t in self.TYPES:
            self.type_edit.addItem(self.TYPE_LABELS[t], t)
        self.type_edit.currentIndexChanged.connect(self._type_changed)
        form.addRow("Type *", self.type_edit)

        self.date_edit = QDateEdit(QDate.currentDate())
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        self.date_edit.setCalendarPopup(True)
        form.addRow("Date *", self.date_edit)

        self.amount_edit = QDoubleSpinBox()
        self.amount_edit.setRange(0, 1e12)
        self.amount_edit.setDecimals(2)
        self.amount_edit.setSingleStep(1000)
        self.amount_edit.setGroupSeparatorShown(True)
        form.addRow("Amount (positive) *", self.amount_edit)

        import models as _models
        self._held = (_models.shares_held(company_id)
                      if company_id else 0)
        self.shares_edit = QDoubleSpinBox()
        self.shares_edit.setRange(0, max(self._held, 0))
        self.shares_edit.setDecimals(0)
        self.shares_edit.setGroupSeparatorShown(True)
        self._shares_label = QLabel(
            f"Shares sold (held: {self._held:,.0f})")
        form.addRow(self._shares_label, self.shares_edit)

        self.note_edit = QLineEdit()
        self.note_edit.setPlaceholderText("e.g. FY24 dividend, buyer name…")
        form.addRow("Note", self.note_edit)

        layout.addLayout(form)
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._validate)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

        if flow:
            idx = self.type_edit.findData(flow.get('type'))
            if idx >= 0:
                self.type_edit.setCurrentIndex(idx)
            if flow.get('date'):
                self.date_edit.setDate(QDate.fromString(
                    flow['date'][:10], "yyyy-MM-dd"))
            self.amount_edit.setValue(flow.get('amount') or 0)
            if flow.get('shares_delta'):
                self.shares_edit.setMaximum(
                    max(self._held - flow['shares_delta'], 0))
                self.shares_edit.setValue(-flow['shares_delta'])
            self.note_edit.setText(flow.get('note') or '')
        self._type_changed()

    def _type_changed(self):
        is_sale = self.type_edit.currentData() == 'partial_sale'
        self.shares_edit.setVisible(is_sale)
        self._shares_label.setVisible(is_sale)

    def _validate(self):
        if self.amount_edit.value() <= 0:
            QMessageBox.warning(self, "Invalid",
                                "Amount must be greater than zero — the "
                                "direction comes from the type.")
            return
        if self.type_edit.currentData() == 'partial_sale':
            sold = self.shares_edit.value()
            if sold <= 0:
                QMessageBox.warning(self, "Shares required",
                                    "A partial sale needs the number of "
                                    "shares sold.")
                return
            if sold > self._held + 1e-9:
                QMessageBox.warning(
                    self, "Too many shares",
                    f"You hold {self._held:,.0f} shares — you cannot sell "
                    f"{sold:,.0f}.")
                return
        self.accept()

    def get_data(self):
        t = self.type_edit.currentData()
        sold = self.shares_edit.value() if t == 'partial_sale' else 0
        return {
            'date': self.date_edit.date().toString("yyyy-MM-dd"),
            'type': t,
            'amount': self.amount_edit.value(),
            'shares_delta': -sold if sold else None,
            'note': self.note_edit.text().strip(),
        }


class JournalDialog(QDialog):
    """One dated 'how it's going' note. The period label defaults to the
    quarter of the chosen date (metrics.quarter_label)."""

    def __init__(self, parent=None, entry=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Journal Entry" if entry
                            else "Add Journal Entry")
        self.setMinimumWidth(460)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(8)

        self.date_edit = QDateEdit(QDate.currentDate())
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        self.date_edit.setCalendarPopup(True)
        self.date_edit.dateChanged.connect(self._suggest_period)
        form.addRow("Date *", self.date_edit)

        self.period_edit = QLineEdit()
        form.addRow("Period label", self.period_edit)

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("e.g. Strong Q2, new CFO hired")
        form.addRow("Title", self.title_edit)

        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText(
            "How is the company going? A few honest sentences — revenue, "
            "runway, wins, worries…")
        self.text_edit.setMinimumHeight(120)
        form.addRow("Text *", self.text_edit)

        layout.addLayout(form)
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._validate)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

        if entry:
            if entry.get('date'):
                self.date_edit.setDate(QDate.fromString(
                    entry['date'][:10], "yyyy-MM-dd"))
            self.period_edit.setText(entry.get('period_label') or '')
            self.title_edit.setText(entry.get('title') or '')
            self.text_edit.setPlainText(entry.get('text') or '')
        else:
            self._suggest_period()

    def _suggest_period(self):
        import metrics as _m
        from datetime import date as _date
        d = self.date_edit.date()
        self.period_edit.setText(_m.quarter_label(
            _date(d.year(), d.month(), d.day())))

    def _validate(self):
        if not self.text_edit.toPlainText().strip():
            QMessageBox.warning(self, "Text required",
                                "The entry needs some text.")
            return
        self.accept()

    def get_data(self):
        return {
            'date': self.date_edit.date().toString("yyyy-MM-dd"),
            'period_label': self.period_edit.text().strip() or None,
            'title': self.title_edit.text().strip() or None,
            'text': self.text_edit.toPlainText().strip(),
        }


class DocumentDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Attach Document")
        self.setMinimumWidth(420)
        self._path = None
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        form = QFormLayout()

        file_row = QHBoxLayout()
        self.file_label = QLabel("No file selected")
        self.file_label.setStyleSheet(f"color: {MUTED};")
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse)
        file_row.addWidget(self.file_label, 1)
        file_row.addWidget(browse_btn)
        form.addRow("File *", file_row)

        self.doc_type = QComboBox()
        self.doc_type.addItems(DOC_TYPES)
        form.addRow("Document Type", self.doc_type)

        layout.addLayout(form)
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._validate)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Document", "",
            "Documents (*.pdf *.xlsx *.xls *.docx *.doc);;All Files (*)"
        )
        if path:
            self._path = path
            self.file_label.setText(os.path.basename(path))

    def _validate(self):
        if not self._path:
            QMessageBox.warning(self, "No file", "Please select a file.")
            return
        self.accept()

    def get_data(self):
        return {'path': self._path, 'doc_type': self.doc_type.currentText()}


class MetricsHelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ℹ How Metrics Are Calculated")
        self.setMinimumSize(540, 500)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setSpacing(10)

        entries = [
            ("Total Invested",
             "The sum of all money you put into a company across every funding round."),
            ("Current Value",
             "Your ownership % × the company's current valuation, which you enter manually "
             "in the company details. This is your estimated stake today."),
            ("Gain / Loss",
             "Current Value − Total Invested. Positive = profit, negative = loss."),
            ("ROI — Return on Investment",
             "(Current Value − Invested) ÷ Invested × 100. "
             "Example: ROI of 150% means your holding is worth 2.5× what you paid in."),
            ("MOIC — Multiple on Invested Capital",
             "Current Value ÷ Invested. "
             "1.0× = break-even. 2.0× = doubled your money. 0.5× = lost half."),
            ("IRR — Internal Rate of Return",
             "The annualised interest rate that would produce the same result as "
             "your actual cash flows (each investment date and the current value today). "
             "Accounts for how long your money has been invested. "
             "Shows 'n/a' when there is not enough data to calculate."),
            ("Valuation Step-Up",
             "How much the company's post-money valuation grew from one round to the next, "
             "shown as an absolute amount and a percentage. A higher step-up usually means "
             "the company raised at a higher price — good for existing investors."),
            ("Ownership %",
             "Your percentage of the total shares in the company. "
             "Can be typed in directly, or auto-calculated from Shares Received ÷ Total Shares. "
             "Watch for dilution: each new round where you don't invest typically reduces your %."),
        ]

        for title, desc in entries:
            box = QGroupBox(title)
            bl = QVBoxLayout(box)
            lbl = QLabel(desc)
            lbl.setWordWrap(True)
            bl.addWidget(lbl)
            inner_layout.addWidget(box)

        inner_layout.addStretch()
        scroll.setWidget(inner)
        layout.addWidget(scroll)

        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        layout.addWidget(close)


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(520)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        tabs = QTabWidget()

        general = QWidget()
        gl = QVBoxLayout(general)
        gl.setSpacing(12)
        form = QFormLayout()
        self.currency_sym  = QLineEdit(models.get_setting('currency', 'TKR'))
        self.currency_sym.setMaximumWidth(80)
        self.currency_name = QLineEdit(models.get_setting('currency_name', 'TKR'))
        self.currency_name.setMaximumWidth(100)
        form.addRow("Currency Symbol", self.currency_sym)
        form.addRow("Currency Name",   self.currency_name)
        gl.addLayout(form)

        backup_group = QGroupBox("Database Backup & Restore")
        bg = QVBoxLayout(backup_group)
        b1 = QPushButton("Backup database…")
        b1.clicked.connect(self._backup)
        b2 = QPushButton("Restore database…")
        b2.setStyleSheet(f"background:{BORDER}; color:{TEXT};")
        b2.clicked.connect(self._restore)
        bg.addWidget(b1)
        bg.addWidget(b2)
        gl.addWidget(backup_group)
        gl.addStretch()
        tabs.addTab(general, "General")

        from ui.ai_settings import AISettingsPage
        self.ai_page = AISettingsPage(self)
        tabs.addTab(self.ai_page, "AI")
        layout.addWidget(tabs)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _save(self):
        models.set_setting('currency',      self.currency_sym.text()  or '$')
        models.set_setting('currency_name', self.currency_name.text() or 'USD')
        self.ai_page.apply()
        self.accept()

    def _backup(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Backup Database", "investments_backup.db", "SQLite Database (*.db)"
        )
        if path:
            models.backup_db(path)
            QMessageBox.information(self, "Backup complete", f"Saved to:\n{path}")

    def _restore(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Restore Database", "", "SQLite Database (*.db)"
        )
        if not path:
            return
        reply = QMessageBox.question(
            self, "Restore database",
            "This will replace all current data with the backup. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            models.restore_db(path)
            QMessageBox.information(self, "Restored",
                "Database restored. Please restart the app for changes to take effect.")
