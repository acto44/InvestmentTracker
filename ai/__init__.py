"""AI plumbing (session 7). INVARIANTS (CLAUDE.md: AI):
- opt-in: is_ai_enabled() is THE single gate — default off, and with it
  off no AI affordance may exist anywhere outside Settings -> AI;
- per-action consent: every send goes through ai.service.send_request,
  which shows the exact payload first (ai/consent.py);
- validated output only: nothing renders un-validated (ai/contract.py);
- the payload body is never persisted (models.ai_activity stores size
  and outcome only).
Session 8 features call ai.service.send_request and render inside
ui.ai_card.AICard — nothing else."""

from __future__ import annotations

import models

AI_ENABLED_KEY = 'ai_enabled'
AI_PROVIDER_KEY = 'ai_provider'
AI_OPENAI_MODEL_KEY = 'ai_openai_model'


def is_ai_enabled() -> bool:
    """THE master-switch gate. Default OFF."""
    return models.get_setting(AI_ENABLED_KEY, '0') == '1'


def set_ai_enabled(on: bool):
    models.set_setting(AI_ENABLED_KEY, '1' if on else '0')


def get_provider(name: str | None = None):
    """The configured provider (or an explicit one by name)."""
    name = name or models.get_setting(AI_PROVIDER_KEY, 'claude_cli')
    if name == 'openai':
        from ai.openai_api import OpenAIProvider
        return OpenAIProvider(
            model=models.get_setting(AI_OPENAI_MODEL_KEY, '') or None)
    from ai.claude_cli import ClaudeCLIProvider
    return ClaudeCLIProvider()
