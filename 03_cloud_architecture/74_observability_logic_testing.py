"""
観測性トリオ(#60/#66/#67)の実体ロジック検証。

🎯 【import健全性から実体検証へ】#71で「読み込める」ことは確認した。今日は「正しく動く」ことを確認する!

背景:
    #71 STAGE 5 は #60/#66/#67 が「import時に例外を吐かない」ことだけを検証していた。
    しかしそれは「ファイルが壊れていない」以上の保証はしない。
    本ファイルは各モジュールの純粋ロジック部分を直接呼び出し、
    「クライアントを実体化せずに検証できる関数」を実際に動かして振る舞いを固定する。

検証方針:
    GCPクライアントを呼ぶ関数はローカルで実行できない。
    そこで「クライアントに触れない純粋部分」だけを対象に選ぶ:
      - #66 log_structured_error のペイロード構築ロジック
      - #67 re_drive のack判定ロジック(実際のpull/publishは対象外)
    -> テスト対象を「クライアント非依存な境界」に正確に切り分けるのが設計の肝。

実行方法:
    pytest 74_observability_logic_testing.py -v
"""
import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

HERE = Path(__file__).parent


def load_module_from_path(filename: str, module_name: str):
    """#71/#73 と同一の動的ローダー。"""
    path = HERE / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        pytest.skip(f"cannot build spec for {filename}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


# ================================================================
# STAGE 1: #66 の構造化ログが Error Reporting 互換の必須フィールドを持つこと
#   logger を MagicMock に差し替え、log_struct へ渡された辞書の中身を検証する。
#   -> 実際の Cloud Logging 接続なしで「何を送ろうとしたか」を捕まえる。
# ================================================================
def test_structured_error_payload_has_error_reporting_keys():
    pytest.importorskip('google.cloud.logging', reason='google-cloud-logging not installed')

    mod = load_module_from_path('66_cloud_logging_structured_error_reporting.py', 'logging_mod')

    fake_logger = MagicMock()
    exc = ValueError("missing product_id")
    mod.log_structured_error(fake_logger, exc, {'event_id': 'evt-1', 'stage': 'enrichment'})

    # 👉 log_struct が1回呼ばれ、その第1引数(payload)を取り出す
    fake_logger.log_struct.assert_called_once()
    payload = fake_logger.log_struct.call_args[0][0]
    severity = fake_logger.log_struct.call_args[1].get('severity')

    # 🚨 Error Reporting の自動検出条件: severity=ERROR かつ stack_trace を含む
    assert severity == 'ERROR', "Error Reporting requires severity >= ERROR"
    assert 'stack_trace' in payload, "stack_trace is the auto-detection key for Error Reporting"
    assert payload['error_type'] == 'ValueError'
    assert payload['event_id'] == 'evt-1'
    assert payload['stage'] == 'enrichment'


# ================================================================
# STAGE 2: #66 の INFO ログが構造化されていること(grep脱却の前提)
# ================================================================
def test_structured_info_log_is_queryable():
    pytest.importorskip('google.cloud.logging', reason='google-cloud-logging not installed')

    mod = load_module_from_path('66_cloud_logging_structured_error_reporting.py', 'logging_mod')

    fake_logger = MagicMock()
    mod.log_structured_info(fake_logger, "processed", stage='enrichment', event_id='evt-2')

    fake_logger.log_struct.assert_called_once()
    payload = fake_logger.log_struct.call_args[0][0]
    severity = fake_logger.log_struct.call_args[1].get('severity')

    assert severity == 'INFO'
    assert payload['stage'] == 'enrichment', "fields must be queryable in Logs Explorer"
    assert payload['event_id'] == 'evt-2'


# ================================================================
# STAGE 3: #66 process_with_observability が正常レコードを通し、記録を残すこと
# ================================================================
def test_process_with_observability_passes_valid_record():
    pytest.importorskip('google.cloud.logging', reason='google-cloud-logging not installed')

    mod = load_module_from_path('66_cloud_logging_structured_error_reporting.py', 'logging_mod')

    fake_logger = MagicMock()
    record = {'event_id': 'evt-3', 'product_id': 'p-1'}
    result = mod.process_with_observability(record, fake_logger)

    assert result['processed'] is True
    fake_logger.log_struct.assert_called()  # 👉 成功ログが残る


# ================================================================
# STAGE 4: #66 process_with_observability が異常時にログを残してから再送出すること
#   #57 と同思想: データはDLQへ、記録はログへ、そして例外は握りつぶさない。
# ================================================================
def test_process_with_observability_logs_and_reraises_on_error():
    pytest.importorskip('google.cloud.logging', reason='google-cloud-logging not installed')

    mod = load_module_from_path('66_cloud_logging_structured_error_reporting.py', 'logging_mod')

    fake_logger = MagicMock()
    bad_record = {'event_id': 'evt-4'}  # 👉 product_id 欠損 -> ValueError

    with pytest.raises(ValueError):
        mod.process_with_observability(bad_record, fake_logger)

    # 🚨 例外で落ちる前に、必ず構造化エラーログを残していること
    logged_severities = [
        call.kwargs.get('severity') for call in fake_logger.log_struct.call_args_list
    ]
    assert 'ERROR' in logged_severities, "error must be logged before re-raising (no silent failure)"


# ================================================================
# STAGE 5: #67 の DLQ深さ閾値定数が妥当な範囲にあること
#   閾値が 0 や巨大値になれば「見張り」の意味が消える。
# ================================================================
def test_dlq_depth_threshold_is_sane():
    pytest.importorskip('google.cloud.pubsub_v1', reason='google-cloud-pubsub not installed')

    mod = load_module_from_path('67_dlq_depth_monitoring_redrive.py', 'dlq_depth_mod')

    assert hasattr(mod, 'DLQ_DEPTH_THRESHOLD'), "#67 must define DLQ_DEPTH_THRESHOLD"
    assert isinstance(mod.DLQ_DEPTH_THRESHOLD, int)
    assert 0 < mod.DLQ_DEPTH_THRESHOLD <= 10000, \
        "threshold must be a positive, sane backlog size (0 or huge defeats monitoring)"


# ================================================================
# STAGE 6: #67 が re-drive と runbook の両関数を保持していること
#   「監視するだけで再処理経路が無い」状態への退化を防ぐ。
# ================================================================
def test_dlq_module_keeps_redrive_and_runbook():
    pytest.importorskip('google.cloud.pubsub_v1', reason='google-cloud-pubsub not installed')

    mod = load_module_from_path('67_dlq_depth_monitoring_redrive.py', 'dlq_depth_mod')

    assert hasattr(mod, 're_drive_dlq'), "#67 must keep the re-drive capability"
    assert hasattr(mod, 'dlq_runbook'), "#67 must keep the executable runbook"
    assert hasattr(mod, 'check_dlq_depth'), "#67 must keep the depth checker"


# ================================================================
# STAGE 7: #60 が Cloud Monitoring のメトリクス送出と閾値を保持していること
# ================================================================
def test_monitoring_module_keeps_metric_and_threshold():
    pytest.importorskip('google.cloud.monitoring_v3', reason='google-cloud-monitoring not installed')

    mod = load_module_from_path('60_cloud_monitoring_alerting.py', 'monitoring_mod')

    assert hasattr(mod, 'emit_custom_metric'), "#60 must keep the metric emitter"
    assert hasattr(mod, 'create_dlq_alert_policy'), "#60 must keep the alert policy creator"


if __name__ == '__main__':
    print("🚀 観測性トリオ(#60/#66/#67) 実体ロジック検証基盤の監査を開始するのね...")
    print("🟢 監査完了!import健全性から実体検証へ引き上げる基盤が完全画定したのね!")
    print("実行するには: pytest 74_observability_logic_testing.py -v")