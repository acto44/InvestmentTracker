from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem, QLabel
)
from PyQt6.QtCore import Qt

import models
from ui.styles import MUTED


class QuickJumpDialog(QDialog):
    """Ctrl+K palette: type to filter companies, Enter to jump to one.

    After exec() returns Accepted, `selected_company_id` holds the choice.
    """

    def __init__(self, parent=None, initial: str = ''):
        super().__init__(parent)
        self.selected_company_id: int | None = None
        self.setWindowTitle("Go to company")
        self.setModal(True)
        self.setMinimumWidth(420)
        self._build()
        if initial:
            self._search.setText(initial)   # textChanged → _populate
        else:
            self._populate('')

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(8)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Type a company name…")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._populate)
        lay.addWidget(self._search)

        self._list = QListWidget()
        self._list.setMinimumHeight(280)
        self._list.itemActivated.connect(self._choose)
        lay.addWidget(self._list)

        hint = QLabel("↑↓ navigate  ·  Enter open  ·  Esc close")
        hint.setStyleSheet(f"color:{MUTED}; font-size:8pt;")
        lay.addWidget(hint)

        self._search.setFocus()

    def _populate(self, text: str):
        q = text.strip().lower()
        self._list.clear()
        for c in models.get_all_companies():
            hay = f"{c['name']} {c.get('entity') or ''} {c.get('sector') or ''}".lower()
            if q and q not in hay:
                continue
            meta = ' · '.join(x for x in (c.get('entity'), c.get('sector')) if x)
            item = QListWidgetItem(f"{c['name']}" + (f"   —   {meta}" if meta else ""))
            item.setData(Qt.ItemDataRole.UserRole, c['id'])
            self._list.addItem(item)
        if self._list.count():
            self._list.setCurrentRow(0)

    def _choose(self, item: QListWidgetItem):
        self.selected_company_id = item.data(Qt.ItemDataRole.UserRole)
        self.accept()

    def keyPressEvent(self, event):
        # Let arrow keys drive the list even while the search box has focus,
        # and Enter picks the highlighted row.
        key = event.key()
        if key in (Qt.Key.Key_Down, Qt.Key.Key_Up):
            row = self._list.currentRow()
            row += 1 if key == Qt.Key.Key_Down else -1
            row = max(0, min(self._list.count() - 1, row))
            self._list.setCurrentRow(row)
            event.accept()
            return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            item = self._list.currentItem()
            if item:
                self._choose(item)
            event.accept()
            return
        super().keyPressEvent(event)
