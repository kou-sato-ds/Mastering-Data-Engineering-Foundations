"""
未分類項目の分類候補提示 — 後始末を数秒で終わらせる。

🎯 【3日連続の後始末を潰す】ファイル名から分類先を推定する!

背景:
    #92 → #93 → #94 と、3日連続で「索引に載せ忘れて後からコミット」が起きた。
    #90 のガードは未分類の上限を5としているため、
    **溜まってからしか気づけない**。

    上限を1に下げるだけでも効くが、それだけでは
    「では何に分類するのか」を毎回考えることになる。

    本ファイルはファイル名のパターンから分類候補を推定し、
    後始末を「考える作業」から「確認する作業」へ変える。

    #97 で「ドキュメントは腐るがテストされたコードは腐らない」と書いたが、
    ここでは **運用手順そのものをコードに落とす** ——
    #75 の dlq_runbook() や #89 の deployment runbook と同じ思想である。

実行方法:
    python 95_classification_advisor.py       # 未分類項目と候補を表示
    pytest 95_advisor_contract_testing.py -v
"""
import importlib.util
import re
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


def load_index():
    return _load('90_repository_index.py', 'index_for_advisor')


# 🎯 【分類ルール】ファイル名のパターン -> 推定される関心。
#    上から順に評価し、最初に一致したものを採用する。
#    順序が意味を持つため dict ではなくリストで持つ。
CLASSIFICATION_RULES = [
    (r'(narrative|script|index|advisor|sibling)', 'meta'),
    (r'(data_quality|quality|drift|freshness)', 'data_quality'),
    (r'(guard|testing|validation|coverage|discovery)', 'testing'),
    (r'(dlq|redrive|dead_letter)', 'fault_tolerance'),
    (r'(flex_template|build|deployment|runbook)', 'deployment'),
    (r'(monitoring|logging|alerting|observability)', 'observability'),
    (r'(iam|service_account|privilege)', 'security'),
    (r'(cost|optimization|partition)', 'cost'),
    (r'(window|session)', 'windowing'),
    (r'(merge|upsert|idempoten)', 'idempotency'),
    (r'(terraform|\.tf$)', 'iac'),
    (r'(composer|airflow|orchestrat)', 'orchestration'),
    (r'(side_input|join|enrich)', 'joins'),
    (r'(pubsub|bq_read|bq_write|ingest)', 'ingestion'),
]


def find_files_for_item(number: int) -> list:
    """項目番号に対応する実ファイル名を返す。"""
    return sorted(
        p.name for p in HERE.iterdir()
        if p.is_file() and p.name.startswith(f'{number}_')
    )


def suggest_concern(filename: str) -> str:
    """
    🔍 ファイル名から分類先を推定する純粋関数。

    ルールに一致しなければ None を返す——
    推測できないことを推測できたふりで隠さない。
    """
    lowered = filename.lower()
    for pattern, concern in CLASSIFICATION_RULES:
        if re.search(pattern, lowered):
            return concern
    return None


def advise() -> list:
    """
    📋 未分類項目それぞれに分類候補を付けて返す。

    各エントリは item・files・suggestion を持つ。
    suggestion が None なら手動判断が必要である。
    """
    index = load_index()

    advice = []
    for number in index.find_unindexed_items():
        files = find_files_for_item(number)
        suggestion = None
        for name in files:
            suggestion = suggest_concern(name)
            if suggestion:
                break
        advice.append({
            'item': number,
            'files': files,
            'suggestion': suggestion,
        })
    return advice


def render_advice() -> str:
    """未分類項目と候補を人間が読める形で出力する。"""
    items = advise()
    if not items:
        return '未分類はありません。索引は実体と一致しています。'

    lines = ['未分類の項目と分類候補:', '']
    for a in items:
        files = ', '.join(a['files']) or '(ファイルなし)'
        suggestion = a['suggestion'] or '(手動判断が必要)'
        lines.append(f"  #{a['item']}: {files}")
        lines.append(f"      -> CONCERN_MAP['{suggestion}'] に追加")
        lines.append('')
    return '\n'.join(lines)


if __name__ == '__main__':
    print("🚀 分類候補提示基盤の監査を開始するのね...")
    print(render_advice())
    print("🟢 監査完了!後始末を考える作業から確認する作業へ変える基盤が完全画定したのね!")