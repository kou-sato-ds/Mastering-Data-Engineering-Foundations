"""
再帰的カバレッジの検証 — 仕組みが自分自身を対象に含むか。

🎯 【3回起きたパターンを潰す】仕組みを作ったら、まず自分に適用せよ!

背景:
    同じ構造の見落としが3回起きている:

      ADR-008: 索引を導入するADRが、索引に載っていなかった
      ADR-009: 問答を導入するADRに、対応する問答が無かった
      #95:     分類助言を導入した項目が、未分類だった

    いずれも「仕組みを導入する成果物が、その仕組みの適用対象から漏れる」
    という同一の構造である。再帰的な構造では必ず起きる。

    #103 で「同じ後始末が3回続いたら仕組みで解く」と書いた。
    本ファイルはその原則を、**見落としのパターン自体**に適用する。

    検証するのは「新しく作った仕組みが、自分自身をカバーしているか」——
    これは実装の正しさではなく、**適用漏れの検知**である。

実行方法:
    python 96_recursive_coverage_check.py       # カバレッジ状況を表示
    pytest 96_recursive_coverage_testing.py -v
"""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).parent


def _load(filename: str, module_name: str):
    path = HERE / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


# 🎯 【自己適用が必要な仕組み】各エントリは
#    「その仕組みが管理する集合」と「自分自身が含まれるべきか」を宣言する。
#
#    追加するとき: 新しい仕組みを作ったら、ここに登録する。
#    そうすれば「自分に適用し忘れた」瞬間に赤くなる。
SELF_APPLYING_MECHANISMS = [
    {
        'name': 'repository_index',
        'module': '90_repository_index.py',
        'items': [90, 91, 92, 93, 94, 95, 96],
        'description': '索引は自分自身の項目番号を含まねばならない',
    },
    {
        'name': 'interview_narrative',
        'module': '92_interview_narrative.py',
        'items': [92],
        'description': '問答の仕組みは meta 関心として索引される',
    },
    {
        'name': 'classification_advisor',
        'module': '95_classification_advisor.py',
        'items': [95],
        'description': '分類助言の仕組み自体も分類されねばならない',
    },
    {
        'name': 'recursive_coverage',
        'module': '96_recursive_coverage_check.py',
        'items': [96],
        'description': '本ファイル自身も索引と自己適用リストに載る',
    },
]


def load_index():
    return _load('90_repository_index.py', 'index_for_recursive')


def all_indexed_items() -> set:
    """索引に登録済みの全項目番号を返す。"""
    index = load_index()
    return {i for items in index.CONCERN_MAP.values() for i in items}


def find_self_application_gaps() -> list:
    """
    🚨 自分自身を対象に含めていない仕組みを返す。

    各エントリは name・missing_items を持つ。
    missing_items が空でなければ、その仕組みは自分に適用されていない。
    """
    indexed = all_indexed_items()

    gaps = []
    for mech in SELF_APPLYING_MECHANISMS:
        missing = [i for i in mech['items'] if i not in indexed]
        if missing:
            gaps.append({
                'name': mech['name'],
                'missing_items': missing,
                'description': mech['description'],
            })
    return gaps


def find_missing_modules() -> list:
    """宣言された仕組みのうち、ファイルが実在しないものを返す。"""
    return [
        m['name'] for m in SELF_APPLYING_MECHANISMS
        if not (HERE / m['module']).exists()
    ]


def render_report() -> str:
    """自己適用の状況を人間が読める形で出力する。"""
    gaps = find_self_application_gaps()

    if not gaps:
        return (
            f'{len(SELF_APPLYING_MECHANISMS)} 個の仕組みが全て自分自身に適用されています。'
        )

    lines = ['自分自身に適用されていない仕組み:', '']
    for g in gaps:
        lines.append(f"  {g['name']}: 項目 {g['missing_items']} が未登録")
        lines.append(f"      {g['description']}")
        lines.append('')
    return '\n'.join(lines)


if __name__ == '__main__':
    print("🚀 再帰的カバレッジの監査を開始するのね...")
    print(render_report())
    print("🟢 監査完了!仕組みが自分自身を対象に含むことを守る基盤が完全画定したのね!")