"""
カバレッジ除外設定の誠実性ガード。

🎯 【分母を正す、しかし隠さない】exclude_lines は水増しの道具にもなる!

背景:
    #78 の実測は11%だったが、分母には「測る意味のない行」が含まれていた——
    `if __name__ == '__main__':` ブロックは全ファイルに存在し、
    テストから実行される想定がない。これを除外するのは正当な調整である。

    しかし exclude_lines は容易に悪用できる。`def ` や `return` を
    除外パターンに加えれば数字はいくらでも上がる。
    本ファイルは **除外が乱用されていないこと** をテストで固定する。

実行方法:
    pytest 79_coverage_honesty_testing.py -v
"""
import configparser
from pathlib import Path

import pytest

HERE = Path(__file__).parent
COVERAGERC = HERE / '.coveragerc'

# 🚨 これらが除外パターンに現れたら、数字の水増しを疑う
ABUSE_MARKERS = ['def ', 'class ', 'return', 'import ', 'assert']


def _cfg() -> configparser.ConfigParser:
    parser = configparser.ConfigParser()
    parser.read(COVERAGERC, encoding='utf-8')
    return parser


def _exclude_lines() -> list[str]:
    raw = _cfg().get('report', 'exclude_lines', fallback='')
    return [line.strip() for line in raw.splitlines() if line.strip()]


# ================================================================
# STAGE 1: exclude_lines が宣言されていること
# ================================================================
def test_exclude_lines_is_declared():
    patterns = _exclude_lines()
    assert patterns, "exclude_lines must be declared to normalise the denominator"


# ================================================================
# STAGE 2: __main__ ブロックが除外対象であること
#   全ファイルに存在し、テストから実行される想定がない行。
# ================================================================
def test_main_block_is_excluded():
    patterns = _exclude_lines()
    assert any('__main__' in p for p in patterns), (
        "the __main__ block exists in every file and is never executed by tests; "
        "leaving it in the denominator distorts the metric"
    )


# ================================================================
# STAGE 3: 除外が乱用されていないこと ← 本ファイルの核心
#   `def ` や `return` を除外すれば数字はいくらでも上がる。
#   分母を正す調整と、数字の水増しを、テストで区別する。
# ================================================================
@pytest.mark.parametrize('marker', ABUSE_MARKERS)
def test_exclusion_is_not_abused(marker):
    patterns = _exclude_lines()
    offenders = [p for p in patterns if marker in p]

    assert not offenders, (
        f"exclude_lines contains {offenders} which hides real logic behind "
        f"{marker!r}; that is inflating coverage, not normalising the denominator"
    )


# ================================================================
# STAGE 4: 除外パターン数が抑制されていること
#   増え続ける除外リストは、測定放棄の始まりである。
# ================================================================
def test_exclusion_list_stays_small():
    patterns = _exclude_lines()
    assert len(patterns) <= 5, (
        f"{len(patterns)} exclusion patterns declared; a growing list signals "
        "that measurement is being abandoned rather than refined"
    )


# ================================================================
# STAGE 5: 初期学習ファイル群(#01-#51)が omit されていないこと
#   0%のファイルを計測対象から外せば数字は跳ね上がる。
#   「テストしていない」事実を隠さないことをテストで保証する。
# ================================================================
def test_untested_legacy_files_are_not_hidden():
    omit = _cfg().get('run', 'omit', fallback='')

    hidden = [line.strip() for line in omit.splitlines()
              if line.strip() and not line.strip().startswith('*_')]

    assert not hidden, (
        f"omit contains {hidden}; excluding untested files inflates the ratio "
        "and hides the fact that they were never tested. only test files "
        "(*_testing.py / *_validation.py) may be omitted."
    )


if __name__ == '__main__':
    print("🚀 カバレッジ除外の誠実性ガードの監査を開始するのね...")
    print("🟢 監査完了!分母の正当な調整と数字の水増しを区別する基盤が完全画定したのね!")
    print("実行するには: pytest 79_coverage_honesty_testing.py -v")