"""THE pipeline every AI feature calls (session 8 included):

    gate → consent (exact payload) → provider off the UI thread →
    contract validation/clamp → ai_activity log → on_done(AIResult)

Exactly one ai_activity row per attempt, holding size + outcome only —
the payload body and any secrets are never persisted. AIResult.data is
the ONLY thing a caller may render (it is validated and HTML-escaped);
AIResult.error is a short human message for the failure label."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from PyQt6.QtCore import QObject, QThread, pyqtSignal

import ai
import models
from ai.base import AIError, AINotAvailable
from ai.consent import ConsentDialog, compose_payload_preview
from ai.contract import (AIRequest, ContractViolation, get_contract,
                         validate_response)


@dataclass
class AIResult:
    outcome: str            # 'sent_ok' | 'cancelled' | 'validation_failed'
                            # | 'provider_error'
    provider: str
    model: str
    task_id: str
    data: dict | None = None    # validated+escaped fields (sent_ok only)
    error: str = ''             # human-readable reason otherwise
    timestamp: str = field(
        default_factory=lambda: datetime.now().strftime('%Y-%m-%d %H:%M'))

    @property
    def ok(self) -> bool:
        return self.outcome == 'sent_ok'


class AICallThread(QThread):
    """Reusable off-UI-thread provider call. cancel() makes the outcome
    silent: the result is discarded (the hard stop is the provider's own
    timeout, which kills any child process)."""
    succeeded = pyqtSignal(str)
    failed = pyqtSignal(object)     # an AIError subclass instance

    def __init__(self, provider, prompt, system, max_tokens, timeout_s,
                 parent=None):
        super().__init__(parent)
        self._provider = provider
        self._prompt = prompt
        self._system = system
        self._max_tokens = max_tokens
        self._timeout_s = timeout_s
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            text = self._provider.complete(
                self._prompt, system=self._system,
                max_tokens=self._max_tokens, timeout_s=self._timeout_s)
        except AIError as e:
            if not self._cancelled:
                self.failed.emit(e)
            return
        except Exception as e:                      # provider bug — still typed
            if not self._cancelled:
                self.failed.emit(e)
            return
        if not self._cancelled:
            self.succeeded.emit(text)


class _Relay(QObject):
    """Signal receiver that lives in the CALLER's thread. Connecting the
    worker's signals to bound methods of this object makes Qt queue the
    delivery back onto the caller's event loop — connecting them to plain
    closures would run validation and UI callbacks in the worker thread."""

    def __init__(self, on_text, on_exc, parent=None):
        super().__init__(parent)
        self._on_text = on_text
        self._on_exc = on_exc

    def text(self, t):
        self._on_text(t)

    def exc(self, e):
        self._on_exc(e)


def _log(provider, task_id, payload_chars, outcome):
    models.log_ai_activity(provider.name, provider.model_label, task_id,
                           payload_chars, outcome)


def send_request(request: AIRequest, provider=None, parent=None,
                 on_done=None, *, max_tokens=1000, timeout_s=120,
                 use_thread=True, consent=None, consent_note=None):
    """Run the full pipeline for `request`. on_done(AIResult) fires when
    finished (synchronously when use_thread=False — the test path).
    `consent` overrides the dialog (tests); default is ConsentDialog.ask.
    Returns the AICallThread (threaded) or the AIResult (synchronous),
    or the cancelled/gated AIResult immediately."""
    if not ai.is_ai_enabled():
        raise AINotAvailable(
            "AI is disabled (Settings → AI). Features must not call "
            "send_request while the master switch is off.")
    provider = provider or ai.get_provider()
    contract = get_contract(request.task_id)
    _user_on_done = on_done or (lambda result: None)
    _last = {}

    def on_done(result):
        _last['result'] = result
        _user_on_done(result)

    preview = compose_payload_preview(request.prompt, contract.system)
    payload_chars = len(request.prompt) + len(contract.system or '')

    ask = consent or (lambda: ConsentDialog.ask(
        parent, provider, contract.purpose, preview,
        note=consent_note))
    if not ask():
        _log(provider, request.task_id, payload_chars, 'cancelled')
        result = AIResult('cancelled', provider.name,
                          provider.model_label, request.task_id,
                          error='Cancelled — nothing was sent.')
        on_done(result)
        return result

    def _finish_success(raw_text: str):
        try:
            data = validate_response(raw_text, contract)
        except ContractViolation as e:
            _log(provider, request.task_id, payload_chars,
                 'validation_failed')
            on_done(AIResult('validation_failed', provider.name,
                             provider.model_label, request.task_id,
                             error=f"AI reply rejected by the "
                                   f"{contract.task_id} contract: {e}"))
            return
        _log(provider, request.task_id, payload_chars, 'sent_ok')
        on_done(AIResult('sent_ok', provider.name, provider.model_label,
                         request.task_id, data=data))

    def _finish_failure(exc):
        _log(provider, request.task_id, payload_chars, 'provider_error')
        on_done(AIResult('provider_error', provider.name,
                         provider.model_label, request.task_id,
                         error=f"{type(exc).__name__}: {exc}"))

    if not use_thread:
        try:
            raw = provider.complete(request.prompt,
                                    system=contract.system,
                                    max_tokens=max_tokens,
                                    timeout_s=timeout_s)
        except Exception as e:
            _finish_failure(e)
            return _last.get('result')
        _finish_success(raw)
        return _last.get('result')

    thread = AICallThread(provider, request.prompt, contract.system,
                          max_tokens, timeout_s, parent=parent)
    relay = _Relay(_finish_success, _finish_failure, parent=thread)
    thread.succeeded.connect(relay.text)
    thread.failed.connect(relay.exc)
    thread.start()
    return thread
