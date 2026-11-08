"""
再計算の範囲 — 元データの一部を直したとき、下流のどの日を作り直すかを割り出す。

背景:
    7日移動平均のように過去を読む集計は、11/3 の元データを直すと 11/3〜11/9 の結果が全部変わる。
    直した日だけ作り直すと、数字が食い違ったまま残る。

方針:
    - 派生テーブルごとに lookback_days(出力1日分が読む入力の日数。当日を含む)を持つ
    - 上流の変わった日 c に対し、出力の c〜c+lookback-1 日を作り直す
    - 依存の順(トポロジカル順)に下流へ伝える。until より先の日は作らない
    - 元データは変わっていないものも空の集合で全部渡す。知らない上流は止める
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from graphlib import TopologicalSorter


@dataclass(frozen=True)
class Derived:
    """派生テーブル。upstreams を読み、出力1日分に lookback_days 日分の入力を使う。"""
    upstreams: tuple[str, ...]
    lookback_days: int = 1


def recompute_scope(sources_changed: dict[str, set[date]], tables: dict[str, Derived],
                    until: date) -> dict[str, list[date]]:
    """派生テーブルごとに、作り直す日を返す。"""
    for name, t in tables.items():
        if t.lookback_days < 1:
            raise ValueError(f'{name}: lookback_days must be at least 1')
        unknown = [u for u in t.upstreams if u not in tables and u not in sources_changed]
        if unknown:
            raise ValueError(f'{name}: unknown upstream {unknown}')
    affected: dict[str, set[date]] = {s: set(days) for s, days in sources_changed.items()}
    order = TopologicalSorter({n: set(t.upstreams) for n, t in tables.items()}).static_order()
    for name in order:
        if name not in tables:
            continue
        t = tables[name]
        days: set[date] = set()
        for upstream in t.upstreams:
            for changed in affected[upstream]:
                for k in range(t.lookback_days):
                    day = changed + timedelta(days=k)
                    if day <= until:
                        days.add(day)
        affected[name] = days
    return {name: sorted(affected[name]) for name in tables}
