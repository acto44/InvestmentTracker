"""Settings → AI page. The master switch (default OFF) is the single
opt-in gate — session 8 features check ai.is_ai_enabled() and simply do
not exist while it is off. "Test connection" runs the FULL pipeline
(consent dialog → provider → contract validation → labeled AICard), so
the user experiences the real flow once before any feature uses it."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QCheckBox, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPushButton, QRadioButton, QVBoxLayout, QWidget,
)

import ai
import models
from ai import keystore
from ai.claude_cli import ClaudeCLIProvider
from ai.contract import build_ping_request
from ai.openai_api import DEFAULT_MODEL, OpenAIProvider
from ui.ai_card import AICard
from ui.styles import GREEN, MUTED, RED, WARN_BG, WARN_BORDER, WARN_TEXT


class AISettingsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread = None
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        self.master = QCheckBox("Enable AI features")
        self.master.setChecked(ai.is_ai_enabled())
        layout.addWidget(self.master)
        master_note = QLabel(
            "Off by default. While off, no AI appears anywhere in the "
            "app. When on, every AI action asks for your consent first "
            "and shows exactly what would be sent — nothing leaves this "
            "machine silently, and AI never writes to your data.")
        master_note.setWordWrap(True)
        master_note.setStyleSheet(f"color:{MUTED}; font-size:9pt;")
        layout.addWidget(master_note)

        prov_group = QGroupBox("Provider")
        pg = QVBoxLayout(prov_group)
        self.rb_claude = QRadioButton(
            "Claude — local Claude Code CLI (your Claude account)")
        self.rb_openai = QRadioButton("OpenAI — API (your API key)")
        current = models.get_setting(ai.AI_PROVIDER_KEY, 'claude_cli')
        (self.rb_openai if current == 'openai'
         else self.rb_claude).setChecked(True)
        self.claude_status = QLabel("…")
        self.openai_status = QLabel("…")
        for lbl in (self.claude_status, self.openai_status):
            lbl.setWordWrap(True)
            lbl.setStyleSheet(f"color:{MUTED}; font-size:9pt; "
                              f"margin-left:24px;")
        pg.addWidget(self.rb_claude)
        pg.addWidget(self.claude_status)
        pg.addWidget(self.rb_openai)
        pg.addWidget(self.openai_status)
        layout.addWidget(prov_group)

        key_group = QGroupBox("OpenAI API key")
        kg = QVBoxLayout(key_group)
        key_row = QHBoxLayout()
        self.key_edit = QLineEdit()
        self.key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_edit.setPlaceholderText(
            "key saved" if keystore.has_api_key() else "sk-…")
        self.save_key_btn = QPushButton("Save key")
        self.save_key_btn.clicked.connect(self._save_key)
        self.remove_key_btn = QPushButton("Remove key")
        self.remove_key_btn.clicked.connect(self._remove_key)
        key_row.addWidget(self.key_edit, 1)
        key_row.addWidget(self.save_key_btn)
        key_row.addWidget(self.remove_key_btn)
        kg.addLayout(key_row)

        model_row = QHBoxLayout()
        model_row.addWidget(QLabel("Model"))
        self.model_edit = QLineEdit(
            models.get_setting(ai.AI_OPENAI_MODEL_KEY, '')
            or DEFAULT_MODEL)
        self.model_edit.setMaximumWidth(220)
        model_row.addWidget(self.model_edit)
        model_row.addStretch()
        kg.addLayout(model_row)

        self.key_security = QLabel()
        self.key_security.setWordWrap(True)
        if keystore.storage_is_encrypted():
            self.key_security.setText(
                "The key is encrypted at rest with Windows DPAPI — only "
                "this Windows user on this machine can read it.")
            self.key_security.setStyleSheet(
                f"color:{MUTED}; font-size:9pt;")
        else:
            self.key_security.setText(
                "⚠ The key is NOT securely encrypted on this OS — it is "
                "only obfuscated on disk.")
            self.key_security.setStyleSheet(
                f"background:{WARN_BG}; color:{WARN_TEXT}; padding:6px;"
                f"border:1px solid {WARN_BORDER}; border-radius:6px;"
                f"font-size:9pt;")
        kg.addWidget(self.key_security)
        layout.addWidget(key_group)

        test_group = QGroupBox("Test connection")
        tg = QVBoxLayout(test_group)
        test_note = QLabel(
            "Sends a fixed test message (no portfolio data) through the "
            "real flow: consent → provider → validation → labeled "
            "result.")
        test_note.setWordWrap(True)
        test_note.setStyleSheet(f"color:{MUTED}; font-size:9pt;")
        tg.addWidget(test_note)
        self.test_btn = QPushButton("Test connection…")
        self.test_btn.clicked.connect(self._test)
        tg.addWidget(self.test_btn)
        self.test_slot = QVBoxLayout()
        tg.addLayout(self.test_slot)
        layout.addWidget(test_group)
        layout.addStretch()

        self._refresh_status()

    # ── status / key management ───────────────────────────────────────────

    def _refresh_status(self):
        ok, reason = ClaudeCLIProvider().is_available()
        self.claude_status.setText(("● " if ok else "○ ") + reason)
        self.claude_status.setStyleSheet(
            f"color:{GREEN if ok else MUTED}; font-size:9pt; "
            f"margin-left:24px;")
        ok, reason = OpenAIProvider(
            model=self.model_edit.text().strip() or None).is_available()
        self.openai_status.setText(("● " if ok else "○ ") + reason)
        self.openai_status.setStyleSheet(
            f"color:{GREEN if ok else MUTED}; font-size:9pt; "
            f"margin-left:24px;")

    def _save_key(self):
        key = self.key_edit.text().strip()
        if not key:
            QMessageBox.information(self, "No key",
                                    "Paste the API key first.")
            return
        keystore.save_api_key(key)
        self.key_edit.clear()
        self.key_edit.setPlaceholderText("key saved")
        self._refresh_status()

    def _remove_key(self):
        keystore.clear_api_key()
        self.key_edit.clear()
        self.key_edit.setPlaceholderText("sk-…")
        self._refresh_status()

    # ── settings persistence (called by the dialog's OK) ─────────────────

    def apply(self):
        ai.set_ai_enabled(self.master.isChecked())
        models.set_setting(
            ai.AI_PROVIDER_KEY,
            'openai' if self.rb_openai.isChecked() else 'claude_cli')
        models.set_setting(ai.AI_OPENAI_MODEL_KEY,
                           self.model_edit.text().strip()
                           or DEFAULT_MODEL)

    # ── test connection: the full real pipeline ──────────────────────────

    def _test(self):
        if not self.master.isChecked():
            QMessageBox.information(
                self, "AI is off",
                "Tick 'Enable AI features' first — the test uses the "
                "real, gated pipeline.")
            return
        self.apply()   # test exactly what is configured on this page
        from ai import service   # imported here: Qt threads only on use
        provider = ai.get_provider()
        self._clear_test_slot()
        self.test_btn.setEnabled(False)
        self.test_btn.setText("Testing…")
        self._thread = service.send_request(
            build_ping_request(), provider, parent=self,
            on_done=self._test_done, timeout_s=120)

    def _test_done(self, result):
        self.test_btn.setEnabled(True)
        self.test_btn.setText("Test connection…")
        self._clear_test_slot()
        if result.ok:
            card = AICard(result.provider, result.model,
                          result.timestamp)
            msg = result.data.get('message', '')
            card.set_body_text(
                f"Connection OK — the model answered: “{msg}”. "
                f"Reply validated against the '{result.task_id}' "
                f"contract.")
            self.test_slot.addWidget(card)
        else:
            label = QLabel(result.error)
            label.setWordWrap(True)
            label.setStyleSheet(
                f"color:{RED if result.outcome != 'cancelled' else MUTED};"
                f" font-size:9pt;")
            self.test_slot.addWidget(label)

    def _clear_test_slot(self):
        while self.test_slot.count():
            item = self.test_slot.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
