"""
#106 増分ロードの検証。遅延到着・同時刻・失敗時の前進を固定する。
"""
import importlib.util
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

HERE = Path(__file__).parent
T0 = datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)


def _mod():
    path = HERE / '106_incremental_load.py'
    spec = importlib.util.spec_from_file_location('incremental_mod', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules['incremental_mod'] = module
    spec.loader.exec_module(module)
    return module


def _row(rid, minutes, value='v'):
    return {'id': rid, 'updated_at': T0 + timedelta(minutes=minutes), 'value': value}


def test_initial_load_reads_everything():
    mod = _mod()
    rows = [_row('a', -100), _row('b', 0)]
    assert len(mod.select_new_rows(rows, None)) == 2


def test_late_arrival_within_lookback_is_picked_up():
    """前回値より10分古い時刻で後から届いた行を取りこぼさない。"""
    mod = _mod()
    rows = [_row('late', -10)]
    assert [r['id'] for r in mod.select_new_rows(rows, T0)] == ['late']


def test_rows_older_than_lookback_are_skipped():
    mod = _mod()
    rows = [_row('old', -60)]
    assert mod.select_new_rows(rows, T0) == []


def test_row_at_exact_watermark_is_not_lost():
    """> で切ると、前回と同一時刻の未処理行が永久に落ちる。"""
    mod = _mod()
    rows = [_row('tie', 0)]
    assert len(mod.select_new_rows(rows, T0, lookback=timedelta(0))) == 1


def test_duplicates_collapse_to_latest_version():
    mod = _mod()
    rows = [_row('a', 0, 'old'), _row('a', 5, 'new')]
    result = mod.dedupe_by_key(rows)
    assert len(result) == 1
    assert result[0]['value'] == 'new'


def test_watermark_never_moves_backwards():
    """lookback で古い行を読み直しても、基準は巻き戻らない。"""
    mod = _mod()
    rows = [_row('late', -10)]
    assert mod.next_watermark(rows, T0) == T0


def test_empty_batch_keeps_the_watermark():
    mod = _mod()
    assert mod.next_watermark([], T0) == T0


def test_failed_load_does_not_advance_the_watermark():
    """失敗後に進めれば、その区間は永久に欠落する。"""
    mod = _mod()
    state = {'watermark': T0}

    def boom(batch):
        raise RuntimeError('warehouse unavailable')

    with pytest.raises(RuntimeError):
        mod.run_increment(state, [_row('a', 30)], boom)

    assert state['watermark'] == T0


def test_successful_load_advances_the_watermark():
    mod = _mod()
    state = {'watermark': T0}
    loaded = []

    result = mod.run_increment(state, [_row('a', 30)], loaded.extend)

    assert result['loaded'] == 1
    assert state['watermark'] == T0 + timedelta(minutes=30)


def test_rerun_after_failure_is_idempotent():
    """失敗後の再実行と通常実行で、同じキー集合がロードされること。"""
    mod = _mod()
    rows = [_row('a', 30), _row('a', 31), _row('b', 32)]

    first = mod.dedupe_by_key(mod.select_new_rows(rows, T0))
    second = mod.dedupe_by_key(mod.select_new_rows(rows, T0))

    assert [r['id'] for r in first] == [r['id'] for r in second] == ['a', 'b']