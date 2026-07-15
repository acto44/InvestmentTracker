from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QSplitter,
    QTabWidget, QFileDialog, QMessageBox, QToolBar
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
        self.resize(1320, 820)
        self._build_menu()
        self._build_toolbar()
        self._build_ui()
        self._restore_state()
        sb = self.statusBar()
        if sb:
            sb.showMessage(
                "Ready — Ctrl+N adds a company, Ctrl+K jumps to one, "
                "or use the toolbar above.")

    # ── Menu ──────────────────────────────────────────────────────────────────

    def _build_menu(self):
        mb = self.menuBar()

        file_m = mb.addMenu("File")
        file_m.addAction("Edit Family Data…",               self._edit_family)
        file_m.addSeparator()
        file_m.addAction("Import from family spreadsheet…", self._import_family)
        file_m.addAction("Re-sync from family spreadsheet…",self._resync_family)
        file_m.addSeparator()
        file_m.addAction("Export family format (Excel)…",   self._export_family_excel)
        file_m.addAction("Import standard Excel…",          self._import_excel)
        file_m.addAction("Export standard Excel…",          self._export_excel)
        file_m.addSeparator()
        file_m.addAction("Export backup (FamiljeInvesteringar)…", self._export_backup)
        file_m.addAction("Import backup…",                 self._import_backup)
        file_m.addSeparator()
        file_m.addAction("Exit",                            self.close)

        view_m = mb.addMenu("View")
        act_refresh = view_m.addAction("Refresh",  self._refresh_all)
        act_refresh.setShortcut(QKeySequence("Ctrl+R"))
        act_jump = view_m.addAction("Go to Company…", self._quick_jump)
        act_jump.setShortcut(QKeySequence("Ctrl+K"))
        view_m.addSeparator()
        view_m.addAction("Compare Companies…",     self._compare_companies)

        settings_m = mb.addMenu("Settings")
        act_prefs = settings_m.addAction("Preferences…", self._open_settings)
        act_prefs.setShortcut(QKeySequence("Ctrl+,"))

        help_m = mb.addMenu("Help")
        help_m.addAction("How metrics are calculated…", self._metrics_help)
        help_m.addAction("About",                  self._about)

    # ── Toolbar ───────────────────────────────────────────────────────────────

    def _build_toolbar(self):
        tb = QToolBar("Main")
        tb.setMovable(False)
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.addToolBar(tb)

        def act(text, slot, shortcut=None, tip=None):
            a = QAction(text, self)
            a.triggered.connect(slot)
            if shortcut:
                a.setShortcut(QKeySequence(shortcut))
            if tip:
                a.setToolTip(tip + (f"  ({shortcut})" if shortcut else ""))
            tb.addAction(a)
            return a

        act("＋ Add Company", self._quick_add_company, "Ctrl+N",
            "Add a new company to the portfolio")
        act("🔍 Go to…", self._quick_jump, "Ctrl+K",
            "Jump straight to a company")
        tb.addSeparator()
        act("⬇ Import", self._import_family, None,
            "Import from the family spreadsheet")
        act("⬆ Export", self._export_family_excel, None,
            "Export the family-format Excel file")
        tb.addSeparator()
        act("⇄ Compare", self._compare_companies, None,
            "Compare companies side by side")
        act("↻ Refresh", self._refresh_all, None,
            "Reload all data")
        act("🕘 History", self._show_history, None,
            "Read-only log of every change to companies, rounds and valuations")
        act("📄 Reports…", self._report_center, None,
            "Report Center — company, portfolio and entity reports, "
            "single or in batches")
        tb.addSeparator()
        act("⚙ Settings", self._open_settings, None,
            "Currency and backup preferences")
        self._toolbar = tb
        self._ai_action = None
        self._refresh_ai_affordances()

    def _refresh_ai_affordances(self):
        """The Ask-AI action EXISTS only while the master switch is on
        (CLAUDE.md: AI) — created/removed here, re-checked after the
        settings dialog closes."""
        import ai
        enabled = ai.is_ai_enabled()
        if enabled and self._ai_action is None:
            a = QAction("✦ Ask AI…", self)
            a.triggered.connect(self._ask_ai)
            a.setToolTip("Ask questions about the portfolio — "
                         "per-question consent, session-only")
            self._toolbar.addAction(a)
            self._ai_action = a
        elif not enabled and self._ai_action is not None:
            self._toolbar.removeAction(self._ai_action)
            self._ai_action.setParent(None)
            self._ai_action.deleteLater()
            self._ai_action = None

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
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.setCentralWidget(self.tabs)

        # Dashboard tab
        self.dashboard = DashboardTab()
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

        self.tabs.currentChanged.connect(self._on_tab)
        self.dashboard.refresh()

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _on_tab(self, idx):
        if idx == 0:
            self.dashboard.refresh()

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
