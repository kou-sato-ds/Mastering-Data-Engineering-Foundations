"""
#116 リトライ方針の検証。実際には眠らず、sleep を差し替えて待ち時間を記録する。
"""
import importlib.util
import random
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent


def _mod():
    path = HERE / '116_retry_backoff.py'
    spec = importlib.util.spec_from_file_location('retry_mod', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules['retry_mod'] = module
    spec.loader.exec_module(module)
    return module


class Flaky:
    """指定回数だけ失敗してから成功する呼び出し。"""

    def __init__(self, failures, error):
        self.failures = failures
        self.error = error
        self.calls = 0

    def __call__(self):
        self.calls += 1
        if self.calls <= self.failures:
            raise self.error
        return 'ok'


class HttpError(Exception):
    def __init__(self, status):
        self.status = status


def test_ceiling_doubles_and_stops_at_cap():
    mod = _mod()

    class Max:
        def uniform(self, a, b):
            return b

    ceilings = [mod.backoff_delay(n, base=1, cap=10, rng=Max()) for n in range(6)]
    assert ceilings == [1, 2, 4, 8, 10, 10]


def test_jitter_stays_within_bounds():
    mod = _mod()
    rng = random.Random(42)
    for n in range(8):
        d = mod.backoff_delay(n, base=1, cap=30, rng=rng)
        assert 0 <= d <= min(30, 2 ** n)


def test_jitter_spreads_clients_apart():
    """全員が同じ秒数待てば、全員が同時に再突撃して相手をまた倒す。"""
    mod = _mod()
    delays = {round(mod.backoff_delay(3, rng=random.Random(seed)), 3) for seed in range(20)}
    assert len(delays) > 10


def test_transient_failure_is_retried_until_success():
    mod = _mod()
    fn = Flaky(2, mod.TransientError('timeout'))
    out = mod.retry_call(fn, rng=random.Random(0))
    assert out['result'] == 'ok'
    assert fn.calls == 3


def test_permanent_failure_is_not_retried():
    """入力が不正なら、100回やっても同じ結果になる。"""
    mod = _mod()
    fn = Flaky(5, mod.PermanentError('bad input'))
    with pytest.raises(mod.PermanentError):
        mod.retry_call(fn)
    assert fn.calls == 1


def test_unknown_error_is_not_retried():
    mod = _mod()
    fn = Flaky(5, ValueError('unexpected'))
    with pytest.raises(ValueError):
        mod.retry_call(fn)
    assert fn.calls == 1


@pytest.mark.parametrize('status,expected', [(429, True), (503, True), (400, False), (403, False)])
def test_http_status_classification(status, expected):
    assert _mod().is_retryable(HttpError(status)) is expected


def test_gives_up_after_max_attempts():
    mod = _mod()
    fn = Flaky(10, mod.TransientError('down'))
    with pytest.raises(mod.TransientError):
        mod.retry_call(fn, max_attempts=4, rng=random.Random(0))
    assert fn.calls == 4


def test_deadline_stops_waiting():
    """締切を越えて待てば、成功しても結果を返せない。"""
    mod = _mod()
    fn = Flaky(10, mod.TransientError('down'))
    slept = []
    with pytest.raises(mod.TransientError):
        mod.retry_call(fn, max_attempts=10, base=10, cap=100, deadline=15,
                       sleep=slept.append, rng=random.Random(1))
    assert sum(slept) <= 15


def test_attempts_are_recorded_for_observability():
    mod = _mod()
    fn = Flaky(1, mod.TransientError('timeout'))
    out = mod.retry_call(fn, rng=random.Random(0))
    assert [a['ok'] for a in out['attempts']] == [False, True]