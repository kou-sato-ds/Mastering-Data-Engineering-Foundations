"""
#98 品質統合の検証。

🎯 【止めるか通すかの判断】1件の異常で全件を落とさないことを固定!

実行方法:
    pytest 98_quality_integration_testing.py -v
"""
import importlib.util
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

HERE = Path(__file__).parent
NOW = datetime(2026, 9, 4, 12, 0, 0, tzinfo=timezone.utc)


def load_module_from_path(filename: str, module_name: str):
    """#71/#80-#97 と同一の動的ローダー。"""
    path = HERE / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        pytest.skip(f"cannot build spec for {filename}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _integ():
    return load_module_from_path('98_quality_pipeline_integration.py', 'quality_integ_mod')


def _row(**overrides):
    base = {
        'event_id': 'evt-1',
        'user_id': 'u-1',
        'event_type': 'click',
        'occurred_at': NOW - timedelta(minutes=5),
    }
    base.update(overrides)
    return base


# ================================================================
# STAGE 1: 正常レコードが main へ流れること
# ================================================================
def test_valid_record_routes_to_main():
    mod = _integ()

    assert mod.classify_record(_row()) == 'main'


# ================================================================
# STAGE 2: 必須列欠落レコードが DLQ へ流れること
# ================================================================
def test_record_with_missing_field_routes_to_dlq():
    mod = _integ()

    row = _row()
    del row['user_id']

    assert mod.classify_record(row) == 'dlq'


# ================================================================
# STAGE 3: 列の追加だけでは DLQ へ落とさないこと
#   上流が列を増やすのは日常的であり、それで全件止めれば運用にならない。
# ================================================================
def test_extra_field_does_not_route_to_dlq():
    mod = _integ()

    assert mod.classify_record(_row(session_id='s-1')) == 'main', (
        "upstream adding a column must not stop the pipeline"
    )


# ================================================================
# STAGE 4: DLQ ペイロードが #65 と同じ4列を持つこと
#   品質起因であることを error_type で区別できること。
# ================================================================
def test_dlq_payload_keeps_investigation_columns():
    mod = _integ()

    row = _row()
    del row['event_type']
    payload = mod.build_dlq_payload(row, 'schema drift')

    for column in ['raw_payload', 'error_type', 'error_message', 'failed_at']:
        assert column in payload

    assert payload['error_type'] == 'DataQualityViolation', (
        "a parse failure and a quality violation need different responses; "
        "the type must distinguish them"
    )
    assert 'event_type' in payload['error_message']


# ================================================================
# STAGE 5: メトリクスが値そのものを送ること
#   閾値をコードに埋め込むと、変更のたびにデプロイが必要になる。
# ================================================================
def test_metrics_carry_raw_values_not_verdicts():
    mod = _integ()
    quality = mod.load_quality()

    rows = [_row(user_id='') for _ in range(4)] + [_row()]
    report = quality.run_quality_checks(rows, now=NOW)
    metrics = mod.build_metrics(report)

    names = {m['name'] for m in metrics}
    assert 'data_quality/null_rate' in names
    assert 'data_quality/row_count' in names

    null_metric = next(
        m for m in metrics
        if m['name'] == 'data_quality/null_rate'
        and m['labels'].get('field') == 'user_id'
    )
    assert isinstance(null_metric['value'], float), (
        "send the measurement, not a boolean verdict; thresholds belong "
        "in the monitoring layer where they can change without a deploy"
    )


# ================================================================
# STAGE 6: NULL 率の悪化ではバッチを止めないこと ← 本ファイルの核心
#   部分的にでも届けた方が良い場合が多い。
# ================================================================
def test_null_rate_degradation_does_not_halt_the_batch():
    mod = _integ()
    quality = mod.load_quality()

    rows = [_row(user_id='') for _ in range(10)]
    report = quality.run_quality_checks(rows, now=NOW)
    decision = mod.decide_batch_action(report)

    assert decision['action'] == 'continue', (
        "halting on a null-rate regression would withhold the rows that "
        "are still usable"
    )
    assert decision['violations'], "the issue must still be reported"


# ================================================================
# STAGE 7: 鮮度異常ではバッチを止めること
#   古いデータを処理し続けても、古い結果を配るだけである。
# ================================================================
def test_staleness_halts_the_batch():
    mod = _integ()
    quality = mod.load_quality()

    rows = [_row(occurred_at=NOW - timedelta(hours=12))]
    report = quality.run_quality_checks(rows, now=NOW)
    decision = mod.decide_batch_action(report)

    assert decision['action'] == 'halt', (
        "stale data means the upstream has stopped; continuing only "
        "redistributes outdated results"
    )


# ================================================================
# STAGE 8: 正常時もログを出すこと
#   無音が「正常」なのか「未実行」なのか区別できなくなる。
# ================================================================
def test_healthy_batch_still_emits_a_log():
    mod = _integ()
    quality = mod.load_quality()

    rows = [_row(event_id=f'e{i}', user_id=f'u{i}') for i in range(5)]
    report = quality.run_quality_checks(rows, now=NOW)
    decision = mod.decide_batch_action(report)
    log = mod.build_quality_log(report, decision)

    assert log['severity'] == 'INFO'
    assert log['row_count'] == 5
    assert log['violation_count'] == 0, (
        "silence cannot distinguish 'healthy' from 'never ran'"
    )


# ================================================================
# STAGE 9: 異常の重さがログ severity に反映されること
# ================================================================
@pytest.mark.parametrize('action,violations,expected', [
    ('continue', [], 'INFO'),
    ('continue', ['null rate for user_id: 40.0%'], 'WARNING'),
    ('halt', ['data is 12.0h stale'], 'ERROR'),
])
def test_log_severity_reflects_the_decision(action, violations, expected):
    mod = _integ()

    report = {'row_count': 1, 'null_rates': {}, 'staleness_hours': None,
              'unknown_event_types': [], 'schema_issues': []}
    decision = {'action': action, 'violations': violations, 'fatal': []}

    assert mod.build_quality_log(report, decision)['severity'] == expected


# ================================================================
# STAGE 10: 全ての異常種別に行き先が定義されていること
#   行き先の無い異常は、検知しても誰にも届かない。
# ================================================================
def test_every_issue_type_has_a_destination():
    mod = _integ()

    valid = {'dlq', 'metric', 'log'}
    undefined = [k for k, v in mod.ROUTING.items() if v not in valid]

    assert not undefined, (
        f"these issue types route nowhere valid: {undefined}. "
        "A detected anomaly with no destination reaches no one."
    )


if __name__ == '__main__':
    print("🚀 品質統合の監査を開始するのね...")
    print("🟢 監査完了!止めるか通すかの判断が固定される基盤が完全画定したのね!")
    print("実行するには: pytest 98_quality_integration_testing.py -v")