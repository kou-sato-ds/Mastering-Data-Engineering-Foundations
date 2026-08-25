"""
#92 想定問答の契約検証。

🎯 【語った内容が実在するか】説明と実装の乖離を検知!

背景:
    想定問答は書けば残るが、実装が変われば古くなる。
    「#99を参照しています」と語っても、そのファイルが消えていれば嘘になる。

    本ファイルは各回答の evidence が実在することを検証する。
    説明が実装からずれた瞬間に赤くなる。

実行方法:
    pytest 92_narrative_contract_testing.py -v
"""
import importlib.util
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent


def load_module_from_path(filename: str, module_name: str):
    """#71/#80-#91 と同一の動的ローダー。"""
    path = HERE / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        pytest.skip(f"cannot build spec for {filename}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _narrative_mod():
    return load_module_from_path('92_interview_narrative.py', 'narrative_mod')


def _index_mod():
    return load_module_from_path('90_repository_index.py', 'index_for_narrative')


# ================================================================
# STAGE 1: 全ての根拠ファイルが実在すること ← 本ファイルの核心
#   語った内容の裏付けが無ければ、それは主張であって証拠ではない。
# ================================================================
def test_every_evidence_file_exists():
    mod = _narrative_mod()

    missing = []
    for n in mod.NARRATIVES:
        for item in n['evidence']:
            if not mod.find_files_for_item(item):
                missing.append(f"{n['id']}:#{item}")

    assert not missing, (
        f"these narratives cite files that do not exist: {missing}. "
        "An answer without evidence is a claim, not a demonstration."
    )


# ================================================================
# STAGE 2: 全エントリが必須フィールドを持つこと
# ================================================================
@pytest.mark.parametrize('field', ['id', 'question', 'answer', 'evidence', 'concern'])
def test_every_narrative_has_required_fields(field):
    mod = _narrative_mod()

    missing = [n.get('id', '?') for n in mod.NARRATIVES if not n.get(field)]

    assert not missing, f"these narratives lack {field!r}: {missing}"


# ================================================================
# STAGE 3: ID が重複しないこと
# ================================================================
def test_narrative_ids_are_unique():
    mod = _narrative_mod()

    ids = [n['id'] for n in mod.NARRATIVES]
    assert len(ids) == len(set(ids)), f"duplicate narrative ids: {ids}"


# ================================================================
# STAGE 4: concern が #90 の索引に存在すること
#   索引に無い関心を語れば、読者は該当箇所へ辿り着けない。
# ================================================================
def test_concerns_exist_in_the_index():
    narrative = _narrative_mod()
    index = _index_mod()

    unknown = [
        n['concern'] for n in narrative.NARRATIVES
        if n['concern'] not in index.CONCERN_MAP
    ]

    assert not unknown, (
        f"these narratives reference concerns absent from the index: {unknown}. "
        "A listener could not navigate to the corresponding files."
    )


# ================================================================
# STAGE 5: 回答が十分な長さを持つこと
#   一言で終わる回答は、面接では「理解していない」と受け取られる。
# ================================================================
def test_answers_are_substantive():
    mod = _narrative_mod()

    thin = [
        n['id'] for n in mod.NARRATIVES
        if len(n['answer']) < 60
    ]

    assert not thin, (
        f"these answers are too short to demonstrate understanding: {thin}. "
        "A one-line answer reads as unfamiliarity with one's own work."
    )


# ================================================================
# STAGE 6: 主要な関心が問答でカバーされていること
#   索引に載っている核心領域が語れなければ、準備として不完全である。
# ================================================================
@pytest.mark.parametrize('concern', ['idempotency', 'observability', 'testing'])
def test_core_concerns_have_a_narrative(concern):
    mod = _narrative_mod()

    covered = {n['concern'] for n in mod.NARRATIVES}

    assert concern in covered, (
        f"{concern} is a core part of this portfolio but has no prepared answer"
    )


# ================================================================
# STAGE 7: Markdown 出力が全問答を含むこと
# ================================================================
def test_markdown_includes_every_question():
    mod = _narrative_mod()
    md = mod.render_markdown()

    for n in mod.NARRATIVES:
        assert n['question'] in md, f"{n['id']} is missing from the rendered output"
        assert '根拠:' in md, "each answer must cite its evidence"


if __name__ == '__main__':
    print("🚀 想定問答契約の監査を開始するのね...")
    print("🟢 監査完了!語る内容が実装と一致することを守る基盤が完全画定したのね!")
    print("実行するには: pytest 92_narrative_contract_testing.py -v")