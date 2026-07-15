import os
import sys
import subprocess

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QGridLayout, QSizePolicy, QTableWidget,
    QTableWidgetItem, QHeaderView, QFileDialog, QMessageBox, QInputDialog,
    QTabWidget
)
from PyQt6.QtCore import Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QDesktopServices

import models
import metrics as m
from ui.styles import (
    GREEN, RED, ACCENT, MUTED, CARD, BORDER, TEXT, ACCENT_LITE,
    CARD_ALT, RED_SOFT, WARN_BG, WARN_BORDER, WARN_TEXT,
    SOFT_BTN_BG, SOFT_BTN_BORDER, SOFT_BTN_TEXT, SOFT_BTN_HOVER,
)

_SOFT_BTN_QSS = (
    f"QPushButton {{ background:{SOFT_BTN_BG}; color:{SOFT_BTN_TEXT}; "
    f"border:1px solid {SOFT_BTN_BORDER}; border-radius:6px; "
    f"padding:4px 12px; font-size:9pt; }}"
    f"QPushButton:hover {{ background:{SOFT_BTN_HOVER}; }}"
)


# ── Formatting helpers ────────────────────────────────────────────────────────

def _sym():
    return models.get_setting('currency', '$')

def _fmt(val, sym='$', dec=0):
    if val is None:
        return "n/a"
    try:
        return f"{sym}{val:,.{dec}f}"
    except Exception:
        return "n/a"

def _pct(val):
    return f"{val:.2f}%" if val is not None else "n/a"

def _moic(val):
    return f"{val:.2f}×" if val is not None else "n/a"

def _irr(val):
    return f"{val * 100:.1f}%" if val is not None else "n/a"


# ── Reusable widgets ──────────────────────────────────────────────────────────

class MetricCard(QFrame):
    def __init__(self, title, value, subtitle=None, color=None, parent=None, tooltip=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(f"""
            QFrame {{
                background: {CARD};
                border: 1px solid {BORDER};
                border-radius: 8px;
            }}
        """)
        if tooltip:
            self.setToolTip(tooltip)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(3)

        t = QLabel(title)
        t.setStyleSheet(f"color:{MUTED}; font-size:9pt; border:none;")
        layout.addWidget(t)

        v = QLabel(str(value))
        v.setStyleSheet(f"font-size:17pt; font-weight:bold; color:{color or TEXT}; border:none;")
        layout.addWidget(v)

        if subtitle:
            s = QLabel(str(subtitle))
            s.setStyleSheet(f"color:{color or MUTED}; font-size:9pt; border:none;")
            layout.addWidget(s)

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)


class SectionLabel(QLabel):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        f = QFont(); f.setBold(True); f.setPointSize(10)
        self.setFont(f)
        self.setStyleSheet(
            f"color:{ACCENT}; border-bottom:2px solid {BORDER}; "
            f"padding-bottom:4px; margin-top:10px;"
        )


# ── Main panel ────────────────────────────────────────────────────────────────

class DetailPanel(QWidget):
    documents_changed = pyqtSignal()   # emitted after any upload / delete

    def __init__(self, parent=None):
        super().__init__(parent)
        self._company_tab = 0          # remembered tab index within a company view
        self._company_shown_id = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)

        self._content = QWidget()
        self._cl = QVBoxLayout(self._content)
        self._cl.setContentsMargins(20, 20, 20, 20)
        self._cl.setSpacing(10)
        self._cl.addStretch()

        self._scroll.setWidget(self._content)
        layout.addWidget(self._scroll)

    def _clear(self):
        self._clear_layout(self._cl)

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
            else:
                sub = item.layout()
                if sub:
                    self._clear_layout(sub)

    # ── Views ─────────────────────────────────────────────────────────────────

    def show_entity(self, entity_name: str):
        self._clear()
        sym      = _sym()
        companies = models.get_companies_by_entity().get(entity_name, [])
        rounds_by = {c['id']: models.get_rounds(c['id']) for c in companies}
        flows_by = models.get_cashflows_by_company()
        import metrics as _m
        pm = _m.portfolio_metrics(companies, rounds_by,
                                  flows_by_company=flows_by)

        title = QLabel(entity_name)
        title.setStyleSheet("font-size:20pt; font-weight:bold;")
        self._cl.addWidget(title)

        sub = QLabel(f"{len(companies)} companies")
        sub.setStyleSheet(f"color:{MUTED};")
        self._cl.addWidget(sub)

        self._cl.addWidget(SectionLabel("Entity Metrics"))
        row = QHBoxLayout(); row.setSpacing(10)

        gain = pm.get('gain')
        gc   = GREEN if (gain is not None and gain >= 0) else RED if gain is not None else None
        gs   = ("+" if gain and gain >= 0 else "−") + f"{sym}{abs(gain):,.0f}" if gain is not None else "n/a"

        row.addWidget(MetricCard("Total Invested", _fmt(pm['total_invested'], sym),
            tooltip="Total amount invested across all companies in this portfolio."))
        row.addWidget(MetricCard("Current Value", _fmt(pm.get('total_current'), sym),
            tooltip="Combined current value of all valued companies in this portfolio.\n"
                    "Companies without a valuation are excluded."))
        row.addWidget(MetricCard("Gain / Loss", gs, _pct(pm.get('roi')), gc,
            tooltip="Total profit or loss across all valued companies in this portfolio.\n"
                    "= Current Value − Invested (for valued companies only)."))
        row.addWidget(MetricCard("MOIC", _moic(pm.get('moic')),
            tooltip="MOIC = Multiple on Invested Capital for this entire portfolio.\n"
                    "How many times the invested money has multiplied in total.\n"
                    "1.0× = broke even  |  2.0× = doubled."))
        row.addWidget(MetricCard("IRR", _irr(pm.get('irr')),
            tooltip="IRR = Internal Rate of Return for this entire portfolio.\n"
                    "The annualised growth rate — like a bank interest rate on the whole portfolio."))
        self._cl.addLayout(row)

        # Company list table
        self._cl.addWidget(SectionLabel("Companies"))
        headers = ["Company", "Sector", "Invested", "Current Value", "Gain/Loss", "MOIC"]
        tbl = QTableWidget(len(companies), len(headers))
        tbl.setHorizontalHeaderLabels(headers)
        tbl.setAlternatingRowColors(True)
        tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        tbl.verticalHeader().setVisible(False)
        tbl.horizontalHeader().setStretchLastSection(True)
        for i, c in enumerate(companies):
            met = _m.company_metrics_for(c, rounds_by.get(c['id'], []),
                                         flows_by.get(c['id'], []))
            gain_c = met.get('gain')
            gs2    = ("+" if gain_c and gain_c >= 0 else "") + _fmt(gain_c, sym) if gain_c is not None else "n/a"
            tbl.setItem(i, 0, QTableWidgetItem(c['name']))
            tbl.setItem(i, 1, QTableWidgetItem(c.get('sector', '') or ''))
            tbl.setItem(i, 2, QTableWidgetItem(_fmt(met['total_invested'], sym)))
            tbl.setItem(i, 3, QTableWidgetItem(_fmt(met.get('current_value'), sym)))
            gi = QTableWidgetItem(gs2)
            if gain_c is not None:
                gi.setForeground(QColor(GREEN if gain_c >= 0 else RED))
            tbl.setItem(i, 4, gi)
            tbl.setItem(i, 5, QTableWidgetItem(_moic(met.get('moic'))))
        tbl.resizeColumnsToContents()
        tbl.setMinimumHeight(min(400, 42 + len(companies) * 36))
        self._cl.addWidget(tbl)
        self._cl.addStretch()

    def show_welcome(self):
        self._clear()
        lbl = QLabel("← Select a company, round, or document\nfrom the tree to view details.")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(f"color:{MUTED}; font-size:12pt;")
        self._cl.addStretch()
        self._cl.addWidget(lbl)
        self._cl.addStretch()

    def show_company(self, cid):
        self._clear()
        c = models.get_company(cid)
        if not c:
            return
        sym   = _sym()
        rounds = models.get_rounds(cid)
        flows = models.get_cashflows(cid)
        met   = m.company_metrics_for(c, rounds, flows)

        # Remember the active tab while staying on the same company,
        # reset when switching to a different one.
        if self._company_shown_id != cid:
            self._company_tab = 0
            self._company_shown_id = cid

        # Title + website button on same row
        title_row = QHBoxLayout()
        title_row.setSpacing(12)

        title = QLabel(c['name'])
        title.setStyleSheet("font-size:20pt; font-weight:bold;")
        title_row.addWidget(title)

        website = (c.get('website') or '').strip()
        if website:
            url = website if website.startswith('http') else f"https://{website}"
            web_btn = QPushButton("🌐  Open website")
            web_btn.setStyleSheet(_SOFT_BTN_QSS)
            web_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            web_btn.clicked.connect(lambda _checked, u=url: QDesktopServices.openUrl(QUrl(u)))
            title_row.addWidget(web_btn)

        title_row.addStretch()
        self._cl.addLayout(title_row)

        meta = []
        if c.get('entity'):          meta.append(c['entity'])
        if c.get('investment_type'): meta.append(c['investment_type'])
        if c.get('sector'):          meta.append(c['sector'])
        if c.get('country'):         meta.append(c['country'])
        if meta:
            ml = QLabel(" · ".join(meta))
            ml.setStyleSheet(f"color:{MUTED}; font-size:9pt;")
            self._cl.addWidget(ml)

        # ── Tabbed layout: Overview / Rounds / Documents ─────────────────────
        tabs = QTabWidget()
        tabs.setDocumentMode(True)

        def _page():
            w = QWidget()
            lay = QVBoxLayout(w)
            lay.setContentsMargins(4, 12, 4, 12)
            lay.setSpacing(10)
            return w, lay

        ov_page, ov = _page()
        rd_page, rd = _page()
        dc_page, dc = _page()

        n_docs = len(models.get_documents(company_id=cid))
        tabs.addTab(ov_page, "Overview")
        tabs.addTab(rd_page, f"Rounds & Cash flows ({len(rounds)})")
        tabs.addTab(dc_page, f"Documents ({n_docs})")

        # Description block
        description = (c.get('description') or '').strip()
        if description:
            desc_frame = QFrame()
            desc_frame.setStyleSheet(
                f"QFrame {{ background:{CARD}; border-left:3px solid {ACCENT}; "
                f"border-radius:0px; padding:0px; }}"
            )
            desc_lay = QVBoxLayout(desc_frame)
            desc_lay.setContentsMargins(14, 10, 14, 10)
            desc_lay.setSpacing(2)
            lbl_hdr = QLabel("About")
            lbl_hdr.setStyleSheet(f"color:{MUTED}; font-size:8pt; font-weight:bold; border:none;")
            desc_text = QLabel(description)
            desc_text.setWordWrap(True)
            desc_text.setStyleSheet(f"color:{TEXT}; font-size:10pt; border:none;")
            desc_lay.addWidget(lbl_hdr)
            desc_lay.addWidget(desc_text)
            ov.addWidget(desc_frame)

        # Investment Thesis
        thesis = (c.get('thesis') or '').strip()
        thesis_hdr = QHBoxLayout()
        thesis_hdr.setSpacing(8)
        thesis_sec_lbl = SectionLabel("Investment Thesis")
        edit_thesis_btn = QPushButton("Edit")
        edit_thesis_btn.setFixedHeight(22)
        edit_thesis_btn.setStyleSheet(_SOFT_BTN_QSS)
        edit_thesis_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        edit_thesis_btn.clicked.connect(lambda _c, _cid=cid: self._edit_thesis(_cid))
        thesis_hdr.addWidget(thesis_sec_lbl)
        thesis_hdr.addWidget(edit_thesis_btn)
        thesis_hdr.addStretch()
        ov.addLayout(thesis_hdr)
        if thesis:
            thesis_frame = QFrame()
            thesis_frame.setStyleSheet(
                f"QFrame {{ background:{CARD}; border-left:3px solid #818CF8; "
                f"border-radius:0px; padding:0px; }}"
            )
            thesis_lay = QVBoxLayout(thesis_frame)
            thesis_lay.setContentsMargins(14, 10, 14, 10)
            thesis_text = QLabel(thesis)
            thesis_text.setWordWrap(True)
            thesis_text.setStyleSheet(f"color:{TEXT}; font-size:10pt; border:none;")
            thesis_lay.addWidget(thesis_text)
            ov.addWidget(thesis_frame)
        else:
            no_thesis = QLabel("No thesis recorded yet — click Edit to add one.")
            no_thesis.setStyleSheet(f"color:{MUTED}; font-size:9pt;")
            ov.addWidget(no_thesis)

        # Position summary: realized vs unrealized, family-office multiples.
        # Every card's tooltip carries the footnote from metrics.py.
        ov.addWidget(SectionLabel("Position Summary"))
        row = QHBoxLayout()
        row.setSpacing(10)

        closed_note = ("\n" + m.FOOTNOTE_CLOSED) if met['closed'] else ""
        as_of = met.get('valuation_as_of') or 'today'

        row.addWidget(MetricCard("Invested", _fmt(met['total_invested'], sym),
            tooltip=m.FOOTNOTE_INVESTED))
        realized_color = GREEN if met['realized'] else None
        row.addWidget(MetricCard("Realized", _fmt(met['realized'], sym),
            color=realized_color, tooltip=m.FOOTNOTE_REALIZED))
        row.addWidget(MetricCard("Current Value", _fmt(met['current_value'], sym),
            tooltip=m.VALUATION_MEANING_FOOTNOTE + closed_note))
        row.addWidget(MetricCard("MOIC", _moic(met['moic']),
            tooltip=m.FOOTNOTE_MOIC))
        row.addWidget(MetricCard("DPI", _moic(met['dpi']),
            tooltip=m.FOOTNOTE_DPI))
        row.addWidget(MetricCard("TVPI", _moic(met['tvpi']),
            tooltip=m.FOOTNOTE_TVPI + "\n" + m.FOOTNOTE_DPI + "\n"
                    + m.FOOTNOTE_RVPI))
        row.addWidget(MetricCard("IRR", _irr(met['irr']),
            tooltip=m.FOOTNOTE_IRR.format(as_of=as_of)))
        ov.addLayout(row)

        # ── Valuation block: history is the single source of truth ────────
        self._add_valuation_block(ov, c, met, sym)

        # Notes
        if c.get('notes'):
            ov.addWidget(SectionLabel("Notes"))
            nl = QLabel(c['notes'])
            nl.setWordWrap(True)
            nl.setStyleSheet(
                f"background:{CARD}; border:1px solid {BORDER}; "
                f"border-radius:6px; padding:10px;"
            )
            ov.addWidget(nl)

        # ── Rounds & Cash flows tab ───────────────────────────────────────────
        if rounds:
            rd.addWidget(SectionLabel("Funding Rounds"))
            self._add_rounds_table(rounds, sym, target=rd)
            self._add_valuation_progression(rounds, sym, target=rd)
        else:
            no_rounds = QLabel(
                "No funding rounds recorded.\n"
                "Right-click the company in the tree → Add Round."
            )
            no_rounds.setStyleSheet(f"color:{MUTED}; font-size:10pt;")
            rd.addWidget(no_rounds)
        self._add_ledger(rd, cid, flows, sym)

        # ── Documents tab ─────────────────────────────────────────────────────
        dc.addWidget(self._doc_category_widget(
            cid, "SHA / Shareholders Agreement",
            lambda t: 'sha' in t.lower() or 'shareholder' in t.lower(), "SHA"))
        dc.addWidget(self._doc_category_widget(
            cid, "Investment Agreements",
            lambda t: 'investment agreement' in t.lower(), "Investment Agreement"))
        dc.addWidget(self._doc_category_widget(
            cid, "Other Documents",
            lambda t: 'sha' not in t.lower() and 'shareholder' not in t.lower()
                      and 'investment agreement' not in t.lower(), "Other"))

        for lay in (ov, rd, dc):
            lay.addStretch()

        tabs.setCurrentIndex(min(self._company_tab, tabs.count() - 1))
        tabs.currentChanged.connect(lambda i: setattr(self, '_company_tab', i))
        self._cl.addWidget(tabs)
        self._cl.addStretch()

    # ── Document section ──────────────────────────────────────────────────────

    def _doc_category_widget(self, cid, heading, type_match, upload_type):
        """Return a card widget for one document category."""
        all_docs = models.get_documents(company_id=cid)
        docs = [d for d in all_docs if type_match(d.get('doc_type') or '')]

        frame = QFrame()
        frame.setStyleSheet(
            f"QFrame {{ background:{CARD}; border:1px solid {BORDER}; border-radius:8px; }}"
        )
        outer = QVBoxLayout(frame)
        outer.setContentsMargins(14, 10, 14, 10)
        outer.setSpacing(6)

        # Header row: category name + upload button
        hdr = QHBoxLayout()
        hdr.setSpacing(8)
        hdr_lbl = QLabel(heading)
        hdr_lbl.setStyleSheet(
            f"font-weight:bold; font-size:9pt; color:{TEXT}; border:none;"
        )
        up_btn = QPushButton("+ Upload")
        up_btn.setFixedHeight(24)
        up_btn.setStyleSheet(
            f"QPushButton {{ background:{ACCENT}; color:white; border:none; "
            f"border-radius:4px; padding:2px 10px; font-size:8pt; }}"
            f"QPushButton:hover {{ background:#2563EB; }}"
        )
        up_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        up_btn.clicked.connect(
            lambda _c, c=cid, t=upload_type: self._upload_doc(c, t)
        )
        hdr.addWidget(hdr_lbl)
        hdr.addStretch()
        hdr.addWidget(up_btn)
        outer.addLayout(hdr)

        if not docs:
            empty = QLabel("No documents uploaded")
            empty.setStyleSheet(f"color:{MUTED}; font-size:8pt; border:none;")
            outer.addWidget(empty)
        else:
            for d in docs:
                row = QHBoxLayout()
                row.setSpacing(6)

                icon = QLabel("📎")
                icon.setStyleSheet("border:none; font-size:10pt;")
                icon.setFixedWidth(20)

                name = QLabel(d['original_filename'])
                name.setStyleSheet(f"color:{TEXT}; font-size:9pt; border:none;")
                name.setToolTip(d.get('added_date') or '')

                open_btn = QPushButton("Open")
                open_btn.setFixedHeight(22)
                open_btn.setStyleSheet(_SOFT_BTN_QSS)
                open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                open_btn.clicked.connect(
                    lambda _c, did=d['id']: self._open_doc_file(did)
                )

                del_btn = QPushButton("✕")
                del_btn.setFixedSize(22, 22)
                del_btn.setStyleSheet(
                    f"QPushButton {{ background:{RED_SOFT}; color:{RED}; border:none; "
                    f"border-radius:4px; font-size:8pt; }}"
                    f"QPushButton:hover {{ background:#3D2126; }}"
                )
                del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                del_btn.clicked.connect(
                    lambda _c, did=d['id'], c=cid: self._delete_doc_detail(did, c)
                )

                row.addWidget(icon)
                row.addWidget(name, 1)
                row.addWidget(open_btn)
                row.addWidget(del_btn)
                outer.addLayout(row)

        return frame

    def _upload_doc(self, cid, doc_type):
        path, _ = QFileDialog.getOpenFileName(
            self, f"Upload — {doc_type}", "",
            "Documents (*.pdf *.docx *.doc *.xlsx *.xls *.png *.jpg *.jpeg);;All Files (*)"
        )
        if path:
            models.add_document(path, doc_type, company_id=cid)
            self.documents_changed.emit()
            self.show_company(cid)

    def _delete_doc_detail(self, did, cid):
        if QMessageBox.question(
            self, "Delete Document", "Remove this document from the tracker?\n(The original file is not deleted.)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) == QMessageBox.StandardButton.Yes:
            models.delete_document(did)
            self.documents_changed.emit()
            self.show_company(cid)

    def _edit_thesis(self, cid):
        c = models.get_company(cid)
        if not c:
            return
        text, ok = QInputDialog.getMultiLineText(
            self, "Investment Thesis",
            f"Why did we invest in {c['name']}?",
            c.get('thesis') or ''
        )
        if ok:
            models.update_company(cid, thesis=text.strip())
            self.show_company(cid)

    def _open_doc_file(self, did):
        path = models.get_document_path(did)
        if not path or not os.path.exists(path):
            QMessageBox.warning(self, "File not found",
                                "The file could not be found on disk.")
            return
        if sys.platform == 'win32':
            os.startfile(path)
        elif sys.platform == 'darwin':
            subprocess.run(['open', path])
        else:
            subprocess.run(['xdg-open', path])

    # ── Cash-flow ledger ──────────────────────────────────────────────────────

    _FLOW_LABELS = {
        'investment': 'Investment', 'follow_on': 'Follow-on',
        'exit_proceeds': 'Exit proceeds', 'partial_sale': 'Partial sale',
        'dividend': 'Dividend', 'distribution': 'Distribution',
        'fee': 'Fee', 'other_in': 'Other (in)', 'other_out': 'Other (out)',
    }

    def _add_ledger(self, rd, cid, flows, sym):
        """Every money movement, with running invested/realized columns.
        Round-linked rows are edited through the round dialog only."""
        rd.addWidget(SectionLabel("Cash Flow Ledger"))
        if flows:
            tbl = QTableWidget(len(flows), 6)
            tbl.setHorizontalHeaderLabels(
                ["Date", "Type", "Amount", "Invested →", "Realized →",
                 "Note"])
            tbl.verticalHeader().setVisible(False)
            tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            tbl.setSelectionBehavior(
                QTableWidget.SelectionBehavior.SelectRows)
            run_inv = run_real = 0.0
            for i, f in enumerate(flows):
                signed = m.signed_amount(f['type'], f['amount'])
                if signed < 0:
                    run_inv += -signed
                else:
                    run_real += signed
                note = f.get('note') or ''
                if f.get('shares_delta'):
                    note = (f"{f['shares_delta']:+,.0f} shares · " + note).strip(' ·')
                cells = [
                    f['date'] or '—',
                    self._FLOW_LABELS.get(f['type'], f['type']),
                    f"{'+' if signed >= 0 else '−'}{sym}{abs(signed):,.0f}",
                    f"{sym}{run_inv:,.0f}",
                    f"{sym}{run_real:,.0f}",
                    note,
                ]
                for col, text in enumerate(cells):
                    item = QTableWidgetItem(str(text))
                    if col == 1:
                        item.setForeground(QColor(
                            RED if signed < 0 else GREEN))
                        if f.get('round_id'):
                            item.setToolTip('Linked to a funding round — '
                                            'edit the round to change it.')
                    if col == 2:
                        item.setForeground(QColor(
                            RED if signed < 0 else GREEN))
                    tbl.setItem(i, col, item)
                tbl.item(i, 0).setData(Qt.ItemDataRole.UserRole, f['id'])
            tbl.horizontalHeader().setSectionResizeMode(
                5, QHeaderView.ResizeMode.Stretch)
            tbl.setMaximumHeight(min(280, 60 + 30 * len(flows)))
            rd.addWidget(tbl)
            self._flow_table = tbl
        else:
            empty = QLabel("No cash flows yet — rounds create investment "
                           "flows automatically; dividends, exits and "
                           "sales are added below.")
            empty.setStyleSheet(f"color:{MUTED}; font-size:9pt;")
            rd.addWidget(empty)
            self._flow_table = None

        btn_row = QHBoxLayout()
        for text, slot in [
                ("＋ Add cash flow", lambda: self._add_flow(cid)),
                ("Edit selected", lambda: self._edit_flow(cid)),
                ("Delete selected", lambda: self._delete_flow(cid))]:
            b = QPushButton(text)
            b.setStyleSheet(_SOFT_BTN_QSS)
            b.clicked.connect(slot)
            btn_row.addWidget(b)
        btn_row.addStretch()
        rd.addLayout(btn_row)

    def _selected_flow(self, cid):
        tbl = getattr(self, '_flow_table', None)
        if tbl is None or tbl.currentRow() < 0:
            QMessageBox.information(self, "No selection",
                                    "Select a row in the ledger first.")
            return None
        fid = tbl.item(tbl.currentRow(), 0).data(Qt.ItemDataRole.UserRole)
        return models.get_cashflow(fid)

    def _add_flow(self, cid):
        from ui.dialogs import CashflowDialog
        dlg = CashflowDialog(self, company_id=cid)
        if dlg.exec():
            d = dlg.get_data()
            models.add_cashflow(cid, d['date'], d['type'], d['amount'],
                                shares_delta=d['shares_delta'],
                                note=d['note'], origin='ui.cashflow_dialog')
            if d['type'] == 'exit_proceeds':
                self._offer_exit_status(cid)
            self.show_company(cid)

    def _edit_flow(self, cid):
        f = self._selected_flow(cid)
        if not f:
            return
        if f.get('round_id'):
            QMessageBox.information(
                self, "Linked to a round",
                "This investment flow belongs to a funding round.\n"
                "Edit the round (Rounds table above) and the flow follows "
                "automatically.")
            return
        from ui.dialogs import CashflowDialog
        dlg = CashflowDialog(self, company_id=cid, flow=f)
        if dlg.exec():
            models.update_cashflow(f['id'], origin='ui.cashflow_dialog',
                                   **dlg.get_data())
            self.show_company(cid)

    def _delete_flow(self, cid):
        f = self._selected_flow(cid)
        if not f:
            return
        if f.get('round_id'):
            QMessageBox.information(
                self, "Linked to a round",
                "This investment flow belongs to a funding round.\n"
                "Delete the round instead — its flow is removed with it.")
            return
        if QMessageBox.question(
                self, "Delete cash flow",
                "Delete this cash flow? The change is recorded in the "
                "history log.",
                QMessageBox.StandardButton.Yes |
                QMessageBox.StandardButton.No
        ) == QMessageBox.StandardButton.Yes:
            models.delete_cashflow(f['id'], origin='ui.cashflow_dialog')
            self.show_company(cid)

    def _offer_exit_status(self, cid):
        c = models.get_company(cid)
        if not c or m.is_closed(c.get('notes')):
            return
        if QMessageBox.question(
                self, "Mark as exited?",
                "You recorded exit proceeds. Set this company's status to "
                "Exited?\n(Unrealized value then counts as 0 — only real "
                "proceeds remain.)",
                QMessageBox.StandardButton.Yes |
                QMessageBox.StandardButton.No
        ) == QMessageBox.StandardButton.Yes:
            notes = 'Status: Exited\n' + (c.get('notes') or '')
            models.update_company(cid, notes=notes.strip(),
                                  origin='ui.cashflow_dialog')

    # ── Rounds table ──────────────────────────────────────────────────────────

    def _add_valuation_block(self, ov, c, met, sym):
        """Current value with as-of/source + full history table with Δ%,
        plus add/edit/delete — all through the valuation history."""
        from ui.dialogs import ValuationDialog
        cid = c['id']
        ov.addWidget(SectionLabel("Valuation"))
        history = models.get_valuations(cid)

        if history:
            cur = history[0]
            label = ValuationDialog.SOURCE_LABELS.get(cur['source'],
                                                      cur['source'])
            note = QLabel(
                f"Current company valuation: {_fmt(cur['value'], sym)}  |  "
                f"Our stake ({_pct(met['ownership'])}): "
                f"{_fmt(met['current_value'], sym)}")
            note.setStyleSheet("font-size:10pt;")
            ov.addWidget(note)
            foot = QLabel(m.UNREALIZED_VALUE_FOOTNOTE.format(
                date=cur['as_of_date'], source=label))
            foot.setStyleSheet(f"color:{MUTED}; font-size:8.5pt;")
            ov.addWidget(foot)

            tbl = QTableWidget(len(history), 5)
            tbl.setHorizontalHeaderLabels(
                ["As of", "Value", "Source", "Note", "Δ% vs previous"])
            tbl.verticalHeader().setVisible(False)
            tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            tbl.setSelectionBehavior(
                QTableWidget.SelectionBehavior.SelectRows)
            for i, v in enumerate(history):
                prev = history[i + 1] if i + 1 < len(history) else None
                delta = ''
                color = None
                if prev and prev['value']:
                    pct = (v['value'] - prev['value']) / prev['value'] * 100
                    delta = f"{pct:+.1f}%"
                    color = GREEN if pct >= 0 else RED
                cells = [
                    v['as_of_date'],
                    _fmt(v['value'], sym),
                    ValuationDialog.SOURCE_LABELS.get(v['source'],
                                                      v['source']),
                    v.get('note') or '',
                    delta,
                ]
                for col, text in enumerate(cells):
                    item = QTableWidgetItem(str(text))
                    if col == 4 and color:
                        item.setForeground(QColor(color))
                    tbl.setItem(i, col, item)
                tbl.item(i, 0).setData(Qt.ItemDataRole.UserRole, v['id'])
            tbl.horizontalHeader().setSectionResizeMode(
                3, QHeaderView.ResizeMode.Stretch)
            tbl.setMaximumHeight(min(220, 60 + 30 * len(history)))
            ov.addWidget(tbl)
            self._val_table = tbl
        else:
            hint = QLabel(
                "ℹ  No valuation recorded — value and return metrics show "
                "n/a.\nAdd a valuation point below, or record one via a "
                "round's post-money value.")
            hint.setWordWrap(True)
            hint.setStyleSheet(
                f"background:{WARN_BG}; border:1px solid {WARN_BORDER}; "
                f"border-radius:6px; padding:10px; color:{WARN_TEXT};")
            ov.addWidget(hint)
            self._val_table = None

        btn_row = QHBoxLayout()
        for text, slot in [
                ("＋ Add valuation", lambda: self._add_valuation(cid)),
                ("Edit selected", lambda: self._edit_valuation(cid)),
                ("Delete selected", lambda: self._delete_valuation(cid)),
                ("View history…", lambda: self._show_history(cid))]:
            b = QPushButton(text)
            b.setStyleSheet(_SOFT_BTN_QSS)
            b.clicked.connect(slot)
            btn_row.addWidget(b)
        btn_row.addStretch()
        ov.addLayout(btn_row)

    def _selected_valuation_id(self):
        tbl = getattr(self, '_val_table', None)
        if tbl is None or tbl.currentRow() < 0:
            return None
        item = tbl.item(tbl.currentRow(), 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _add_valuation(self, cid):
        from ui.dialogs import ValuationDialog
        dlg = ValuationDialog(self)
        if dlg.exec():
            d = dlg.get_data()
            models.add_valuation(cid, d['as_of_date'], d['value'],
                                 d['source'], note=d['note'],
                                 origin='ui.valuation_dialog')
            self.show_company(cid)

    def _edit_valuation(self, cid):
        vid = self._selected_valuation_id()
        if vid is None:
            QMessageBox.information(self, "No selection",
                                    "Select a row in the valuation table first.")
            return
        from ui.dialogs import ValuationDialog
        v = next((x for x in models.get_valuations(cid) if x['id'] == vid),
                 None)
        dlg = ValuationDialog(self, valuation=v)
        if dlg.exec():
            models.update_valuation(vid, origin='ui.valuation_dialog',
                                    **dlg.get_data())
            self.show_company(cid)

    def _delete_valuation(self, cid):
        vid = self._selected_valuation_id()
        if vid is None:
            QMessageBox.information(self, "No selection",
                                    "Select a row in the valuation table first.")
            return
        if QMessageBox.question(
                self, "Delete valuation point",
                "Delete this valuation point? The change is recorded in "
                "the history log.",
                QMessageBox.StandardButton.Yes |
                QMessageBox.StandardButton.No
        ) == QMessageBox.StandardButton.Yes:
            models.delete_valuation(vid, origin='ui.valuation_dialog')
            self.show_company(cid)

    def _show_history(self, cid):
        from ui.history_dialog import HistoryDialog
        HistoryDialog(self, company_id=cid).exec()

    def _add_rounds_table(self, rounds, sym, target=None):
        headers = ["Round", "Date", "Invested", "Pre-Money", "Post-Money",
                   "Shares", "Ownership %", "Status"]
        tbl = QTableWidget(len(rounds), len(headers))
        tbl.setHorizontalHeaderLabels(headers)
        tbl.setAlternatingRowColors(True)
        tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        tbl.verticalHeader().setVisible(False)
        tbl.horizontalHeader().setStretchLastSection(True)
        tbl.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

        for i, r in enumerate(rounds):
            def si(v): return QTableWidgetItem(str(v) if v is not None else "")
            tbl.setItem(i, 0, si(r.get('round_name', '')))
            tbl.setItem(i, 1, si(r.get('date', '')))
            tbl.setItem(i, 2, si(_fmt(r.get('amount_invested'), sym)))
            tbl.setItem(i, 3, si(_fmt(r.get('pre_money_valuation'), sym)))
            tbl.setItem(i, 4, si(_fmt(r.get('post_money_valuation'), sym)))
            shares = r.get('shares_received')
            tbl.setItem(i, 5, si(f"{int(shares):,}" if shares else "n/a"))
            tbl.setItem(i, 6, si(_pct(r.get('ownership_pct'))))
            status_item = QTableWidgetItem(r.get('status', ''))
            status_item.setForeground(
                QColor(GREEN) if r.get('status') == 'Open' else QColor(MUTED)
            )
            tbl.setItem(i, 7, status_item)

        tbl.resizeColumnsToContents()
        tbl.setFixedHeight(min(220, 42 + len(rounds) * 36))
        (target or self._cl).addWidget(tbl)

    def _add_valuation_progression(self, rounds, sym, target=None):
        target = target or self._cl
        dated = [(r.get('date') or '', r) for r in rounds if r.get('post_money_valuation')]
        if len(dated) < 2:
            return
        dated.sort(key=lambda x: x[0])

        target.addWidget(SectionLabel("Valuation Progression (Post-Money)"))
        grid = QGridLayout()
        grid.setSpacing(6)
        for col, h in enumerate(["Round", "Post-Money", "Step-Up"]):
            lbl = QLabel(h)
            lbl.setStyleSheet(f"font-weight:bold; color:{MUTED}; font-size:9pt;")
            grid.addWidget(lbl, 0, col)

        prev = None
        for i, (_, r) in enumerate(dated, 1):
            pv = r['post_money_valuation']
            grid.addWidget(QLabel(r.get('round_name', '')), i, 0)
            grid.addWidget(QLabel(_fmt(pv, sym)), i, 1)
            if prev and pv:
                pct = (pv - prev) / prev * 100
                sign = "+" if pct >= 0 else ""
                sl = QLabel(f"{sign}{pct:.0f}%")
                sl.setStyleSheet(f"color:{GREEN if pct >= 0 else RED}; font-weight:bold;")
                grid.addWidget(sl, i, 2)
            prev = pv

        target.addLayout(grid)

    def show_round(self, rid):
        self._clear()
        r = models.get_round(rid)
        if not r:
            return
        sym = _sym()
        c   = models.get_company(r['company_id'])

        title = QLabel(f"{r.get('round_name', 'Round')}  —  {c['name'] if c else ''}")
        title.setStyleSheet("font-size:16pt; font-weight:bold;")
        self._cl.addWidget(title)

        date_lbl = QLabel(r.get('date', '') or '')
        date_lbl.setStyleSheet(f"color:{MUTED}; margin-bottom:6px;")
        self._cl.addWidget(date_lbl)

        self._cl.addWidget(SectionLabel("Round Details"))

        grid = QGridLayout()
        grid.setSpacing(8)
        fields = [
            ("Amount Invested",       _fmt(r.get('amount_invested'), sym, 2)),
            ("Pre-Money Valuation",   _fmt(r.get('pre_money_valuation'), sym)),
            ("Post-Money Valuation",  _fmt(r.get('post_money_valuation'), sym)),
            ("Shares Received",       f"{int(r['shares_received']):,}" if r.get('shares_received') else "n/a"),
            ("Price Per Share",       _fmt(r.get('price_per_share'), sym, 4)),
            ("Total Shares Outstanding", f"{int(r['total_shares_outstanding']):,}" if r.get('total_shares_outstanding') else "n/a"),
            ("Our Ownership %",       _pct(r.get('ownership_pct'))),
            ("Status",                r.get('status', '')),
        ]
        for i, (label, value) in enumerate(fields):
            row_i, col_i = divmod(i, 2)
            ll = QLabel(label + ":")
            ll.setStyleSheet(f"color:{MUTED}; font-size:9pt;")
            vl = QLabel(value)
            vl.setStyleSheet("font-weight:bold;")
            grid.addWidget(ll, row_i, col_i * 2)
            grid.addWidget(vl, row_i, col_i * 2 + 1)

        self._cl.addLayout(grid)
        self._cl.addStretch()

    def show_document(self, did):
        self._clear()
        doc = models.get_document_detail(did)
        if not doc:
            return

        title = QLabel(f"📎  {doc['original_filename']}")
        title.setStyleSheet("font-size:14pt; font-weight:bold;")
        self._cl.addWidget(title)

        for label, value in [
            ("Type",    doc.get('doc_type', '')),
            ("Company", doc.get('company_name', '') or ""),
            ("Round",   doc.get('round_name', '')   or ""),
            ("Added",   doc.get('added_date', '')   or ""),
        ]:
            if value:
                lbl = QLabel(f"{label}: {value}")
                lbl.setStyleSheet(f"color:{MUTED};")
                self._cl.addWidget(lbl)

        path = models.get_document_path(did)
        if path and os.path.exists(path):
            btn = QPushButton("Open Document")
            btn.setFixedWidth(160)

            def open_it():
                if sys.platform == 'win32':
                    os.startfile(path)
                elif sys.platform == 'darwin':
                    subprocess.run(['open', path])
                else:
                    subprocess.run(['xdg-open', path])

            btn.clicked.connect(open_it)
            self._cl.addWidget(btn)

        self._cl.addStretch()
