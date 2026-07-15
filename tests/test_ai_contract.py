"""Contract matrix: validate_response is the only door between raw model
output and the UI — parse, type-check, clamp, escape, reject."""

import pytest

from ai.contract import (CONTRACTS, PING, Contract, ContractViolation,
                         Field, build_ping_request, strip_fence,
                         validate_response)


def test_valid_payload_passes():
    out = validate_response('{"ok": true, "message": "pong"}', PING)
    assert out == {'ok': True, 'message': 'pong'}


def test_fence_wrapped_json_accepted():
    raw = '```json\n{"ok": true, "message": "pong"}\n```'
    out = validate_response(raw, PING)
    assert out['ok'] is True and out['message'] == 'pong'
    # bare fence too
    raw = '```\n{"ok": false, "message": "hi"}\n```'
    assert validate_response(raw, PING)['ok'] is False


def test_only_a_single_wrapping_fence_is_stripped():
    inner = 'code with ``` inside'
    assert strip_fence(f'```\n{inner}\n```') == inner
    # a fence in the middle of prose is NOT a wrapper
    assert strip_fence('text ```json``` more') == 'text ```json``` more'


def test_missing_required_field_rejected():
    with pytest.raises(ContractViolation) as e:
        validate_response('{"ok": true}', PING)
    assert e.value.reason['field'] == 'message'
    assert e.value.reason['rule'] == 'missing'


def test_wrong_type_rejected():
    with pytest.raises(ContractViolation) as e:
        validate_response('{"ok": "yes", "message": "hi"}', PING)
    assert e.value.reason == {'field': 'ok', 'rule': 'wrong-type',
                              'detail': 'expected bool, got str'}


def test_int_field_refuses_bool():
    c = Contract('t', 'p', 's', (Field('n', 'int'),))
    with pytest.raises(ContractViolation):
        validate_response('{"n": true}', c)
    assert validate_response('{"n": 3}', c) == {'n': 3}


def test_oversize_string_clamped_by_default():
    long = 'x' * 5000
    out = validate_response(
        f'{{"ok": true, "message": "{long}"}}', PING)
    assert out['message'].endswith('…')
    assert len(out['message']) <= PING.fields[1].max_len + 1


def test_oversize_string_rejected_when_contract_says_so():
    c = Contract('t', 'p', 's',
                 (Field('msg', 'str', max_len=10, on_oversize='reject'),))
    with pytest.raises(ContractViolation) as e:
        validate_response('{"msg": "12345678901"}', c)
    assert e.value.reason['rule'] == 'oversize'


def test_embedded_html_escaped():
    raw = '{"ok": true, "message": "<script>alert(1)</script>"}'
    out = validate_response(raw, PING)
    assert '<script>' not in out['message']
    assert '&lt;script&gt;' in out['message']


def test_list_clamping_and_item_types():
    c = Contract('t', 'p', 's',
                 (Field('items', 'list', max_items=2, item_max_len=5),))
    out = validate_response('{"items": ["aa", "bb", "cc"]}', c)
    assert out['items'] == ['aa', 'bb']            # clamped to max_items
    out = validate_response('{"items": ["<b>123456</b>"]}', c)
    assert out['items'][0].startswith('&lt;b&gt;')  # clamped THEN escaped
    with pytest.raises(ContractViolation) as e:
        validate_response('{"items": [1, 2]}', c)
    assert e.value.reason['rule'] == 'wrong-item-type'


def test_oversize_list_rejected_when_contract_says_so():
    c = Contract('t', 'p', 's',
                 (Field('items', 'list', max_items=1,
                        on_oversize='reject'),))
    with pytest.raises(ContractViolation) as e:
        validate_response('{"items": ["a", "b"]}', c)
    assert e.value.reason['rule'] == 'oversize-list'


def test_unknown_extra_fields_dropped():
    raw = ('{"ok": true, "message": "hi", '
           '"injected": "<img src=x onerror=alert(1)>"}')
    out = validate_response(raw, PING)
    assert set(out) == {'ok', 'message'}


def test_non_json_and_non_object_rejected():
    with pytest.raises(ContractViolation) as e:
        validate_response('sorry, I cannot do that', PING)
    assert e.value.reason['rule'] == 'not-json'
    with pytest.raises(ContractViolation) as e:
        validate_response('[1, 2, 3]', PING)
    assert e.value.reason['rule'] == 'not-object'


def test_ping_contract_registered_and_prompt_fixed():
    assert 'ping' in CONTRACTS
    req = build_ping_request()
    assert req.task_id == 'ping'
    # the ping payload is a FIXED string — it can never carry data
    assert 'pong' in req.prompt
