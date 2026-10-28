"""
カナリアリリースの昇格判定 — 旧版と比べて悪化していないかを、2標本の比率の検定で決める。

背景:
    新しい版を一部のリクエストだけに流し(カナリア)、旧版(ベースライン)と失敗率を比べる。
    件数が少ないうちに「失敗0件だから安全」と昇格すれば、偶然を根拠にすることになる。
    逆に件数が多いと、0.03% のような実務上無意味な差まで統計的に有意になる。

方針:
    - 明らかに壊れている(失敗率が hard_max 超)なら、件数が少なくても即 rollback
    - 件数が min_requests 未満なら wait(失敗が見えないことは安全の証拠ではない)
    - 片側 z 検定で有意(z >= Z_CRITICAL)かつ、差が abs_margin を超えるときだけ rollback
    - それ以外は promote
"""
from __future__ import annotations

import math
from dataclasses import dataclass

Z_CRITICAL = 1.645  # 片側 5%


def _rate(errors: int, total: int) -> float:
    """失敗率。不正な件数は止める。"""
    if errors < 0 or total < 0 or errors > total:
        raise ValueError(f'invalid counts: errors={errors}, total={total}')
    return errors / total if total else 0.0


def two_proportion_z(base_err: int, base_n: int, can_err: int, can_n: int) -> float:
    """カナリアが旧版より悪いほど大きくなる z 値(合併比率を使う)。"""
    p_base, p_can = _rate(base_err, base_n), _rate(can_err, can_n)
    if base_n == 0 or can_n == 0:
        return 0.0
    pooled = (base_err + can_err) / (base_n + can_n)
    se = math.sqrt(pooled * (1 - pooled) * (1 / base_n + 1 / can_n))
    diff = p_can - p_base
    if se == 0:
        return 0.0 if diff == 0 else math.copysign(math.inf, diff)
    return diff / se


@dataclass(frozen=True)
class Decision:
    """判定。action は promote / wait / rollback。"""
    action: str
    reason: str


def decide(baseline: tuple[int, int], canary: tuple[int, int], min_requests: int = 500,
           abs_margin: float = 0.001, hard_max: float = 0.05, early_min: int = 20) -> Decision:
    """baseline / canary は (失敗数, 全数)。"""
    base_rate, can_rate = _rate(*baseline), _rate(*canary)
    if canary[1] >= early_min and can_rate > hard_max:
        return Decision('rollback', f'canary error rate {can_rate:.2%} exceeds {hard_max:.0%}')
    if canary[1] < min_requests:
        return Decision('wait', f'only {canary[1]} canary requests (< {min_requests})')
    z = two_proportion_z(*baseline, *canary)
    diff = can_rate - base_rate
    if z >= Z_CRITICAL and diff > abs_margin:
        return Decision('rollback', f'z={z:.2f}, canary worse by {diff:.2%}')
    return Decision('promote', f'z={z:.2f}, difference {diff:.2%}')
