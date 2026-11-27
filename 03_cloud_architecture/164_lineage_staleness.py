"""
鮮度の伝わり方 — 表の「データの時点」を入力から辿り、古い理由になっている元データを示す。

背景:
    ダッシュボードの表が今朝作り直されていても、元のデータが昨日から止まっていれば中身は昨日のまま。
    表の作成時刻だけを見る監視では気づけない。

方針:
    - 元データ(source)の時点は、最後に更新された時刻
    - 派生した表の時点 = min(作った時刻, 入力の時点のうち一番古いもの)
      (古い材料を混ぜた結果は古い方まで。元が更新されても作り直すまでは古いまま)
    - その時点を決めた元(root)を一緒に覚える。作った時刻で決まったなら、その表自身
    - 古すぎる表は「表: 何時間前 <- 原因」の形で返す。直す場所がすぐ分かる
    - 知らない入力・作った時刻の欠け・循環は止める
"""
from __future__ import annotations

from datetime import datetime, timedelta
from graphlib import CycleError, TopologicalSorter

AsOf = dict[str, tuple[datetime, str]]


def data_as_of(sources: dict[str, datetime], tables: dict[str, tuple[str, ...]],
               built_at: dict[str, datetime]) -> AsOf:
    """表ごとに (データの時点, その時点を決めた元) を返す。元データも含む。"""
    for name, upstreams in tables.items():
        unknown = [u for u in upstreams if u not in tables and u not in sources]
        if unknown:
            raise ValueError(f'{name}: unknown input {unknown}')
        if name not in built_at:
            raise ValueError(f'{name}: missing build time')
    result: AsOf = {name: (ts, name) for name, ts in sources.items()}
    try:
        order = list(TopologicalSorter({n: set(u) for n, u in tables.items()}).static_order())
    except CycleError as error:
        raise ValueError(f'cycle: {error.args[1]}') from error
    for name in order:
        if name not in tables:
            continue
        candidates = [result[u] for u in tables[name]] + [(built_at[name], name)]
        result[name] = min(candidates, key=lambda c: c[0])
    return result


def stale_tables(as_of: AsOf, now: datetime, max_age: timedelta) -> list[str]:
    """max_age より古い表を「表: N時間前 <- 原因」で返す。"""
    report: list[str] = []
    for name in sorted(as_of):
        ts, root = as_of[name]
        age = now - ts
        if age > max_age:
            report.append(f'{name}: {int(age.total_seconds() // 3600)}h old <- {root}')
    return report
