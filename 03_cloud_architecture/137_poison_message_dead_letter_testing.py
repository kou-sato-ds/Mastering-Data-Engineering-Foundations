"""#137 毒メッセージの隔離の検証。"""
import importlib.util
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent


def _mod():
    spec = importlib.util.spec_from_file_location('poison_mod', HERE / '137_poison_message_dead_letter.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules['poison_mod'] = module
    spec.loader.exec_module(module)
    return module


def _handler(body):
    """kind に応じて成功・一時失敗・恒久失敗を起こす。"""
    if body.get('kind') == 'flaky':
        raise TimeoutError('slow')
    if body.get('kind') == 'broken':
        raise KeyError('required_field')


def _msgs(mod, *kinds):
    return [mod.Message(f'm{i}', {'kind': k}) for i, k in enumerate(kinds)]


def test_success_is_acked():
    mod = _mod()
    result = mod.process_batch(_msgs(mod, 'ok', 'ok'), _handler, {})
    assert result.acked == ['m0', 'm1']


def test_one_bad_message_does_not_block_the_rest():
    """1件の失敗で、正常な他のメッセージまで再配信しない。"""
    mod = _mod()
    result = mod.process_batch(_msgs(mod, 'ok', 'flaky', 'ok'), _handler, {})
    assert result.acked == ['m0', 'm2']
    assert result.retry == ['m1']


def test_transient_failure_goes_to_dlq_after_max_receives():
    mod = _mod()
    attempts: dict = {}
    batch = _msgs(mod, 'flaky')
    assert mod.process_batch(batch, _handler, attempts, max_receives=3).retry == ['m0']
    assert mod.process_batch(batch, _handler, attempts, max_receives=3).retry == ['m0']
    third = mod.process_batch(batch, _handler, attempts, max_receives=3)
    assert third.dead_lettered == {'m0': 'TimeoutError (gave up after 3 attempts)'}


def test_permanent_failure_goes_to_dlq_immediately():
    """何度やっても直らないものに、再試行の時間を使わない。"""
    mod = _mod()
    result = mod.process_batch(_msgs(mod, 'broken'), _handler, {})
    assert result.dead_lettered == {'m0': 'KeyError (permanent, attempt 1)'}
    assert result.retry == []


def test_recovered_message_is_acked_and_forgotten():
    """受信回数の記録は、終わったら消す。"""
    mod = _mod()
    attempts: dict = {}
    calls = {'n': 0}

    def once_slow(body):
        calls['n'] += 1
        if calls['n'] == 1:
            raise TimeoutError('once')

    batch = [mod.Message('m0', {})]
    mod.process_batch(batch, once_slow, attempts)
    assert attempts == {'m0': 1}
    assert mod.process_batch(batch, once_slow, attempts).acked == ['m0']
    assert attempts == {}


def test_dead_lettered_ids_are_removed_from_attempts():
    mod = _mod()
    attempts: dict = {}
    mod.process_batch(_msgs(mod, 'broken'), _handler, attempts)
    assert attempts == {}


def test_counts_add_up():
    mod = _mod()
    batch = _msgs(mod, 'ok', 'flaky', 'broken', 'ok')
    r = mod.process_batch(batch, _handler, {})
    assert len(r.acked) + len(r.retry) + len(r.dead_lettered) == len(batch)


def test_invalid_max_receives_stops():
    mod = _mod()
    with pytest.raises(ValueError, match='max_receives'):
        mod.process_batch([], _handler, {}, max_receives=0)


def test_this_file_passes_the_type_hint_ratchet():
    spec = importlib.util.spec_from_file_location('audit_for_137', HERE / '117_type_hint_audit.py')
    audit = importlib.util.module_from_spec(spec)
    sys.modules['audit_for_137'] = audit
    spec.loader.exec_module(audit)
    assert audit.audit_file(HERE / '137_poison_message_dead_letter.py')['missing'] == []
