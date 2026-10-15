"""
#122 レート制限の検証。時刻は数値で渡し、実際には待たない。
"""
import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

HERE = Path(__file__).parent
NOW = datetime(2026, 10, 15, 3, 0, 0, tzinfo=timezone.utc)


def _mod():
    path = HERE / '122_rate_limit.py'
    spec = importlib.util.spec_from_file_location('rate_mod', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules['rate_mod'] = module
    spec.loader.exec_module(module)
    return module


def test_burst_up_to_capacity_is_allowed():
    """短い集中は許す。それがトークンバケットの利点。"""
    mod = _mod()
    b = mod.TokenBucket(capacity=5, refill_per_sec=1)
    assert all(b.try_acquire(0.0) for _ in range(5))
    assert b.try_acquire(0.0) is False


def test_tokens_refill_over_time():
    mod = _mod()
    b = mod.TokenBucket(capacity=5, refill_per_sec=2)
    for _ in range(5):
        b.try_acquire(0.0)
    assert b.try_acquire(0.4) is False
    assert b.try_acquire(0.5) is True


def test_refill_never_exceeds_capacity():
    """長く休んでも、貯められるのは capacity まで。平均の速さを守る。"""
    mod = _mod()
    b = mod.TokenBucket(capacity=3, refill_per_sec=1)
    b.refill(1000.0)
    assert b.tokens == 3


def test_wait_time_tells_how_long_to_wait():
    mod = _mod()
    b = mod.TokenBucket(capacity=1, refill_per_sec=0.5)
    b.try_acquire(0.0)
    assert b.wait_time(0.0) == pytest.approx(2.0)
    assert b.wait_time(2.0) == 0.0


def test_invalid_bucket_is_rejected():
    mod = _mod()
    with pytest.raises(ValueError):
        mod.TokenBucket(capacity=0, refill_per_sec=1)


@pytest.mark.parametrize('value,expected', [
    ('120', 120.0),
    ('Thu, 15 Oct 2026 03:00:30 GMT', 30.0),
    ('Thu, 15 Oct 2026 02:59:00 GMT', 0.0),
])
def test_retry_after_formats(value, expected):
    """秒数と日時の2形式。過去の日時は「今すぐ」。"""
    assert _mod().parse_retry_after(value, NOW) == pytest.approx(expected)


@pytest.mark.parametrize('value', [None, '', 'soon', 'not a date'])
def test_unreadable_retry_after_is_none(value):
    """解釈できない値で待ち時間を決めない。呼び出し側の計算に任せる。"""
    assert _mod().parse_retry_after(value, NOW) is None


def test_server_instruction_beats_own_estimate():
    """相手の都合を一番よく知っているのは相手である。"""
    mod = _mod()
    assert mod.decide_wait(retry_after=20.0, own_estimate=2.0) == 20.0
    assert mod.decide_wait(retry_after=None, own_estimate=2.0) == 2.0


def test_extreme_values_are_capped():
    """相手が 99999 を返しても、1日待ったりはしない。"""
    mod = _mod()
    assert mod.decide_wait(retry_after=99999.0, own_estimate=1.0) == mod.MAX_WAIT_SECONDS


def test_this_file_passes_the_type_hint_ratchet():
    """#117 のラチェット: 新しいファイルは公開関数100%型付き。"""
    spec = importlib.util.spec_from_file_location('audit_for_122', HERE / '117_type_hint_audit.py')
    audit = importlib.util.module_from_spec(spec)
    sys.modules['audit_for_122'] = audit
    spec.loader.exec_module(audit)
    assert audit.audit_file(HERE / '122_rate_limit.py')['missing'] == []