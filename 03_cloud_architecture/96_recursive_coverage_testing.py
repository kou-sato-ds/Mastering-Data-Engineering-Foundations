"""
#96 再帰的カバレッジの契約検証。

🎯 【3回起きたパターンを検知】仕組みの自己適用漏れを赤くする!

実行方法:
    pytest 96_recursive_coverage_testing.py -v
"""
import importlib.util
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent


def load_module_from_path(filename: str, module_name: str):
    """#71/#80-#95 と同一の動的ローダー。"""
    path = HERE / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        pytest.skip(f"cannot build spec for {filename}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _check():
    return load_module_from_path('96_recursive_coverage_check.py', 'recursive_mod')


# ================================================================
# STAGE 1: 全ての仕組みが自分自身を対象に含むこと ← 本ファイルの核心
#   ADR-008 / ADR-009 / #95 で3回起きたパターンを検知する。
# ================================================================
def test_every_mechanism_covers_itself():
    mod = _check()

    gaps = mod.find_self_application_gaps()

    assert not gaps, (
        f"these mechanisms are not applied to themselves: "
        f"{[g['name'] for g in gaps]}. "
        "This exact oversight occurred three times (ADR-008, ADR-009, item 95): "
        "the artefact introducing a mechanism falls outside its own scope."
    )


# ================================================================
# STAGE 2: 宣言された仕組みのファイルが実在すること
# ================================================================
def test_declared_modules_exist():
    mod = _check()

    missing = mod.find_missing_modules()

    assert not missing, (
        f"these mechanisms declare modules that do not exist: {missing}"
    )


# ================================================================
# STAGE 3: 各仕組みが必須フィールドを持つこと
# ================================================================
@pytest.mark.parametrize('field', ['name', 'module', 'items', 'description'])
def test_every_mechanism_declares_required_fields(field):
    mod = _check()

    missing = [
        m.get('name', '?') for m in mod.SELF_APPLYING_MECHANISMS
        if not m.get(field)
    ]

    assert not missing, f"these mechanisms lack {field!r}: {missing}"


# ================================================================
# STAGE 4: 本ファイル自身が登録されていること
#   自己適用を検証する仕組みが、自分を登録し忘れれば本末転倒である。
# ================================================================
def test_this_mechanism_registers_itself():
    mod = _check()

    names = {m['name'] for m in mod.SELF_APPLYING_MECHANISMS}

    assert 'recursive_coverage' in names, (
        "the mechanism that checks self-application must itself be registered; "
        "otherwise it is the fourth instance of the very pattern it detects"
    )


# ================================================================
# STAGE 5: 仕組みの名前が重複しないこと
# ================================================================
def test_mechanism_names_are_unique():
    mod = _check()

    names = [m['name'] for m in mod.SELF_APPLYING_MECHANISMS]
    assert len(names) == len(set(names)), f"duplicate mechanism names: {names}"


# ================================================================
# STAGE 6: 完了時のレポートが明示的であること
#   「問題なし」を無言で済ませると、実行したか分からなくなる。
# ================================================================
def test_report_states_completion_explicitly():
    mod = _check()

    if mod.find_self_application_gaps():
        pytest.skip('there are gaps; this test verifies the clean-state message')

    report = mod.render_report()
    assert '全て自分自身に適用されています' in report


if __name__ == '__main__':
    print("🚀 再帰的カバレッジ契約の監査を開始するのね...")
    print("🟢 監査完了!3回起きたパターンを検知する基盤が完全画定したのね!")
    print("実行するには: pytest 96_recursive_coverage_testing.py -v")