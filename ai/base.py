"""Provider contract + typed failures. Nothing outside ai/ touches
subprocesses or HTTP directly — providers implement AIProvider and raise
ONLY the exceptions below, so callers can react without string-matching.

Data-handling rule (CLAUDE.md: AI): the `prompt` argument is the payload
and may contain financial data — providers must pass it via stdin or a
request body, NEVER as a command-line argument (visible to every local
process). The `system` argument is reserved for FIXED instruction strings
from ai/contract.py; user or database content never goes in `system`.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


class AIError(Exception):
    """Base for every failure a provider may raise."""


class AINotAvailable(AIError):
    """The provider cannot run at all (no CLI installed, no key saved)."""


class AIAuthError(AIError):
    """Credentials rejected or missing — message says how to fix it."""


class AITimeout(AIError):
    """The provider did not answer in time; any child process was killed."""


class AIProviderError(AIError):
    """The provider ran but failed. `detail` is a short, scrubbed reason
    (never the payload, never a secret)."""

    def __init__(self, detail: str):
        super().__init__(detail)
        self.detail = detail


@runtime_checkable
class AIProvider(Protocol):
    name: str           # stable id used in ai_activity ('claude_cli', …)
    model_label: str    # human-readable model shown in consent/AICard
    destination: str    # consent line: where the data goes

    def is_available(self) -> tuple[bool, str]:
        """(usable, human reason) — never raises."""
        ...

    def complete(self, prompt: str, *, system: str | None = None,
                 max_tokens: int = 1000, timeout_s: float = 120) -> str:
        """Blocking single completion. Raises only AIError subclasses."""
        ...
