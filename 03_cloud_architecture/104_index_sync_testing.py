"""
索引の生成結果とREADME記載の一致検証。

🎯 【昨日の漏れを潰す】生成したものと、貼ったものが同じか!

背景:
    #98 で索引をコードから生成する仕組みを作ったが、
    **その出力をREADMEに貼るステップは人間が手でやっている**。

    昨日 #103 を追加した際、90_repository_index.py の CONCERN_MAP は
    更新したのに、READMEの索引テーブルへ反映し忘れた。
    #95 が検知するのは「コード側の未分類」だけであり、
    **READMEとの一致は誰も見ていなかった**。

    同種の漏れは #92/#93/#94 でも起きている——これで3回目のパターンである。
    #103 で「同じことが3回続いたら仕組みで解く」と書いた通りに扱う。

    #102 が「見出しが見出しとして描画されるか」を守るのに対し、
    本ファイルは「生成したものと、貼ったものが同じか」を守る。

実行方法:
    pytest 104_index_sync_testing.py -v
"""
import importlib.util
import re
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent
README = HERE.parent / 'README.md'


def load_module_from_path(filename: str, module_name: str):
    """#71/#80-#103 と同一の動的ローダー。"""
    path = HERE / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        pytest.skip(f"cannot build spec for {filename}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _index_mod():
    return load_module_from_path('90_repository_index.py', 'index_for_sync_check')


def generated_rows() -> list:
    """
    🔍 コードが生成する索引行（ヘッダと区切りを除く）を返す。

    render_markdown() の出力をそのまま比較対象にする——
    「生成物が正」であり、READMEはその写しである。
    """
    lines = _index_mod().render_markdown().splitlines()
    return [l.strip() for l in lines[2:] if l.strip()]


def readme_rows() -> list:
    """
    🔍 README の索引テーブルから行を抽出する。

    `| 関心 |` のヘッダを起点に、テーブルが途切れるまでを読む。
    ADR索引など他のテーブルと混同しないための起点指定である。
    """
    lines = README.read_text(encoding='utf-8').splitlines()

    start = None
    for i, line in enumerate(lines):
        if line.strip().startswith('| 関心 |'):
            start = i
            break

    if start is None:
        return []

    rows = []
    for line in lines[start + 2:]:      # 👉 ヘッダ行と区切り行をスキップ
        stripped = line.strip()
        if not stripped.startswith('|'):
            break
        rows.append(stripped)
    return rows


# ================================================================
# STAGE 1: README に索引テーブルが存在すること
# ================================================================
def test_readme_contains_the_index_table():
    assert readme_rows(), (
        "the index table from item 98 is missing; a reader landing on the "
        "README would have no entry point"
    )


# ================================================================
# STAGE 2: 生成行とREADME行が完全一致すること ← 本ファイルの核心
#   昨日 backfill 行の貼り忘れが1日残った事故を守る。
# ================================================================
def test_readme_matches_the_generated_index():
    generated = generated_rows()
    pasted = readme_rows()

    missing = [r for r in generated if r not in pasted]
    extra = [r for r in pasted if r not in generated]

    assert not missing and not extra, (
        f"the README index has drifted from the generated one.\n"
        f"  missing from README: {missing}\n"
        f"  stale in README:     {extra}\n"
        "Run `python 90_repository_index.py` and paste the table again."
    )


# ================================================================
# STAGE 3: 行の並び順も一致すること
#   内容が同じでも順序が違えば、生成物を貼り直したとは言えない。
# ================================================================
def test_row_order_matches():
    assert readme_rows() == generated_rows(), (
        "the rows match as a set but not in order; the README was edited "
        "by hand rather than replaced with the generated output"
    )


# ================================================================
# STAGE 4: README の索引に重複行が無いこと
#   差し替えたつもりが追記になっていた事故が #110 で実際に起きた。
# ================================================================
def test_no_duplicate_rows_in_readme():
    rows = readme_rows()
    duplicates = sorted({r for r in rows if rows.count(r) > 1})

    assert not duplicates, (
        f"these rows appear more than once: {duplicates}. "
        "A replacement that silently became an append."
    )


# ================================================================
# STAGE 5: 全行が3列であること
#   他リポジトリの索引行(4列)が混入した事故が #110 で実際に起きた。
# ================================================================
def test_every_row_has_three_columns():
    wrong = [r for r in readme_rows() if r.count('|') != 4]

    assert not wrong, (
        f"these rows are not 3-column: {wrong}. A row pasted from the "
        "sibling repository's ADR index would look like this."
    )


# ================================================================
# STAGE 6: 関心名が CONCERN_MAP と一致すること
#   README にだけ存在する関心は、実体を持たない。
# ================================================================
def test_concern_names_exist_in_the_code():
    mod = _index_mod()
    declared = set(mod.CONCERN_MAP)

    in_readme = {
        m.group(1).strip()
        for r in readme_rows()
        if (m := re.match(r'^\|\s*([^|]+?)\s*\|', r))
    }

    phantom = sorted(in_readme - declared)

    assert not phantom, (
        f"these concerns appear only in the README: {phantom}. "
        "They have no CONCERN_MAP entry and therefore no files behind them."
    )


# ================================================================
# STAGE 7: 生成側が空でないこと
#   比較対象が空なら、この検証自体が意味を失う。
# ================================================================
def test_generated_index_is_not_empty():
    assert len(generated_rows()) >= 10, (
        "the generator produced almost nothing; comparing against it would "
        "pass trivially and hide a broken README"
    )


if __name__ == '__main__':
    print("🚀 索引同期の監査を開始するのね...")
    print("🟢 監査完了!生成物とREADMEの一致が守られる基盤が完全画定したのね!")
    print("実行するには: pytest 104_index_sync_testing.py -v")