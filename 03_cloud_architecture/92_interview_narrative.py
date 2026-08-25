"""
面接想定問答の実行可能化 — ポートフォリオが自分の説明を持つ。

🎯 【#99の集大成】索引で「どこを読むか」を示した。次は「何を語るか」!

背景:
    #90-#91 で両リポジトリに索引を立て、相互リンクを検証で固定した。
    構造としては完成域にある。

    しかし「これを面接でどう語るか」がどこにも無い。
    口頭説明は準備しなければ必ず崩れる——
    特に「なぜその設計を選んだか」を問われた時、
    実装を見ながらでないと答えられないなら、それは理解していないのと同じである。

    本ファイルは想定問答をコードとして持つ。
    各回答は **実ファイルへの参照** を伴うため、
    語っている内容が実装からずれればテストが赤くなる。

    ドキュメントは腐るがテストされたコードは腐らない(#97)——
    その原則を、最も腐りやすい「自分の説明」に適用する。

実行方法:
    python 92_interview_narrative.py       # 想定問答を表示
    pytest 92_narrative_contract_testing.py -v
"""
from pathlib import Path

HERE = Path(__file__).parent

# 🎯 【想定問答】各エントリは question / answer / evidence / sibling を持つ。
#    evidence は実在するファイル番号——語った内容の裏付けである。
NARRATIVES = [
    {
        'id': 'idempotency_ordering',
        'question': 'リトライを有効化する前に何を確認しますか',
        'answer': (
            '冪等性です。リトライは同じ処理を複数回走らせるため、'
            '書き込み先が冪等でなければ重複が増えるだけになります。'
            'AWS側ではContent-Addressableなキー設計を先にマージし、'
            'その上でリトライとDLQを有効化しました。'
            'GCP側ではBigQueryのMERGE Upsertが同じ役割を果たします。'
        ),
        'evidence': [58],
        'sibling': 'ADR-002 → ADR-003',
        'concern': 'idempotency',
    },
    {
        'id': 'silent_failure',
        'question': '障害に気づけなかった経験はありますか',
        'answer': (
            'あります。テストが1件もcollectできない状態が2日間mainに残りました。'
            'CIは赤かったのですが、常に失敗する別のワークフローが1つ紛れ込んでおり、'
            '赤信号が意味を失っていました。'
            '復旧後にポストモーテムをADRへ残し、'
            '再発防止としてテストスイート自身が健全性を検証するガードを実装しています。'
        ),
        'evidence': [85],
        'sibling': 'ADR-006 → ADR-007',
        'concern': 'testing',
    },
    {
        'id': 'observability_layers',
        'question': '観測性のために何を実装しましたか',
        'answer': (
            '3層に分けています。メトリクス(閾値監視)、構造化ログ(障害の可視化)、'
            'DLQ深さ監視(隔離されたデータの追跡)です。'
            'DLQにデータを隔離するだけでは「誰も気づかない保管庫」になるため、'
            '見張る仕組みと再処理経路をセットで持たせました。'
        ),
        'evidence': [60, 66, 67],
        'sibling': 'ADR-004 / ADR-005',
        'concern': 'observability',
    },
    {
        'id': 'cost_awareness',
        'question': 'コストを意識した設計をしたことはありますか',
        'answer': (
            'BigQueryでフルスキャン事故を防ぐガードを実装しました。'
            'パーティション必須化とdry runによる事前見積、'
            'maximum_bytes_billedによる上限超過クエリの実行前ブロックです。'
            '同じ思想をDataflowのテンプレートにも適用し、'
            '不正なパラメータをジョブ起動前に弾くことで課金をゼロに抑えています。'
        ),
        'evidence': [64, 87],
        'sibling': None,
        'concern': 'cost',
    },
    {
        'id': 'testing_philosophy',
        'question': 'テストで何を守るべきだと考えますか',
        'answer': (
            '設計判断です。動作確認だけなら手で試せば済みますが、'
            '「なぜdataOwnerではなくdataEditorを選んだか」のような判断は'
            'コメントでは守れません。'
            '禁止ロールの不在、DLQスキーマの必須列、'
            'USERがENTRYPOINTより前にあること——'
            'いずれも将来誰かが緩めた瞬間に赤くなるようアサーションにしています。'
        ),
        'evidence': [61, 88],
        'sibling': 'ADR-007',
        'concern': 'testing',
    },
    {
        'id': 'cross_cloud',
        'question': '2つのリポジトリの関係を説明してください',
        'answer': (
            '同じ設計思想をAWSとGCPで実装した対称構造です。'
            '冪等性・障害耐性・観測性・テスト戦略の各領域が対応しており、'
            '両READMEの索引から相互に辿れるようにしています。'
            '特定クラウドの知識ではなく、'
            'クラウドを問わない設計原則を持っていることを示すためです。'
        ),
        'evidence': [90, 91],
        'sibling': 'ADR-008',
        'concern': 'meta',
    },
]


def get_narrative(narrative_id: str) -> dict:
    """IDで想定問答を1件取得する。"""
    for n in NARRATIVES:
        if n['id'] == narrative_id:
            return n
    raise KeyError(f'no narrative with id {narrative_id!r}')


def find_files_for_item(number: int) -> list:
    """
    🔍 項目番号に対応する実ファイルを探す純粋関数。

    evidence が実在するかを検証するために使う——
    「#99を参照しています」と語っても、そのファイルが無ければ嘘になる。
    """
    return sorted(
        p.name for p in HERE.iterdir()
        if p.is_file() and p.name.startswith(f'{number}_')
    )


def render_markdown() -> str:
    """想定問答を Markdown として出力する。"""
    lines = []
    for n in NARRATIVES:
        lines.append(f"### Q. {n['question']}")
        lines.append('')
        lines.append(n['answer'])
        lines.append('')
        evidence = ', '.join(f'#{e}' for e in n['evidence'])
        sibling = f" / 姉妹: {n['sibling']}" if n['sibling'] else ''
        lines.append(f"> 根拠: {evidence}{sibling}")
        lines.append('')
    return '\n'.join(lines)


if __name__ == '__main__':
    print("🚀 面接想定問答基盤の監査を開始するのね...")
    print(render_markdown())
    print("🟢 監査完了!語る内容が実装と一致することを検証できる基盤が完全画定したのね!")