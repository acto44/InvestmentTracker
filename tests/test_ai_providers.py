"""Providers with the outside world mocked out (zero network — enforced
by the autouse no_network fixture), plus keystore round-trips."""

import io
import json
import subprocess
import sys
import urllib.error
import urllib.request

import pytest

import ai.claude_cli as claude_cli
import ai.keystore as keystore
import ai.openai_api as openai_api
from ai.base import AIAuthError, AINotAvailable, AIProviderError, AITimeout
from ai.claude_cli import ClaudeCLIProvider
from ai.openai_api import OpenAIProvider


# ── the network ban itself ────────────────────────────────────────────────────

def test_network_is_banned_during_tests():
    with pytest.raises(RuntimeError, match='Blocked'):
        urllib.request.urlopen('http://example.com')
    import socket
    with pytest.raises(RuntimeError, match='Blocked'):
        socket.create_connection(('example.com', 80))


# ── Claude CLI provider (subprocess mocked) ──────────────────────────────────

def _cli_ok(result_text):
    return subprocess.CompletedProcess(
        args=[], returncode=0, stderr='',
        stdout=json.dumps({'type': 'result', 'subtype': 'success',
                           'is_error': False, 'result': result_text}))


@pytest.fixture
def fake_claude(monkeypatch):
    """find_claude → fixed path; subprocess.run → recorder."""
    calls = {}

    def fake_run(args, **kwargs):
        calls['args'] = args
        calls['kwargs'] = kwargs
        return calls.get('response', _cli_ok('{"ok": true}'))

    monkeypatch.setattr(claude_cli, 'find_claude',
                        lambda: r'C:\fake\claude.exe')
    monkeypatch.setattr(claude_cli.subprocess, 'run', fake_run)
    return calls


def test_claude_argument_construction_and_stdin(fake_claude):
    p = ClaudeCLIProvider()
    secret = 'PAYLOAD with private figures 12345'
    out = p.complete(secret, system='fixed instruction')
    assert out == '{"ok": true}'
    args = fake_claude['args']
    kwargs = fake_claude['kwargs']
    assert args[0] == r'C:\fake\claude.exe'
    assert '-p' in args
    assert args[args.index('--output-format') + 1] == 'json'
    assert args[args.index('--tools') + 1] == ''      # no machine access
    assert '--no-session-persistence' in args         # no disk traces
    assert args[args.index('--system-prompt') + 1] == 'fixed instruction'
    # the payload goes via STDIN, never argv (argv is world-readable)
    assert kwargs['input'] == secret
    assert secret not in args
    assert not kwargs.get('shell')
    assert kwargs['timeout'] == 120


def test_claude_model_flag_only_when_configured(fake_claude):
    ClaudeCLIProvider().complete('x')
    assert '--model' not in fake_claude['args']
    ClaudeCLIProvider(model='claude-sonnet-5').complete('x')
    assert fake_claude['args'][
        fake_claude['args'].index('--model') + 1] == 'claude-sonnet-5'


def test_claude_timeout_maps_to_aitimeout(monkeypatch):
    monkeypatch.setattr(claude_cli, 'find_claude',
                        lambda: r'C:\fake\claude.exe')

    def timeout_run(args, **kwargs):
        # subprocess.run itself kills the child before raising this
        raise subprocess.TimeoutExpired(cmd=args, timeout=5)

    monkeypatch.setattr(claude_cli.subprocess, 'run', timeout_run)
    with pytest.raises(AITimeout):
        ClaudeCLIProvider().complete('x', timeout_s=5)


def test_claude_auth_failure_maps_to_aiautherror(fake_claude):
    fake_claude['response'] = subprocess.CompletedProcess(
        args=[], returncode=1, stdout='',
        stderr='Not authenticated. Please run /login')
    with pytest.raises(AIAuthError) as e:
        ClaudeCLIProvider().complete('x')
    assert 'signed in' in str(e.value)            # actionable message


def test_claude_error_json_and_garbage_output(fake_claude):
    fake_claude['response'] = subprocess.CompletedProcess(
        args=[], returncode=0, stderr='',
        stdout=json.dumps({'type': 'result', 'subtype': 'error',
                           'is_error': True, 'result': 'model exploded'}))
    with pytest.raises(AIProviderError, match='model exploded'):
        ClaudeCLIProvider().complete('x')
    fake_claude['response'] = subprocess.CompletedProcess(
        args=[], returncode=0, stderr='', stdout='not json at all')
    with pytest.raises(AIProviderError, match='non-JSON'):
        ClaudeCLIProvider().complete('x')


def test_claude_not_installed_is_not_available(monkeypatch):
    monkeypatch.setattr(claude_cli, 'find_claude', lambda: None)
    ok, reason = ClaudeCLIProvider().is_available()
    assert not ok and 'not found' in reason.lower()
    with pytest.raises(AINotAvailable):
        ClaudeCLIProvider().complete('x')


# ── OpenAI provider (urlopen mocked) ─────────────────────────────────────────

class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def read(self):
        return json.dumps(self._payload).encode('utf-8')

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


@pytest.fixture
def fake_openai(monkeypatch):
    calls = {}

    def fake_urlopen(req, timeout=None, context=None):
        calls['req'] = req
        calls['timeout'] = timeout
        calls['context'] = context
        if 'raise' in calls:
            raise calls['raise']
        return _FakeResponse(calls.get('response', {
            'choices': [{'message': {'content': '{"ok": true}'}}]}))

    monkeypatch.setattr(openai_api.urllib.request, 'urlopen',
                        fake_urlopen)
    return calls


def test_openai_request_shape(fake_openai):
    p = OpenAIProvider(api_key='sk-test-abc')
    out = p.complete('the payload', system='fixed instruction',
                     max_tokens=321, timeout_s=44)
    assert out == '{"ok": true}'
    req = fake_openai['req']
    assert req.full_url == openai_api.ENDPOINT
    assert req.get_method() == 'POST'
    assert req.headers['Authorization'] == 'Bearer sk-test-abc'
    assert req.headers['Content-type'] == 'application/json'
    body = json.loads(req.data.decode('utf-8'))
    assert body['model'] == openai_api.DEFAULT_MODEL
    assert body['messages'] == [
        {'role': 'system', 'content': 'fixed instruction'},
        {'role': 'user', 'content': 'the payload'}]
    assert body['max_completion_tokens'] == 321
    assert fake_openai['timeout'] == 44
    assert fake_openai['context'] is not None     # TLS context


def test_openai_no_key_refuses_before_any_request(monkeypatch, tmp_path):
    keystore.set_store_dir(str(tmp_path))         # empty store: no key
    try:
        called = {'n': 0}

        def must_not_run(*a, **k):
            called['n'] += 1
            raise AssertionError('request must not be built')

        monkeypatch.setattr(openai_api.urllib.request, 'urlopen',
                            must_not_run)
        with pytest.raises(AIAuthError, match='No OpenAI API key'):
            OpenAIProvider().complete('x')
        assert called['n'] == 0
    finally:
        keystore.set_store_dir(None)


def test_openai_401_maps_to_auth_error_without_leaking_key(fake_openai):
    fake_openai['raise'] = urllib.error.HTTPError(
        openai_api.ENDPOINT, 401, 'Unauthorized', {},
        io.BytesIO(b'{"error": {"message": '
                   b'"Incorrect API key provided: sk-verysecret123"}}'))
    with pytest.raises(AIAuthError) as e:
        OpenAIProvider(api_key='sk-verysecret123').complete('x')
    assert 'sk-verysecret123' not in str(e.value)
    assert '401' in str(e.value)


def test_openai_http_error_detail_is_scrubbed(fake_openai):
    fake_openai['raise'] = urllib.error.HTTPError(
        openai_api.ENDPOINT, 500, 'Server Error', {},
        io.BytesIO(b'oops sk-leaked-in-body-000 happened'))
    with pytest.raises(AIProviderError) as e:
        OpenAIProvider(api_key='sk-k').complete('x')
    assert 'sk-leaked-in-body-000' not in str(e.value)
    assert 'sk-***' in str(e.value)


def test_openai_timeout_maps_to_aitimeout(fake_openai):
    fake_openai['raise'] = urllib.error.URLError(TimeoutError())
    with pytest.raises(AITimeout):
        OpenAIProvider(api_key='sk-k').complete('x', timeout_s=3)


def test_openai_malformed_response(fake_openai):
    fake_openai['response'] = {'choices': []}
    with pytest.raises(AIProviderError, match='no message content'):
        OpenAIProvider(api_key='sk-k').complete('x')


# ── keystore ─────────────────────────────────────────────────────────────────

@pytest.fixture
def key_store(tmp_path):
    keystore.set_store_dir(str(tmp_path))
    yield tmp_path
    keystore.set_store_dir(None)


@pytest.mark.skipif(sys.platform != 'win32',
                    reason='DPAPI is Windows-only')
def test_dpapi_roundtrip_and_ciphertext(key_store):
    secret = 'sk-roundtrip-secret-123'
    keystore.save_api_key(secret)
    assert keystore.load_api_key() == secret
    assert keystore.storage_is_encrypted() is True
    blob = (key_store / 'openai_key.bin').read_bytes()
    assert secret.encode() not in blob            # encrypted at rest
    keystore.clear_api_key()
    assert keystore.load_api_key() is None
    assert not keystore.has_api_key()


def test_fallback_store_roundtrip_with_warning_flag(key_store,
                                                    monkeypatch):
    monkeypatch.setattr(keystore, '_dpapi_available', lambda: False)
    secret = 'sk-fallback-secret-456'
    keystore.save_api_key(secret)
    assert keystore.load_api_key() == secret
    # the flag the settings UI turns into a visible warning
    assert keystore.storage_is_encrypted() is False
    blob = (key_store / 'openai_key.bin').read_bytes()
    assert blob.startswith(b'OBF1\n')
    assert secret.encode() not in blob            # not plaintext (only!)


def test_corrupt_key_file_returns_none(key_store):
    (key_store / 'openai_key.bin').write_bytes(b'DPAPI1\ngarbage')
    assert keystore.load_api_key() is None
