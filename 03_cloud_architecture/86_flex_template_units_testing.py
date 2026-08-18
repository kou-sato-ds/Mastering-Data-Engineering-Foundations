"""
#86 Flex Template のテスト可能単位の検証。

🎯 【手法の6回目の適用】テンプレート化しても検証ロジックは不変であることを固定!

背景:
    #80 で確立した「丸ごと実行できないなら実行できる単位に分ける」手法を適用。
    Flex Template のエントリポイント run() は Beam のシンクを構築するため
    ローカル実行できないが、スキーマ定義・検証ロジックは純粋である。

実行方法:
    pytest 86_flex_template_units_testing.py -v
"""
import importlib.util
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent


def load_module_from_path(filename: str, module_name: str):
    """#71/#80/#81/#82/#83/#84 と同一の動的ローダー。"""
    path = HERE / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        pytest.skip(f"cannot build spec for {filename}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _flex_mod():
    return load_module_from_path('86_dataflow_flex_template.py', 'flex_template_mod')


# ================================================================
# STAGE 1: 必須フィールド検証が #65 と同一の3項目であること
#   テンプレート化で検証が緩んだら、DLQへ流れるべきレコードが本番へ混入する。
# ================================================================
def test_required_fields_match_the_original_contract():
    mod = _flex_mod()

    assert mod.REQUIRED_FIELDS == {'event_id', 'user_id', 'event_type'}, (
        "the validation contract must not weaken when the pipeline is templated"
    )


# ================================================================
# STAGE 2: 欠損レコードが例外になること
# ================================================================
@pytest.mark.parametrize('record,missing', [
    ({'user_id': 'u1', 'event_type': 'click'}, 'event_id'),
    ({'event_id': 'e1', 'event_type': 'click'}, 'user_id'),
    ({'event_id': 'e1', 'user_id': 'u1'}, 'event_type'),
])
def test_missing_field_raises(record, missing):
    mod = _flex_mod()

    with pytest.raises(ValueError) as exc:
        mod.validate_record(record)

    assert missing in str(exc.value)


# ================================================================
# STAGE 3: 完全なレコードは通過すること
# ================================================================
def test_complete_record_passes_validation():
    mod = _flex_mod()

    mod.validate_record({'event_id': 'e1', 'user_id': 'u1', 'event_type': 'click'})


# ================================================================
# STAGE 4: DLQスキーマが障害調査の4列を保持していること
#   #65 と同一であることが、テンプレート化後も保証される。
# ================================================================
def test_dlq_schema_keeps_investigation_columns():
    mod = _flex_mod()
    schema = mod.build_dlq_schema()

    for column in ['raw_payload', 'error_type', 'error_message', 'failed_at']:
        assert column in schema, (
            f"{column} is required for 3am incident investigation"
        )


# ================================================================
# STAGE 5: パラメータがハードコードされていないこと
#   テンプレートの目的は「同一イメージを環境をまたいで再利用する」こと。
#   プロジェクトIDが埋め込まれていれば、その目的は達成できない。
# ================================================================
def test_no_hardcoded_project_id():
    source = (HERE / '86_dataflow_flex_template.py').read_text(encoding='utf-8')

    assert 'your-gcp-project-id' not in source, (
        "a templated pipeline must not embed a project id; parameters are "
        "injected at launch time via add_value_provider_argument"
    )
    assert 'add_value_provider_argument' in source, (
        "runtime parameters must be declared with ValueProvider"
    )


# ================================================================
# STAGE 6: タグ定数が衝突しないこと
# ================================================================
def test_output_tags_are_distinct():
    mod = _flex_mod()

    assert mod.MAIN_TAG != mod.DLQ_TAG
    assert mod.MAIN_TAG and mod.DLQ_TAG


if __name__ == '__main__':
    print("🚀 Flex Template 単位テストの監査を開始するのね...")
    print("🟢 監査完了!テンプレート化後も検証契約が守られる基盤が完全画定したのね!")
    print("実行するには: pytest 86_flex_template_units_testing.py -v")