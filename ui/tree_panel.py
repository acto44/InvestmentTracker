import os
import sys
import subprocess

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTreeWidget,
    QTreeWidgetItem, QMenu, QLabel, QMessageBox, QFrame, QLineEdit
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QBrush, QColor, QIcon, QPixmap, QPainter

import models
from ui.styles import (
    ACCENT, MUTED, TEXT, BORDER,
    STATUS_ACTIVE, STATUS_EXITED, STATUS_BANKRUPT,
)

_dot_cache: dict[str, QIcon] = {}

def _status_dot(color: str) -> QIcon:
    """Small filled circle icon used as a company status indicator."""
    if color not in _dot_cache:
        pm = QPixmap(12, 12)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(color))
        p.drawEllipse(2, 2, 8, 8)
        p.end()
        _dot_cache[color] = QIcon(pm)
    return _dot_cache[color]

NODE_ENTITY  = "entity"
NODE_COMPANY = "company"
NODE_ROUND   = "round"
NODE_DOC     = "doc"

# signal emits (node_type: str, node_key: str)
# node_key is the entity name for entities, or str(id) for everything else


class TreePanel(QWidget):
    # (node_type, node_key)  — node_key is entity-name or str(id)
    selection_changed = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()
        self.refresh()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 4, 8)
        layout.setSpacing(8)

        header = QHBoxLayout()
        title = QLabel("Portfolio")
        f = QFont(); f.setBold(True); f.setPointSize(11)
        title.setFont(f)
        header.addWidget(title)
        header.addStretch()
        add_btn = QPushButton("+ Company")
        add_btn.setFixedHeight(30)
        add_btn.clicked.connect(self._add_company)
        header.addWidget(add_btn)
        layout.addLayout(header)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(f"color: {BORDER};")
        layout.addWidget(line)

        self._filter = QLineEdit()
        self._filter.setPlaceholderText("🔍  Filter companies…")
        self._filter.setClearButtonEnabled(True)
        self._filter.textChanged.connect(self._apply_filter)
        layout.addWidget(self._filter)

        # Empty-state hint (shown instead of the tree when there's no data)
        self._empty = QWidget()
        el = QVBoxLayout(self._empty)
        el.setSpacing(10)
        el.addStretch()
        e_lbl = QLabel("No companies yet.\n\nAdd your first company\nor import a spreadsheet\nvia the File menu.")
        e_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        e_lbl.setStyleSheet(f"color:{MUTED}; font-size:10pt;")
        el.addWidget(e_lbl)
        e_btn = QPushButton("+ Add your first company")
        e_btn.clicked.connect(self._add_company)
        el.addWidget(e_btn, alignment=Qt.AlignmentFlag.AlignHCenter)
        el.addStretch()
        self._empty.hide()
        layout.addWidget(self._empty)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setAlternatingRowColors(True)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._context_menu)
        self.tree.itemSelectionChanged.connect(self._on_selection)
        self.tree.itemDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self.tree)

    # ── Refresh ───────────────────────────────────────────────────────────────

    def refresh(self):
        saved = self._current_key()
        self.tree.blockSignals(True)
        self.tree.clear()

        by_entity = models.get_companies_by_entity()

        has_data = bool(by_entity)
        self.tree.setVisible(has_data)
        self._filter.setVisible(has_data)
        self._empty.setVisible(not has_data)

        multi_entity = len(by_entity) > 1 or (len(by_entity) == 1 and list(by_entity.keys())[0] != 'Other')

        for entity_name, companies in sorted(by_entity.items()):
            if multi_entity:
                e_item = self._make_entity_item(entity_name, companies)
                self.tree.addTopLevelItem(e_item)
                e_item.setExpanded(True)
                for c in companies:
                    c_item = self._make_company_item(c)
                    e_item.addChild(c_item)
            else:
                for c in companies:
                    c_item = self._make_company_item(c)
                    self.tree.addTopLevelItem(c_item)
                    c_item.setExpanded(True)

        self.tree.blockSignals(False)
        if saved:
            self._restore_key(saved)
        if self._filter.text():
            self._apply_filter(self._filter.text())

    def _make_entity_item(self, name, companies):
        total = sum(
            sum((r.get('amount_invested') or 0) for r in models.get_rounds(c['id']))
            for c in companies
        )
        sym = models.get_setting('currency', 'TKR')
        label = f"{name}  ({len(companies)} companies · {sym} {total:,.0f})"
        item = QTreeWidgetItem([label])
        item.setData(0, Qt.ItemDataRole.UserRole, (NODE_ENTITY, name))
        f = QFont(); f.setBold(True); f.setPointSize(10)
        item.setFont(0, f)
        item.setForeground(0, QBrush(QColor(ACCENT)))
        return item

    def _make_company_item(self, c):
        rounds = models.get_rounds(c['id'])
        total  = sum((r.get('amount_invested') or 0) for r in rounds)
        sym    = models.get_setting('currency', 'TKR')
        label  = f"{c['name']}  —  {sym} {total:,.0f}"
        item   = QTreeWidgetItem([label])
        item.setData(0, Qt.ItemDataRole.UserRole, (NODE_COMPANY, c['id']))
        f = QFont(); f.setBold(True)
        item.setFont(0, f)

        notes = (c.get('notes') or '').lower()
        if 'bankrupt' in notes:
            item.setIcon(0, _status_dot(STATUS_BANKRUPT))
            item.setToolTip(0, "Bankrupt (written off)")
        elif 'status: exited' in notes:
            item.setIcon(0, _status_dot(STATUS_EXITED))
            item.setToolTip(0, "Exited")
        else:
            item.setIcon(0, _status_dot(STATUS_ACTIVE))
            item.setToolTip(0, "Active")

        for r in rounds:
            amt   = r.get('amount_invested') or 0
            r_lbl = f"    {r['round_name']}  ·  {r.get('date', '') or '?'}  ·  {sym} {amt:,.0f}"
            r_item = QTreeWidgetItem([r_lbl])
            r_item.setData(0, Qt.ItemDataRole.UserRole, (NODE_ROUND, r['id']))

            for d in models.get_documents(round_id=r['id']):
                d_item = QTreeWidgetItem([f"      📎 {d['original_filename']}"])
                d_item.setData(0, Qt.ItemDataRole.UserRole, (NODE_DOC, d['id']))
                r_item.addChild(d_item)

            item.addChild(r_item)

        for d in models.get_documents(company_id=c['id']):
            d_item = QTreeWidgetItem([f"    📎 {d['original_filename']}"])
            d_item.setData(0, Qt.ItemDataRole.UserRole, (NODE_DOC, d['id']))
            item.addChild(d_item)

        item.setExpanded(False)
        return item

    # ── Selection helpers ────────────────────────────────────────────────────

    def _current_key(self):
        items = self.tree.selectedItems()
        if items:
            return items[0].data(0, Qt.ItemDataRole.UserRole)
        return None

    def _restore_key(self, key):
        def search(item):
            if item.data(0, Qt.ItemDataRole.UserRole) == key:
                self.tree.setCurrentItem(item)
                return True
            for i in range(item.childCount()):
                if search(item.child(i)):
                    return True
            return False
        for i in range(self.tree.topLevelItemCount()):
            if search(self.tree.topLevelItem(i)):
                break

    def select_company(self, company_id: int):
        """Programmatically select a company node (used by Ctrl+K quick jump)."""
        self._restore_key((NODE_COMPANY, company_id))

    def _apply_filter(self, text: str):
        """Hide companies whose name doesn't match; hide entities with no visible children."""
        q = text.strip().lower()

        def match_company(item) -> bool:
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if not data or data[0] != NODE_COMPANY:
                return True
            return not q or q in item.text(0).lower()

        for i in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(i)
            data = top.data(0, Qt.ItemDataRole.UserRole)
            if data and data[0] == NODE_ENTITY:
                any_visible = False
                for j in range(top.childCount()):
                    child = top.child(j)
                    visible = match_company(child)
                    child.setHidden(not visible)
                    any_visible = any_visible or visible
                top.setHidden(not any_visible)
            else:
                top.setHidden(not match_company(top))

    def _on_selection(self):
        items = self.tree.selectedItems()
        if not items:
            return
        data = items[0].data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return
        ntype, nkey = data
        self.selection_changed.emit(ntype, str(nkey))

    def _on_double_click(self, item, _col):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if data and data[0] == NODE_DOC:
            self._open_doc(data[1])

    # ── Context menu ─────────────────────────────────────────────────────────

    def _context_menu(self, pos):
        item = self.tree.itemAt(pos)
        menu = QMenu(self)

        if not item:
            menu.addAction("Add Company",          self._add_company)
            menu.addSeparator()
            menu.addAction("Compare Companies…",   self._compare_companies)
            menu.exec(self.tree.mapToGlobal(pos))
            return

        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return
        ntype, nkey = data

        if ntype == NODE_ENTITY:
            menu.addAction("Add Company to this entity", lambda: self._add_company(entity=str(nkey)))
        elif ntype == NODE_COMPANY:
            nid = int(nkey)
            menu.addAction("Add Round",       lambda: self._add_round(nid))
            menu.addAction("Report…",         lambda: self._report(nid))
            menu.addAction("Attach Document", lambda: self._attach_doc(company_id=nid))
            menu.addSeparator()
            menu.addAction("Edit Company",    lambda: self._edit_company(nid))
            menu.addAction("Delete Company",  lambda: self._delete_company(nid))
        elif ntype == NODE_ROUND:
            nid = int(nkey)
            menu.addAction("Attach Document", lambda: self._attach_doc(round_id=nid))
            menu.addSeparator()
            menu.addAction("Edit Round",      lambda: self._edit_round(nid))
            menu.addAction("Delete Round",    lambda: self._delete_round(nid))
        elif ntype == NODE_DOC:
            nid = int(nkey)
            menu.addAction("Open Document",   lambda: self._open_doc(nid))
            menu.addSeparator()
            menu.addAction("Delete Document", lambda: self._delete_doc(nid))

        menu.exec(self.tree.mapToGlobal(pos))

    # ── Company actions ───────────────────────────────────────────────────────

    def _compare_companies(self):
        from ui.compare_dialog import CompareDialog
        CompareDialog(self).exec()

    def _add_company(self, entity=''):
        from ui.dialogs import CompanyDialog
        dlg = CompanyDialog(self, default_entity=entity)
        if dlg.exec():
            self.refresh()

    def _edit_company(self, cid):
        from ui.dialogs import CompanyDialog
        dlg = CompanyDialog(self, company_id=cid)
        if dlg.exec():
            self.refresh()

    def _delete_company(self, cid):
        c = models.get_company(cid)
        if QMessageBox.question(
            self, "Delete Company",
            f"Delete '{c['name']}' and all its rounds and documents?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) == QMessageBox.StandardButton.Yes:
            models.delete_company(cid, origin='ui.tree_panel')
            self.refresh()
            self.selection_changed.emit("none", "0")

    def _report(self, cid):
        from ui.report_dialog import ReportDialog
        ReportDialog(self, company_id=cid).exec()

    # ── Round actions ────────────────────────────────────────────────────────

    def _add_round(self, cid):
        from ui.dialogs import RoundDialog
        dlg = RoundDialog(self)
        if dlg.exec():
            data = dlg.get_data()
            record_val = data.pop('record_valuation', False)
            rid = models.add_round(cid, origin='ui.round_dialog', **data)
            if record_val and data.get('post_money_valuation'):
                models.add_valuation(
                    cid, data['date'], data['post_money_valuation'],
                    'round_post_money',
                    note=f"post-money of round '{data['round_name']}'",
                    round_id=rid, origin='ui.round_dialog')
            self.refresh()

    def _edit_round(self, rid):
        from ui.dialogs import RoundDialog
        rd = models.get_round(rid)
        dlg = RoundDialog(self, round_data=rd)
        if dlg.exec():
            data = dlg.get_data()
            record_val = data.pop('record_valuation', False)
            models.update_round(rid, origin='ui.round_dialog', **data)
            linked = models.get_valuation_for_round(rid)
            if record_val and data.get('post_money_valuation'):
                if linked:
                    models.update_valuation(
                        linked['id'], origin='ui.round_dialog',
                        as_of_date=data['date'],
                        value=data['post_money_valuation'])
                else:
                    models.add_valuation(
                        rd['company_id'], data['date'],
                        data['post_money_valuation'], 'round_post_money',
                        note=f"post-money of round '{data['round_name']}'",
                        round_id=rid, origin='ui.round_dialog')
            self.refresh()

    def _delete_round(self, rid):
        if QMessageBox.question(
            self, "Delete Round", "Delete this funding round and its documents?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) != QMessageBox.StandardButton.Yes:
            return
        linked = models.get_valuation_for_round(rid)
        if linked:
            also = QMessageBox.question(
                self, "Linked valuation point",
                "This round recorded a valuation point "
                f"({linked['value']:,.0f} as of {linked['as_of_date']}).\n"
                "Delete that valuation point too?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if also == QMessageBox.StandardButton.Yes:
                models.delete_valuation(linked['id'], origin='ui.round_dialog')
        models.delete_round(rid, origin='ui.round_dialog')
        self.refresh()
        self.selection_changed.emit("none", "0")

    # ── Document actions ──────────────────────────────────────────────────────

    def _attach_doc(self, company_id=None, round_id=None):
        from ui.dialogs import DocumentDialog
        dlg = DocumentDialog(self)
        if dlg.exec():
            d = dlg.get_data()
            models.add_document(d['path'], d['doc_type'],
                                company_id=company_id, round_id=round_id)
            self.refresh()

    def _delete_doc(self, did):
        if QMessageBox.question(
            self, "Delete Document", "Remove this document?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) == QMessageBox.StandardButton.Yes:
            models.delete_document(did)
            self.refresh()

    def _open_doc(self, did):
        path = models.get_document_path(did)
        if not path or not os.path.exists(path):
            QMessageBox.warning(self, "File not found",
                                "The document file could not be found.")
            return
        if sys.platform == 'win32':
            os.startfile(path)
        elif sys.platform == 'darwin':
            subprocess.run(['open', path])
        else:
            subprocess.run(['xdg-open', path])
