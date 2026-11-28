"""#165 バックフィルを1日の上限の中で配る検証。"""
import importlib.util
import sys
from datetime import date
from pathlib import Path

import pytest

HERE = Path(__file__).parent


def _mod():
    spec = importlib.util.spec_from_file_location('quota_mod', HERE / '165_backfill_quota_schedule.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules['quota_mod'] = module
    spec.loader.exec_module(module)
    return module


def _d(day):
    return date(2026, 11, day)


def test_nothing_to_backfill():
    mod = _mod()
    assert mod.schedule_backfill({}, 100) == []


def test_everything_fits_in_one_day():
    mod = _mod()
    assert mod.schedule_backfill({_d(1): 30, _d(2): 30}, 100) == [[_d(2), _d(1)]]


def test_work_is_spread_over_days_newest_first():
    """使う人がまず見るのは最近の数字。"""
    mod = _mod()
    slots = {_d(d): 40 for d in range(1, 6)}
    assert mod.schedule_backfill(slots, 100) == [[_d(5), _d(4)], [_d(3), _d(2)], [_d(1)]]


def test_oldest_first_is_available():
    mod = _mod()
    slots = {_d(d): 40 for d in range(1, 4)}
    assert mod.schedule_backfill(slots, 100, newest_first=False) == [[_d(1), _d(2)], [_d(3)]]


def test_reserve_leaves_room_for_the_normal_daily_run():
    """入れ直しのせいで、今日の取り込みを止めない。"""
    mod = _mod()
    slots = {_d(1): 40, _d(2): 40}
    assert mod.schedule_backfill(slots, 100) == [[_d(2), _d(1)]]
    assert mod.schedule_backfill(slots, 100, reserve=30) == [[_d(2)], [_d(1)]]


def test_exactly_full_day_does_not_spill():
    mod = _mod()
    assert mod.schedule_backfill({_d(1): 60, _d(2): 40}, 100) == [[_d(2), _d(1)]]


def test_order_is_kept_even_if_a_later_day_would_fit():
    """後ろの小さい日を先に詰めない。どの日がいつ終わるかを約束できる。"""
    mod = _mod()
    slots = {_d(3): 70, _d(2): 70, _d(1): 10}
    assert mod.schedule_backfill(slots, 100) == [[_d(3)], [_d(2), _d(1)]]


def test_day_larger_than_the_daily_room_stops():
    mod = _mod()
    with pytest.raises(ValueError, match='split it'):
        mod.schedule_backfill({_d(1): 150}, 100)


def test_no_room_or_negative_cost_stops():
    mod = _mod()
    with pytest.raises(ValueError, match='no room'):
        mod.schedule_backfill({_d(1): 10}, 100, reserve=100)
    with pytest.raises(ValueError, match='negative'):
        mod.schedule_backfill({_d(1): -1}, 100)


def test_this_file_passes_the_type_hint_ratchet():
    spec = importlib.util.spec_from_file_location('audit_for_165', HERE / '117_type_hint_audit.py')
    audit = importlib.util.module_from_spec(spec)
    sys.modules['audit_for_165'] = audit
    spec.loader.exec_module(audit)
    assert audit.audit_file(HERE / '165_backfill_quota_schedule.py')['missing'] == []
