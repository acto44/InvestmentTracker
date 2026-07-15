from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QSplitter,
    QTabWidget, QFileDialog, QMessageBox, QToolBar, QFrame, QLabel,
    QPushButton
)
from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtGui import QAction, QKeySequence

import models
import excel_io
from ui.tree_panel import TreePanel, NODE_ENTITY, NODE_COMPANY, NODE_ROUND, NODE_DOC
from ui.detail_panel import DetailPanel
from ui.dashboard import DashboardTab
from ui.dialogs import MetricsHelpDialog, SettingsDialog


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Investment Tracker")
        self.setMinimumSize(1100, 700)
        self.resize(1500, 860)   # roomy enough for the right rail
        self._build_topbar()
        self._build_ui()
        self._ai_action = None
        self._ai_rail_btn = None
        self._refresh_ai_affordances()
        self._build_shortcuts()
        self._restore_state()
        sb = self.statusBar()
        if sb:
            sb.showMessage(
                "Ready — Ctrl+N adds a company, Ctrl+K searches, "
                "navigation is in the sidebar.")

    # ── Global shortcuts (survived the menu bar's removal) ────────────────────

    def _build_shortcuts(self):
        for text, seq, slot in (
                ("Add Company", "Ctrl+N", self._quick_add_company),
                ("Go to Company", "Ctrl+K", self._quick_jump),
                ("Refresh", "Ctrl+R", self._refresh_all),
                ("Preferences", "Ctrl+,", self._open_settings)):
            a = QAction(text, self)
            a.setShortcut(QKeySequence(seq))
            a.triggered.connect(slot)
            self.addAction(a)

    # ── Top bar: global search + primary actions ──────────────────────────────

    def _build_topbar(self):
        from PyQt6.QtWidgets import QLineEdit, QMenu, QSizePolicy
        tb = QToolBar("Main")
        tb.setMovable(False)
        self.addToolBar(tb)

        self._search = QLineEdit()
        self._search.setObjectName("GlobalSearch")
        self._search.setPlaceholderText(
            "Search companies, sectors…   (Ctrl+K)")
        self._search.setFixedWidth(340)
        self._search.setClearButtonEnabled(True)
        self._search.textEdited.connect(self._search_typed)
        tb.addWidget(self._search)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding,
                             QSizePolicy.Policy.Preferred)
        tb.addWidget(spacer)

        def top_btn(text, slot=None, menu=None, primary=False, tip=None):
            b = QPushButton(text)
            if not primary:
                b.setObjectName("TopBtn")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            if tip:
                b.setToolTip(tip)
            if menu is not None:
                b.setMenu(menu)
            if slot is not None:
                b.clicked.connect(slot)
            tb.addWidget(b)
            return b

        top_btn("＋  Add Company", self._quick_add_company, primary=True,
                tip="Add a new company to the portfolio  (Ctrl+N)")

        imp = QMenu(self)
        imp.addAction("Import from family spreadsheet…",
                      self._import_family)
        imp.addAction("Re-sync from family spreadsheet…",
                      self._resync_family)
        imp.addAction("Import standard Excel…", self._import_excel)
        imp.addSeparator()
        imp.addAction("Import backup…", self._import_backup)
        imp.addSeparator()
        imp.addAction("Edit Family Data…", self._edit_family)
        top_btn("⬇  Import", menu=imp)

        exp = QMenu(self)
        exp.addAction("Export family format (Excel)…",
                      self._export_family_excel)
        exp.addAction("Export standard Excel…", self._export_excel)
        exp.addSeparator()
        exp.addAction("Export backup (FamiljeInvesteringar)…",
                      self._export_backup)
        top_btn("⬆  Export", menu=exp)

        top_btn("↻  Refresh", self._refresh_all,
                tip="Reload all data  (Ctrl+R)")

        help_m = QMenu(self)
        help_m.addAction("How metrics are calculated…", self._metrics_help)
        help_m.addAction("About", self._about)
        top_btn(" ? ", menu=help_m, tip="Help")
        self._toolbar = tb

    def _search_typed(self, text):
        """The global search box hands off to the existing Ctrl+K
        palette, seeded with what was typed."""
        if not text.strip():
            return
        self._search.blockSignals(True)
        self._search.clear()
        self._search.blockSignals(False)
        from ui.quick_jump import QuickJumpDialog
        dlg = QuickJumpDialog(self, initial=text)
        if dlg.exec() and dlg.selected_company_id is not None:
            self.tabs.setCurrentIndex(1)
            self.tree.select_company(dlg.selected_company_id)

    def _refresh_ai_affordances(self):
        """The Ask-AI entry EXISTS only while the master switch is on
        (CLAUDE.md: AI) — created/removed here, re-checked after the
        settings dialog closes. The QAction is the stable programmatic
        surface (shortcuts, tests); the rail button triggers it."""
        import ai
        enabled = ai.is_ai_enabled()
        if enabled and self._ai_action is None:
            a = QAction("✦ Ask AI…", self)
            a.triggered.connect(self._ask_ai)
            a.setToolTip("Ask questions about the portfolio — "
                         "per-question consent, session-only")
            self.addAction(a)
            self._ai_action = a
            b = QPushButton("✦  Ask AI")
            b.setObjectName("RailBtn")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(a.trigger)
            self._rail_layout.insertWidget(self._rail_ai_index, b)
            self._ai_rail_btn = b
        elif not enabled and self._ai_action is not None:
            self.removeAction(self._ai_action)
            self._ai_action.setParent(None)
            self._ai_action.deleteLater()
            self._ai_action = None
            self._ai_rail_btn.setParent(None)
            self._ai_rail_btn.deleteLater()
            self._ai_rail_btn = None

    def _ask_ai(self):
        from ui.ai_qa import AskAIDialog
        AskAIDialog(self).exec()

    def _show_history(self):
        from ui.history_dialog import HistoryDialog
        HistoryDialog(self).exec()

    def _report_center(self):
        from ui.report_center import ReportCenter
        ReportCenter(self).exec()

    def _quick_add_company(self):
        from ui.dialogs import CompanyDialog
        if CompanyDialog(self).exec():
            self._refresh_all()
            sb = self.statusBar()
            if sb:
                sb.showMessage("Company added.")

    def _quick_jump(self):
        from ui.quick_jump import QuickJumpDialog
        dlg = QuickJumpDialog(self)
        if dlg.exec() and dlg.selected_company_id is not None:
            self.tabs.setCurrentIndex(1)          # Portfolio tab
            self.tree.select_company(dlg.selected_company_id)

    # ── Window-state persistence ─────────────────────────────────────────────

    def _restore_state(self):
        s = QSettings("FamilyInvestmentTracker", "InvestmentTracker")
        geo = s.value("geometry")
        if geo is not None:
            self.restoreGeometry(geo)
            # Never start minimized/hidden, even if the app was closed that way
            if self.isMinimized():
                self.setWindowState(
                    self.windowState() & ~Qt.WindowState.WindowMinimized)
        sizes = s.value("splitter")
        if sizes:
            try:
                self._splitter.setSizes([int(x) for x in sizes])
            except (TypeError, ValueError):
                pass
        tab = s.value("tab")
        if tab is not None:
            try:
                self.tabs.setCurrentIndex(int(tab))
            except (TypeError, ValueError):
                pass

    def closeEvent(self, event):
        s = QSettings("FamilyInvestmentTracker", "InvestmentTracker")
        s.setValue("geometry", self.saveGeometry())
        s.setValue("splitter", self._splitter.sizes())
        s.setValue("tab", self.tabs.currentIndex())
        super().closeEvent(event)

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        """App shell (session 11): persistent left navigation rail +
        content stack. self.tabs stays a QTabWidget (hidden tab bar) so
        every existing caller/test keeps working — the rail drives it."""
        shell = QWidget()
        shell_lay = QHBoxLayout(shell)
        shell_lay.setContentsMargins(0, 0, 0, 0)
        shell_lay.setSpacing(0)
        shell_lay.addWidget(self._build_rail())

        self.tabs = QTabWidget()
        self.tabs.setObjectName("MainStack")
        self.tabs.setDocumentMode(True)
        shell_lay.addWidget(self.tabs, 1)
        self.setCentralWidget(shell)

        # Dashboard tab
        self.dashboard = DashboardTab()
        self.dashboard.open_company.connect(self._open_company)
        self.dashboard.view_all.connect(
            lambda: self.tabs.setCurrentIndex(2))
        self.dashboard.show_history.connect(self._show_history)
        self.dashboard.quick_action.connect(self._quick_action)
        self.tabs.addTab(self.dashboard, "  Dashboard  ")

        # Portfolio tab
        portfolio = QWidget()
        p_layout  = QHBoxLayout(portfolio)
        p_layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter = splitter

        self.tree = TreePanel()
        self.tree.setMinimumWidth(230)
        self.tree.setMaximumWidth(380)
        self.tree.selection_changed.connect(self._on_select)
        splitter.addWidget(self.tree)

        self.detail = DetailPanel()
        self.detail.show_welcome()
        self.detail.documents_changed.connect(self.tree.refresh)
        splitter.addWidget(self.detail)
        splitter.setSizes([280, 900])

        p_layout.addWidget(splitter)
        self.tabs.addTab(portfolio, "  Portfolio  ")

        # Companies + Transactions pages (session 11 shell — read-only
        # compositions of existing data)
        from ui.companies_page import CompaniesPage
        from ui.transactions_page import TransactionsPage
        self.companies_page = CompaniesPage()
        self.companies_page.open_company.connect(self._open_company)
        self.tabs.addTab(self.companies_page, "  Companies  ")
        self.transactions_page = TransactionsPage()
        self.tabs.addTab(self.transactions_page, "  Transactions  ")

        self.tabs.currentChanged.connect(self._on_tab)
        self.tabs.currentChanged.connect(self._sync_rail)
        # hide AFTER the tabs exist — QTabWidget re-shows the bar when
        # the first tab is added, so hiding earlier does not stick
        bar = self.tabs.tabBar()
        if bar:
            bar.hide()
        self.dashboard.refresh()

    def _open_company(self, cid: int):
        self.tabs.setCurrentIndex(1)
        self.tree.select_company(cid)

    def _quick_action(self, key: str):
        """Right-rail Quick Actions → the existing handlers."""
        {'add': self._quick_add_company,
         'import': self._import_family,
         'report': self._report_center,
         'compare': self._compare_companies}[key]()

    def _build_rail(self):
        from PyQt6.QtWidgets import QComboBox, QHBoxLayout as HB
        from version import APP_VERSION
        rail = QFrame()
        rail.setObjectName("NavRail")
        rail.setFixedWidth(230)
        lay = QVBoxLayout(rail)
        lay.setContentsMargins(12, 16, 12, 14)
        lay.setSpacing(4)
        self._rail_layout = lay

        brand_row = HB()
        brand_row.setSpacing(10)
        logo = QLabel("↗")
        logo.setObjectName("RailLogo")
        logo.setFixedSize(32, 32)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand_row.addWidget(logo)
        brand = QLabel("Investment Tracker")
        brand.setObjectName("RailBrand")
        brand_row.addWidget(brand, 1)
        lay.addLayout(brand_row)
        lay.addSpacing(20)

        def rail_btn(text, slot, checkable=False):
            b = QPushButton(text)
            b.setObjectName("RailBtn")
            b.setCheckable(checkable)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(slot)
            lay.addWidget(b)
            return b

        self._nav_buttons = {}
        for idx, (icon, label) in enumerate((
                ("📊", "Dashboard"), ("💼", "Portfolio"),
                ("🏢", "Companies"), ("🔁", "Transactions"))):
            self._nav_buttons[idx] = rail_btn(
                f"{icon}  {label}",
                lambda _=False, i=idx: self.tabs.setCurrentIndex(i),
                checkable=True)
        self._nav_buttons[0].setChecked(True)

        n_events, last_ts = models.audit_summary()
        hist = rail_btn("🕘  History", self._show_history)
        badge = QLabel(f"{n_events:,}")
        badge.setObjectName("RailBadge")
        hb = HB(hist)
        hb.setContentsMargins(0, 0, 10, 0)
        hb.addStretch()
        hb.addWidget(badge)
        self._history_badge = badge

        rail_btn("📄  Reports", self._report_center)
        rail_btn("⇄  Compare", self._compare_companies)
        self._rail_ai_index = lay.count()   # Ask AI slot (when enabled)
        lay.addStretch()
        rail_btn("⚙  Settings", self._open_settings)

        lay.addSpacing(8)
        self._portfolio_combo = QComboBox()
        self._portfolio_combo.setObjectName("RailCombo")
        self._portfolio_combo.addItem("All portfolios", None)
        for e in models.get_entities():
            self._portfolio_combo.addItem(e, e)
        self._portfolio_combo.currentIndexChanged.connect(
            self._on_portfolio_pick)
        lay.addWidget(self._portfolio_combo)

        status_row = HB()
        status_row.setSpacing(6)
        dot = QLabel("●")
        dot.setStyleSheet("color:#34D399; font-size:8pt;")
        status_row.addWidget(dot)
        ts = (last_ts or '').replace('T', ' ')[:16]
        self._last_update_lbl = QLabel(
            f"Last update {ts}" if ts else "No changes recorded yet")
        self._last_update_lbl.setObjectName("RailMeta")
        status_row.addWidget(self._last_update_lbl, 1)
        lay.addLayout(status_row)
        ver = QLabel(f"v{APP_VERSION}")
        ver.setObjectName("RailMeta")
        lay.addWidget(ver)
        return rail

    def _on_portfolio_pick(self, idx):
        """Sidebar portfolio dropdown — the exact same filtering path
        the old dashboard entity pills used."""
        self.dashboard._set_filter(self._portfolio_combo.itemData(idx))
        self.tabs.setCurrentIndex(0)

    def _sync_rail(self, idx):
        for i, b in self._nav_buttons.items():
            b.setChecked(i == idx)

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _on_tab(self, idx):
        if idx == 0:
            self.dashboard.refresh()
        elif idx == 2:
            self.companies_page.refresh()
        elif idx == 3:
            self.transactions_page.refresh()

    def _on_select(self, ntype, nkey):
        if ntype == NODE_ENTITY:
            self.detail.show_entity(nkey)
        elif ntype == NODE_COMPANY:
            self.detail.show_company(int(nkey))
        elif ntype == NODE_ROUND:
            self.detail.show_round(int(nkey))
        elif ntype == NODE_DOC:
            self.detail.show_document(int(nkey))
        else:
            self.detail.show_welcome()

    def _refresh_all(self):
        self.tree.refresh()
        self.dashboard.refresh()
        n_events, last_ts = models.audit_summary()
        self._history_badge.setText(f"{n_events:,}")
        ts = (last_ts or '').replace('T', ' ')[:16]
        if ts:
            self._last_update_lbl.setText(f"Last update {ts}")

    def _compare_companies(self):
        from ui.compare_dialog import CompareDialog
        CompareDialog(self).exec()

    # ── File actions ──────────────────────────────────────────────────────────

    def _edit_family(self):
        from ui.family_edit_dialog import FamilyEditDialog
        dlg = FamilyEditDialog(self)
        dlg.exec()
        self._refresh_all()

    def _resync_family(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Re-sync from Family Spreadsheet", "",
            "Excel Files (*.xlsx *.xls);;All Files (*)"
        )
        if not path:
            return
        try:
            parsed = excel_io.parse_family_excel(path)
            count  = excel_io.import_family_data(parsed)
            self._refresh_all()
            sb = self.statusBar()
            if sb:
                sb.showMessage(
                    f"Re-sync complete: {count} new companies, existing ones updated.")
            QMessageBox.information(self, "Re-sync complete",
                f"Imported {count} new, updated all existing companies from:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Re-sync error", str(e))

    def _export_family_excel(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Family Format to Excel",
            "family_portfolio.xlsx", "Excel Files (*.xlsx)"
        )
        if path:
            try:
                excel_io.export_family_excel(path)
                QMessageBox.information(self, "Export complete",
                    f"Family data exported to:\n{path}")
            except Exception as e:
                QMessageBox.critical(self, "Export error", str(e))

    def _import_family(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Family Spreadsheet", "",
            "Excel Files (*.xlsx *.xls);;All Files (*)"
        )
        if not path:
            return
        try:
            from ui.family_import_dialog import FamilyImportDialog
            dlg = FamilyImportDialog(self, path)
            if dlg.exec():
                self._refresh_all()
                sb = self.statusBar()
                if sb:
                    sb.showMessage("Family spreadsheet imported.")
        except Exception as e:
            QMessageBox.critical(self, "Import Error", str(e))

    def _import_excel(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Excel File", "",
            "Excel Files (*.xlsx *.xls);;All Files (*)"
        )
        if not path:
            return
        try:
            from ui.import_dialog import ImportPreviewDialog
            dlg = ImportPreviewDialog(self, path)
            if dlg.exec():
                self._refresh_all()
                sb = self.statusBar()
                if sb:
                    sb.showMessage("Import complete.")
        except Exception as e:
            QMessageBox.critical(self, "Import Error", str(e))

    def _export_excel(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Portfolio to Excel", "portfolio_export.xlsx",
            "Excel Files (*.xlsx)"
        )
        if path:
            try:
                excel_io.export_portfolio(path)
                QMessageBox.information(self, "Export complete",
                    f"Portfolio exported to:\n{path}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", str(e))

    def _open_settings(self):
        dlg = SettingsDialog(self)
        if dlg.exec():
            self._refresh_ai_affordances()
            self._refresh_all()

    def _metrics_help(self):
        MetricsHelpDialog(self).exec()

    def _about(self):
        QMessageBox.about(
            self, "About Investment Tracker",
            "Investment Tracker\n\n"
            "Track private company investments across funding rounds.\n"
            "Data stored locally in investments.db.\n\n"
            "Built with Python 3 · PyQt6 · SQLite · Matplotlib · openpyxl"
        )

    def _export_backup(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export backup", "FamiljeInvesteringar.zip",
            "Zip archive (*.zip)"
        )
        if path:
            try:
                models.export_portable_zip(path)
                QMessageBox.information(self, "Backup exported",
                    f"All data and documents saved to:\n{path}\n\n"
                    "Share this file — the recipient can load it via File → Import backup.")
            except Exception as e:
                QMessageBox.critical(self, "Export error", str(e))

    def _import_backup(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import backup", "",
            "Zip archive (*.zip);;All files (*)"
        )
        if not path:
            return
        reply = QMessageBox.question(
            self, "Replace all data?",
            "This will replace your current database and documents with the backup.\n"
            "Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            models.import_portable_zip(path)
            self._refresh_all()
            QMessageBox.information(self, "Backup imported",
                "Data restored successfully.")
        except Exception as e:
            QMessageBox.critical(self, "Import error", str(e))
