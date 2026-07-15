"""The full pipeline with a FakeProvider (zero network): consent shows
exactly what the provider receives, every outcome writes one ai_activity
row, no payload body or secret ever lands in the database, and with the
master switch off the app has no AI surface at all."""

import sqlite3

import pytest

import ai
import models
from ai import keystore
from ai.base import AINotAvailable, AIProviderError
from ai.consent import (PROMPT_HEADER, SYSTEM_HEADER, ConsentDialog,
                        compose_payload_preview)
from ai.contract import PING, AIRequest, build_ping_request
from ai.service import AICallThread, send_request


class FakeProvider:
    name = 'fake'
    model_label = 'fake-1'
    destination = 'Nowhere (test fake)'

    def __init__(self, reply='{"ok": true, "message": "pong"}',
                 exc=None):
        self.calls = []
        self.reply = reply
        self.exc = exc

    def is_available(self):
        return True, 'fake provider'

    def complete(self, prompt, *, system=None, max_tokens=1000,
                 timeout_s=120):
        self.calls.append({'prompt': prompt, 'system': system})
        if self.exc:
            raise self.exc
        return self.reply


@pytest.fixture
def ai_on(temp_db):
    ai.set_ai_enabled(True)
    return temp_db


# ── migration v5 ─────────────────────────────────────────────────────────────

def test_migration_v5_creates_ai_activity(temp_db):
    conn = models.get_conn()
    row = conn.execute("SELECT name FROM sqlite_master WHERE "
                       "type='table' AND name='ai_activity'").fetchone()
    assert row is not None
    with pytest.raises(sqlite3.IntegrityError):   # outcome CHECK enforced
        conn.execute(
            "INSERT INTO ai_activity (ts_utc, provider, model, task_id, "
            "payload_chars, outcome) VALUES ('t','p','m','ping',1,'oops')")
    conn.close()
    assert models.get_setting('schema_version') == str(
        models.SCHEMA_VERSION)


def test_log_ai_activity_roundtrip(temp_db):
    models.log_ai_activity('fake', 'fake-1', 'ping', 42, 'sent_ok')
    rows = models.get_ai_activity()
    assert len(rows) == 1
    r = rows[0]
    assert (r['provider'], r['model'], r['task_id'],
            r['payload_chars'], r['outcome']) == (
        'fake', 'fake-1', 'ping', 42, 'sent_ok')
    assert 'payload' not in r or r.get('payload') is None


# ── the master switch ────────────────────────────────────────────────────────

def test_ai_default_off_and_gate_blocks_pipeline(temp_db):
    assert ai.is_ai_enabled() is False            # default OFF
    with pytest.raises(AINotAvailable):
        send_request(build_ping_request(), FakeProvider(),
                     use_thread=False, consent=lambda: True)
    assert models.get_ai_activity() == []         # nothing even logged


def test_master_switch_off_means_no_ai_in_main_window(qtbot, demo_db):
    from PyQt6.QtGui import QAction

    from ui.ai_card import AICard
    from ui.main_window import MainWindow

    assert ai.is_ai_enabled() is False
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    assert window.findChildren(AICard) == []
    texts = [a.text() for a in window.findChildren(QAction)]
    assert not any('AI' in t for t in texts), texts


# ── pipeline outcomes (synchronous test path) ───────────────────────────────

def test_accept_path_sends_validates_and_logs(ai_on):
    fake = FakeProvider()
    seen = []
    result = send_request(build_ping_request(), fake, use_thread=False,
                          consent=lambda: True, on_done=seen.append)
    assert result.ok and seen == [result]
    assert result.data == {'ok': True, 'message': 'pong'}
    rows = models.get_ai_activity()
    assert len(rows) == 1 and rows[0]['outcome'] == 'sent_ok'
    assert rows[0]['payload_chars'] == (len(build_ping_request().prompt)
                                        + len(PING.system))
    assert fake.calls[0]['system'] == PING.system


def test_cancel_sends_nothing_and_logs_cancelled(ai_on):
    fake = FakeProvider()
    result = send_request(build_ping_request(), fake, use_thread=False,
                          consent=lambda: False)
    assert result.outcome == 'cancelled'
    assert fake.calls == []                       # NOTHING left the machine
    rows = models.get_ai_activity()
    assert len(rows) == 1 and rows[0]['outcome'] == 'cancelled'


def test_invalid_reply_logs_validation_failed(ai_on):
    fake = FakeProvider(reply='I am not JSON, sorry')
    result = send_request(build_ping_request(), fake, use_thread=False,
                          consent=lambda: True)
    assert result.outcome == 'validation_failed'
    assert result.data is None                    # never rendered
    assert models.get_ai_activity()[0]['outcome'] == 'validation_failed'


def test_provider_error_logs_provider_error(ai_on):
    fake = FakeProvider(exc=AIProviderError('backend on fire'))
    result = send_request(build_ping_request(), fake, use_thread=False,
                          consent=lambda: True)
    assert result.outcome == 'provider_error'
    assert 'backend on fire' in result.error
    assert models.get_ai_activity()[0]['outcome'] == 'provider_error'


# ── consent: the preview IS what the provider receives ──────────────────────

def test_payload_preview_is_byte_for_byte_what_provider_receives(ai_on):
    fake = FakeProvider()
    request = AIRequest('ping', 'custom payload åäö <&> exact-bytes')
    send_request(request, fake, use_thread=False, consent=lambda: True)
    captured = fake.calls[0]
    preview = compose_payload_preview(request.prompt, PING.system)
    assert preview == (f"{SYSTEM_HEADER}\n{captured['system']}\n\n"
                       f"{PROMPT_HEADER}\n{captured['prompt']}")


def test_consent_dialog_shows_payload_and_defaults_to_cancel(qtbot,
                                                             temp_db):
    preview = compose_payload_preview('the exact prompt', 'the system')
    dlg = ConsentDialog(None, 'fake', 'fake-1', 'Nowhere (test fake)',
                        'testing', preview)
    qtbot.addWidget(dlg)
    assert dlg.payload_text() == preview          # shown verbatim
    assert dlg._cancel_btn.isDefault()            # Enter = Cancel
    assert not dlg._send_btn.isDefault()


# ── threaded path (the session-8 pattern) ────────────────────────────────────

def test_threaded_call_delivers_result_on_caller_thread(qtbot, ai_on):
    fake = FakeProvider()
    results = []
    thread = send_request(build_ping_request(), fake,
                          consent=lambda: True, on_done=results.append)
    assert isinstance(thread, AICallThread)
    qtbot.waitUntil(lambda: len(results) == 1, timeout=5000)
    assert results[0].ok and results[0].data['message'] == 'pong'
    thread.wait(3000)


def test_cancelled_thread_discards_result(qtbot, ai_on):
    import threading

    gate = threading.Event()

    class GatedFake(FakeProvider):
        def complete(self, prompt, **kwargs):
            gate.wait(5)                          # hold until cancelled
            return super().complete(prompt, **kwargs)

    fake = GatedFake()
    results = []
    thread = send_request(build_ping_request(), fake,
                          consent=lambda: True, on_done=results.append)
    thread.cancel()                               # …while still running
    gate.set()
    thread.wait(3000)
    qtbot.wait(200)                               # drain the event queue
    assert results == []                          # discarded, not delivered


# ── nothing sensitive is persisted ───────────────────────────────────────────

def test_no_payload_or_secrets_in_database(ai_on, tmp_path):
    keystore.set_store_dir(str(tmp_path / 'keys'))
    try:
        keystore.save_api_key('sk-SCAN-SECRET-KEY-999')
        fake = FakeProvider(
            reply='{"ok": true, "message": "RESPONSE-MARKER-888"}')
        request = AIRequest('ping', 'SECRET-PAYLOAD-MARKER-777')
        send_request(request, fake, use_thread=False,
                     consent=lambda: True)
        assert models.get_ai_activity()[0]['outcome'] == 'sent_ok'
    finally:
        keystore.set_store_dir(None)

    blob = open(ai_on, 'rb').read()               # the raw DB file
    assert b'SECRET-PAYLOAD-MARKER-777' not in blob   # no payload body
    assert b'RESPONSE-MARKER-888' not in blob         # no reply body
    assert b'sk-SCAN-SECRET-KEY-999' not in blob      # no key, ever


# ── the labeling primitive ───────────────────────────────────────────────────

def test_ai_card_labels_provenance_and_disclaimer(qtbot, temp_db):
    from PyQt6.QtWidgets import QLabel

    from ui.ai_card import DISCLAIMER, AICard

    card = AICard('fake', 'fake-1', '2026-07-15 12:00')
    qtbot.addWidget(card)
    assert card.header_text() == (
        'AI-generated · fake · fake-1 · 2026-07-15 12:00')
    card.set_body_text('hello')
    labels = [l.text() for l in card.findChildren(QLabel)]
    assert 'hello' in labels
    assert DISCLAIMER in labels


# ── settings page persistence ────────────────────────────────────────────────

def test_ai_settings_page_applies_settings(qtbot, temp_db, monkeypatch,
                                           tmp_path):
    import ai.claude_cli as claude_cli
    import ai.openai_api as openai_api

    # no real subprocess / keystore probes while building the page
    monkeypatch.setattr(claude_cli.ClaudeCLIProvider, 'is_available',
                        lambda self: (True, 'mocked'))
    monkeypatch.setattr(openai_api.OpenAIProvider, 'is_available',
                        lambda self: (False, 'no key'))
    keystore.set_store_dir(str(tmp_path))
    try:
        from ui.ai_settings import AISettingsPage

        page = AISettingsPage()
        qtbot.addWidget(page)
        assert not page.master.isChecked()        # reflects default OFF
        page.master.setChecked(True)
        page.rb_openai.setChecked(True)
        page.model_edit.setText('gpt-4.1-mini')
        page.apply()
        assert ai.is_ai_enabled() is True
        assert models.get_setting(ai.AI_PROVIDER_KEY) == 'openai'
        assert models.get_setting(ai.AI_OPENAI_MODEL_KEY) == 'gpt-4.1-mini'
    finally:
        keystore.set_store_dir(None)
