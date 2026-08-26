"""
索引と想定問答の相互リンク — 語れる領域を索引から辿れるようにする。

🎯 【#99の思想を内部へ】姉妹リポジトリでやった相互リンクを、リポジトリ内で!

背景:
    #92 で想定問答を持たせたが、**索引(#90)からは問答へ辿れない**。
    読者が索引の `idempotency` 行を見ても、
    そこに対応する準備済みの説明があることに気づけない。

    #91 で姉妹リポジトリに対して行った相互リンク検証を、
    今度は同一リポジトリ内の2つの構造(索引と問答)に適用する。

    索引が「どこを読むか」、問答が「何を語るか」を担う。
    両者が繋がって初めて、読者は「この領域について本人はこう説明する」
    という情報に辿り着ける。

実行方法:
    python 93_narrative_index_link.py       # 統合ビューを表示
    pytest 93_narrative_index_testing.py -v
"""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).parent


def _load(filename: str, module_name: str):
    """索引・問答モジュールを動的に読み込む。"""
    path = HERE / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def load_index():
    return _load('90_repository_index.py', 'index_for_link')


def load_narrative():
    return _load('92_interview_narrative.py', 'narrative_for_link')


def build_narrative_lookup() -> dict:
    """
    🔍 関心 -> 想定問答リスト の対応表を構築する純粋関数。

    1つの関心に複数の問答が紐づくこともあるため、リストで持つ。
    """
    narrative = load_narrative()
    lookup = {}
    for n in narrative.NARRATIVES:
        lookup.setdefault(n['concern'], []).append(n)
    return lookup


def find_concerns_without_narrative() -> list:
    """
    🚨 索引にあるが、語る準備が無い関心を返す。

    全ての関心に問答が要るわけではない(foundations等は基礎習得期)が、
    「何を語れて何を語れないか」を把握しておくこと自体に価値がある。
    """
    index = load_index()
    lookup = build_narrative_lookup()
    return [c for c in index.CONCERN_MAP if c not in lookup]


def build_integrated_view() -> list:
    """
    📋 索引と問答を統合したビューを構築する。

    各エントリは concern・items・sibling・questions を持つ。
    読者は関心から入り、該当ファイルと想定問答の両方へ辿れる。
    """
    index = load_index()
    lookup = build_narrative_lookup()

    view = []
    for entry in index.build_index():
        concern = entry['concern']
        view.append({
            'concern': concern,
            'items': entry['items'],
            'sibling': entry['sibling'],
            'questions': [n['question'] for n in lookup.get(concern, [])],
        })
    return view


def render_markdown() -> str:
    """統合ビューを Markdown テーブルとして出力する。"""
    index = load_index()

    lines = ['| 関心 | 項目 | 想定問答 | 姉妹対応 |', '|---|---|---|---|']
    for entry in build_integrated_view():
        items = index.format_item_range(entry['items'])
        questions = '<br>'.join(f'Q. {q}' for q in entry['questions']) or '—'
        sibling = entry['sibling'] or '—'
        lines.append(f"| {entry['concern']} | {items} | {questions} | {sibling} |")
    return '\n'.join(lines)


if __name__ == '__main__':
    print("🚀 索引と想定問答の相互リンク基盤の監査を開始するのね...")
    print(render_markdown())
    print("\n語る準備が無い関心:", find_concerns_without_narrative())
    print("🟢 監査完了!読者が関心から説明まで辿れる基盤が完全画定したのね!")