"""Session 8: narrative / risk-flag / Q&A capabilities on the session-7
rails. FakeProvider everywhere — the autouse network ban stays in force.
The load-bearing guarantees: whitelisted payloads (documents never leave),
pseudonym mapping never persisted, report export makes ZERO provider
calls, Q&A leaves no trace in the DB, and with the switch off none of
the feature UI exists."""

import json

import pytest

import ai
import models
from ai import context as aictx
from ai.contract import (NARRATIVE, QA, RISK_FLAGS, AIRequest,
                         ContractViolation, validate_response)
from ai.service import AIResult, send_request
from reporting.builder import (build_company_report_model,
                               build_portfolio_report_model)
from reporting.export import generate_company_report


class FakeProvider:
    name = 'fake'
    model_label = 'fake-1'
    destination = 'Nowhere (test fake)'

    def __init__(self, reply='{}'):
        self.calls = []
        self.reply = reply

    def is_available(self):
        return True, 'fake'

    def complete(self, prompt, *, system=None, max_tokens=1000,
                 timeout_s=120):
        self.calls.append({'prompt': prompt, 'system': system})
        return self.reply


@pytest.fixture
def ai_on(demo_db):
    ai.set_ai_enabled(True)
    return demo_db


@pytest.fixture
def yes_consent(monkeypatch):
    from ai import service
    monkeypatch.setattr(service.ConsentDialog, 'ask',
                        staticmethod(lambda *a, **k: True))


def _rich_company_id():
    """A demo company with valuations AND flows (for meaty packs)."""
    best, best_score = None, -1
    for c in models.get_all_companies():
        score = (len(models.get_valuations(c['id']))
                 + len(models.get_cashflows(c['id'])))
        if score > best_score:
            best, best_score = c, score
    return best['id']


VALID_NARRATIVE = json.dumps({
    'sections': [
        {'id': 'position_narrative', 'title': 'Position today',
         'paragraphs': ['First paragraph.', 'Second paragraph.']},
        {'id': 'quarter_review', 'title': 'Recent developments',
         'paragraphs': ['Third.']},
    ],
    'caveats': ['Valuation is an internal estimate.'],
})

VALID_FLAGS = json.dumps({
    'flags': [{'severity': 'high', 'title': 'Stale valuation',
               'rationale': 'Last valuation is old.',
               'based_on': ['valuation_history']}],
})

VALID_QA = json.dumps({
    'answer_paragraphs': ['The NAV is concentrated.'],
    'used_fields': ['overview', 'active_holdings'],
    'follow_up_suggestions': ['Which holding grew most?'],
})


# ── contract matrices ────────────────────────────────────────────────────────

def test_narrative_contract_valid():
    out = validate_response(VALID_NARRATIVE, NARRATIVE)
    assert out['sections'][0]['id'] == 'position_narrative'
    assert out['sections'][1]['paragraphs'] == ['Third.']
    assert out['caveats'] == ['Valuation is an internal estimate.']


def test_narrative_contract_rejections_and_clamps():
    with pytest.raises(ContractViolation) as e:
        validate_response('{"caveats": []}', NARRATIVE)
    assert e.value.reason['field'] == 'sections'

    with pytest.raises(ContractViolation) as e:
        validate_response(json.dumps({'sections': [
            {'id': 'sales_pitch', 'title': 't', 'paragraphs': ['p']}]}),
            NARRATIVE)
    assert e.value.reason['rule'] == 'bad-choice'

    with pytest.raises(ContractViolation) as e:
        validate_response(json.dumps({'sections': [
            {'id': 'quarter_review', 'paragraphs': ['p']}]}), NARRATIVE)
    assert e.value.reason == {'field': 'sections[0].title',
                              'rule': 'missing',
                              'detail': 'required field absent'}

    many = json.dumps({'sections': [
        {'id': 'position_narrative', 'title': f't{i}',
         'paragraphs': ['a', 'b', 'c', 'd', 'e', 'f']} for i in range(5)]})
    out = validate_response(many, NARRATIVE)
    assert len(out['sections']) == 2          # clamped
    assert len(out['sections'][0]['paragraphs']) == 4

    long_para = json.dumps({'sections': [
        {'id': 'position_narrative', 'title': 't',
         'paragraphs': ['x' * 3000]}]})
    out = validate_response(long_para, NARRATIVE)
    assert out['sections'][0]['paragraphs'][0].endswith('…')

    inj = json.dumps({'sections': [
        {'id': 'position_narrative',
         'title': '<img src=x onerror=alert(1)>',
         'paragraphs': ['<script>x</script>']}]})
    out = validate_response(inj, NARRATIVE)
    assert '<img' not in out['sections'][0]['title']
    assert '&lt;script&gt;' in out['sections'][0]['paragraphs'][0]

    with pytest.raises(ContractViolation):
        validate_response('the position looks fine to me', NARRATIVE)


def test_risk_contract_valid_and_empty():
    out = validate_response(VALID_FLAGS, RISK_FLAGS)
    assert out['flags'][0]['severity'] == 'high'
    out = validate_response('{"flags": []}', RISK_FLAGS)
    assert out['flags'] == []                  # empty list is valid


def test_risk_contract_rejections_and_clamps():
    with pytest.raises(ContractViolation) as e:
        validate_response(json.dumps({'flags': [
            {'severity': 'catastrophic', 'title': 't', 'rationale': 'r',
             'based_on': []}]}), RISK_FLAGS)
    assert e.value.reason['rule'] == 'bad-choice'

    many = json.dumps({'flags': [
        {'severity': 'low', 'title': f't{i}', 'rationale': 'r' * 900,
         'based_on': []} for i in range(12)]})
    out = validate_response(many, RISK_FLAGS)
    assert len(out['flags']) == 8              # clamped
    assert out['flags'][0]['rationale'].endswith('…')

    inj = json.dumps({'flags': [
        {'severity': 'low', 'title': '<b>x</b>', 'rationale': 'r',
         'based_on': ['<i>f</i>']}]})
    out = validate_response(inj, RISK_FLAGS)
    assert '&lt;b&gt;' in out['flags'][0]['title']
    assert '&lt;i&gt;' in out['flags'][0]['based_on'][0]

    with pytest.raises(ContractViolation):
        validate_response('```\nnot json\n```', RISK_FLAGS)


def test_qa_contract_matrix():
    out = validate_response(VALID_QA, QA)
    assert out['answer_paragraphs'] == ['The NAV is concentrated.']

    with pytest.raises(ContractViolation) as e:
        validate_response('{"used_fields": []}', QA)
    assert e.value.reason['field'] == 'answer_paragraphs'

    many = json.dumps({'answer_paragraphs': ['p' * 900] * 9,
                       'follow_up_suggestions': ['a', 'b', 'c', 'd']})
    out = validate_response(many, QA)
    assert len(out['answer_paragraphs']) == 6  # clamped
    assert out['answer_paragraphs'][0].endswith('…')
    assert len(out['follow_up_suggestions']) == 3

    inj = json.dumps({'answer_paragraphs': ['<a href=x>y</a>']})
    out = validate_response(inj, QA)
    assert '<a href' not in out['answer_paragraphs'][0]

    with pytest.raises(ContractViolation):
        validate_response('I would say roughly half.', QA)


# ── whitelists: documents never leave, not even names ────────────────────────

def test_no_document_names_or_paths_in_any_payload(demo_db):
    cid = _rich_company_id()
    conn = models.get_conn()
    conn.execute(
        "INSERT INTO documents (company_id, doc_type, original_filename, "
        "stored_filename, added_date) VALUES (?,?,?,?,?)",
        (cid, 'SHA', 'SECRET_SHA_Agreement.pdf',
         'SECRET_SHA_Agreement.pdf', '2024-01-01'))
    conn.commit()
    conn.close()

    model = build_company_report_model(cid)
    assert model['documents']['rows'], 'the REPORT model has documents'

    prompts = [aictx.narrative_prompt(model), aictx.risk_prompt(model)]
    pack = aictx.build_company_pack(model)
    prompts.append(aictx.qa_prompt(pack, 'How is it going?', []))
    p_model = build_portfolio_report_model()
    p_pack = aictx.build_portfolio_pack(p_model)
    prompts.append(aictx.qa_prompt(p_pack, 'How is the portfolio?', []))

    for prompt in prompts:
        aictx.assert_no_forbidden_keys(prompt)     # no documents keys
        assert 'SECRET_SHA_Agreement' not in prompt
        assert '.pdf' not in prompt
        assert 'investments.db' not in prompt      # no file paths either


# ── pseudonymization ─────────────────────────────────────────────────────────

def test_pseudonymized_payload_and_restored_answer(demo_db):
    cid = _rich_company_id()
    model = build_company_report_model(cid)
    name = model['meta']['company_name']
    entity = model['meta']['entity']

    pseudo = aictx.Pseudonymizer()
    prompt = aictx.narrative_prompt(model, pseudo)
    assert name not in prompt
    assert 'Company A' in prompt
    if entity:
        assert entity not in prompt
        assert 'Entity 1' in prompt

    reply = json.dumps({'sections': [
        {'id': 'position_narrative', 'title': 'About Company A',
         'paragraphs': ['Company A develops steadily.']}]})
    restored = pseudo.restore_in(validate_response(reply, NARRATIVE))
    assert name in restored['sections'][0]['paragraphs'][0]
    assert 'Company A' not in restored['sections'][0]['paragraphs'][0]


def test_pseudonym_mapping_never_persisted(ai_on, yes_consent,
                                           monkeypatch):
    models.set_setting(ai.AI_PSEUDONYMIZE_KEY, '1')
    cid = _rich_company_id()
    name = models.get_company(cid)['name']
    fake = FakeProvider(reply=json.dumps({'sections': [
        {'id': 'position_narrative', 'title': 'Company A today',
         'paragraphs': ['Company A holds steady.']}]}))
    monkeypatch.setattr(ai, 'get_provider', lambda n=None: fake)

    from ui.ai_company import generate_for_company
    result = generate_for_company(None, cid, 'narrative',
                                  use_thread=False)
    assert result.ok
    assert name not in fake.calls[0]['prompt']     # real name never sent

    row = models.get_ai_output(cid, 'narrative')
    assert name in row['response_json']            # stored WITH real name
    assert 'Company A' not in row['response_json']
    blob = open(ai_on, 'rb').read()
    assert b'Company A' not in blob                # no alias/mapping in DB


# ── persistence, provenance, zero-AI-calls exports ───────────────────────────

def _forbid_provider(monkeypatch):
    calls = {'n': 0}

    def boom(*a, **k):
        calls['n'] += 1
        raise AssertionError('provider fetched during a banned flow')

    monkeypatch.setattr(ai, 'get_provider', boom)
    return calls


def test_stored_narrative_in_report_with_zero_ai_calls(ai_on, tmp_path,
                                                       monkeypatch):
    cid = _rich_company_id()
    data = validate_response(VALID_NARRATIVE, NARRATIVE)
    models.save_ai_output(cid, 'narrative', 'fake', 'fake-1', 123,
                          json.dumps(data))
    calls = _forbid_provider(monkeypatch)

    written = generate_company_report(
        cid, formats=('html',), out_dir=str(tmp_path),
        include_ai=('narrative', 'risk_flags'))
    html = open(written[0], encoding='utf-8').read()
    assert 'AI narrative' in html
    assert 'fake · fake-1 · generated' in html      # provenance line
    assert 'Position today' in html
    assert 'verify before decisions' in html
    assert 'AI risk flags' not in html              # none stored → absent
    assert calls['n'] == 0                          # export never calls AI


def test_export_without_include_ai_shows_nothing(ai_on, tmp_path,
                                                 monkeypatch):
    cid = _rich_company_id()
    models.save_ai_output(cid, 'narrative', 'fake', 'fake-1', 123,
                          json.dumps(validate_response(VALID_NARRATIVE,
                                                       NARRATIVE)))
    calls = _forbid_provider(monkeypatch)
    written = generate_company_report(cid, formats=('html',),
                                      out_dir=str(tmp_path))
    html = open(written[0], encoding='utf-8').read()
    assert 'AI narrative' not in html               # stored ≠ included
    assert calls['n'] == 0


def test_deleting_ai_output_removes_section(ai_on, tmp_path):
    cid = _rich_company_id()
    models.save_ai_output(cid, 'narrative', 'fake', 'fake-1', 1,
                          json.dumps(validate_response(VALID_NARRATIVE,
                                                       NARRATIVE)))
    p1 = generate_company_report(cid, formats=('html',),
                                 out_dir=str(tmp_path / 'a'),
                                 include_ai=('narrative',))
    assert 'AI narrative' in open(p1[0], encoding='utf-8').read()
    models.delete_ai_output(cid, 'narrative')
    p2 = generate_company_report(cid, formats=('html',),
                                 out_dir=str(tmp_path / 'b'),
                                 include_ai=('narrative',))
    assert 'AI narrative' not in open(p2[0], encoding='utf-8').read()


def test_regeneration_replaces_not_accumulates(ai_on):
    cid = _rich_company_id()
    for i in range(3):
        models.save_ai_output(cid, 'narrative', 'fake', f'fake-{i}', 1,
                              json.dumps({'sections': []}))
    conn = models.get_conn()
    n = conn.execute("SELECT COUNT(*) FROM ai_outputs").fetchone()[0]
    conn.close()
    assert n == 1                                   # one CURRENT output
    assert models.get_ai_output(cid, 'narrative')['model'] == 'fake-2'


def test_no_ai_calls_at_app_start(qtbot, ai_on, monkeypatch):
    calls = _forbid_provider(monkeypatch)
    from ui.main_window import MainWindow
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    assert calls['n'] == 0                          # boot is AI-silent


# ── Q&A: session-only, no trace ──────────────────────────────────────────────

def test_qa_flow_leaves_no_trace_in_db(qtbot, ai_on, yes_consent,
                                       monkeypatch):
    fake = FakeProvider(reply=json.dumps({
        'answer_paragraphs': ['UNIQUE-ANSWER-MARKER-551'],
        'used_fields': ['overview'],
        'follow_up_suggestions': []}))
    monkeypatch.setattr(ai, 'get_provider', lambda n=None: fake)

    from ui.ai_qa import AskAIDialog
    dlg = AskAIDialog()
    qtbot.addWidget(dlg)
    dlg.question_edit.setPlainText('UNIQUE-QUESTION-MARKER-550')
    dlg._ask()
    qtbot.waitUntil(lambda: len(dlg._turns) == 1, timeout=5000)
    assert 'UNIQUE-QUESTION-MARKER-550' in fake.calls[0]['prompt']
    assert dlg._turns[0]['answer'] == 'UNIQUE-ANSWER-MARKER-551'

    # follow-up carries the session history in the payload…
    dlg.question_edit.setPlainText('And a follow-up?')
    dlg._ask()
    qtbot.waitUntil(lambda: len(dlg._turns) == 2, timeout=5000)
    assert 'UNIQUE-ANSWER-MARKER-551' in fake.calls[1]['prompt']
    dlg.close()

    # …but NOTHING lands in the database
    blob = open(ai_on, 'rb').read()
    assert b'UNIQUE-QUESTION-MARKER-550' not in blob
    assert b'UNIQUE-ANSWER-MARKER-551' not in blob
    rows = models.get_ai_activity()
    assert rows[0]['task_id'] == 'qa'               # logged: size+outcome
    conn = models.get_conn()
    n = conn.execute("SELECT COUNT(*) FROM ai_outputs").fetchone()[0]
    conn.close()
    assert n == 0                                   # qa is never persisted


def test_qa_task_cannot_be_persisted_by_schema(temp_db):
    import sqlite3
    conn = models.get_conn()
    with pytest.raises(sqlite3.IntegrityError):     # CHECK(task IN (...))
        conn.execute(
            "INSERT INTO ai_outputs (company_id, task, provider, model, "
            "created_at, request_chars, response_json) "
            "VALUES (NULL,'qa','p','m','t',1,'{}')")
    conn.close()


# ── failure honesty in the company block ─────────────────────────────────────

def test_company_block_shows_typed_error_with_retry(qtbot, ai_on):
    from PyQt6.QtWidgets import QLabel, QPushButton

    from ui.ai_company import CompanyAIBlock
    cid = _rich_company_id()
    block = CompanyAIBlock(cid, 'X')
    qtbot.addWidget(block)
    block._done('narrative', AIResult(
        'validation_failed', 'fake', 'fake-1', 'narrative',
        error="AI reply rejected by the narrative contract: "
              "sections: missing — required field absent"))
    labels = [l.text() for l in block.findChildren(QLabel)]
    assert any('rejected by the narrative contract' in t for t in labels)
    buttons = [b.text() for b in block.findChildren(QPushButton)]
    assert any(b.startswith('Retry') for b in buttons)


# ── the consent dialog knows about pseudonymization ──────────────────────────

def test_consent_note_reaches_the_dialog(ai_on, monkeypatch):
    from ai import service
    seen = {}

    def fake_ask(parent, provider, purpose, payload, note=None):
        seen['note'] = note
        return False

    monkeypatch.setattr(service.ConsentDialog, 'ask',
                        staticmethod(fake_ask))
    send_request(AIRequest('qa', 'x'), FakeProvider(), use_thread=False,
                 consent_note='PSEUDONYMIZATION NOTE')
    assert seen['note'] == 'PSEUDONYMIZATION NOTE'


# ── switch off ⇒ none of the feature UI exists ───────────────────────────────

def test_switch_off_means_no_feature_ui(qtbot, demo_db):
    assert ai.is_ai_enabled() is False
    from ui.ai_company import CompanyAIBlock
    from ui.main_window import MainWindow
    from ui.report_dialog import ReportDialog

    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    assert window._ai_action is None                # no Ask-AI action
    cid = _rich_company_id()
    window.tree.select_company(cid)
    assert window.findChildren(CompanyAIBlock) == []

    dlg = ReportDialog(None, company_id=cid)
    qtbot.addWidget(dlg)
    assert dlg._ai_boxes == {}                      # no AI checkboxes


def test_switch_on_means_feature_ui_exists(qtbot, ai_on):
    from ui.ai_company import CompanyAIBlock
    from ui.main_window import MainWindow
    from ui.report_dialog import ReportDialog

    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    assert window._ai_action is not None
    assert 'Ask AI' in window._ai_action.text()
    cid = _rich_company_id()
    window.tree.select_company(cid)
    assert window.findChildren(CompanyAIBlock)

    dlg = ReportDialog(None, company_id=cid)
    qtbot.addWidget(dlg)
    assert set(dlg._ai_boxes) == {'narrative', 'risk_flags'}
