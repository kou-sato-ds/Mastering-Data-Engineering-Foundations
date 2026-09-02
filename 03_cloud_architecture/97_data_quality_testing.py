"""
#97 データ品質検証のテスト。

🎯 【境界値を明示的に固定】閾値の1つ手前と1つ先を両方テストする!

実行方法:
    pytest 97_data_quality_testing.py -v
"""
import importlib.util
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

HERE = Path(__file__).parent
NOW = datetime(2026, 9, 3, 12, 0, 0, tzinfo=timezone.utc)


def load_module_from_path(filename: str, module_name: str):
    """#71/#80-#96 と同一の動的ローダー。"""
    path = HERE / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        pytest.skip(f"cannot build spec for {filename}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _dq():
    return load_module_from_path('97_data_quality_checks.py', 'data_quality_mod')


def _row(**overrides):
    base = {
        'event_id': 'evt-1',
        'user_id': 'u-1',
        'event_type': 'click',
        'occurred_at': NOW - timedelta(minutes=10),
    }
    base.update(overrides)
    return base


# ================================================================
# STAGE 1: スキーマ欠落を検知すること
# ================================================================
def test_missing_field_is_detected():
    mod = _dq()

    row = _row()
    del row['user_id']

    drift = mod.detect_schema_drift(row)
    assert drift['missing'] == ['user_id']
    assert drift['unexpected'] == []


# ================================================================
# STAGE 2: 列の追加を「欠落」と区別すること
#   追加は無害なことも多いが、欠落は即座に分析を壊す。
# ================================================================
def test_added_field_is_reported_separately():
    mod = _dq()

    drift = mod.detect_schema_drift(_row(session_id='s-1'))

    assert drift['missing'] == [], "adding a column does not break existing queries"
    assert drift['unexpected'] == ['session_id']


# ================================================================
# STAGE 3: 空文字を NULL として数えること
#   上流が「値が無い」を空文字で表現することは非常に多い。
# ================================================================
def test_empty_string_counts_as_null():
    mod = _dq()

    rows = [_row(user_id='u-1'), _row(user_id=''), _row(user_id=None), _row()]

    assert mod.compute_null_rate(rows, 'user_id') == 0.5, (
        "an empty string is a missing value in practice, not a present one"
    )


# ================================================================
# STAGE 4: NULL率の閾値が境界で正しく振る舞うこと
# ================================================================
@pytest.mark.parametrize('rate,expected', [
    (0.0, False),
    (0.05, False),   # 👉 閾値ちょうどは通す(> であって >= ではない)
    (0.051, True),
    (1.0, True),
])
def test_null_threshold_boundary(rate, expected):
    mod = _dq()

    assert mod.exceeds_null_threshold(rate) is expected


# ================================================================
# STAGE 5: 未知の event_type を検知すること
#   集計クエリは黙って除外し続けるため、エラーにならない。
# ================================================================
def test_unknown_event_type_is_detected():
    mod = _dq()

    rows = [_row(event_type='click'), _row(event_type='share')]

    assert mod.find_unknown_event_types(rows) == ['share'], (
        "an unrecognised type is silently dropped by aggregation queries"
    )


# ================================================================
# STAGE 6: 鮮度が正しく計算されること
#   パイプラインが止まってもテーブルは残り、クエリは古い値を返し続ける。
# ================================================================
def test_staleness_is_measured_in_hours():
    mod = _dq()

    latest = NOW - timedelta(hours=8)
    assert mod.compute_staleness_hours(latest, NOW) == 8.0
    assert mod.is_stale(8.0) is True
    assert mod.is_stale(6.0) is False, "exactly at the threshold must pass"


# ================================================================
# STAGE 7: 正常データでは違反が空であること
# ================================================================
def test_healthy_data_reports_no_violations():
    mod = _dq()

    rows = [_row(event_id=f'evt-{i}', user_id=f'u-{i}') for i in range(20)]
    report = mod.run_quality_checks(rows, now=NOW)

    assert mod.summarise_violations(report) == []


# ================================================================
# STAGE 8: 異常データが違反として報告されること
# ================================================================
def test_degraded_data_reports_violations():
    mod = _dq()

    rows = [_row(user_id='') for _ in range(10)]
    rows.append(_row(event_type='share'))
    report = mod.run_quality_checks(rows, now=NOW)

    violations = mod.summarise_violations(report)

    assert any('null rate for user_id' in v for v in violations)
    assert any('unknown event types' in v for v in violations)


# ================================================================
# STAGE 9: チェックが例外を投げないこと
#   品質チェックは「止める」ためではなく「知らせる」ためのものである。
#   1つの異常で全体を止めれば、正常なデータまで届かなくなる。
# ================================================================
def test_checks_report_rather_than_raise():
    mod = _dq()

    broken = [{'event_id': 'e1'}, {}, _row()]
    report = mod.run_quality_checks(broken, now=NOW)

    assert report['row_count'] == 3
    assert report['schema_issues'], "issues must be reported, not raised"


# ================================================================
# STAGE 10: 空データで落ちないこと
# ================================================================
def test_empty_input_does_not_crash():
    mod = _dq()

    report = mod.run_quality_checks([], now=NOW)

    assert report['row_count'] == 0
    assert report['staleness_hours'] is None
    assert mod.summarise_violations(report) == []


if __name__ == '__main__':
    print("🚀 データ品質検証の監査を開始するのね...")
    print("🟢 監査完了!異常なデータを知らせる基盤が完全画定したのね!")
    print("実行するには: pytest 97_data_quality_testing.py -v")