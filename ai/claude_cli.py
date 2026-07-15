"""Claude provider via the locally installed Claude Code CLI — the
owner's own Claude account, no API key handled by this app.

Flags verified against claude 2.1.210 on this machine (2026-07-15):
  -p / --print               non-interactive, print result and exit
  --output-format json       single JSON object on stdout with a
                             'result' string, 'is_error', 'subtype'
  --system-prompt <s>        session system prompt (fixed strings only)
  --tools ""                 disable ALL tools — a completion call must
                             never be able to touch this machine
  --no-session-persistence   nothing written to the CLI's session store
                             (the payload must leave no disk traces)
NOTE: --bare is deliberately NOT used — it disables OAuth/keychain auth
and would break the owner's account login.

Privacy: the prompt is passed via STDIN, never as an argv element (argv
is visible to every local process). The subprocess runs in a neutral temp
directory so the CLI's CLAUDE.md auto-discovery cannot pick up project or
personal context. There is no max-tokens CLI flag; max_tokens is accepted
for protocol compatibility and enforced by the contract clamp instead."""

from __future__ import annotations

import glob
import json
import os
import re
import shutil
import subprocess
import tempfile

from ai.base import AIAuthError, AINotAvailable, AIProviderError, AITimeout

_AUTH_HINTS = ('login', 'log in', 'logged in', 'not authenticated',
               'authentication', 'credential', 'api key', 'oauth',
               'subscription', 'unauthorized')

_AUTH_FIX = ("Claude CLI is installed but not signed in — open a "
             "terminal, run claude, complete the login, then try again.")

_VERSION_RE = re.compile(r'(\d+)\.(\d+)\.(\d+)')


def find_claude() -> str | None:
    """PATH first; else the newest claude bundled inside the VS Code
    Claude Code extension (how it ships on this machine)."""
    exe = shutil.which('claude')
    if exe:
        return exe
    ext = 'claude.exe' if os.name == 'nt' else 'claude'
    pattern = os.path.join(os.path.expanduser('~'), '.vscode',
                           'extensions', 'anthropic.claude-code-*',
                           'resources', 'native-binary', ext)
    candidates = glob.glob(pattern)
    if not candidates:
        return None

    def version_key(path):
        m = _VERSION_RE.search(os.path.basename(
            os.path.dirname(os.path.dirname(os.path.dirname(path)))))
        return tuple(int(g) for g in m.groups()) if m else (0, 0, 0)

    return max(candidates, key=version_key)


def _no_window_flags() -> int:
    # the app is a windowed .exe — a child console must never flash up
    return subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0


def _neutral_cwd() -> str:
    d = os.path.join(tempfile.gettempdir(), 'fit-ai-neutral')
    os.makedirs(d, exist_ok=True)
    return d


class ClaudeCLIProvider:
    name = 'claude_cli'
    destination = 'Anthropic via your Claude account'

    def __init__(self, model: str | None = None):
        self.model = model  # None → the CLI's default model

    @property
    def model_label(self) -> str:
        return self.model or 'CLI default model'

    def is_available(self):
        exe = find_claude()
        if not exe:
            return False, ("Claude Code CLI not found — not on PATH and "
                           "no VS Code Claude Code extension install.")
        try:
            proc = subprocess.run(
                [exe, '--version'], capture_output=True, text=True,
                timeout=15, creationflags=_no_window_flags())
        except Exception as e:
            return False, f"Claude CLI found but not runnable: {e}"
        if proc.returncode != 0:
            return False, (f"claude --version failed (exit "
                           f"{proc.returncode}).")
        return True, f"Claude Code {proc.stdout.strip()}"

    def complete(self, prompt: str, *, system: str | None = None,
                 max_tokens: int = 1000, timeout_s: float = 120) -> str:
        exe = find_claude()
        if not exe:
            raise AINotAvailable(self.is_available()[1])
        args = [exe, '-p', '--output-format', 'json', '--tools', '',
                '--no-session-persistence']
        if system:
            args += ['--system-prompt', system]
        if self.model:
            args += ['--model', self.model]
        try:
            # prompt via stdin ONLY; run() kills the child on timeout
            proc = subprocess.run(
                args, input=prompt, capture_output=True, text=True,
                encoding='utf-8', timeout=timeout_s, cwd=_neutral_cwd(),
                creationflags=_no_window_flags())
        except subprocess.TimeoutExpired:
            raise AITimeout(f"Claude CLI did not answer within "
                            f"{timeout_s:.0f}s (process killed).")
        except OSError as e:
            raise AIProviderError(f"Could not start Claude CLI: {e}")

        if proc.returncode != 0:
            blob = f"{proc.stderr or ''} {proc.stdout or ''}".lower()
            if any(h in blob for h in _AUTH_HINTS):
                raise AIAuthError(_AUTH_FIX)
            detail = (proc.stderr or proc.stdout or '').strip()[:300]
            raise AIProviderError(
                f"Claude CLI exited with code {proc.returncode}: "
                f"{detail or 'no output'}")

        try:
            data = json.loads(proc.stdout)
        except ValueError:
            raise AIProviderError(
                f"Claude CLI returned non-JSON output: "
                f"{(proc.stdout or '').strip()[:200]!r}")
        if data.get('is_error') or data.get('subtype') != 'success':
            detail = str(data.get('result') or data.get('subtype')
                         or 'unknown error')
            if any(h in detail.lower() for h in _AUTH_HINTS):
                raise AIAuthError(_AUTH_FIX)
            raise AIProviderError(detail[:300])
        return data.get('result') or ''
