"""OpenAI provider via plain urllib over HTTPS — the owner's own API key,
deliberately NO openai SDK (CLAUDE.md: DEPENDENCIES — stdlib first; a new
runtime dependency would need a register entry, and urllib does the job).

Default model gpt-4.1-mini: checked against the OpenAI docs on
2026-07-15 — the GPT-4o family is legacy for new API users and the 4.1
family is the recommended default tier; the model is configurable in
Settings -> AI either way. max_completion_tokens is used (max_tokens is
deprecated on current models).

The API key comes from ai/keystore.py and must NEVER appear in logs or
exception texts — every error detail is passed through _scrub()."""

from __future__ import annotations

import json
import re
import socket
import ssl
import urllib.error
import urllib.request

from ai import keystore
from ai.base import AIAuthError, AIProviderError, AITimeout

ENDPOINT = 'https://api.openai.com/v1/chat/completions'
DEFAULT_MODEL = 'gpt-4.1-mini'

_KEY_RE = re.compile(r'sk-[A-Za-z0-9_\-]{4,}')

_NO_KEY = ("No OpenAI API key saved — add one in Settings → AI. "
           "The key stays on this machine.")


def _scrub(text: str) -> str:
    """Belt and braces: no sk-… token ever reaches a message or log."""
    return _KEY_RE.sub('sk-***', text or '')


class OpenAIProvider:
    name = 'openai'
    destination = 'OpenAI via your API key'

    def __init__(self, model: str | None = None,
                 api_key: str | None = None):
        self.model = model or DEFAULT_MODEL
        self._explicit_key = api_key

    @property
    def model_label(self) -> str:
        return self.model

    def _api_key(self) -> str | None:
        return self._explicit_key or keystore.load_api_key()

    def is_available(self):
        if not self._api_key():
            return False, _NO_KEY
        at_rest = ('encrypted (DPAPI)' if keystore.storage_is_encrypted()
                   else 'obfuscated — NOT securely encrypted on this OS')
        return True, f"API key saved, {at_rest}; model {self.model}."

    def complete(self, prompt: str, *, system: str | None = None,
                 max_tokens: int = 1000, timeout_s: float = 60) -> str:
        key = self._api_key()
        if not key:
            # refuse BEFORE any request object exists
            raise AIAuthError(_NO_KEY)
        messages = []
        if system:
            messages.append({'role': 'system', 'content': system})
        messages.append({'role': 'user', 'content': prompt})
        body = json.dumps({
            'model': self.model,
            'messages': messages,
            'max_completion_tokens': int(max_tokens),
        }).encode('utf-8')
        req = urllib.request.Request(
            ENDPOINT, data=body, method='POST',
            headers={'Content-Type': 'application/json',
                     'Authorization': f'Bearer {key}'})
        try:
            with urllib.request.urlopen(
                    req, timeout=timeout_s,
                    context=ssl.create_default_context()) as resp:
                data = json.loads(resp.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            try:
                detail = e.read().decode('utf-8', 'replace')[:300]
            except Exception:
                detail = ''
            if e.code in (401, 403):
                raise AIAuthError(
                    f"OpenAI rejected the API key (HTTP {e.code}). "
                    f"Check the key in Settings → AI.")
            raise AIProviderError(
                f"OpenAI HTTP {e.code}: {_scrub(detail)}")
        except (TimeoutError, socket.timeout):
            raise AITimeout(f"OpenAI did not answer within "
                            f"{timeout_s:.0f}s.")
        except urllib.error.URLError as e:
            if isinstance(e.reason, (TimeoutError, socket.timeout)):
                raise AITimeout(f"OpenAI did not answer within "
                                f"{timeout_s:.0f}s.")
            raise AIProviderError(
                f"Could not reach OpenAI: {_scrub(str(e.reason))}")

        try:
            content = data['choices'][0]['message']['content']
        except (KeyError, IndexError, TypeError):
            raise AIProviderError(
                "OpenAI response contained no message content.")
        if not isinstance(content, str):
            raise AIProviderError(
                "OpenAI response content was not text.")
        return content
