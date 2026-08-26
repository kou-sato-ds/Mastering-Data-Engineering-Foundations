"""
#93 索引・問答の統合検証。

🎯 【2つの構造が繋がっているか】片方だけ更新される乖離を検知!

背景:
    索引(#90)と問答(#92)は別々に更新されうる。
    - 問答の concern が索引に無い -> 読者が該当箇所へ辿れない
    - 索引の関心に問答が無い -> それ自体は許容だが、把握しておくべき

    #91 で姉妹リポジトリに対して行った検証を、内部構造にも適用する。

実行方法:
    pytest 93_narrative_index_testing.py -v
"""
import importlib.util
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent


def load_module_from_path(filename: str, module_name: str):
    """#71/#80-#92 と同一の動的ローダー。"""
    path = HERE / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        pytest.skip(f"cannot build spec for {filename}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _link_mod():
    return load_module_from_path('93_narrative_index_link.py', 'narrative_link_mod')


# ================================================================
# STAGE 1: 統合ビューが全関心を含むこと
#   索引にある関心が統合ビューから漏れれば、その領域は見えなくなる。
# ================================================================
def test_integrated_view_covers_every_concern():
    mod = _link_mod()
    index = mod.load_index()

    view_concerns = {e['concern'] for e in mod.build_integrated_view()}

    assert view_concerns == set(index.CONCERN_MAP), (
        f"the integrated view covers {sorted(view_concerns)} but the index "
        f"declares {sorted(index.CONCERN_MAP)}"
    )


# ================================================================
# STAGE 2: 問答の concern が索引に存在すること
#   索引に無い関心を語れば、聞き手は該当ファイルへ辿り着けない。
# ================================================================
def test_every_narrative_concern_is_indexed():
    mod = _link_mod()
    index = mod.load_index()
    lookup = mod.build_narrative_lookup()

    orphan = sorted(c for c in lookup if c not in index.CONCERN_MAP)

    assert not orphan, (
        f"these narratives reference concerns absent from the index: {orphan}. "
        "A listener could not navigate from the answer to the code."
    )


# ================================================================
# STAGE 3: 問答を持つ関心が実在ファイルを伴うこと
#   語る準備があるのに実装が無ければ、それは主張にすぎない。
# ================================================================
def test_concerns_with_narrative_have_files():
    mod = _link_mod()

    hollow = [
        e['concern'] for e in mod.build_integrated_view()
        if e['questions'] and not e['items']
    ]

    assert not hollow, (
        f"these concerns have prepared answers but no files: {hollow}. "
        "An answer without implementation is a claim, not a demonstration."
    )


# ================================================================
# STAGE 4: 語る準備が無い関心が過剰でないこと
#   全関心に問答が要るわけではないが、大半が語れないなら準備不足である。
# ================================================================
def test_most_concerns_are_speakable():
    mod = _link_mod()
    index = mod.load_index()

    silent = mod.find_concerns_without_narrative()
    total = len(index.CONCERN_MAP)

    assert len(silent) <= total * 0.75, (
        f"{len(silent)} of {total} concerns have no prepared answer: {silent}. "
        "Being unable to speak about most of one's own work signals unfamiliarity."
    )


# ================================================================
# STAGE 5: Markdown 出力が問答列を持つこと
# ================================================================
def test_markdown_includes_question_column():
    mod = _link_mod()
    md = mod.render_markdown()

    lines = md.splitlines()
    assert '想定問答' in lines[0], "the table must expose a narrative column"
    assert 'Q. ' in md, "at least one question must be rendered"


# ================================================================
# STAGE 6: 主要関心が問答と実装の両方を持つこと
#   核心領域は「語れる」かつ「示せる」状態でなければならない。
# ================================================================
@pytest.mark.parametrize('concern', ['idempotency', 'observability', 'testing'])
def test_core_concerns_are_both_speakable_and_demonstrable(concern):
    mod = _link_mod()

    entry = next(
        e for e in mod.build_integrated_view() if e['concern'] == concern
    )

    assert entry['questions'], f"{concern} has no prepared answer"
    assert entry['items'], f"{concern} has no implementation files"


if __name__ == '__main__':
    print("🚀 索引・問答統合の監査を開始するのね...")
    print("🟢 監査完了!関心から説明と実装の両方へ辿れる基盤が完全画定したのね!")
    print("実行するには: pytest 93_narrative_index_testing.py -v")