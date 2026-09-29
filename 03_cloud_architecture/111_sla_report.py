"""
運用レポート(SLA / SLO) — 約束した水準を守れたか、あとどれだけ余裕があるか。

背景:
    発注者に「パイプラインは順調です」と伝えても、何も伝わらない。
    伝えるべきは数字である:
      - 成功率は目標(SLO)を満たしたか
      - 遅延は許容範囲か
      - 目標を割るまで、あと何回失敗してよいか(エラーバジェット)

    #68 のメトリクスと #75 の DLQ 深さを、人が読むレポートへまとめる。
"""
import math

SLO_SUCCESS_RATE = 0.99
SLO_P95_SECONDS = 300


def percentile(values, p):
    """
    最近傍順位法でパーセンタイルを返す。

    平均ではなく p95 を使う理由:
        100回中95回が10秒で終わり、5回が1時間かかっても、平均は約3分に見える。
        「たまに1時間待たされる」という発注者の体験は、平均には現れない。
    """
    if not values:
        return None
    ordered = sorted(values)
    rank = max(math.ceil(p / 100 * len(ordered)), 1)
    return ordered[rank - 1]


def summarize_runs(runs):
    """実行記録({'ok': bool, 'seconds': float})を集計する。"""
    total = len(runs)
    succeeded = sum(1 for r in runs if r['ok'])
    return {
        'total': total,
        'succeeded': succeeded,
        'failed': total - succeeded,
        'success_rate': (succeeded / total) if total else None,
        'p95_seconds': percentile([r['seconds'] for r in runs if r['ok']], 95),
    }


def error_budget(summary, slo=SLO_SUCCESS_RATE):
    """
    エラーバジェット(許容できる失敗数)の残りを返す。

    「成功率 99.2%」より「あと2回失敗すると目標を割る」の方が、
    次に何をすべきかが伝わる。
    """
    if not summary['total']:
        return None
    allowed = math.floor(summary['total'] * (1 - slo))
    return {'allowed': allowed, 'used': summary['failed'], 'remaining': allowed - summary['failed']}


def evaluate(summary, dlq_depth=0):
    """
    SLO を評価する。

    実行が0件の期間は 'no_data' とする。
    分母0を「失敗0件=100%成功」と報告すれば、止まっていたことが隠れる。
    """
    if not summary['total']:
        return {'status': 'no_data', 'breaches': ['no runs recorded in this period']}

    breaches = []
    if summary['success_rate'] < SLO_SUCCESS_RATE:
        breaches.append(f"success rate {summary['success_rate']:.2%} below {SLO_SUCCESS_RATE:.0%}")
    if summary['p95_seconds'] is not None and summary['p95_seconds'] > SLO_P95_SECONDS:
        breaches.append(f"p95 {summary['p95_seconds']}s above {SLO_P95_SECONDS}s")
    if dlq_depth > 0:
        breaches.append(f'{dlq_depth} messages waiting in the DLQ')

    return {'status': 'breach' if breaches else 'ok', 'breaches': breaches}


def render_report(period, summary, budget, verdict):
    """発注者に送れる Markdown を返す。"""
    lines = [f'## 運用レポート {period}', '', f"- 判定: **{verdict['status']}**"]
    if summary['total']:
        lines += [
            f"- 実行: {summary['total']}回 / 成功率 {summary['success_rate']:.2%}",
            f"- 処理時間(p95): {summary['p95_seconds']}秒",
        ]
    if budget:
        lines.append(f"- エラーバジェット残: {budget['remaining']}回 (許容 {budget['allowed']}回)")
    for b in verdict['breaches']:
        lines.append(f'- ⚠️ {b}')
    return '\n'.join(lines)