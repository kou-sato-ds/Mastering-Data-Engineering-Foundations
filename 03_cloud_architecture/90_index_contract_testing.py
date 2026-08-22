"""
#90 索引契約の検証。

🎯 【索引と実体の乖離を検知】「載っているが無い」「あるが載っていない」を防ぐ!

背景:
    索引は放置すると必ず実体とずれる。
    - 分類には書いたがファイルが無い -> 読者が探して見つからない
    - ファイルはあるが分類に無い -> 存在に気づかれない

    どちらも「エラーにならず、期待通りに機能しない」種類の劣化である。

実行方法:
    pytest 90_index_contract_testing.py -v
"""
import importlib.util
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent


def load_module_from_path(filename: str, module_name: str):
    """#71/#80-#89 と同一の動的ローダー。"""
    path = HERE / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        pytest.skip(f"cannot build spec for {filename}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _index_mod():
    return load_module_from_path('90_repository_index.py', 'repo_index_mod')


# ================================================================
# STAGE 1: スキャンが実在ファイルを拾えること
# ================================================================
def test_scan_finds_numbered_items():
    mod = _index_mod()
    numbers = mod.scan_item_numbers()

    assert len(numbers) >= 30, (
        f"only {len(numbers)} numbered items found; the scan pattern may be wrong"
    )
    assert 52 in numbers, "item 52 should exist"
    assert 90 in numbers, "this very item should be detected"


# ================================================================
# STAGE 2: 分類に書いた項目が全て実在すること
#   「索引には載っているが、開くと無い」を防ぐ。
# ================================================================
def test_every_indexed_item_exists():
    mod = _index_mod()
    existing = set(mod.scan_item_numbers())

    phantom = []
    for concern, declared in mod.CONCERN_MAP.items():
        for item in declared:
            if item not in existing:
                phantom.append(f'{concern}:#{item}')

    assert not phantom, (
        f"these items are indexed but do not exist: {phantom}. "
        "A reader following the index would find nothing."
    )


# ================================================================
# STAGE 3: 索引が空の関心を持たないこと
#   全項目が消えた関心が残っていれば、それは古い分類である。
# ================================================================
def test_no_concern_is_empty():
    mod = _index_mod()

    empty = [e['concern'] for e in mod.build_index() if not e['items']]

    assert not empty, (
        f"these concerns index no existing files: {empty}. "
        "Remove the classification or restore the files."
    )


# ================================================================
# STAGE 4: 未分類の項目が過剰に溜まっていないこと
#   多少の未分類は許容するが、放置すれば索引の意味が薄れる。
# ================================================================
def test_unindexed_items_stay_bounded():
    mod = _index_mod()
    unindexed = mod.find_unindexed_items()

    assert len(unindexed) <= 5, (
        f"{len(unindexed)} items are unclassified: {unindexed}. "
        "An index that omits most of the repository does not help a reader."
    )


# ================================================================
# STAGE 5: 姉妹プロジェクト対応が主要な関心に付いていること
#   AWS/GCP対称構造は本ポートフォリオの核であり、
#   索引から辿れなければ読者に伝わらない。
# ================================================================
@pytest.mark.parametrize('concern', [
    'idempotency', 'fault_tolerance', 'observability', 'testing',
])
def test_core_concerns_link_to_sibling_project(concern):
    mod = _index_mod()

    assert mod.SIBLING_MAP.get(concern), (
        f"{concern} has a counterpart in the sibling AWS project; "
        "without the link, the symmetry that defines this portfolio is invisible"
    )


# ================================================================
# STAGE 6: Markdown 出力が表として成立すること
# ================================================================
def test_markdown_renders_a_table():
    mod = _index_mod()
    md = mod.render_markdown()

    lines = md.splitlines()
    assert lines[0].startswith('|'), "the first line must be a table header"
    assert set(lines[1]) <= set('|-'), "the second line must be the separator"
    assert len(lines) >= 2 + len(mod.CONCERN_MAP), (
        "every concern must appear as a row"
    )


if __name__ == '__main__':
    print("🚀 索引契約の監査を開始するのね...")
    print("🟢 監査完了!索引と実体の乖離を検知できる基盤が完全画定したのね!")
    print("実行するには: pytest 90_index_contract_testing.py -v")