"""Per-company AI features (session 8): narrative sections + risk flags.

ONE generation path — generate_for_company() — shared by the Overview
block and the report dialog's "generate first" offer: build the report
model (the AI sees only what a report shows) → whitelisted context pack
(ai/context.py) → consent with the exact payload → provider off the UI
thread → contract validation → pseudonym restore → persist to ai_outputs
with provenance. Reports later render ONLY the persisted row; export
never calls a provider.

Failure honesty: validation failures say so (with the structured reason)
and offer Retry; the raw model output is never rendered; cancelling
leaves the UI clean."""

from __future__ import annotations

import json
from functools import partial

from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

import ai
import models
from ai import context as aictx
from ai.contract import AIRequest
from ui.styles import (AMBER, GREEN, MUTED, RED,
                       SOFT_BTN_BG, SOFT_BTN_BORDER, SOFT_BTN_HOVER,
                       SOFT_BTN_TEXT)
from ui.ai_card import AICard

_SOFT = (f"QPushButton {{ background:{SOFT_BTN_BG}; color:{SOFT_BTN_TEXT};"
         f"border:1px solid {SOFT_BTN_BORDER}; border-radius:6px;"
         f"padding:5px 12px; font-weight:600; }}"
         f"QPushButton:hover {{ background:{SOFT_BTN_HOVER}; }}")

SEVERITY_COLORS = {'low': GREEN, 'medium': AMBER, 'high': RED}

TASK_LABELS = {'narrative': 'AI narrative',
               'risk_flags': 'AI risk flags'}


def generate_for_company(parent, company_id: int, task: str,
                         on_done=None, use_thread=True):
    """The one generation flow (task: 'narrative' | 'risk_flags').
    on_done(AIResult) fires when finished; on sent_ok the output is
    already persisted. Returns the worker thread (or the result when
    use_thread=False — the test path)."""
    from ai import service
    from reporting.builder import build_company_report_model

    model = build_company_report_model(company_id)
    pseudo = (aictx.Pseudonymizer() if ai.is_pseudonymize_enabled()
              else None)
    prompt = (aictx.narrative_prompt(model, pseudo) if task == 'narrative'
              else aictx.risk_prompt(model, pseudo))
    request = AIRequest(task, prompt)
    provider = ai.get_provider()

    def _finish(result):
        if result.ok:
            data = (pseudo.restore_in(result.data) if pseudo
                    else result.data)
            models.save_ai_output(
                company_id, task, result.provider, result.model,
                len(prompt), json.dumps(data, ensure_ascii=False))
        if on_done:
            on_done(result)

    return service.send_request(
        request, provider, parent=parent, on_done=_finish,
        max_tokens=2000, timeout_s=180, use_thread=use_thread,
        consent_note=pseudo.enabled_note if pseudo else None)


# ── card rendering from a persisted ai_outputs row ───────────────────────────

def _provenance(row) -> tuple[str, str, str]:
    ts = (row['created_at'] or '').replace('T', ' ')[:16]
    return row['provider'], row['model'], ts


def narrative_card(row, parent=None) -> AICard:
    """row = ai_outputs row. Strings in response_json are already
    HTML-escaped by the contract — rendered as rich text, NOT re-escaped."""
    card = AICard(*_provenance(row), parent=parent)
    d = json.loads(row['response_json'])
    parts = []
    for s in d.get('sections', []):
        parts.append(f"<b>{s['title']}</b>")
        parts.extend(s.get('paragraphs', []))
    for cv in d.get('caveats', []):
        parts.append(f"<span style='color:{MUTED}; font-size:9pt;'>"
                     f"Caveat: {cv}</span>")
    card.set_body_text('<br><br>'.join(parts)
                       or 'The model returned no sections.')
    return card


def flags_card(row, parent=None) -> AICard:
    card = AICard(*_provenance(row), parent=parent)
    d = json.loads(row['response_json'])
    flags = d.get('flags', [])
    if not flags:
        card.set_body_text('No flags raised.')
        return card
    parts = []
    for f in flags:
        color = SEVERITY_COLORS.get(f['severity'], MUTED)
        based = ', '.join(f.get('based_on', []))
        based_html = (f"<br><span style='color:{MUTED}; font-size:8pt;'>"
                      f"based on: {based}</span>" if based else '')
        parts.append(
            f"<span style='color:{color};'>●</span> "
            f"<b>{f['title']}</b> "
            f"<span style='color:{color}; font-size:8pt;'>"
            f"[{f['severity']}]</span><br>{f['rationale']}{based_html}")
    card.set_body_text('<br><br>'.join(parts))
    return card


# ── the Overview block ───────────────────────────────────────────────────────

class CompanyAIBlock(QWidget):
    """Only ever constructed when is_ai_enabled() — the caller checks."""

    def __init__(self, company_id: int, company_name: str, parent=None):
        super().__init__(parent)
        self._cid = company_id
        self._name = company_name
        self._thread = None
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 8, 0, 0)
        self._layout.setSpacing(8)
        self._rebuild()

    def _clear(self):
        while self._layout.count():
            item = self._layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
            elif item.layout() is not None:
                sub = item.layout()
                while sub.count():
                    si = sub.takeAt(0)
                    if si.widget() is not None:
                        si.widget().deleteLater()

    def _rebuild(self):
        self._clear()
        header = QLabel("AI insights")
        header.setStyleSheet("font-size:11pt; font-weight:bold;")
        self._layout.addWidget(header)
        note = QLabel("Opt-in — nothing is generated or sent without "
                      "your consent per action.")
        note.setStyleSheet(f"color:{MUTED}; font-size:8.5pt;")
        self._layout.addWidget(note)

        self._buttons = {}
        for task in ('narrative', 'risk_flags'):
            row = models.get_ai_output(self._cid, task)
            if row:
                card = (narrative_card(row, self) if task == 'narrative'
                        else flags_card(row, self))
                self._layout.addWidget(card)
            btn_row = QHBoxLayout()
            label = TASK_LABELS[task]
            gen = QPushButton(
                (f"↻ Regenerate {label}…" if row
                 else f"✦ Generate {label}…"))
            gen.setStyleSheet(_SOFT)
            gen.clicked.connect(partial(self._generate, task))
            self._buttons[task] = gen
            btn_row.addWidget(gen)
            if row:
                rm = QPushButton("Remove")
                rm.setStyleSheet(_SOFT)
                rm.clicked.connect(partial(self._remove, task))
                btn_row.addWidget(rm)
            btn_row.addStretch()
            self._layout.addLayout(btn_row)

    # ── actions ───────────────────────────────────────────────────────────

    def _generate(self, task):
        btn = self._buttons[task]
        btn.setEnabled(False)
        btn.setText(f"Generating {TASK_LABELS[task]}…")
        self._thread = generate_for_company(
            self, self._cid, task, on_done=partial(self._done, task))

    def _done(self, task, result):
        if result.outcome == 'cancelled':
            self._rebuild()
            return
        if result.ok:
            self._rebuild()
            return
        # failure honesty: typed message, raw output never rendered
        self._rebuild()
        err = QLabel(result.error)
        err.setWordWrap(True)
        err.setStyleSheet(f"color:{RED}; font-size:9pt;")
        retry = QPushButton(f"Retry {TASK_LABELS[task]}…")
        retry.setStyleSheet(_SOFT)
        retry.clicked.connect(partial(self._generate, task))
        self._layout.addWidget(err)
        self._layout.addWidget(retry)

    def _remove(self, task):
        models.delete_ai_output(self._cid, task)
        self._rebuild()
