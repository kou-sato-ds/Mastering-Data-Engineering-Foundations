"""
パーティション刈り込みの検査 — 日付で分けたテーブルを、本当に日付で絞って読んでいるか。

背景:
    日付パーティションのテーブルに日付で絞らないクエリを投げると、全期間を読む。
    従量課金のクエリエンジンでは、1回で大きな費用になる。
    さらに CAST(dt AS STRING) LIKE '2026-11%' のように、パーティション列を関数で包むと
    「絞っているつもりで、刈り込めていない」状態になる。

方針:
    - 条件は SQL の文字列ではなく構造(Filter)で受け取る(dry-run や実行計画から取り出す想定)
    - パーティション列への範囲条件だけで刈り込む。範囲は半開区間 [start, end)
    - パーティション列でも prunable=False の条件(関数で包んだもの)は刈り込みに使わず、理由を残す
    - 刈り込めていない・読み込み量が上限を超える、を問題として返す
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class Filter:
    """クエリの条件1つ。prunable=False は、列を関数で包むなどして刈り込みに使えないもの。"""
    column: str
    start: date | None = None
    end: date | None = None
    prunable: bool = True


@dataclass
class ScanPlan:
    """読むことになるパーティションと量。"""
    partitions: list[date]
    bytes_scanned: int
    pruned: bool
    ignored: list[str] = field(default_factory=list)


def plan_scan(partition_bytes: dict[date, int], partition_column: str,
              filters: list[Filter]) -> ScanPlan:
    """条件から、読むパーティションを決める。"""
    usable = [f for f in filters if f.column == partition_column and f.prunable]
    ignored = [f'filter on {f.column} cannot prune (wrapped in an expression)'
               for f in filters if f.column == partition_column and not f.prunable]
    if not usable:
        selected = sorted(partition_bytes)
    else:
        starts = [f.start for f in usable if f.start is not None]
        ends = [f.end for f in usable if f.end is not None]
        lo, hi = (max(starts) if starts else None), (min(ends) if ends else None)
        selected = sorted(d for d in partition_bytes
                          if (lo is None or d >= lo) and (hi is None or d < hi))
    return ScanPlan(selected, sum(partition_bytes[d] for d in selected), bool(usable), ignored)


def review(plan: ScanPlan, total_partitions: int, max_bytes: int) -> list[str]:
    """問題を返す。空なら実行してよい。"""
    problems: list[str] = []
    if not plan.pruned:
        problems.append(f'no usable partition filter: full scan of {total_partitions} partitions')
        problems.extend(plan.ignored)
    if plan.bytes_scanned > max_bytes:
        problems.append(f'scans {plan.bytes_scanned} bytes (> {max_bytes})')
    return problems
