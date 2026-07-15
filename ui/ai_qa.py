"""Portfolio Q&A (session 8). SESSION-ONLY by design: questions and
answers live on this dialog instance and die with it — nothing is
persisted anywhere (scan-tested). Every question is its own consented
send; the payload is the scope's report-model pack + this session's
prior turns + the question, nothing else."""

from __future__ import annotations

import html
from functools import partial

from PyQt6.QtWidgets import (
    QComboBox, QDialog, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton,
    QScrollArea, QVBoxLayout, QWidget,
)

import ai
import models
from ai import context as aictx
from ai.contract import AIRequest
from ui.ai_card import AICard
from ui.styles import MUTED, RED


class AskAIDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ask AI about the portfolio")
        self.setMinimumSize(640, 560)
        self._turns: list[dict] = []      # session-only, dies with me
        self._thread = None

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        top = QHBoxLayout()
        top.addWidget(QLabel("Scope"))
        self.scope_combo = QComboBox()
        self.scope_combo.addItem("Portfolio (all holdings)", None)
        for c in models.get_all_companies():
            self.scope_combo.addItem(c['name'], c['id'])
        top.addWidget(self.scope_combo, 1)
        layout.addLayout(top)

        self._cards_host = QWidget()
        self._cards = QVBoxLayout(self._cards_host)
        self._cards.setSpacing(10)
        self._cards.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._cards_host)
        layout.addWidget(scroll, 1)

        self.question_edit = QPlainTextEdit()
        self.question_edit.setPlaceholderText(
            "e.g. Which holdings drive most of the NAV, and which are "
            "carried at estimates?")
        self.question_edit.setFixedHeight(64)
        layout.addWidget(self.question_edit)

        bottom = QHBoxLayout()
        note = QLabel("Session only — nothing is saved. Every question "
                      "asks for your consent and shows the exact payload.")
        note.setWordWrap(True)
        note.setStyleSheet(f"color:{MUTED}; font-size:8.5pt;")
        bottom.addWidget(note, 1)
        self.ask_btn = QPushButton("Ask…")
        self.ask_btn.clicked.connect(self._ask)
        bottom.addWidget(self.ask_btn)
        layout.addLayout(bottom)

    # ── flow ──────────────────────────────────────────────────────────────

    def _add_widget(self, w):
        self._cards.insertWidget(self._cards.count() - 1, w)

    def _ask(self):
        question = self.question_edit.toPlainText().strip()
        if not question:
            return
        from ai import service
        from reporting.builder import (build_company_report_model,
                                       build_portfolio_report_model)

        pseudo = (aictx.Pseudonymizer() if ai.is_pseudonymize_enabled()
                  else None)
        cid = self.scope_combo.currentData()
        if cid is None:
            model = build_portfolio_report_model()
            pack = aictx.build_portfolio_pack(model, pseudo)
        else:
            model = build_company_report_model(cid)
            pack = aictx.build_company_pack(model, pseudo)
        as_of = model['meta']['as_of']
        prompt = aictx.qa_prompt(pack, question, self._turns, pseudo)

        self.ask_btn.setEnabled(False)
        self.ask_btn.setText("Asking…")
        self._thread = service.send_request(
            AIRequest('qa', prompt), ai.get_provider(), parent=self,
            on_done=partial(self._answered, question, as_of, pseudo),
            max_tokens=1500, timeout_s=180,
            consent_note=pseudo.enabled_note if pseudo else None)

    def _answered(self, question, as_of, pseudo, result):
        self.ask_btn.setEnabled(True)
        self.ask_btn.setText("Ask…")
        if result.outcome == 'cancelled':
            return                        # clean UI, question box intact
        if not result.ok:
            err = QLabel(result.error + "  (your question is still in "
                         "the box — press Ask to retry)")
            err.setWordWrap(True)
            err.setStyleSheet(f"color:{RED}; font-size:9pt;")
            self._add_widget(err)
            return

        data = pseudo.restore_in(result.data) if pseudo else result.data
        card = AICard(result.provider, result.model, result.timestamp,
                      parent=self)
        parts = [f"<b>Q: {html.escape(question)}</b>"]
        parts.extend(data.get('answer_paragraphs', []))
        parts.append(f"<span style='color:{MUTED}; font-size:8.5pt;'>"
                     f"Based on data as of {html.escape(as_of)}.</span>")
        follow = data.get('follow_up_suggestions', [])
        if follow:
            parts.append(f"<span style='color:{MUTED}; font-size:8.5pt;'>"
                         "You could ask next: "
                         + ' · '.join(follow) + "</span>")
        card.set_body_text('<br><br>'.join(parts))
        self._add_widget(card)

        # payload for later turns carries plain text, not escaped HTML
        answer_plain = html.unescape(
            ' '.join(data.get('answer_paragraphs', [])))
        self._turns.append({'question': question,
                            'answer': answer_plain})
        self.question_edit.clear()
