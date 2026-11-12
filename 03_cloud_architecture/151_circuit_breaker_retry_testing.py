"""#151 サーキットブレーカーの検証。3回連続失敗で開き、10秒後に1回だけ試す。"""
import importlib.util
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent


def _mod():
    spec = importlib.util.spec_from_file_location('breaker_mod', HERE / '151_circuit_breaker_retry.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules['breaker_mod'] = module
    spec.loader.exec_module(module)
    return module


def _breaker(mod):
    return mod.CircuitBreaker(failure_threshold=3, reset_timeout=10)


def _down():
    raise ConnectionError('down')


def _fail(mod, b, times, now=0.0):
    for _ in range(times):
        with pytest.raises(ConnectionError):
            b.call(_down, now)


def test_closed_circuit_passes_calls():
    mod = _mod()
    assert _breaker(mod).call(lambda: 'ok', 0) == 'ok'


def test_consecutive_failures_open_the_circuit():
    mod = _mod()
    b = _breaker(mod)
    _fail(mod, b, 3)
    assert b.state == 'open'


def test_a_success_resets_the_count():
    """止めるのは「連続」のときだけ。"""
    mod = _mod()
    b = _breaker(mod)
    _fail(mod, b, 2)
    b.call(lambda: 'ok', 0)
    _fail(mod, b, 2)
    assert b.state == 'closed'


def test_open_circuit_rejects_without_calling():
    """落ちている相手を呼び続けない。タイムアウトまで待たされない。"""
    mod = _mod()
    b = _breaker(mod)
    _fail(mod, b, 3)
    calls = []
    with pytest.raises(mod.CircuitOpenError):
        b.call(lambda: calls.append(1), 5)
    assert calls == []


def test_after_the_timeout_one_trial_is_allowed():
    mod = _mod()
    b = _breaker(mod)
    _fail(mod, b, 3, now=0)
    assert b.allow(10) is True
    assert b.state == 'half_open'


def test_only_one_trial_at_a_time():
    """復旧しかけた相手に、試しの呼び出しを殺到させない。"""
    mod = _mod()
    b = _breaker(mod)
    _fail(mod, b, 3, now=0)
    assert b.allow(10) is True
    assert b.allow(10) is False


def test_successful_trial_closes_the_circuit():
    mod = _mod()
    b = _breaker(mod)
    _fail(mod, b, 3, now=0)
    assert b.call(lambda: 'back', 10) == 'back'
    assert b.state == 'closed' and b.failures == 0


def test_failed_trial_reopens_and_restarts_the_timer():
    mod = _mod()
    b = _breaker(mod)
    _fail(mod, b, 3, now=0)
    _fail(mod, b, 1, now=10)
    assert b.state == 'open'
    assert b.allow(15) is False
    assert b.allow(20) is True


def test_invalid_settings_stop():
    mod = _mod()
    with pytest.raises(ValueError):
        mod.CircuitBreaker(failure_threshold=0)
    with pytest.raises(ValueError):
        mod.CircuitBreaker(reset_timeout=0)


def test_this_file_passes_the_type_hint_ratchet():
    spec = importlib.util.spec_from_file_location('audit_for_151', HERE / '117_type_hint_audit.py')
    audit = importlib.util.module_from_spec(spec)
    sys.modules['audit_for_151'] = audit
    spec.loader.exec_module(audit)
    assert audit.audit_file(HERE / '151_circuit_breaker_retry.py')['missing'] == []
