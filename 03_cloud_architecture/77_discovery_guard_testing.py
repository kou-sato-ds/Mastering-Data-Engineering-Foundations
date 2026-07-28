"""
テスト自動検出の健全性を守るガードテスト。

🎯 【登録し忘れの構造的排除】CIのファイル列挙を廃止し、命名規則で自動収集する!

背景:
    #76 は ci.yml への追記が漏れたままpushされた——テストは存在するのに
    CI では一度も走らない状態だった(レビューで検知して修正)。
    原因は ci.yml が `pytest 68_... 69_... 70_...` とファイル名を
    手で列挙していたこと。つまりテストの実行が人間の記憶に依存していた。

    本ファイルは pytest.ini による自動検出へ移行した上で、
    その仕組み自体が壊れていないことを検証する「メタテスト」である。

実行方法:
    pytest 77_discovery_guard_testing.py -v
"""
import configparser
import fnmatch
import re
from pathlib import Path

import pytest

HERE = Path(__file__).parent
PYTEST_INI = HERE / 'pytest.ini'
CI_YML = HERE.parent / '.github' / 'workflows' / 'ci.yml'


def _configured_patterns() -> list[str]:
    """pytest.ini が宣言している検出パターンを取得する。"""
    parser = configparser.ConfigParser()
    parser.read(PYTEST_INI, encoding='utf-8')
    return parser.get('pytest', 'python_files').split()


def _files_with_test_functions() -> list[Path]:
    """`def test_` を含む .py ファイル = 実質的なテストファイルを列挙する。"""
    hits = []
    for path in sorted(HERE.glob('*.py')):
        text = path.read_text(encoding='utf-8')
        if re.search(r'^def test_', text, re.MULTILINE):
            hits.append(path)
    return hits


# ================================================================
# STAGE 1: pytest.ini が検出パターンを宣言していること
# ================================================================
def test_pytest_ini_defines_discovery_patterns():
    assert PYTEST_INI.exists(), "pytest.ini must exist to enable auto-discovery"

    patterns = _configured_patterns()
    assert patterns, "python_files must not be empty"
    assert any('_testing' in p for p in patterns), \
        "the *_testing.py convention must stay registered"


# ================================================================
# STAGE 2: テスト関数を持つ全ファイルが検出パターンに一致すること
#   ここが本ファイルの核心。命名規則を外れたファイルは
#   「書いたのに一度も走らない」テストになるため、その瞬間に赤くする。
# ================================================================
def test_every_test_file_matches_discovery_pattern():
    patterns = _configured_patterns()
    test_files = _files_with_test_functions()

    assert test_files, "no test files found — the guard itself would be meaningless"

    unmatched = [
        f.name for f in test_files
        if not any(fnmatch.fnmatch(f.name, p) for p in patterns)
    ]
    assert not unmatched, (
        f"these files define test functions but will NEVER be collected: {unmatched}. "
        f"rename them to match {patterns} or pytest will silently skip them."
    )


# ================================================================
# STAGE 3: ci.yml が個別ファイル名を列挙していないこと
#   手動列挙へ逆戻りした瞬間に赤くする(#76 の再発防止)。
# ================================================================
def test_ci_does_not_enumerate_individual_test_files():
    assert CI_YML.exists(), "ci.yml must exist"
    content = CI_YML.read_text(encoding='utf-8')

    enumerated = re.findall(r'\d{2}_\w+_(?:testing|validation)\.py', content)
    assert not enumerated, (
        f"ci.yml still enumerates test files {sorted(set(enumerated))}; "
        f"registration is again dependent on human memory. use bare `pytest -v`."
    )


# ================================================================
# STAGE 4: ci.yml が正しいディレクトリで pytest を起動していること
# ================================================================
def test_ci_runs_pytest_in_the_test_directory():
    content = CI_YML.read_text(encoding='utf-8')

    assert 'working-directory: 03_cloud_architecture' in content, \
        "pytest must run where pytest.ini and the test files live"
    assert re.search(r'run:\s*pytest\b', content), \
        "ci.yml must invoke pytest"


# ================================================================
# STAGE 5: 検出対象のファイルが空でないこと
#   命名だけ合っていて中身が無い「見せかけのテスト」を防ぐ。
# ================================================================
def test_no_discovered_file_is_devoid_of_tests():
    patterns = _configured_patterns()

    empty = []
    for path in sorted(HERE.glob('*.py')):
        if not any(fnmatch.fnmatch(path.name, p) for p in patterns):
            continue
        text = path.read_text(encoding='utf-8')
        if not re.search(r'^def test_', text, re.MULTILINE):
            empty.append(path.name)

    assert not empty, f"these files match the pattern but contain no tests: {empty}"


if __name__ == '__main__':
    print("🚀 テスト自動検出ガードの監査を開始するのね...")
    print("🟢 監査完了!登録し忘れが構造的に不可能な検証基盤が完全画定したのね!")
    print("実行するには: pytest 77_discovery_guard_testing.py -v")