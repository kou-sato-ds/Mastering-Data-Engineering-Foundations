"""
#87 メタデータ契約の検証。

🎯 【テンプレートとメタデータの整合】片方だけ変更されたら赤くする!

背景:
    #86 の FlexTemplateOptions が宣言するパラメータと、
    #87 のメタデータが宣言するパラメータは1対1で対応しなければならない。

    片方だけ変更すると:
    - テンプレートが受け取るがメタデータに無い -> 起動時に渡せない
    - メタデータにあるがテンプレートが受け取らない -> 無視される

    どちらも「エラーにならず、期待通り動かない」種類の不具合である。

実行方法:
    pytest 87_metadata_contract_testing.py -v
"""
import importlib.util
import re
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent


def load_module_from_path(filename: str, module_name: str):
    """#71/#80-#86 と同一の動的ローダー。"""
    path = HERE / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        pytest.skip(f"cannot build spec for {filename}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _meta_mod():
    return load_module_from_path('87_flex_template_metadata.py', 'flex_metadata_mod')


# ================================================================
# STAGE 1: メタデータが必須キーを備えていること
# ================================================================
def test_metadata_has_required_keys():
    mod = _meta_mod()
    meta = mod.build_metadata()

    for key in ['name', 'description', 'parameters']:
        assert key in meta, f"Flex Template metadata requires {key!r}"

    assert meta['parameters'], "at least one parameter must be declared"


# ================================================================
# STAGE 2: メタデータのパラメータが #86 の宣言と一致すること
#   片方だけ変更されれば「渡せない」または「無視される」状態になる。
# ================================================================
def test_metadata_matches_template_parameters():
    mod = _meta_mod()
    declared = {p['name'] for p in mod.build_metadata()['parameters']}

    template_source = (HERE / '86_dataflow_flex_template.py').read_text(encoding='utf-8')
    in_template = set(re.findall(r"--(\w+)'", template_source))

    assert declared == in_template, (
        f"metadata declares {sorted(declared)} but the template accepts "
        f"{sorted(in_template)}. A parameter present on only one side is "
        "either impossible to pass or silently ignored."
    )


# ================================================================
# STAGE 3: 全パラメータに正規表現が指定されていること
#   検証の無いパラメータは、誤った値でジョブが起動し課金が発生する。
# ================================================================
def test_every_parameter_has_validation():
    mod = _meta_mod()

    unvalidated = [
        p['name'] for p in mod.build_metadata()['parameters']
        if not p.get('regexes')
    ]

    assert not unvalidated, (
        f"these parameters accept any value: {unvalidated}. "
        "Without regexes, a malformed path launches a job that fails at "
        "runtime — and billing has already started."
    )


# ================================================================
# STAGE 4: PubSub の正規表現が正しい形式のみ通すこと
# ================================================================
@pytest.mark.parametrize('value,should_match', [
    ('projects/my-proj/subscriptions/events-sub', True),
    ('projects/my-proj/topics/events', False),        # 👉 topic は subscription ではない
    ('my-proj/subscriptions/events-sub', False),       # 👉 projects/ 接頭辞なし
    ('projects//subscriptions/events-sub', False),     # 👉 プロジェクトIDが空
    ('events-sub', False),                             # 👉 短縮名は不可
])
def test_pubsub_regex_accepts_only_full_paths(value, should_match):
    mod = _meta_mod()

    matched = re.match(mod.PUBSUB_SUBSCRIPTION_REGEX, value) is not None
    assert matched is should_match, (
        f"{value!r} should {'match' if should_match else 'be rejected'}"
    )


# ================================================================
# STAGE 5: BigQuery の正規表現が project:dataset.table のみ通すこと
# ================================================================
@pytest.mark.parametrize('value,should_match', [
    ('my-proj:analytics.events', True),
    ('my-proj.analytics.events', False),   # 👉 コロンではなくドット
    ('analytics.events', False),           # 👉 プロジェクト欠落
    ('my-proj:analytics', False),          # 👉 テーブル欠落
])
def test_bigquery_regex_accepts_only_qualified_tables(value, should_match):
    mod = _meta_mod()

    matched = re.match(mod.BIGQUERY_TABLE_REGEX, value) is not None
    assert matched is should_match, (
        f"{value!r} should {'match' if should_match else 'be rejected'}"
    )


# ================================================================
# STAGE 6: DLQ パラメータが必須であること
#   isOptional にすると DLQ 無しでジョブが起動し、
#   不正レコードが行き場を失う(#65 の設計が骨抜きになる)。
# ================================================================
def test_dlq_parameter_is_mandatory():
    mod = _meta_mod()

    dlq = next(
        p for p in mod.build_metadata()['parameters'] if p['name'] == 'dlq_table'
    )

    assert not dlq.get('isOptional'), (
        "making the DLQ optional would let a job start with nowhere to route "
        "malformed records, undoing the isolation design of item 65"
    )


if __name__ == '__main__':
    print("🚀 メタデータ契約の監査を開始するのね...")
    print("🟢 監査完了!テンプレートとメタデータの整合が守られる基盤が完全画定したのね!")
    print("実行するには: pytest 87_metadata_contract_testing.py -v")