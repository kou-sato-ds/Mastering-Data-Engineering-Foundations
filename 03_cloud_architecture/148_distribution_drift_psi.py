"""
分布のずれ検知(PSI) — 件数も型も正しいのに、値の分布だけが変わったことを見つける。

背景:
    上流の単位変更(歳 → 月)や不具合(金額がゼロ寄りになる)は、エラーにならない。
    件数・型・null の検査は全部通るので、集計結果がおかしいと言われて初めて気づく。

方針:
    - 基準期間の値から、同じ件数ずつ入る区切り(分位点)を作る
    - 基準と今回を同じ区切りで数え、PSI = Σ (今回の割合 - 基準の割合) × ln(今回 / 基準)
    - 割合が 0 の区間は EPSILON に置き換える(無限大にしない)
    - PSI < 0.1 は stable、0.25 未満は moderate、それ以上は major(業界でよく使う目安)
    - 区間の数より値が少ないと区切りが作れないので止める
"""
from __future__ import annotations

import math
from bisect import bisect_right
from dataclasses import dataclass

EPSILON = 1e-4


def quantile_edges(values: list[float], bins: int) -> list[float]:
    """基準の値を bins 個の区間に同じ件数ずつ分ける、内側の区切り。"""
    ordered = sorted(values)
    return sorted({ordered[len(ordered) * i // bins] for i in range(1, bins)})


def bin_counts(values: list[float], edges: list[float]) -> list[int]:
    """各区間に入る値の数。"""
    counts = [0] * (len(edges) + 1)
    for value in values:
        counts[bisect_right(edges, value)] += 1
    return counts


def psi(expected: list[int], actual: list[int]) -> float:
    """Population Stability Index。0 なら同じ分布。"""
    total_e, total_a = sum(expected), sum(actual)
    result = 0.0
    for e, a in zip(expected, actual):
        pe, pa = max(e / total_e, EPSILON), max(a / total_a, EPSILON)
        result += (pa - pe) * math.log(pa / pe)
    return result


@dataclass(frozen=True)
class DriftResult:
    """PSI の値と、stable / moderate / major の判定。"""
    psi: float
    level: str


def evaluate(baseline: list[float], current: list[float], bins: int = 10) -> DriftResult:
    """基準 baseline と今回 current の分布のずれを判定する。"""
    if bins < 2:
        raise ValueError('bins must be at least 2')
    if len(baseline) < bins or len(current) < bins:
        raise ValueError(f'need at least {bins} values on each side')
    edges = quantile_edges(baseline, bins)
    value = psi(bin_counts(baseline, edges), bin_counts(current, edges))
    level = 'stable' if value < 0.1 else 'moderate' if value < 0.25 else 'major'
    return DriftResult(value, level)
