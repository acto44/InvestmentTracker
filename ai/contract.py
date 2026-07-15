"""Task contracts: every AI task declares up front what it sends (a fixed
system instruction + a prompt) and the exact JSON shape it accepts back.
validate_response() is the ONLY door between raw model output and the UI —
it parses, type-checks, CLAMPS (max lengths, max list sizes) and
HTML-escapes every string. Unknown fields are dropped. Anything that
violates the contract raises ContractViolation with a structured reason;
un-validated output is never rendered."""

from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Field:
    name: str
    type: str                    # 'str' | 'bool' | 'int' | 'float' | 'list'
    required: bool = True
    max_len: int = 2000          # str fields (source chars, pre-escape)
    on_oversize: str = 'clamp'   # 'clamp' (truncate) | 'reject'
    max_items: int = 20          # list fields (items are str)
    item_max_len: int = 500


@dataclass(frozen=True)
class Contract:
    task_id: str
    purpose: str                 # one line shown in the consent dialog
    system: str                  # FIXED instruction string — never data
    fields: tuple


@dataclass(frozen=True)
class AIRequest:
    """What a feature wants sent: the task (→ its contract) + the payload
    prompt. The prompt is the part that may contain financial data."""
    task_id: str
    prompt: str


class ContractViolation(Exception):
    """Structured rejection: .reason = {'field', 'rule', 'detail'}."""

    def __init__(self, field: str, rule: str, detail: str):
        self.reason = {'field': field, 'rule': rule, 'detail': detail}
        super().__init__(f"{field}: {rule} — {detail}")


# ── registry ─────────────────────────────────────────────────────────────────

PING = Contract(
    task_id='ping',
    purpose='Verify the AI connection with a fixed test message '
            '(contains no portfolio data).',
    system='You are a connection test endpoint. Reply with JSON only, '
           'no prose, no code fences.',
    fields=(Field('ok', 'bool'),
            Field('message', 'str', max_len=200)),
)

PING_PROMPT = ('Connection test. Reply with exactly this JSON and '
               'nothing else: {"ok": true, "message": "pong"}')

CONTRACTS = {c.task_id: c for c in (PING,)}


def get_contract(task_id: str) -> Contract:
    return CONTRACTS[task_id]


def build_ping_request() -> AIRequest:
    return AIRequest('ping', PING_PROMPT)


# ── validation ───────────────────────────────────────────────────────────────

_FENCE = re.compile(r'^\s*```[a-zA-Z0-9_-]*\s*\n(.*?)\n?\s*```\s*$',
                    re.DOTALL)


def strip_fence(raw: str) -> str:
    """Remove ONE wrapping code fence if the whole text is fenced."""
    m = _FENCE.match(raw or '')
    return m.group(1) if m else (raw or '')


def _clamp_str(value: str, f: Field, limit: int) -> str:
    if len(value) > limit:
        if f.on_oversize == 'reject':
            raise ContractViolation(
                f.name, 'oversize',
                f'{len(value)} chars exceeds max {limit}')
        value = value[:limit].rstrip() + '…'
    # escape AFTER clamping: the limit applies to source characters
    return html.escape(value, quote=True)


def _validate_value(value, f: Field):
    if f.type == 'bool':
        if not isinstance(value, bool):
            raise ContractViolation(
                f.name, 'wrong-type',
                f'expected bool, got {type(value).__name__}')
        return value
    if f.type in ('int', 'float'):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ContractViolation(
                f.name, 'wrong-type',
                f'expected {f.type}, got {type(value).__name__}')
        return int(value) if f.type == 'int' else float(value)
    if f.type == 'str':
        if not isinstance(value, str):
            raise ContractViolation(
                f.name, 'wrong-type',
                f'expected str, got {type(value).__name__}')
        return _clamp_str(value, f, f.max_len)
    if f.type == 'list':
        if not isinstance(value, list):
            raise ContractViolation(
                f.name, 'wrong-type',
                f'expected list, got {type(value).__name__}')
        if len(value) > f.max_items:
            if f.on_oversize == 'reject':
                raise ContractViolation(
                    f.name, 'oversize-list',
                    f'{len(value)} items exceeds max {f.max_items}')
            value = value[:f.max_items]
        out = []
        for item in value:
            if not isinstance(item, str):
                raise ContractViolation(
                    f.name, 'wrong-item-type',
                    f'list items must be str, got {type(item).__name__}')
            out.append(_clamp_str(item, f, f.item_max_len))
        return out
    raise ContractViolation(f.name, 'bad-contract',
                            f'unknown field type {f.type!r}')


def validate_response(raw: str, contract: Contract) -> dict:
    """Parse + validate + clamp. Returns ONLY the contract's fields, every
    string HTML-escaped. Raises ContractViolation on any deviation."""
    text = strip_fence(raw)
    try:
        data = json.loads(text)
    except ValueError as e:
        raise ContractViolation('<root>', 'not-json', str(e)[:200])
    if not isinstance(data, dict):
        raise ContractViolation('<root>', 'not-object',
                                f'expected object, got '
                                f'{type(data).__name__}')
    out = {}
    for f in contract.fields:
        if f.name not in data:
            if f.required:
                raise ContractViolation(f.name, 'missing',
                                        'required field absent')
            continue
        out[f.name] = _validate_value(data[f.name], f)
    return out  # unknown extra fields are dropped, never rendered
