"""#138 冪等キーの検証。"""
import importlib.util
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent


def _mod():
    spec = importlib.util.spec_from_file_location('idem_mod', HERE / '138_idempotency_key_store.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules['idem_mod'] = module
    spec.loader.exec_module(module)
    return module


def _charge(calls):
    def action(payload):
        calls.append(payload)
        return {'charge_id': f'ch_{len(calls)}', 'amount': payload['amount']}
    return action


def test_first_request_runs():
    mod = _mod()
    calls = []
    result, replayed = mod.execute(mod.IdempotencyStore(), 'k1', {'amount': 500}, _charge(calls), now=0)
    assert result == {'charge_id': 'ch_1', 'amount': 500}
    assert replayed is False


def test_retry_returns_the_saved_response_without_running_again():
    """通信が切れた後の再送で、二重請求しない。"""
    mod = _mod()
    store, calls = mod.IdempotencyStore(), []
    mod.execute(store, 'k1', {'amount': 500}, _charge(calls), now=0)
    result, replayed = mod.execute(store, 'k1', {'amount': 500}, _charge(calls), now=10)
    assert replayed is True
    assert result['charge_id'] == 'ch_1'
    assert len(calls) == 1


def test_key_order_does_not_change_the_fingerprint():
    mod = _mod()
    assert mod.fingerprint({'a': 1, 'b': 2}) == mod.fingerprint({'b': 2, 'a': 1})


def test_same_key_with_different_payload_is_a_conflict():
    """黙って前の結果を返せば、500円の依頼に50円の結果を返すことになる。"""
    mod = _mod()
    store, calls = mod.IdempotencyStore(), []
    mod.execute(store, 'k1', {'amount': 500}, _charge(calls), now=0)
    with pytest.raises(mod.IdempotencyConflict):
        mod.execute(store, 'k1', {'amount': 50}, _charge(calls), now=1)


def test_duplicate_while_in_progress_is_rejected():
    """処理中に同じ依頼が来ても、同時に2回走らせない。"""
    mod = _mod()
    store = mod.IdempotencyStore()

    def slow_action(payload):
        mod.execute(store, 'k1', payload, lambda p: {}, now=1)
        return {}

    with pytest.raises(mod.RequestInProgress):
        mod.execute(store, 'k1', {'amount': 500}, slow_action, now=0)


def test_failed_request_can_be_retried():
    """失敗を記録すれば、再送しても永遠に失敗を返すことになる。"""
    mod = _mod()
    store, calls = mod.IdempotencyStore(), []

    def broken(payload):
        raise TimeoutError('gateway')

    with pytest.raises(TimeoutError):
        mod.execute(store, 'k1', {'amount': 500}, broken, now=0)
    result, replayed = mod.execute(store, 'k1', {'amount': 500}, _charge(calls), now=1)
    assert replayed is False and len(calls) == 1


def test_expired_record_is_forgotten():
    mod = _mod()
    store, calls = mod.IdempotencyStore(ttl_seconds=60), []
    mod.execute(store, 'k1', {'amount': 500}, _charge(calls), now=0)
    _, replayed = mod.execute(store, 'k1', {'amount': 500}, _charge(calls), now=60)
    assert replayed is False and len(calls) == 2


def test_different_keys_are_independent():
    mod = _mod()
    store, calls = mod.IdempotencyStore(), []
    mod.execute(store, 'k1', {'amount': 500}, _charge(calls), now=0)
    mod.execute(store, 'k2', {'amount': 500}, _charge(calls), now=0)
    assert len(calls) == 2


def test_missing_key_stops():
    mod = _mod()
    with pytest.raises(ValueError, match='required'):
        mod.execute(mod.IdempotencyStore(), '', {'amount': 1}, _charge([]), now=0)


def test_this_file_passes_the_type_hint_ratchet():
    spec = importlib.util.spec_from_file_location('audit_for_138', HERE / '117_type_hint_audit.py')
    audit = importlib.util.module_from_spec(spec)
    sys.modules['audit_for_138'] = audit
    spec.loader.exec_module(audit)
    assert audit.audit_file(HERE / '138_idempotency_key_store.py')['missing'] == []
