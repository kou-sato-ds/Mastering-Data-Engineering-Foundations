"""
#99 品質 DoFn の実行検証。

🎯 【DirectRunnerで実際に流す】純粋関数から実行可能なパイプラインへ!

実行方法:
    pytest 99_quality_dofn_testing.py -v
"""
import importlib.util
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import apache_beam as beam
from apache_beam.testing.test_pipeline import TestPipeline
from apache_beam.testing.util import assert_that, equal_to
import pytest

HERE = Path(__file__).parent
NOW = datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)


def load_module_from_path(filename: str, module_name: str):
    """#71/#80-#98 と同一の動的ローダー。"""
    path = HERE / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        pytest.skip(f"cannot build spec for {filename}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _dofn():
    return load_module_from_path('99_quality_dofn.py', 'quality_dofn_mod')


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
def test_valid_record_flows_to_main():
    mod = _dofn()
    valid = _row()

    with TestPipeline() as p:
        results = mod.build_quality_pipeline(p, [valid])
        assert_that(results[mod.MAIN_TAG], equal_to([valid]),
                    label='MainOutputCheck')
        assert_that(results[mod.DLQ_TAG], equal_to([]),
                    label='DlqShouldBeEmpty')


# ================================================================
# STAGE 2: 必須列欠落レコードが DLQ へ流れること
# ================================================================
def test_record_with_missing_field_flows_to_dlq():
    mod = _dofn()

    invalid = _row()
    del invalid['user_id']

    with TestPipeline() as p:
        results = mod.build_quality_pipeline(p, [invalid])

        assert_that(results[mod.MAIN_TAG], equal_to([]),
                    label='MainShouldBeEmpty')

        def check_dlq(records):
            assert len(records) == 1
            assert records[0]['error_type'] == 'DataQualityViolation'
            assert 'user_id' in records[0]['error_message']

        assert_that(results[mod.DLQ_TAG], check_dlq, label='DlqContentCheck')


# ================================================================
# STAGE 3: 混在バッチが独立して振り分けられること
#   1件の異常で正常レコードまで落とさないこと。
# ================================================================
def test_mixed_batch_splits_independently():
    mod = _dofn()

    valid = _row(event_id='evt-ok')
    invalid = _row(event_id='evt-ng')
    del invalid['event_type']

    with TestPipeline() as p:
        results = mod.build_quality_pipeline(p, [valid, invalid])

        assert_that(results[mod.MAIN_TAG], equal_to([valid]),
                    label='MainKeepsValid')

        def check_one(records):
            assert len(records) == 1, (
                'exactly one record should be quarantined; the valid row '
                'must not be affected'
            )

        assert_that(results[mod.DLQ_TAG], check_one, label='DlqCountCheck')


# ================================================================
# STAGE 4: 列の追加では DLQ へ落ちないこと
# ================================================================
def test_extra_column_stays_in_main():
    mod = _dofn()
    row = _row(session_id='s-1')

    with TestPipeline() as p:
        results = mod.build_quality_pipeline(p, [row])
        assert_that(results[mod.DLQ_TAG], equal_to([]),
                    label='ExtraColumnIsHarmless')


# ================================================================
# STAGE 5: タグ定数が衝突しないこと
# ================================================================
def test_output_tags_are_distinct():
    mod = _dofn()

    assert mod.MAIN_TAG != mod.DLQ_TAG
    assert mod.MAIN_TAG and mod.DLQ_TAG


# ================================================================
# STAGE 6: setup() でモジュールを1回だけ読むこと
#   process() 内で毎回 import すればレコード数分の I/O が発生する。
# ================================================================
def test_module_is_loaded_in_setup_not_process():
    source = (HERE / '99_quality_dofn.py').read_text(encoding='utf-8')

    setup_pos = source.index('def setup(self)')
    process_pos = source.index('def process(self, row)')
    load_pos = source.index('_load(\n', setup_pos)

    assert setup_pos < load_pos < process_pos, (
        'the module must be loaded in setup(); loading it inside process() '
        'would repeat file I/O for every record'
    )


if __name__ == '__main__':
    print("🚀 品質DoFnの監査を開始するのね...")
    print("🟢 監査完了!品質異常が実際に振り分けられる基盤が完全画定したのね!")
    print("実行するには: pytest 99_quality_dofn_testing.py -v")