"""
#119 タイムゾーンと日付境界の検証。
"""
import importlib.util
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

HERE = Path(__file__).parent


def _mod():
    path = HERE / '119_timezone_boundary.py'
    spec = importlib.util.spec_from_file_location('tz_mod', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules['tz_mod'] = module
    spec.loader.exec_module(module)
    return module


def test_naive_datetime_is_rejected():
    """UTC か JST か分からない時刻が、9時間ずれの元凶。"""
    with pytest.raises(ValueError, match='naive'):
        _mod().to_utc(datetime(2026, 10, 6, 8, 0))


def test_early_morning_jst_belongs_to_that_day():
    """日本時間 8:30 は、UTC ではまだ前日。営業日は日本時間で決める。"""
    mod = _mod()
    t = datetime(2026, 10, 6, 8, 30, tzinfo=mod.JST)
    assert t.astimezone(timezone.utc).date() == date(2026, 10, 5)
    assert mod.business_date(t) == date(2026, 10, 6)


def test_partition_uses_business_date_not_utc_date():
    mod = _mod()
    t = datetime(2026, 10, 5, 23, 30, tzinfo=timezone.utc)
    assert mod.partition_key(t) == 'dt=2026-10-06'


def test_day_bounds_are_shifted_by_nine_hours():
    mod = _mod()
    start, end = mod.day_bounds_utc(date(2026, 10, 6))
    assert start == datetime(2026, 10, 5, 15, 0, tzinfo=timezone.utc)
    assert end == datetime(2026, 10, 6, 15, 0, tzinfo=timezone.utc)


def test_last_fraction_of_a_second_is_included():
    """23:59:59 で切ると、最後の1秒の取引が消える。"""
    mod = _mod()
    t = datetime(2026, 10, 6, 23, 59, 59, 900000, tzinfo=mod.JST)
    assert mod.in_business_day(t, date(2026, 10, 6))


def test_midnight_belongs_to_the_next_day_only():
    """半開区間なので、0:00 ちょうどは翌日にだけ属する。"""
    mod = _mod()
    t = datetime(2026, 10, 7, 0, 0, tzinfo=mod.JST)
    assert not mod.in_business_day(t, date(2026, 10, 6))
    assert mod.in_business_day(t, date(2026, 10, 7))


def test_misplaced_rows_are_found():
    """過去に UTC の日付で切って保存したデータを見つける。"""
    mod = _mod()
    t = datetime(2026, 10, 6, 8, 30, tzinfo=mod.JST)
    rows = [
        {'id': 'ok', 'event_at': t, 'partition': 'dt=2026-10-06'},
        {'id': 'ng', 'event_at': t, 'partition': 'dt=2026-10-05'},
    ]
    result = mod.find_misplaced(rows)
    assert len(result) == 1 and result[0].startswith('ng')


def test_same_instant_in_different_zones_is_equal():
    mod = _mod()
    a = datetime(2026, 10, 6, 9, 0, tzinfo=mod.JST)
    b = datetime(2026, 10, 6, 0, 0, tzinfo=timezone.utc)
    assert mod.to_utc(a) == mod.to_utc(b)


def test_this_file_passes_the_type_hint_ratchet():
    """#117 のラチェット: 新しいファイルは公開関数100%型付き。"""
    spec = importlib.util.spec_from_file_location('audit_for_119', HERE / '117_type_hint_audit.py')
    audit = importlib.util.module_from_spec(spec)
    sys.modules['audit_for_119'] = audit
    spec.loader.exec_module(audit)
    assert audit.audit_file(HERE / '119_timezone_boundary.py')['missing'] == []