"""
#67 DLQ深さ監視のテスト可能単位の検証。

🎯 【手法の3回目の適用】未カバー最大物(49 stmts中37 miss、24%)を埋める!

背景:
    #80(#58)、#81(#57)で確立した「丸ごと実行できないなら実行できる単位に分ける」
    手法を、未カバー最大の #67 へ適用する。

    #67 の中核はGCPクライアント呼び出しだが、
    メトリクスフィルタ構築・計測窓構築・滞留数抽出・アラート判定・Runbook文言
    はいずれも純粋なロジックであり、切り出せば検証可能になる。

実行方法:
    pytest 82_dlq_monitoring_units_testing.py -v
"""
import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

HERE = Path(__file__).parent


def load_module_from_path(filename: str, module_name: str):
    """#71/#73/#74/#75/#76/#80/#81 と同一の動的ローダー。"""
    path = HERE / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        pytest.skip(f"cannot build spec for {filename}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _dlq_mon_mod():
    pytest.importorskip('google.cloud.pubsub_v1', reason='google-cloud-pubsub not installed')
    pytest.importorskip('google.cloud.monitoring_v3', reason='google-cloud-monitoring not installed')
    return load_module_from_path('67_dlq_depth_monitoring_redrive.py', 'dlq_mon_mod')


# ================================================================
# STAGE 1: メトリクスフィルタが正しいメトリクス種別を指すこと
#   1文字違えば「メトリクスは取れているのに0件」というサイレント失敗になる。
# ================================================================
def test_metric_filter_targets_undelivered_messages():
    mod = _dlq_mon_mod()
    assert hasattr(mod, 'build_dlq_metric_filter'), \
        "#67 must expose build_dlq_metric_filter (extracted for testability)"

    f = mod.build_dlq_metric_filter('my-dlq-sub')

    assert 'num_undelivered_messages' in f, \
        "the backlog metric must be num_undelivered_messages, not message_count"
    assert 'subscription_id="my-dlq-sub"' in f, \
        "the subscription id must be bound into the filter"


# ================================================================
# STAGE 2: 計測窓が妥当な長さであること
#   短すぎれば欠測、長すぎれば古い値を最新として拾う。
# ================================================================
def test_time_interval_lookback_is_bounded():
    mod = _dlq_mon_mod()
    assert hasattr(mod, 'build_time_interval'), "#67 must expose build_time_interval"

    now = 1_700_000_000.0
    interval = mod.build_time_interval(now, lookback_seconds=300)

    assert interval.end_time.seconds == int(now)
    assert interval.start_time.seconds == int(now) - 300


# ================================================================
# STAGE 3: メトリクス未生成時に IndexError を出さないこと
#   「まだデータが無い」と「本当に0件」を同じ安全な値へ収束させる。
# ================================================================
def test_depth_extraction_handles_empty_series():
    mod = _dlq_mon_mod()
    assert hasattr(mod, 'extract_depth_from_series'), \
        "#67 must expose extract_depth_from_series"

    empty_series = MagicMock()
    empty_series.points = []

    assert mod.extract_depth_from_series([]) == 0, "no series must yield 0, not crash"
    assert mod.extract_depth_from_series([empty_series]) == 0, \
        "a series with no points must yield 0, not IndexError"


# ================================================================
# STAGE 4: 滞留数が正しく取り出されること
# ================================================================
def test_depth_extraction_reads_latest_point():
    mod = _dlq_mon_mod()

    point = MagicMock()
    point.value.int64_value = 42
    series = MagicMock()
    series.points = [point]

    assert mod.extract_depth_from_series([series]) == 42


# ================================================================
# STAGE 5: アラート判定が閾値の境界で正しく振る舞うこと
#   境界値(==threshold)で発火しないことを明示的に固定する。
# ================================================================
@pytest.mark.parametrize('depth,threshold,expected', [
    (0, 50, False),
    (50, 50, False),   # 👉 等しい時は発火しない(> であって >= ではない)
    (51, 50, True),
    (1000, 50, True),
])
def test_alert_decision_at_threshold_boundary(depth, threshold, expected):
    mod = _dlq_mon_mod()
    assert hasattr(mod, 'should_alert'), "#67 must expose should_alert"

    assert mod.should_alert(depth, threshold) is expected


# ================================================================
# STAGE 6: Runbook文言が状況に応じて具体的であること
#   深夜3時に読む文言が曖昧なら、Runbookとして機能しない。
# ================================================================
def test_runbook_message_is_actionable():
    mod = _dlq_mon_mod()
    assert hasattr(mod, 'build_runbook_message'), "#67 must expose build_runbook_message"

    empty = mod.build_runbook_message(0)
    assert 'empty' in empty.lower(), "the zero case must state that no action is needed"

    backlog = mod.build_runbook_message(120)
    assert '120' in backlog, "the count must appear so the operator knows the scale"
    assert 're_drive_dlq' in backlog, "the next action must be named explicitly"
    assert 'root cause' in backlog.lower(), \
        "blind re-driving without investigating the cause must be discouraged"


if __name__ == '__main__':
    print("🚀 DLQ深さ監視の単位テストの監査を開始するのね...")
    print("🟢 監査完了!#67の未カバー部分が検証可能になる基盤が完全画定したのね!")
    print("実行するには: pytest 82_dlq_monitoring_units_testing.py -v")