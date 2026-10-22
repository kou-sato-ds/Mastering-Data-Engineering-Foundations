"""
#129 バックフィルの分割実行の検証。日付は数値で組み立てる。
"""
import importlib.util
import sys
from datetime import date
from pathlib import Path

import pytest

HERE = Path(__file__).parent


def _mod():
    path = HERE / '129_backfill_chunk_runner.py'
    spec = importlib.util.spec_from_file_location('backfill_runner_mod', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules['backfill_runner_mod'] = module
    spec.loader.exec_module(module)
    return module


def _ten_days(mod):
    """1月1日〜1月11日(半開)を3日ずつ → 4つの塊。"""
    return mod.chunk_range(date(2026, 1, 1), date(2026, 1, 11), days=3)


def test_chunks_cover_the_range_without_gaps_or_overlaps():
    """半開区間: 前の塊の終わり = 次の塊の始まり。"""
    mod = _mod()
    chunks = _ten_days(mod)
    assert chunks[0][0] == date(2026, 1, 1)
    assert chunks[-1][1] == date(2026, 1, 11)
    for (_, prev_end), (next_start, _) in zip(chunks, chunks[1:]):
        assert prev_end == next_start


def test_last_chunk_may_be_shorter():
    mod = _mod()
    chunks = _ten_days(mod)
    assert len(chunks) == 4
    assert chunks[-1] == (date(2026, 1, 10), date(2026, 1, 11))


@pytest.mark.parametrize('start, end, days', [
    (date(2026, 1, 5), date(2026, 1, 5), 1),
    (date(2026, 1, 1), date(2026, 1, 5), 0),
])
def test_invalid_range_is_rejected(start, end, days):
    mod = _mod()
    with pytest.raises(ValueError):
        mod.chunk_range(start, end, days)


def test_completed_chunks_are_skipped_on_resume():
    """300日目で落ちても、次回は残りだけをやる。"""
    mod = _mod()
    chunks = _ten_days(mod)
    completed = {mod.chunk_id(chunks[0]), mod.chunk_id(chunks[1])}
    calls = []
    report = mod.run_backfill(chunks, lambda s, e: calls.append(s), completed)
    assert calls == [date(2026, 1, 7), date(2026, 1, 10)]
    assert len(report.skipped) == 2
    assert report.ok


def test_rerun_after_success_does_nothing():
    """何度実行しても、終わった塊は二度と流さない(冪等)。"""
    mod = _mod()
    chunks = _ten_days(mod)
    completed: set = set()
    mod.run_backfill(chunks, lambda s, e: None, completed)
    calls = []
    report = mod.run_backfill(chunks, lambda s, e: calls.append(s), completed)
    assert calls == []
    assert len(report.skipped) == 4


def test_single_failure_does_not_stop_the_rest():
    mod = _mod()
    chunks = _ten_days(mod)

    def run(start, end):
        if start == date(2026, 1, 4):
            raise TimeoutError('slow upstream')

    report = mod.run_backfill(chunks, run, set())
    assert report.failed == {'2026-01-04_2026-01-07': 'TimeoutError'}
    assert len(report.done) == 3
    assert not report.ok


def test_consecutive_failures_stop_the_run():
    """上流が落ちているなら、残りを叩かない。"""
    mod = _mod()
    chunks = mod.chunk_range(date(2026, 1, 1), date(2026, 1, 11), days=1)
    calls = []

    def down(start, end):
        calls.append(start)
        raise ConnectionError('upstream down')

    report = mod.run_backfill(chunks, down, set(), max_consecutive_failures=3)
    assert len(calls) == 3
    assert report.stopped_early
    assert len(report.not_attempted) == 7


def test_a_success_resets_the_failure_streak():
    """散発的な失敗では止めない。止めるのは「連続」のときだけ。"""
    mod = _mod()
    chunks = mod.chunk_range(date(2026, 1, 1), date(2026, 1, 7), days=1)

    def flaky(start, end):
        if start.day % 2 == 1:
            raise TimeoutError('flaky')

    report = mod.run_backfill(chunks, flaky, set(), max_consecutive_failures=2)
    assert not report.stopped_early
    assert len(report.failed) == 3
    assert len(report.done) == 3


def test_failed_chunk_is_retried_on_the_next_run():
    """失敗した塊は完了にしない。次回の実行で自然に再挑戦される。"""
    mod = _mod()
    chunks = _ten_days(mod)
    completed: set = set()
    attempts = {'n': 0}

    def first_time_fails(start, end):
        if start == date(2026, 1, 4):
            attempts['n'] += 1
            if attempts['n'] == 1:
                raise TimeoutError('once')

    assert not mod.run_backfill(chunks, first_time_fails, completed).ok
    second = mod.run_backfill(chunks, first_time_fails, completed)
    assert second.done == ['2026-01-04_2026-01-07']
    assert second.ok


def test_newest_first_fills_recent_data_first():
    mod = _mod()
    chunks = _ten_days(mod)
    calls = []
    mod.run_backfill(chunks, lambda s, e: calls.append(s), set(), newest_first=True)
    assert calls[0] == date(2026, 1, 10)
    assert calls[-1] == date(2026, 1, 1)


def test_report_counts_add_up():
    mod = _mod()
    chunks = mod.chunk_range(date(2026, 1, 1), date(2026, 1, 11), days=1)
    completed = {mod.chunk_id(chunks[0])}

    def down(start, end):
        raise ConnectionError('down')

    r = mod.run_backfill(chunks, down, completed, max_consecutive_failures=2)
    assert len(r.done) + len(r.skipped) + len(r.failed) + len(r.not_attempted) == r.total


def test_this_file_passes_the_type_hint_ratchet():
    """#117 のラチェット: 新しいファイルは公開関数100%型付き。"""
    spec = importlib.util.spec_from_file_location('audit_for_129', HERE / '117_type_hint_audit.py')
    audit = importlib.util.module_from_spec(spec)
    sys.modules['audit_for_129'] = audit
    spec.loader.exec_module(audit)
    assert audit.audit_file(HERE / '129_backfill_chunk_runner.py')['missing'] == []