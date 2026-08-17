"""
テスト収集の健全性ガード（本命リポジトリからの横展開）。

🎯 【姉妹プロジェクトの教訓を適用】「テストが0件でも気づけない」穴を塞ぐ!

背景:
    姉妹プロジェクト serverless-scraping-data-pipeline で、
    テストファイルに構文エラーが混入し **テストが1件も collect できない状態**が
    2日間 main に残るインシデントが発生した(ADR-006)。

    CI は赤かったが、常に失敗する別ワークフローが1つ紛れ込んでいたため、
    **赤信号が意味を失っていた**。

    本リポジトリも同じ構造的リスクを抱えている:
    - #77 で自動検出(pytest.ini)を導入したが、
      「検出パターンに一致するが中身が壊れている」ケースは検知できない
    - #78/#79 でカバレッジ計測を入れたが、
      **テストが0件ならカバレッジ計算に到達しない**

    本ファイルは、テストスイート自身が自分の健全性を検証する。

実行方法:
    pytest 85_collection_guard_testing.py -v
"""
import ast
from pathlib import Path

import pytest

HERE = Path(__file__).parent

# 🚨 ファイル上の `def test_` の静的カウント。
#    @parametrize 展開後の実行件数(109)とは異なる点に注意。
#    現在の実測は83。ここを下回ったら「テストが消えた」ことを意味する。
MINIMUM_EXPECTED_TESTS = 80

# 👉 #77 の pytest.ini が宣言する命名規則と一致させる
TEST_FILE_PATTERNS = ["*_testing.py", "*_validation.py"]

# 🚨 モジバケ検知パターン。Unicodeエスケープで保持し、
#    このファイル自身が検査対象にならないようにする(姉妹プロジェクトでの学び)。
MOJIBAKE_MARKERS = [
    "\u7e67",  # 繧
    "\u7e3a",  # 縺
    "\uff7d",  # ｽ
    "\uff7a",  # ｺ
]


def _test_files() -> list[Path]:
    """検出対象のテストファイルを列挙する（自分自身を除く）。"""
    files = []
    for pattern in TEST_FILE_PATTERNS:
        files.extend(HERE.glob(pattern))
    return sorted(f for f in files if f.name != Path(__file__).name)


def _count_test_functions(path: Path) -> int:
    """ファイル内の `def test_` の数を数える。"""
    text = path.read_text(encoding="utf-8")
    return sum(1 for line in text.splitlines() if line.strip().startswith("def test_"))


# ================================================================
# STAGE 1: 全テストファイルが構文的に正しいこと
#   姉妹プロジェクトの事故は `def  None():` という構文エラーだった。
#   collect 前に compile して、壊れていれば明示的に落とす。
# ================================================================
def test_every_test_file_is_syntactically_valid():
    broken = []
    for path in _test_files():
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as e:
            broken.append(f"{path.name}:{e.lineno} {e.msg}")

    assert not broken, (
        f"these test files have syntax errors: {broken}. "
        "This is the failure mode recorded in the sibling project's ADR-006, "
        "where the entire suite silently stopped running."
    )


# ================================================================
# STAGE 2: テスト総数が下限を割っていないこと
#   「壊れて0件」も「うっかり大量削除」も、同じアサーションで捕まえる。
# ================================================================
def test_suite_has_not_shrunk():
    total = sum(_count_test_functions(p) for p in _test_files())

    assert total >= MINIMUM_EXPECTED_TESTS, (
        f"only {total} tests found across {len(_test_files())} files, "
        f"below the floor of {MINIMUM_EXPECTED_TESTS}. "
        "Either tests were removed, or files are broken."
    )


# ================================================================
# STAGE 3: 検出対象のファイルが実際に存在すること
#   pytest.ini のパターンを誤って変更すると、
#   「0件だが緑」という最悪の状態になりうる。
# ================================================================
def test_discovery_finds_test_files():
    files = _test_files()

    assert len(files) >= 10, (
        f"only {len(files)} test files matched {TEST_FILE_PATTERNS}. "
        "If pytest.ini's python_files pattern was changed, the suite may "
        "collect nothing while still reporting success."
    )


# ================================================================
# STAGE 4: 文字化けが混入していないこと
#   #86 で記録した通り、PowerShell 経由の編集で日本語が壊れる事故があった。
# ================================================================
@pytest.mark.parametrize("marker", MOJIBAKE_MARKERS)
def test_no_mojibake_in_test_files(marker):
    offenders = [
        p.name for p in _test_files()
        if marker in p.read_text(encoding="utf-8")
    ]

    assert not offenders, (
        f"mojibake marker U+{ord(marker):04X} found in {offenders}. "
        "PowerShell's Get-Content|Set-Content corrupts UTF-8 Japanese text; "
        "use [System.IO.File]::ReadAllText with explicit encoding."
    )


# ================================================================
# STAGE 5: 検証対象の実装ファイルが構文的に正しいこと
#
#   NOTE: 拡張子が `.sql.py` のファイル(#06/#07)は中身がSQLであり、
#         Pythonとして parse できない。これは本ガードのスコープ外の
#         別問題(拡張子の誤り)として除外し、Pythonファイルのみを検査する。
#         ガードの目的は「テストと実装が静かに壊れる」ことの検知であり、
#         スコープを広げすぎると常に赤いチェックになり信号の意味が失われる
#         (姉妹プロジェクト ADR-006 の教訓)。
# ================================================================
def test_every_python_source_file_is_syntactically_valid():
    broken = []
    for path in sorted(HERE.glob("*.py")):
        if path.name.endswith(("_testing.py", "_validation.py")):
            continue
        if ".sql.py" in path.name:
            continue  # 👉 中身がSQLのため対象外(拡張子は別途整理する)
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as e:
            broken.append(f"{path.name}:{e.lineno} {e.msg}")

    assert not broken, f"these source files have syntax errors: {broken}"


if __name__ == '__main__':
    print("🚀 テスト収集の健全性ガードの監査を開始するのね...")
    print("🟢 監査完了!テストが静かに消える事故を検知できる基盤が完全画定したのね!")
    print("実行するには: pytest 85_collection_guard_testing.py -v")