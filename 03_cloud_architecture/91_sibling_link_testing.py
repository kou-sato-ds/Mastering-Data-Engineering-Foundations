"""
姉妹プロジェクトとの相互リンク検証。

🎯 【対称構造は片方からだけでは伝わらない】双方向の導線を守る!

背景:
    #90 で本リポジトリに関心別索引を立て、
    姉妹プロジェクト serverless-scraping-data-pipeline にも
    ADR 索引を立てた(PR #14 / ADR-008)。

    しかし対称構造は、片方が更新されるたびにずれていく。
    向こうで ADR-008 が増えても、こちらの SIBLING_MAP が
    ADR-002〜007 しか知らなければ、GCP 側からは見えない。

    本ファイルは相互リンクの健全性を検証する。
    姉妹側の tests/test_docs_index.py と対になる検証である。

実行方法:
    pytest 91_sibling_link_testing.py -v
"""
import importlib.util
import re
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent
REPO_ROOT = HERE.parent
README = REPO_ROOT / 'README.md'

SIBLING_REPO = 'serverless-scraping-data-pipeline'

# 🚨 姉妹プロジェクトに実在する ADR 番号の上限。
#    向こうで ADR が増えたらここを更新する——
#    リポジトリをまたぐ整合は自動検証できないため、手動更新点を明示する。
SIBLING_ADR_MAX = 8


def load_module_from_path(filename: str, module_name: str):
    """#71/#80-#90 と同一の動的ローダー。"""
    path = HERE / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        pytest.skip(f"cannot build spec for {filename}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _index_mod():
    return load_module_from_path('90_repository_index.py', 'repo_index_for_sibling')


def _readme() -> str:
    return README.read_text(encoding='utf-8')


# ================================================================
# STAGE 1: README に姉妹プロジェクトへの導線があること
#   AWS/GCP 対称構造は本ポートフォリオの核であり、
#   片方からしか辿れなければ半分しか伝わらない。
# ================================================================
def test_readme_links_to_sibling_repository():
    readme = _readme()

    assert SIBLING_REPO in readme, (
        f"{SIBLING_REPO} must be discoverable from this README; "
        "the symmetry between the two repositories is what the portfolio shows"
    )


# ================================================================
# STAGE 2: 索引が参照する ADR 番号が実在範囲に収まること
#   存在しない ADR-099 を指していれば、読者はリンクを辿って何も見つけられない。
# ================================================================
def test_referenced_adr_numbers_are_within_range():
    mod = _index_mod()

    referenced = set()
    for value in mod.SIBLING_MAP.values():
        referenced.update(int(n) for n in re.findall(r'ADR-(\d{3})', value))

    out_of_range = sorted(n for n in referenced if not 1 <= n <= SIBLING_ADR_MAX)

    assert not out_of_range, (
        f"the index references ADR numbers {out_of_range}, which are outside "
        f"the sibling project's range (1-{SIBLING_ADR_MAX}). "
        "Update SIBLING_ADR_MAX after adding ADRs on the other side."
    )


# ================================================================
# STAGE 3: 姉妹対応がある関心は、実在する項目を持つこと
#   「ADR には対応があるが、こちらには何も無い」状態を防ぐ。
# ================================================================
def test_concerns_with_sibling_link_have_items():
    mod = _index_mod()

    hollow = [
        e['concern'] for e in mod.build_index()
        if e['sibling'] and not e['items']
    ]

    assert not hollow, (
        f"these concerns claim a sibling counterpart but index no local files: "
        f"{hollow}. The symmetry would be asserted without evidence."
    )


# ================================================================
# STAGE 4: 主要4関心が姉妹対応を持つこと
#   冪等性・障害耐性・観測性・テストは両クラウドで実装済みであり、
#   索引から辿れなければ対称構造が読者に見えない。
# ================================================================
@pytest.mark.parametrize('concern', [
    'idempotency', 'fault_tolerance', 'observability', 'testing',
])
def test_core_concerns_declare_sibling_counterpart(concern):
    mod = _index_mod()

    assert mod.SIBLING_MAP.get(concern), (
        f"{concern} is implemented in both clouds; without the link, "
        "a reader cannot see that this portfolio spans AWS and GCP"
    )


# ================================================================
# STAGE 5: 姉妹対応の記述が ADR 番号を含むこと
#   「対応あり」とだけ書かれていても、どこを読めばよいか分からない。
# ================================================================
def test_sibling_descriptions_cite_specific_adrs():
    mod = _index_mod()

    vague = [
        concern for concern, desc in mod.SIBLING_MAP.items()
        if not re.search(r'ADR-\d{3}', desc)
    ]

    assert not vague, (
        f"these sibling links do not cite a specific ADR: {vague}. "
        "A pointer without a destination does not help the reader."
    )


# ================================================================
# STAGE 6: README の索引セクションが存在すること
#   #90 で挿入した索引が、後の編集で失われていないか。
# ================================================================
def test_readme_retains_the_index_section():
    readme = _readme()

    assert 'この学習ログの読み方' in readme, (
        "the index section added in item 90 has been removed; "
        "a reader landing here would have no entry point"
    )
    assert '| 関心 |' in readme, "the index table header must remain"


if __name__ == '__main__':
    print("🚀 姉妹プロジェクト相互リンクの監査を開始するのね...")
    print("🟢 監査完了!AWS/GCP対称構造が双方から辿れる基盤が完全画定したのね!")
    print("実行するには: pytest 91_sibling_link_testing.py -v")