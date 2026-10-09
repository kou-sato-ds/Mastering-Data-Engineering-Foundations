"""
上流データの到着待ち(レディネス判定) — 「今朝のレポートが空っぽ」を防ぐ。

背景:
    定刻で集計を走らせると、上流のデータがまだ届いていない(書きかけの)うちに
    処理が始まることがある。エラーは出ず、空や欠けた数字がそのまま配られる。

    本ファイルは「走ってよいか」を判定する:
      - ファイルがあるかではなく、書き終わった印(完了マーカー)があるかで判断する
      - 件数が最低ラインに届いていなければ待つ
      - 締切を過ぎたら、一部だけで走らずに失敗として知らせる
        (欠けた数字を配るより、届かないことを伝える方が正しい)

    #67 の Composer DAG が「いつ・どの順で走らせるか」なら、
    本ファイルは「今走ってよいか」を扱う。
    #117 のラチェットにより、公開関数は100%型付き。
"""
from __future__ import annotations

from dataclasses import dataclass

RUN = 'run'
WAIT = 'wait'
FAIL = 'fail'


@dataclass(frozen=True)
class Upstream:
    name: str
    partition_exists: bool
    has_success_marker: bool
    row_count: int
    min_rows: int


def not_ready_reasons(u: Upstream) -> list[str]:
    """
    1つの上流が「まだ使えない」理由を返す。空なら準備完了。

    完了マーカーが無ければ、行数が十分に見えても書きかけかもしれない。
    """
    if not u.partition_exists:
        return [f'{u.name}: partition has not arrived']
    reasons: list[str] = []
    if not u.has_success_marker:
        reasons.append(f'{u.name}: no completion marker; the write may still be in progress')
    if u.row_count < u.min_rows:
        reasons.append(f'{u.name}: {u.row_count} rows, below the minimum of {u.min_rows}')
    return reasons


def check_all(upstreams: list[Upstream]) -> list[str]:
    """全ての上流の未準備理由をまとめて返す。"""
    reasons: list[str] = []
    for u in sorted(upstreams, key=lambda x: x.name):
        reasons += not_ready_reasons(u)
    return reasons


def decide(upstreams: list[Upstream], waited_seconds: float, timeout_seconds: float) -> str:
    """
    run / wait / fail を返す。

    準備が整っていなければ決して run を返さない。
    締切を過ぎたら fail。一部の上流だけで走る選択肢は用意しない。
    上流が1つも登録されていなければ fail(何を待つべきか分からない状態で走らせない)。
    """
    if not upstreams:
        return FAIL
    if not check_all(upstreams):
        return RUN
    if waited_seconds >= timeout_seconds:
        return FAIL
    return WAIT


def next_poll(waited_seconds: float, interval_seconds: float, timeout_seconds: float) -> float:
    """次に確認するまでの秒数。締切を越えて待たない。"""
    remaining = max(timeout_seconds - waited_seconds, 0.0)
    return min(interval_seconds, remaining)


def render_status(upstreams: list[Upstream], decision: str) -> str:
    """担当者に送る状況報告。fail のときは、何が届いていないかを並べる。"""
    lines = [f'判定: {decision}']
    lines += [f'- {r}' for r in check_all(upstreams)]
    return '\n'.join(lines)