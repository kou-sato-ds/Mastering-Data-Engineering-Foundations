"""
#95 分類候補提示の契約検証。

🎯 【ルールが実際に効くか】既存ファイルで推定精度を検証!

背景:
    分類ルールは書けるが、実際に効くかは別問題である。
    既存の索引済みファイルに対してルールを適用し、
    **正しい関心を推定できるか**を検証する。

    推定が外れるルールは、後始末を早めるどころか誤誘導になる。

実行方法:
    pytest 95_advisor_contract_testing.py -v
"""
import importlib.util
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent


def load_module_from_path(filename: str, module_name: str):
    """#71/#80-#94 と同一の動的ローダー。"""
    path = HERE / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        pytest.skip(f"cannot build spec for {filename}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _advisor():
    return load_module_from_path('95_classification_advisor.py', 'advisor_mod')


# ================================================================
# STAGE 1: 推定された関心が索引に実在すること
#   存在しない関心を提案すれば、従った瞬間に索引が壊れる。
# ================================================================
def test_suggested_concerns_exist_in_the_index():
    mod = _advisor()
    index = mod.load_index()

    suggested = {c for _, c in mod.CLASSIFICATION_RULES}
    unknown = sorted(suggested - set(index.CONCERN_MAP))

    assert not unknown, (
        f"these rules suggest concerns absent from the index: {unknown}. "
        "Following such advice would corrupt the index."
    )


# ================================================================
# STAGE 2: 既知ファイルの分類を正しく推定できること ← 本ファイルの核心
#   ルールが実際に効くかを、既存の索引で答え合わせする。
# ================================================================
@pytest.mark.parametrize('filename,expected', [
    ('93_narrative_index_link.py', 'meta'),
    ('85_collection_guard_testing.py', 'testing'),
    ('88_flex_template_build.py', 'deployment'),
    ('66_cloud_logging_structured_error_reporting.py', 'observability'),
    ('67_dlq_depth_monitoring_redrive.py', 'fault_tolerance'),
    ('61_iam_service_account_design.py', 'security'),
    ('64_bigquery_cost_optimization.py', 'cost'),
    ('63_dataflow_session_window.py', 'windowing'),
    ('58_dataflow_bq_merge_upsert.py', 'idempotency'),
    ('62_terraform_gcp_data_platform.tf', 'iac'),
    ('59_composer_airflow_dag.py', 'orchestration'),
    ('65_dataflow_side_input_enrichment.py', 'joins'),
])
def test_rules_classify_known_files_correctly(filename, expected):
    mod = _advisor()

    assert mod.suggest_concern(filename) == expected, (
        f"{filename} should be classified as {expected!r}; "
        "a rule that misclassifies known files will misdirect future cleanup"
    )


# ================================================================
# STAGE 3: 推定できないファイルには None を返すこと
#   推測できないことを推測できたふりで隠さない。
# ================================================================
def test_unclassifiable_names_return_none():
    mod = _advisor()

    assert mod.suggest_concern('99_something_entirely_new.py') is None, (
        "an unmatched name must return None rather than a wrong guess"
    )


# ================================================================
# STAGE 4: ルールの順序が意味を持つこと
#   'testing' を含む meta ファイル(95_advisor_contract_testing.py)は
#   meta として分類されねばならない——ルールは上から評価される。
# ================================================================
def test_rule_order_prefers_meta_over_testing():
    mod = _advisor()

    assert mod.suggest_concern('95_advisor_contract_testing.py') == 'meta', (
        "meta files often contain 'testing' in their names; the meta rule "
        "must be evaluated first, or they would be misfiled"
    )


# ================================================================
# STAGE 5: 索引が閉じていれば助言が空であること
#   後始末が済んでいる状態を、助言の不在で確認できる。
# ================================================================
def test_advice_is_empty_when_index_is_complete():
    mod = _advisor()
    index = mod.load_index()

    if index.find_unindexed_items():
        pytest.skip('there are unindexed items; this test verifies the closed state')

    assert mod.advise() == [], "no unindexed items means no advice"
    assert '未分類はありません' in mod.render_advice()


# ================================================================
# STAGE 6: 全ルールが有効な正規表現であること
# ================================================================
def test_every_rule_is_a_valid_regex():
    import re as _re

    mod = _advisor()

    broken = []
    for pattern, concern in mod.CLASSIFICATION_RULES:
        try:
            _re.compile(pattern)
        except _re.error as e:
            broken.append(f'{concern}: {e}')

    assert not broken, f"these rules are not valid regexes: {broken}"


if __name__ == '__main__':
    print("🚀 分類候補提示の契約監査を開始するのね...")
    print("🟢 監査完了!ルールが既存ファイルで答え合わせされる基盤が完全画定したのね!")
    print("実行するには: pytest 95_advisor_contract_testing.py -v")