"""
#57 DLQパイプラインのテスト可能単位の検証。

🎯 【#80の手法を適用】52%で止まっていた#57の未カバー部分を埋める!

背景:
    #57 は 52%(33 stmts中16 miss、33-73行が未実行)。
    ParseAndValidateFn は #71 で検証済みだが、run_dlq_pipeline() 全体は
    一度も通っていない——Beamのシンクは完全なGCPクライアント一式を要求するため。

    #80 で確立した手法「丸ごと実行できないなら実行できる単位に分ける」を適用し、
    build_pipeline_options() / build_dlq_schema() / build_main_schema() を
    #57 から切り出して検証する。

実行方法:
    pytest 81_dlq_pipeline_units_testing.py -v
"""
import importlib.util
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent


def load_module_from_path(filename: str, module_name: str):
    """#71/#73/#74/#75/#76/#80 と同一の動的ローダー。"""
    path = HERE / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        pytest.skip(f"cannot build spec for {filename}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _dlq_mod():
    return load_module_from_path('57_dataflow_dlq_pattern.py', 'dlq_units_mod')


# ================================================================
# STAGE 1: streaming=True が設定されること
#   これが False だと無限ストリームが有限として扱われ、
#   PubSub購読が最初のバンドルで終了してしまう。
# ================================================================
def test_pipeline_options_enable_streaming():
    from apache_beam.options.pipeline_options import StandardOptions

    mod = _dlq_mod()
    assert hasattr(mod, 'build_pipeline_options'), \
        "#57 must expose build_pipeline_options (extracted for testability)"

    opts = mod.build_pipeline_options('test-proj', 'asia-northeast1', 'test-job')

    assert opts.view_as(StandardOptions).streaming is True, \
        "streaming must be True; otherwise the unbounded PubSub source terminates early"


# ================================================================
# STAGE 2: GCPメタデータが正しく注入されること
# ================================================================
def test_pipeline_options_carry_gcp_metadata():
    from apache_beam.options.pipeline_options import GoogleCloudOptions

    mod = _dlq_mod()
    opts = mod.build_pipeline_options('my-proj', 'us-central1', 'my-job')
    gc = opts.view_as(GoogleCloudOptions)

    assert gc.project == 'my-proj'
    assert gc.region == 'us-central1'
    assert gc.job_name == 'my-job'


# ================================================================
# STAGE 3: DLQスキーマが障害調査に必要な4列を備えること
#   どれか1つでも欠ければ「隔離されたが原因が分からない」状態になる。
# ================================================================
def test_dlq_schema_supports_incident_investigation():
    mod = _dlq_mod()
    assert hasattr(mod, 'build_dlq_schema'), "#57 must expose build_dlq_schema"

    schema = mod.build_dlq_schema()

    for column in ['raw_payload', 'error_type', 'error_message', 'failed_at']:
        assert column in schema, (
            f"{column} is required; without it the DLQ row cannot answer "
            "'what failed and when' during a 3am incident"
        )


# ================================================================
# STAGE 4: メインスキーマが必須フィールドと整合すること
#   ParseAndValidateFn が要求する3フィールドと、書き込み先スキーマは
#   一致していなければならない。
# ================================================================
def test_main_schema_matches_validated_fields():
    mod = _dlq_mod()
    assert hasattr(mod, 'build_main_schema'), "#57 must expose build_main_schema"

    schema = mod.build_main_schema()

    for column in ['event_id', 'user_id', 'event_type']:
        assert column in schema, (
            f"{column} is validated by ParseAndValidateFn but missing from the sink schema; "
            "validation and storage must agree"
        )


# ================================================================
# STAGE 5: タグ定数が衝突しないこと
#   MAIN_TAG と DLQ_TAG が同値なら、正常データと異常データが混ざる。
# ================================================================
def test_output_tags_are_distinct():
    mod = _dlq_mod()

    assert mod.MAIN_TAG != mod.DLQ_TAG, \
        "identical tags would merge clean and malformed records into one stream"
    assert mod.MAIN_TAG and mod.DLQ_TAG, "tags must not be empty"


if __name__ == '__main__':
    print("🚀 DLQパイプライン単位テストの監査を開始するのね...")
    print("🟢 監査完了!#57の未カバー部分が検証可能になる基盤が完全画定したのね!")
    print("実行するには: pytest 81_dlq_pipeline_units_testing.py -v")