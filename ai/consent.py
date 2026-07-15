"""Per-action consent — the product, not friction. Shown before EVERY
send: who runs the model, where the data goes, why, and the EXACT payload
(byte-for-byte what the provider will receive). There is deliberately no
"always allow" and no "don't ask again". Cancel is the default button."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QFontDatabase
from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QPlainTextEdit,
    QToolButton, QVBoxLayout,
)

from ui.styles import (ACCENT, ACCENT_LITE, BORDER, CARD, MUTED,
                       WARN_BG, WARN_BORDER, WARN_TEXT)

SYSTEM_HEADER = '── system instruction ──'
PROMPT_HEADER = '── prompt ──'


def compose_payload_preview(prompt: str, system: str | None) -> str:
    """The text the consent dialog shows. The prompt and system strings
    appear VERBATIM — this is what the provider receives, delimited."""
    parts = []
    if system:
        parts.append(f"{SYSTEM_HEADER}\n{system}")
    parts.append(f"{PROMPT_HEADER}\n{prompt}")
    return '\n\n'.join(parts)


class ConsentDialog(QDialog):
    def __init__(self, parent, provider_name: str, model_label: str,
                 destination: str, purpose: str, payload_text: str):
        super().__init__(parent)
        self.setWindowTitle("Send to AI?")
        self.setMinimumWidth(560)
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        badge = QLabel(f"  {provider_name} · {model_label}  ")
        badge.setStyleSheet(
            f"background:{ACCENT_LITE}; color:{ACCENT}; font-weight:bold;"
            f"border:1px solid {BORDER}; border-radius:6px; padding:4px;")
        badge_row = QHBoxLayout()
        badge_row.addWidget(badge)
        badge_row.addStretch()
        layout.addLayout(badge_row)

        dest = QLabel(f"This data leaves this machine → {destination}")
        dest.setWordWrap(True)
        dest.setStyleSheet(
            f"background:{WARN_BG}; color:{WARN_TEXT}; padding:8px 10px;"
            f"border:1px solid {WARN_BORDER}; border-radius:6px;")
        layout.addWidget(dest)

        why = QLabel(f"Purpose: {purpose}")
        why.setWordWrap(True)
        layout.addWidget(why)

        self._toggle = QToolButton()
        self._toggle.setText("Exact payload being sent "
                             f"({len(payload_text)} chars)")
        self._toggle.setCheckable(True)
        self._toggle.setChecked(True)
        self._toggle.setArrowType(Qt.ArrowType.DownArrow)
        self._toggle.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._toggle.toggled.connect(self._toggle_payload)
        layout.addWidget(self._toggle)

        self._payload = QPlainTextEdit()
        self._payload.setPlainText(payload_text)
        self._payload.setReadOnly(True)
        mono = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        mono.setPointSize(9)
        self._payload.setFont(mono)
        self._payload.setMinimumHeight(180)
        self._payload.setStyleSheet(
            f"background:{CARD}; border:1px solid {BORDER};"
            f"border-radius:7px;")
        layout.addWidget(self._payload, 1)

        note = QLabel("You will be asked again for every AI action — "
                      "there is no \"always allow\".")
        note.setStyleSheet(f"color:{MUTED}; font-size:9pt;")
        layout.addWidget(note)

        btns = QDialogButtonBox()
        send_btn = btns.addButton(
            "Send", QDialogButtonBox.ButtonRole.AcceptRole)
        cancel_btn = btns.addButton(QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        # Cancel is the safe default: Enter cancels unless Send is chosen
        send_btn.setDefault(False)
        send_btn.setAutoDefault(False)
        cancel_btn.setDefault(True)
        cancel_btn.setAutoDefault(True)
        cancel_btn.setFocus()
        self._cancel_btn = cancel_btn
        self._send_btn = send_btn
        layout.addWidget(btns)

    def _toggle_payload(self, on: bool):
        self._payload.setVisible(on)
        self._toggle.setArrowType(
            Qt.ArrowType.DownArrow if on else Qt.ArrowType.RightArrow)

    def payload_text(self) -> str:
        return self._payload.toPlainText()

    @staticmethod
    def ask(parent, provider, purpose: str, payload_text: str) -> bool:
        """True only if the user explicitly clicked Send."""
        dlg = ConsentDialog(parent, provider.name, provider.model_label,
                            provider.destination, purpose, payload_text)
        return dlg.exec() == QDialog.DialogCode.Accepted
