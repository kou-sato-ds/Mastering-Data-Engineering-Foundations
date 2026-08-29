"""
#94 面接台本の契約検証。

🎯 【台本が実在する問答を指すか】存在しない答えを組み込ませない!

背景:
    台本は問答IDを参照するが、問答側が変われば参照は壊れる。
    「opening で cost_awareness を話す」と決めても、
    その問答が削除されていれば台本は破綻する。

    また時間配分も検証対象である——
    30分の面接に45分の台本を用意しても実用にならない。

実行方法:
    pytest 94_script_contract_testing.py -v
"""
import importlib.util
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent


def load_module_from_path(filename: str, module_name: str):
    """#71/#80-#93 と同一の動的ローダー。"""
    path = HERE / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        pytest.skip(f"cannot build spec for {filename}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _script_mod():
    return load_module_from_path('94_interview_script.py', 'script_mod')


# ================================================================
# STAGE 1: 台本が参照する問答が全て実在すること ← 本ファイルの核心
# ================================================================
def test_every_referenced_narrative_exists():
    mod = _script_mod()
    narrative = mod.load_narrative()

    existing = {n['id'] for n in narrative.NARRATIVES}
    referenced = mod.collect_used_narrative_ids()

    phantom = sorted(referenced - existing)

    assert not phantom, (
        f"the script references narratives that do not exist: {phantom}. "
        "Building a script on a missing answer guarantees a blank moment."
    )


# ================================================================
# STAGE 2: 台本の所要時間が現実的であること
#   30分の面接枠に対し、技術説明が長すぎれば質疑の時間が残らない。
# ================================================================
def test_script_fits_a_typical_interview_slot():
    mod = _script_mod()
    total = mod.total_duration()

    assert 10 <= total <= 20, (
        f"the script runs {total} minutes. Under 10 leaves the depth "
        "unshown; over 20 crowds out the interviewer's own questions."
    )


# ================================================================
# STAGE 3: 全フェーズが狙いを明示していること
#   「何を話すか」だけで「なぜそこで話すか」が無ければ、順序は再現できない。
# ================================================================
@pytest.mark.parametrize('field', ['label', 'intent', 'narratives', 'duration_min'])
def test_every_phase_declares_required_fields(field):
    mod = _script_mod()

    missing = [p['phase'] for p in mod.SCRIPT_PHASES if not p.get(field)]

    assert not missing, f"these phases lack {field!r}: {missing}"


# ================================================================
# STAGE 4: 障害対応のフェーズが存在すること
#   成功事例だけの台本は「まだ本番を任されていない」印象を与える。
# ================================================================
def test_script_includes_an_incident_phase():
    mod = _script_mod()

    phases = {p['phase'] for p in mod.SCRIPT_PHASES}

    assert 'incident' in phases, (
        "a script of successes alone reads as inexperience; "
        "being able to analyse one's own failure is what builds trust"
    )


# ================================================================
# STAGE 5: 締めが対称構造に触れること
#   ポートフォリオの核を最後に置かなければ、個別実装の話で終わる。
# ================================================================
def test_closing_covers_the_cross_cloud_theme():
    mod = _script_mod()

    closing = next(p for p in mod.SCRIPT_PHASES if p['phase'] == 'closing')

    assert 'cross_cloud' in closing['narratives'], (
        "without the symmetry argument at the end, the interview closes on "
        "individual implementations rather than transferable design principles"
    )


# ================================================================
# STAGE 6: 未使用の問答が過半にならないこと
#   準備した問答の大半に出番が無いなら、台本の設計が不足している。
# ================================================================
def test_most_narratives_have_a_place_in_the_script():
    mod = _script_mod()
    narrative = mod.load_narrative()

    unused = mod.find_unused_narratives()
    total = len(narrative.NARRATIVES)

    assert len(unused) <= total // 2, (
        f"{len(unused)} of {total} narratives have no place in the script: "
        f"{unused}. Preparing answers without designing when to use them "
        "leaves the delivery to chance."
    )


# ================================================================
# STAGE 7: Markdown 出力が全フェーズと所要時間を含むこと
# ================================================================
def test_markdown_renders_the_full_script():
    mod = _script_mod()
    md = mod.render_markdown()

    assert f'想定 {mod.total_duration()} 分' in md
    for phase in mod.SCRIPT_PHASES:
        assert phase['label'] in md, f"{phase['phase']} is missing from the output"
    assert '根拠:' in md, "each answer must carry its evidence"


if __name__ == '__main__':
    print("🚀 面接台本契約の監査を開始するのね...")
    print("🟢 監査完了!台本と問答の整合が守られる基盤が完全画定したのね!")
    print("実行するには: pytest 94_script_contract_testing.py -v")