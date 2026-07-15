"""AICard — THE labeling primitive. Every AI-visible thing in the app
(session 8 included) renders inside one of these, so AI output is always
visually distinct from recorded facts: provenance header on top, the
"verify before decisions" disclaimer at the bottom, no exceptions."""

from __future__ import annotations

from PyQt6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from ui.styles import ACCENT, ACCENT_LITE, BORDER, CARD, MUTED

DISCLAIMER = "AI output — verify before decisions."


class AICard(QFrame):
    def __init__(self, provider: str, model: str, timestamp: str,
                 parent=None):
        super().__init__(parent)
        self.setObjectName("AICard")
        self.setStyleSheet(
            f"QFrame#AICard {{ background:{CARD}; "
            f"border:1px solid {BORDER}; border-radius:8px; }}")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        self._header = QLabel(
            f"AI-generated · {provider} · {model} · {timestamp}")
        self._header.setStyleSheet(
            f"background:{ACCENT_LITE}; color:{ACCENT}; font-weight:bold;"
            f"font-size:9pt; border-radius:5px; padding:4px 8px;")
        layout.addWidget(self._header)

        self._body = QVBoxLayout()
        self._body.setSpacing(6)
        layout.addLayout(self._body)

        footer = QLabel(DISCLAIMER)
        footer.setStyleSheet(
            f"color:{MUTED}; font-size:9pt; font-style:italic;")
        layout.addWidget(footer)

    def set_body_text(self, text: str):
        self.clear_body()
        label = QLabel(text)
        label.setWordWrap(True)
        label.setTextInteractionFlags(
            label.textInteractionFlags()
            | label.textInteractionFlags().TextSelectableByMouse)
        self._body.addWidget(label)

    def set_body_widget(self, widget: QWidget):
        self.clear_body()
        self._body.addWidget(widget)

    def clear_body(self):
        while self._body.count():
            item = self._body.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def header_text(self) -> str:
        return self._header.text()
