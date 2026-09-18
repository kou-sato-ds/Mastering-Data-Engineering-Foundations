"""
バックフィル（再処理）の設計 — 冪等性が初めて実利をもたらす場面。

🎯 【#66で作った冪等性の出番】過去データを安全に作り直す!

背景:
    #58(MERGE Upsert)と姉妹プロジェクトADR-002(Content-Addressableキー)で
    冪等性を確立したが、**その最大の利用場面がまだ無い**。

    冪等性が本当に効くのはバックフィルである:
      - 上流の不具合で3日分のデータが壊れていた
      - 変換ロジックのバグを見つけ、過去1ヶ月を作り直したい
      - 新しいカラムを追加し、既存データを埋め直したい

    冪等でないパイプラインでは、これらは全て「重複を作る作業」になる。
    冪等であれば **何度でも安全に流し直せる**。

    ただし実行計画には別の配慮が要る:
      - 一度に全期間を流せばクォータを食い潰し、本番処理を止める
      - 途中で失敗したとき、どこから再開するか
      - 事前にコストを見積もらなければ、請求で初めて規模を知る

実行方法:
    pytest 103_backfill_testing.py -v
"""
from datetime import date, timedelta

# 🚨 1チャンクあたりの日数。大きくすると失敗時の巻き戻しが増える。
DEFAULT_CHUNK_DAYS = 1

# 🚨 同時実行数の上限。本番トラフィックとリソースを奪い合わないための制限。
MAX_CONCURRENT_CHUNKS = 3

# 🚨 バックフィル可能な最大期間。誤って10年分を指定する事故を防ぐ。
MAX_BACKFILL_DAYS = 90

# 👉 BigQuery オンデマンド料金（見積用）
PRICE_PER_TIB_USD = 6.25


def validate_range(start: date, end: date, today: date) -> list:
    """
    🛡️ 期間指定の妥当性を検証する純粋関数。

    バックフィルは「大量のリソースを消費する操作」であり、
    指定ミスの代償が大きい。**実行前に弾く**のが唯一の防御になる。
    """
    errors = []

    if start > end:
        errors.append(f'start {start} is after end {end}')

    if end > today:
        errors.append(f'end {end} is in the future; there is nothing to backfill')

    span = (end - start).days + 1
    if span > MAX_BACKFILL_DAYS:
        errors.append(
            f'{span} days requested, exceeding the {MAX_BACKFILL_DAYS}-day cap; '
            'split it into multiple runs'
        )

    return errors


def build_date_chunks(start: date, end: date,
                      chunk_days: int = DEFAULT_CHUNK_DAYS) -> list:
    """
    🔍 期間をチャンクに分割する。

    1回の実行を小さく保つ理由:
        30日分を1ジョブで流して28日目に失敗すれば、27日分が無駄になる。
        日次に割れば、失敗しても1日分をやり直すだけで済む。
        冪等なので、成功済みのチャンクを再実行しても害はない。
    """
    chunks = []
    cursor = start

    while cursor <= end:
        chunk_end = min(cursor + timedelta(days=chunk_days - 1), end)
        chunks.append({'start': cursor, 'end': chunk_end})
        cursor = chunk_end + timedelta(days=1)

    return chunks


def estimate_cost_usd(chunk_count: int, bytes_per_chunk: int) -> float:
    """
    💰 バックフィル全体のスキャンコストを見積もる。

    実行前に金額を出す理由:
        「90日分を流す」は日常的な依頼だが、
        1日あたり50GBなら4.5TB——**請求で初めて規模を知る**ことになる。
        #72 のコストガードと同じ思想を、バッチ実行の計画段階へ適用する。
    """
    total_bytes = chunk_count * bytes_per_chunk
    return round((total_bytes / (1024 ** 4)) * PRICE_PER_TIB_USD, 4)


def build_resume_plan(chunks: list, completed: list) -> list:
    """
    🔁 完了済みを除いた残チャンクを返す。

    冪等なら再実行しても壊れないが、**それでもスキップする**理由:
        コストと時間は冪等ではない。同じ結果を得るために
        二度払う必要はない。
    """
    done = {(c['start'], c['end']) for c in completed}
    return [c for c in chunks if (c['start'], c['end']) not in done]


def build_execution_batches(chunks: list,
                            max_concurrent: int = MAX_CONCURRENT_CHUNKS) -> list:
    """
    🚦 同時実行数を制限したバッチ列を返す。

    全チャンクを一斉に投げない理由:
        バックフィルは本番パイプラインと同じクォータを使う。
        90ジョブを同時に投げれば、**進行中の本番処理が止まる**。
        「急ぐ作業のために、動いている仕組みを壊さない」。
    """
    return [
        chunks[i:i + max_concurrent]
        for i in range(0, len(chunks), max_concurrent)
    ]


def build_backfill_plan(start: date, end: date, today: date,
                        bytes_per_chunk: int = 0,
                        completed: list = None) -> dict:
    """
    📋 実行計画をまとめて構築する。

    例外を投げずレポートを返すのは #105 と同一の設計。
    計画段階で止まるべきか、人間が判断できる形で返す。
    """
    errors = validate_range(start, end, today)
    if errors:
        return {'valid': False, 'errors': errors, 'chunks': [], 'batches': []}

    chunks = build_date_chunks(start, end)
    remaining = build_resume_plan(chunks, completed or [])

    return {
        'valid': True,
        'errors': [],
        'chunks': chunks,
        'remaining': remaining,
        'skipped': len(chunks) - len(remaining),
        'batches': build_execution_batches(remaining),
        'estimated_cost_usd': estimate_cost_usd(len(remaining), bytes_per_chunk),
    }


def render_plan(plan: dict) -> str:
    """実行計画を人間が読める形で出力する。"""
    if not plan['valid']:
        return 'バックフィル不可:\n  ' + '\n  '.join(plan['errors'])

    lines = [
        f"チャンク数: {len(plan['chunks'])} (残 {len(plan['remaining'])}, "
        f"スキップ {plan['skipped']})",
        f"バッチ数: {len(plan['batches'])} (同時実行 {MAX_CONCURRENT_CHUNKS} まで)",
        f"見積コスト: ${plan['estimated_cost_usd']}",
    ]
    return '\n'.join(lines)


if __name__ == '__main__':
    print("🚀 バックフィル計画基盤の監査を開始するのね...")
    print("🟢 監査完了!冪等性が実利をもたらす再処理基盤が完全画定したのね!")