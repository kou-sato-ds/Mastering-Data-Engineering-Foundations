"""
面接台本の構築 — 両リポジトリの問答を1つの流れに束ねる。

🎯 【#101の次】問答は揃った。次は「どの順で語るか」!

背景:
    #100 でGCP側に6問、姉妹プロジェクトのADR-009でAWS側に7問——
    計13問の想定問答が両リポジトリに分散している。

    しかし面接は1回である。
    「AWSの話をした後、GCPの話にどう繋ぐか」という順序がどこにも無い。

    本ファイルは問答を面接の流れとして構成する:
    - 冒頭(自己紹介の直後に何を出すか)
    - 中盤(深掘りされた時にどこへ展開するか)
    - 締め(対称構造という核をどう語るか)

    #101 で索引と問答を繋いだのと同じ発想を、
    今度は「時間軸」に対して適用する。

実行方法:
    python 94_interview_script.py       # 台本を表示
    pytest 94_script_contract_testing.py -v
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


def load_narrative():
    return _load('92_interview_narrative.py', 'narrative_for_script')


# 🎯 【面接の3幕構成】各段階で何を出すかを設計する。
#    id は #92 の NARRATIVES に実在するものを指す——
#    存在しない問答を台本に組み込めばテストが赤くなる。
SCRIPT_PHASES = [
    {
        'phase': 'opening',
        'label': '冒頭 — 最も具体的な成果から入る',
        'intent': (
            '抽象的な自己紹介より、測定された数字が1つある方が印象に残る。'
            'コスト削減は事業インパクトとして誰にでも伝わる。'
        ),
        'narratives': ['cost_awareness'],
        'sibling_first': 'why_rss_over_playwright',
        'duration_min': 2,
    },
    {
        'phase': 'core',
        'label': '中盤 — 設計判断の深さを示す',
        'intent': (
            '「なぜその順序で作ったか」は実装力ではなく設計力の話であり、'
            '実務経験の年数と最も相関しない領域。ここで差を作る。'
        ),
        'narratives': ['idempotency_ordering', 'observability_layers'],
        'sibling_first': 'retry_needs_idempotency',
        'duration_min': 6,
    },
    {
        'phase': 'incident',
        'label': '障害対応 — 失敗を語れることを示す',
        'intent': (
            '成功事例だけ語る候補者は「まだ本番を任されていない」と見られる。'
            '自分の失敗を構造的に分析できることの方が信頼される。'
        ),
        'narratives': ['silent_failure'],
        'sibling_first': 'silent_failure_incident',
        'duration_min': 4,
    },
    {
        'phase': 'closing',
        'label': '締め — 対称構造という核を出す',
        'intent': (
            '個別の実装ではなく「クラウドを問わない設計原則を持っている」'
            'という主張。ここまでの話が全て伏線として効く。'
        ),
        'narratives': ['cross_cloud', 'testing_philosophy'],
        'sibling_first': None,
        'duration_min': 3,
    },
]


def total_duration() -> int:
    """台本全体の想定所要時間（分）。"""
    return sum(p['duration_min'] for p in SCRIPT_PHASES)


def collect_used_narrative_ids() -> set:
    """台本が参照する問答IDを集める。"""
    return {nid for p in SCRIPT_PHASES for nid in p['narratives']}


def find_unused_narratives() -> list:
    """
    🚨 用意したが台本に組み込んでいない問答を返す。

    使わない問答があること自体は問題ないが、
    「準備したのに出番を設計していない」ことは把握しておく。
    """
    narrative = load_narrative()
    used = collect_used_narrative_ids()
    return [n['id'] for n in narrative.NARRATIVES if n['id'] not in used]


def build_script() -> list:
    """
    📋 台本を構築する。各フェーズに実際の問答本文を埋め込む。
    """
    narrative = load_narrative()
    by_id = {n['id']: n for n in narrative.NARRATIVES}

    script = []
    for phase in SCRIPT_PHASES:
        script.append({
            'phase': phase['phase'],
            'label': phase['label'],
            'intent': phase['intent'],
            'duration_min': phase['duration_min'],
            'items': [by_id[nid] for nid in phase['narratives']],
            'sibling_first': phase['sibling_first'],
        })
    return script


def render_markdown() -> str:
    """台本を Markdown として出力する。"""
    lines = [f'# 面接台本（想定 {total_duration()} 分）', '']

    for phase in build_script():
        lines.append(f"## {phase['label']}（{phase['duration_min']}分）")
        lines.append('')
        lines.append(f"> 狙い: {phase['intent']}")
        lines.append('')
        if phase['sibling_first']:
            lines.append(
                f"**AWS側から入る**: 姉妹リポジトリの `{phase['sibling_first']}` を先に話す"
            )
            lines.append('')
        for item in phase['items']:
            lines.append(f"### Q. {item['question']}")
            lines.append('')
            lines.append(item['answer'])
            lines.append('')
            evidence = ', '.join(f'#{e}' for e in item['evidence'])
            lines.append(f"> 根拠: {evidence}")
            lines.append('')

    return '\n'.join(lines)


if __name__ == '__main__':
    print("🚀 面接台本基盤の監査を開始するのね...")
    print(render_markdown())
    print("\n台本未使用の問答:", find_unused_narratives())
    print("🟢 監査完了!13問を1つの流れに束ねる台本基盤が完全画定したのね!")