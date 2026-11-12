"""#150 スケジュール実行の取りこぼし検知の検証。11/12 0時〜4時、毎時、締め切り15分。"""
import importlib.util
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

HERE = Path(__file__).parent
START, END = datetime(2026, 11, 12, 0), datetime(2026, 11, 12, 4)
HOUR, DELAY = timedelta(hours=1), timedelta(minutes=15)


def _mod():
    spec = importlib.util.spec_from_file_location('missed_mod', HERE / '150_orchestration_missed_runs.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules['missed_mod'] = module
    spec.loader.exec_module(module)
    return module


def _h(hour, minute=1):
    return datetime(2026, 11, 12, hour, minute)


def _ok_runs(mod, hours=(0, 1, 2, 3)):
    return [mod.Run(_h(h, 0), _h(h), 'success') for h in hours]


def _audit(mod, runs):
    return mod.audit_runs(runs, START, END, HOUR, DELAY)


def test_expected_slots_are_half_open():
    mod = _mod()
    assert mod.expected_slots(START, END, HOUR) == [_h(h, 0) for h in range(4)]


def test_every_slot_once_and_on_time_is_ok():
    mod = _mod()
    assert _audit(mod, _ok_runs(mod)).ok


def test_skipped_hour_is_missing():
    """1回抜けても次の回は普通に動くので、誰も気づかない。"""
    mod = _mod()
    audit = _audit(mod, _ok_runs(mod, (0, 1, 3)))
    assert audit.missing == [_h(2, 0)]


def test_hour_with_only_failures_needs_a_rerun():
    mod = _mod()
    runs = _ok_runs(mod, (0, 1, 3)) + [mod.Run(_h(2, 0), _h(2), 'failed')]
    audit = _audit(mod, runs)
    assert audit.failed_only == [_h(2, 0)]
    assert audit.missing == []


def test_failure_followed_by_a_successful_retry_is_fine():
    mod = _mod()
    runs = _ok_runs(mod) + [mod.Run(_h(2, 0), _h(2, 0), 'failed')]
    assert _audit(mod, runs).ok


def test_two_successes_for_one_hour_are_duplicates():
    """冪等でない処理なら、その時間の数字が倍になる。"""
    mod = _mod()
    runs = _ok_runs(mod) + [mod.Run(_h(1, 0), _h(1, 5), 'success')]
    assert _audit(mod, runs).duplicate == [_h(1, 0)]


def test_success_after_the_deadline_is_late():
    mod = _mod()
    runs = _ok_runs(mod, (0, 1, 3)) + [mod.Run(_h(2, 0), _h(2, 40), 'success')]
    assert _audit(mod, runs).late == [_h(2, 0)]


def test_run_at_an_unexpected_time_is_unknown():
    mod = _mod()
    runs = _ok_runs(mod) + [mod.Run(_h(1, 30), _h(1, 30), 'success')]
    assert _audit(mod, runs).unknown == [_h(1, 30)]


def test_non_positive_interval_stops():
    mod = _mod()
    with pytest.raises(ValueError, match='interval'):
        mod.expected_slots(START, END, timedelta(0))


def test_this_file_passes_the_type_hint_ratchet():
    spec = importlib.util.spec_from_file_location('audit_for_150', HERE / '117_type_hint_audit.py')
    audit = importlib.util.module_from_spec(spec)
    sys.modules['audit_for_150'] = audit
    spec.loader.exec_module(audit)
    assert audit.audit_file(HERE / '150_orchestration_missed_runs.py')['missing'] == []
