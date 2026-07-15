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
    type: str                    # 'str' | 'bool' | 'int' | 'float' |
                                 # 'list' (of str) | 'object_list'
    required: bool = True
    max_len: int = 2000          # str fields (source chars, pre-escape)
    on_oversize: str = 'clamp'   # 'clamp' (truncate) | 'reject'
    max_items: int = 20          # list/object_list fields
    item_max_len: int = 500      # str items inside 'list'
    choices: tuple | None = None       # str fields: allowed values only
    item_fields: tuple | None = None   # object_list: schema per item


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

# ── session-8 task contracts ─────────────────────────────────────────────────
# The system strings are FIXED (never data). Each demands: use only what
# is in the payload, invent nothing, say so when data is missing.

_GROUND_RULES = (
    'Ground rules: base every statement ONLY on the JSON payload you '
    'receive — use no outside knowledge about any company or market. '
    'Use only numbers that literally appear in the payload; never '
    'invent or extrapolate figures, names, dates or events. Neutral, '
    'professional investment-report tone. State uncertainty explicitly '
    'and say when the data is too thin to conclude anything. Reply '
    'with JSON only — no prose around it, no code fences.')

NARRATIVE = Contract(
    task_id='narrative',
    purpose='Draft narrative report sections for this company from the '
            'figures shown in the payload.',
    system=(
        'You draft narrative sections for a private family investment '
        'report about one portfolio company. ' + _GROUND_RULES + ' '
        'Output schema: {"sections": [{"id": "position_narrative" or '
        '"quarter_review", "title": string (max 80 chars), '
        '"paragraphs": [up to 4 strings, each max 600 chars]}], '
        '"caveats": [up to 3 strings, each max 200 chars]}. Write '
        '"position_narrative" (how the position stands today) and, '
        'if the journal entries support it, "quarter_review" (recent '
        'developments). Put every data limitation into "caveats".'),
    fields=(
        Field('sections', 'object_list', max_items=2, item_fields=(
            Field('id', 'str',
                  choices=('position_narrative', 'quarter_review')),
            Field('title', 'str', max_len=80),
            Field('paragraphs', 'list', max_items=4, item_max_len=600),
        )),
        Field('caveats', 'list', required=False, max_items=3,
              item_max_len=200),
    ),
)

RISK_FLAGS = Contract(
    task_id='risk_flags',
    purpose='Point out risk flags visible in this company\'s figures.',
    system=(
        'You review one portfolio company of a private family '
        'investment portfolio for risk flags. ' + _GROUND_RULES + ' '
        'Output schema: {"flags": [up to 8 of {"severity": "low" or '
        '"medium" or "high", "title": string (max 80 chars), '
        '"rationale": string (max 400 chars), "based_on": [names of '
        'the payload fields the flag rests on]}]}. Only flag what the '
        'payload itself supports (e.g. stale valuation dates, '
        'concentration, estimate-based values, negative development). '
        'An empty "flags" list is a perfectly good answer.'),
    fields=(
        Field('flags', 'object_list', max_items=8, item_fields=(
            Field('severity', 'str', choices=('low', 'medium', 'high')),
            Field('title', 'str', max_len=80),
            Field('rationale', 'str', max_len=400),
            Field('based_on', 'list', max_items=12, item_max_len=80),
        )),
    ),
)

QA = Contract(
    task_id='qa',
    purpose='Answer one question about the portfolio data shown in the '
            'payload.',
    system=(
        'You answer questions about a private family investment '
        'portfolio. The payload contains the portfolio data (exactly '
        'what the owner\'s reports show), the conversation so far, and '
        'the question. ' + _GROUND_RULES + ' '
        'Output schema: {"answer_paragraphs": [up to 6 strings, each '
        'max 700 chars], "used_fields": [names of payload fields the '
        'answer rests on], "follow_up_suggestions": [up to 3 short '
        'questions the owner might ask next]}.'),
    fields=(
        Field('answer_paragraphs', 'list', max_items=6,
              item_max_len=700),
        Field('used_fields', 'list', required=False, max_items=24,
              item_max_len=80),
        Field('follow_up_suggestions', 'list', required=False,
              max_items=3, item_max_len=120),
    ),
)

CONTRACTS = {c.task_id: c for c in (PING, NARRATIVE, RISK_FLAGS, QA)}


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
        if f.choices is not None:
            if value not in f.choices:
                raise ContractViolation(
                    f.name, 'bad-choice',
                    f'{value!r} not in {f.choices}')
            return value                  # enum tokens are fixed and safe
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
    if f.type == 'object_list':
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
        for i, item in enumerate(value):
            if not isinstance(item, dict):
                raise ContractViolation(
                    f.name, 'wrong-item-type',
                    f'items must be objects, got {type(item).__name__}')
            obj = {}
            for sub in f.item_fields:
                if sub.name not in item:
                    if sub.required:
                        raise ContractViolation(
                            f'{f.name}[{i}].{sub.name}', 'missing',
                            'required field absent')
                    continue
                obj[sub.name] = _validate_value(item[sub.name], sub)
            out.append(obj)               # unknown item keys are dropped
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
