"""
集計の加法性 — その数値を、その方向に足してよいかを集計の前に確かめる。

背景:
    スター・スキーマの数値には3種類あり、足し方を間違えると集計が黙って嘘になる。
      additive      : 売上・件数。どの方向に足してもよい
      semi_additive : 口座残高・在庫数。店舗をまたいで足すのはよいが、日をまたいで足すと二重に数える
      non_additive  : 率・単価。足しても平均しても正しくない。分子と分母から計算し直す

方針:
    - 数値ごとに種類と時間の軸(既定 date)を宣言する
    - 集計で畳む(collapsed)軸と、使う関数から問題を返す
        semi_additive を時間の軸で sum → 問題(last / avg / min / max を使う)
        non_additive を sum / avg → 問題(recompute = 分子と分母から計算し直す)
    - 知らない数値・知らない関数は止める
"""
from __future__ import annotations

from dataclasses import dataclass

VALID_KINDS = frozenset({'additive', 'semi_additive', 'non_additive'})
FUNCTIONS = frozenset({'sum', 'avg', 'min', 'max', 'last', 'recompute'})


@dataclass(frozen=True)
class Measure:
    """数値の定義。kind は additive / semi_additive / non_additive。"""
    name: str
    kind: str
    time_dim: str = 'date'

    def __post_init__(self) -> None:
        if self.kind not in VALID_KINDS:
            raise ValueError(f'unknown kind: {self.kind}')


def check_aggregation(measures: dict[str, Measure], aggregations: dict[str, str],
                      collapsed: set[str]) -> list[str]:
    """aggregations は「数値 → 関数」。collapsed は集計で畳む軸。問題の一覧を返す。"""
    problems: list[str] = []
    for name, func in sorted(aggregations.items()):
        if name not in measures:
            raise ValueError(f'unknown measure: {name}')
        if func not in FUNCTIONS:
            raise ValueError(f'unknown function: {func}')
        measure = measures[name]
        if measure.kind == 'semi_additive' and func == 'sum' and measure.time_dim in collapsed:
            problems.append(f'{name}: summing a balance over {measure.time_dim} double counts; '
                            'use last, avg, min or max')
        if measure.kind == 'non_additive' and func in ('sum', 'avg'):
            problems.append(f'{name}: a ratio cannot be {func}-ed; '
                            'recompute it from its numerator and denominator')
    return problems
