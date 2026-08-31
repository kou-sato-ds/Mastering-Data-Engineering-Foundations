"""
リポジトリ構造の自己記述 — 索引をコードから生成する。

🎯 【#97の原則を索引へ】手書きの目次は腐る。生成すれば腐らない!

背景:
    #89 で「ドキュメントは腐るがテストされたコードは腐らない」と書いた。
    その原則が最も効くのは **README の目次そのもの** である。

    現在 README には #60-#97 が時系列に並んでいるが、
    採用担当者が最初に開いた時「どこから読めばよいか」が分からない。
    かといって手書きの索引を置けば、項目を追加するたびに更新漏れが起きる。

    本ファイルはファイル群をスキャンして索引を生成し、
    README との整合をテストで固定する。

実行方法:
    python 90_repository_index.py       # 索引を表示
    pytest 90_index_contract_testing.py -v
"""
import re
from pathlib import Path

HERE = Path(__file__).parent

# 🎯 【関心別の分類】採用担当者が「何を確認したいか」で引ける索引を作る。
#    キーは設計上の関心、値は該当する項目番号。
CONCERN_MAP = {
    'foundations': list(range(1, 52)),   # 👉 #01-#51: Spark/ML/BQ の基礎習得期
    'idempotency': [58],
    'fault_tolerance': [57, 67],
    'observability': [60, 66, 67],
    'security': [61],
    'iac': [62],
    'cost': [64],
    'windowing': [55, 56, 63],
    'joins': [65],
    'orchestration': [59],
    'ingestion': [52, 53, 54],
    'testing': [68, 69, 70, 71, 73, 74, 75, 76, 77, 78, 79,
                80, 81, 82, 83, 84, 85],
    'deployment': [86, 87, 88, 89],
    'meta': [90, 91, 92, 93, 94, 95],
}

# 👉 姉妹プロジェクトとの対応（AWS/GCP対称構造）
SIBLING_MAP = {
    'idempotency': 'ADR-002 (Content-Addressable S3 keys)',
    'fault_tolerance': 'ADR-003 (exception propagation + SQS DLQ)',
    'observability': 'ADR-004 / ADR-005 (Powertools + correlation id)',
    'testing': 'ADR-006 / ADR-007 (broken main postmortem + collection guard)',
    'meta': 'ADR-008 (ADR index verified by tests)',
}


def scan_item_numbers() -> list:
    """
    🔍 ディレクトリをスキャンし、実在する項目番号を返す純粋関数。

    手書きのリストではなくファイルシステムを情報源にすることで、
    「ファイルは消したが索引には残っている」という乖離を防ぐ。

    NOTE: #62 は Terraform (.tf) であり Python ではない。
          拡張子を限定すると索引から漏れるため、番号接頭辞のみで判定する。
          初回実装では `*.py` に限定しており、実際に #62 が
          「索引にあるが存在しない」と誤判定された。
    """
    numbers = set()
    for path in HERE.iterdir():
        if not path.is_file():
            continue
        match = re.match(r'^(\d+)_', path.name)
        if match:
            numbers.add(int(match.group(1)))
    return sorted(numbers)


def build_index() -> list:
    """
    📋 関心別の索引を構築する。

    各エントリは concern（関心）・items（項目番号）・sibling（姉妹対応）を持つ。
    """
    existing = set(scan_item_numbers())
    index = []
    for concern, items in CONCERN_MAP.items():
        index.append({
            'concern': concern,
            'items': [i for i in items if i in existing],
            'declared': items,
            'sibling': SIBLING_MAP.get(concern),
        })
    return index


def find_unindexed_items() -> list:
    """
    🚨 実在するがどの関心にも分類されていない項目を返す。

    「作ったが索引に載せ忘れた」を検知する。
    """
    indexed = {i for items in CONCERN_MAP.values() for i in items}
    return [n for n in scan_item_numbers() if n not in indexed]


def format_item_range(items: list) -> str:
    """
    🔍 連続する番号を範囲表記に畳む。

    #01-#51 のような長い連番をそのまま並べると索引が読めなくなるため、
    連続部分は `#1-#51` の形にまとめる。
    """
    if not items:
        return '—'

    ranges = []
    start = prev = items[0]
    for n in items[1:]:
        if n == prev + 1:
            prev = n
            continue
        ranges.append((start, prev))
        start = prev = n
    ranges.append((start, prev))

    return ', '.join(
        f'#{a}' if a == b else f'#{a}-#{b}' for a, b in ranges
    )


def render_markdown() -> str:
    """索引を Markdown テーブルとして出力する。"""
    lines = ['| 関心 | 項目 | 姉妹プロジェクト対応 |', '|---|---|---|']
    for entry in build_index():
        items = format_item_range(entry['items'])
        sibling = entry['sibling'] or '—'
        lines.append(f"| {entry['concern']} | {items} | {sibling} |")
    return '\n'.join(lines)


if __name__ == '__main__':
    print("🚀 リポジトリ索引の自己記述基盤の監査を開始するのね...")
    print(render_markdown())
    print("\nUnindexed:", find_unindexed_items())
    print("🟢 監査完了!手書きせず生成される索引基盤が完全画定したのね!")