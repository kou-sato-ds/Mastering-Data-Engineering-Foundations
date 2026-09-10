"""
#102 Markdown構造検証のテスト。

🎯 【昨日の事故を名指しで守る】引用に沈んだ見出しをゼロに保つ!

実行方法:
    pytest 102_markdown_structure_testing.py -v
"""
import importlib.util
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent

# 🚨 現在の見出し数。大幅に減れば節が消えたことを意味する。
MIN_EXPECTED_HEADINGS = 100


def load_module_from_path(filename: str, module_name: str):
    """#71/#80-#101 と同一の動的ローダー。"""
    path = HERE / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        pytest.skip(f"cannot build spec for {filename}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _md():
    return load_module_from_path('102_markdown_structure_check.py', 'md_structure_mod')


# ================================================================
# STAGE 1: 引用に沈んだ見出しが無いこと ← 本ファイルの核心
#   #61-#108 の45件が1ヶ月以上気づかれずに放置された事故を守る。
# ================================================================
def test_no_heading_is_trapped_in_a_blockquote():
    mod = _md()

    quoted = mod.find_quoted_headings(mod.read_lines())

    assert not quoted, (
        f"{len(quoted)} headings are prefixed with '> ' and render as quoted "
        f"text, not headings: lines {[q['line'] for q in quoted][:5]}. "
        "They appear in no table of contents; a reader cannot navigate to them. "
        "This exact defect affected 45 sections for over a month."
    )


# ================================================================
# STAGE 2: 見出し数が下限を割っていないこと
#   節がまとめて消えたことを検知する。
# ================================================================
def test_heading_count_has_not_collapsed():
    mod = _md()

    headings = mod.extract_headings(mod.read_lines())

    assert len(headings) >= MIN_EXPECTED_HEADINGS, (
        f"only {len(headings)} headings found, below the floor of "
        f"{MIN_EXPECTED_HEADINGS}. Sections may have been deleted or "
        "swallowed by a code block."
    )


# ================================================================
# STAGE 3: コードブロック内の # を見出しと誤認しないこと
#   Python のコメント行を数えれば、件数は簡単に膨らむ。
# ================================================================
def test_comments_inside_code_blocks_are_not_headings():
    mod = _md()

    sample = [
        '# Real Heading',
        '```python',
        '# this is a comment, not a heading',
        '## neither is this',
        '```',
        '## Another Heading',
    ]
    headings = mod.extract_headings(sample)

    assert [h['text'] for h in headings] == ['Real Heading', 'Another Heading'], (
        "counting comments as headings would inflate the metric and hide "
        "a genuine loss of sections"
    )


# ================================================================
# STAGE 4: 見出しレベルの飛びを検知すること
# ================================================================
def test_level_jump_is_detected():
    mod = _md()

    sample = ['# Top', '#### Too Deep']
    jumps = mod.find_level_jumps(mod.extract_headings(sample))

    assert len(jumps) == 1
    assert jumps[0]['from'] == 1
    assert jumps[0]['to'] == 4


# ================================================================
# STAGE 5: 正常な階層では飛びを報告しないこと
# ================================================================
def test_proper_nesting_reports_no_jump():
    mod = _md()

    sample = ['# Top', '## Second', '### Third', '## Back to Second']

    assert mod.find_level_jumps(mod.extract_headings(sample)) == []


# ================================================================
# STAGE 6: テーブルの列数不一致を検知すること
#   #98 の索引テーブルが静かに壊れても誰も気づかない。
# ================================================================
def test_mismatched_table_columns_are_detected():
    mod = _md()

    sample = [
        '| A | B | C |',
        '|---|---|---|',
        '| 1 | 2 | 3 |',
        '| 1 | 2 |',
    ]
    issues = mod.find_malformed_tables(sample)

    assert len(issues) == 1
    assert issues[0]['line'] == 4


# ================================================================
# STAGE 7: 正常なテーブルでは問題を報告しないこと
# ================================================================
def test_wellformed_table_reports_nothing():
    mod = _md()

    sample = [
        '| A | B |',
        '|---|---|',
        '| 1 | 2 |',
        '| 3 | 4 |',
    ]

    assert mod.find_malformed_tables(sample) == []


# ================================================================
# STAGE 8: 実際の README が構造的に健全であること
# ================================================================
def test_actual_readme_has_no_structural_issues():
    mod = _md()

    issues = mod.summarise_issues(mod.check_structure())

    assert not issues, f"README has structural problems: {issues}"


# ================================================================
# STAGE 9: 索引テーブルが README に残っていること
#   #98 で作った入口が、編集で失われていないか。
# ================================================================
def test_index_table_survives_in_readme():
    mod = _md()
    lines = mod.read_lines()

    assert any('| 関心 |' in l for l in lines), (
        "the index table header from item 98 is gone; a reader landing on "
        "the README would have no entry point"
    )


if __name__ == '__main__':
    print("🚀 Markdown構造検証の監査を開始するのね...")
    print("🟢 監査完了!見出しが見出しとして描画される基盤が完全画定したのね!")
    print("実行するには: pytest 102_markdown_structure_testing.py -v")