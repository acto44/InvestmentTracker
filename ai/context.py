"""Context packs: what the AI is allowed to see, built FROM the report
models (sessions 5–6) with explicit per-field picks — the AI reads
exactly what a report shows, nothing else. No raw DB access, no document
contents, no document NAMES, no file paths. The pack is serialized to
deterministic JSON and that string IS the prompt — so the consent
preview shows every byte that would leave the machine; there are no
silent inclusions.

Pseudonymization (optional, default off): company/entity names are
replaced by "Company A"/"Entity 1" in the pack AND inside free-text
fields (thesis, journal, notes). The mapping lives only on the
Pseudonymizer instance for the response round-trip — it is never
persisted, logged, or sent."""

from __future__ import annotations

import html
import json
import re

# The one place the report models' documents section is named — to keep
# it OUT. Everything below builds packs by explicit key picks; these keys
# must never appear (tested against a company that has documents).
FORBIDDEN_KEYS = ('documents', 'filename', 'doc_type', 'path')


def _fmt(x):
    """Report models carry {'raw', 'fmt'} pairs; packs send the fmt
    string — the exact text a printed report shows."""
    return x['fmt'] if isinstance(x, dict) and 'fmt' in x else x


class Pseudonymizer:
    """In-memory only. add_*() registers a real name, apply() swaps real
    names for aliases inside a pack, restore_in() swaps aliases back
    inside a VALIDATED (already HTML-escaped) response — restored names
    are escaped on the way in."""

    def __init__(self):
        self._alias_by_name: dict[str, str] = {}
        self._n_companies = 0
        self._n_entities = 0

    @property
    def enabled_note(self) -> str:
        return ('Pseudonymization: ON — real company/entity names are '
                'replaced before sending; the name mapping stays in '
                'memory on this machine only.')

    def add_company(self, name: str) -> str:
        return self._add(name, 'company')

    def add_entity(self, name: str) -> str:
        return self._add(name, 'entity')

    def _add(self, name: str, kind: str) -> str:
        name = (name or '').strip()
        if not name:
            return ''
        if name not in self._alias_by_name:
            if kind == 'company':
                self._n_companies += 1
                n = self._n_companies
                letters = ''
                while n:
                    n, rem = divmod(n - 1, 26)
                    letters = chr(ord('A') + rem) + letters
                self._alias_by_name[name] = f'Company {letters}'
            else:
                self._n_entities += 1
                self._alias_by_name[name] = f'Entity {self._n_entities}'
        return self._alias_by_name[name]

    def apply(self, obj):
        """Recursively replace registered real names in every string
        (longest names first, so 'NovaTech AI Labs' wins over
        'NovaTech AI')."""
        if isinstance(obj, str):
            for name in sorted(self._alias_by_name,
                               key=len, reverse=True):
                obj = obj.replace(name, self._alias_by_name[name])
            return obj
        if isinstance(obj, list):
            return [self.apply(x) for x in obj]
        if isinstance(obj, dict):
            return {k: self.apply(v) for k, v in obj.items()}
        return obj

    def restore_in(self, data):
        """Swap aliases back inside a validated response. Validated
        strings are HTML-escaped, so restored names are escaped too."""
        if isinstance(data, str):
            for name, alias in self._alias_by_name.items():
                data = data.replace(alias, html.escape(name, quote=True))
            return data
        if isinstance(data, list):
            return [self.restore_in(x) for x in data]
        if isinstance(data, dict):
            return {k: self.restore_in(v) for k, v in data.items()}
        return data


def _to_prompt(pack: dict) -> str:
    """Deterministic serialization — the exact bytes shown in consent
    and sent to the provider."""
    return json.dumps(pack, indent=2, ensure_ascii=False)


# ── company pack (narrative + risk flags share it: same task data) ──────────

def build_company_pack(model: dict,
                       pseudo: Pseudonymizer | None = None) -> dict:
    """Explicit picks from build_company_report_model(). The documents
    section is deliberately never read."""
    meta, pos = model['meta'], model['position']
    if pseudo:
        pseudo.add_company(meta['company_name'])
        pseudo.add_entity(meta['entity'])
    pack = {
        'company': meta['company_name'],
        'entity': meta['entity'],
        'sector': meta['sector'],
        'country': meta['country'],
        'currency': meta['currency'],
        'figures_as_of': meta['as_of'],
        'description': meta['description'],
        'thesis': model['thesis']['text'],
        'position': {
            'invested': _fmt(pos['invested']),
            'realized': _fmt(pos['realized']),
            'current_value': _fmt(pos['current_value']),
            'value_is_estimate': pos['is_estimate'],
            'valuation_as_of': pos['val_as_of'],
            'valuation_source': pos['val_source'],
            'moic': _fmt(pos['moic']),
            'dpi': _fmt(pos['dpi']),
            'rvpi': _fmt(pos['rvpi']),
            'tvpi': _fmt(pos['tvpi']),
            'irr': _fmt(pos['irr']),
        },
        'valuation_history': [
            {'date': r['date'], 'value': _fmt(r['value']),
             'source': r['source'], 'change_pct': _fmt(r['delta_pct']),
             'note': r['note']}
            for r in model['valuations']['rows']],
        'cash_flows': [
            {'date': r['date'], 'type': r['type'],
             'amount': _fmt(r['signed']), 'note': r['note']}
            for r in model['ledger']['rows']],
        'ownership': {
            'shares_held': _fmt(model['ownership']['shares_held']),
            'ownership_pct': _fmt(model['ownership']['ownership_pct']),
            'basis': model['ownership']['basis'],
        },
        'journal': [
            {'date': u['date'], 'period': u.get('period_label') or '',
             'title': u.get('title') or '', 'text': u['text']}
            for u in model['thesis']['journal']],
    }
    return pseudo.apply(pack) if pseudo else pack


# ── portfolio pack (Q&A) ─────────────────────────────────────────────────────

def build_portfolio_pack(model: dict,
                         pseudo: Pseudonymizer | None = None) -> dict:
    """Explicit picks from build_portfolio_report_model()."""
    meta, o = model['meta'], model['overview']
    if pseudo:
        for row in (model['holdings']['active']
                    + model['holdings']['exited']):
            pseudo.add_company(row['name'])
            pseudo.add_entity(row.get('entity') or '')

    def _holding(r, exited=False):
        d = {'name': r['name'], 'entity': r['entity'],
             'invested': _fmt(r['invested']),
             'realized': _fmt(r['realized'])}
        if exited:
            d['multiple'] = _fmt(r['multiple'])
        else:
            d.update({'sector': r['sector'],
                      'current_value': _fmt(r['current']),
                      'value_is_estimate': r['is_estimate'],
                      'moic': _fmt(r['moic']),
                      'pct_of_nav': _fmt(r['pct_nav'])})
        d['irr'] = _fmt(r['irr'])
        return d

    pack = {
        'scope': meta['prepared_for'] or 'whole portfolio',
        'currency': meta['currency'],
        'figures_as_of': meta['as_of'],
        'overview': {
            'nav': _fmt(o['nav']), 'invested': _fmt(o['invested']),
            'realized': _fmt(o['realized']), 'moic': _fmt(o['moic']),
            'dpi': _fmt(o['dpi']), 'tvpi': _fmt(o['tvpi']),
            'pooled_irr': _fmt(o['irr']),
            'active_holdings': o['n_active'],
            'exited_or_closed': o['n_exited'],
            'positions_at_estimate': o['n_estimates'],
        },
        'allocation_by_sector': [
            {'sector': r['label'], 'value': _fmt(r['value']),
             'pct': _fmt(r['pct'])}
            for r in model['allocation']['by_sector']],
        'allocation_by_entity': (
            [{'entity': r['label'], 'value': _fmt(r['value']),
              'pct': _fmt(r['pct'])}
             for r in model['allocation']['by_entity']]
            if model['allocation']['by_entity'] else None),
        'active_holdings': [_holding(r) for r in
                            model['holdings']['active']],
        'exited_positions': [_holding(r, exited=True) for r in
                             model['holdings']['exited']],
        'notes': model['appendix']['aggregation_notes'],
    }
    return pseudo.apply(pack) if pseudo else pack


# ── prompts ──────────────────────────────────────────────────────────────────

def narrative_prompt(company_model: dict,
                     pseudo: Pseudonymizer | None = None) -> str:
    return _to_prompt(build_company_pack(company_model, pseudo))


def risk_prompt(company_model: dict,
                pseudo: Pseudonymizer | None = None) -> str:
    return _to_prompt(build_company_pack(company_model, pseudo))


def qa_prompt(pack: dict, question: str,
              previous_turns: list[dict],
              pseudo: Pseudonymizer | None = None) -> str:
    """pack is a company or portfolio pack (already pseudonymized if
    pseudo is set); the question and prior turns get the same
    treatment so the payload is consistent."""
    body = {'data': pack,
            'previous_turns': previous_turns,
            'question': question}
    if pseudo:
        body['previous_turns'] = pseudo.apply(previous_turns)
        body['question'] = pseudo.apply(question)
    return _to_prompt(body)


def assert_no_forbidden_keys(prompt: str):
    """Belt and braces used by tests: no documents-section key may ever
    appear in a payload."""
    for key in FORBIDDEN_KEYS:
        if re.search(rf'"{key}"\s*:', prompt):
            raise AssertionError(f'forbidden key {key!r} in AI payload')
