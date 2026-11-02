"""
ファクトの粒度検査 — 宣言した粒度で1行に定まっているかを確かめる。

背景:
    スター・スキーマで最初に決めるのは「1行が何を表すか」(粒度 = grain)である。
    例: 日付 × 店舗 × 商品 で1行。この粒度で同じキーの行が2つあると、
    SUM(売上) が黙って倍になる。エラーは出ない。

方針:
    - 粒度の列の値の組をキーにして、同じキーの行を数える
    - 完全に同じ行の重複(exact)と、キーは同じで中身が違う重複(conflicting)を分ける。
      前者は落とせば済むが、後者はどちらが正しいか人が決める必要がある。勝手に捨てない
    - 粒度の列が空(None / 空文字)の行は、どのキーにも属さないので別に数える
    - 粒度が空の宣言は止める(何も検査していないのに「問題なし」になる)
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

Key = tuple[Any, ...]


@dataclass
class GrainReport:
    """粒度検査の結果。"""
    total: int
    null_key_rows: int = 0
    exact_duplicates: dict[Key, int] = field(default_factory=dict)
    conflicting: dict[Key, int] = field(default_factory=dict)

    @property
    def extra_rows(self) -> int:
        """粒度どおりなら存在しないはずの行の数(合計を膨らませている行)。"""
        counts = list(self.exact_duplicates.values()) + list(self.conflicting.values())
        return sum(c - 1 for c in counts)

    @property
    def ok(self) -> bool:
        """粒度どおりに1行ずつか。"""
        return self.null_key_rows == 0 and not self.exact_duplicates and not self.conflicting


def check_grain(rows: list[dict[str, Any]], grain: tuple[str, ...]) -> GrainReport:
    """rows が grain の列の組で1行ずつに定まっているかを調べる。"""
    if not grain:
        raise ValueError('grain must name at least one column')
    report = GrainReport(total=len(rows))
    groups: dict[Key, list[str]] = {}
    for row in rows:
        key = tuple(row.get(column) for column in grain)
        if any(value is None or value == '' for value in key):
            report.null_key_rows += 1
            continue
        groups.setdefault(key, []).append(
            json.dumps(row, sort_keys=True, default=str, ensure_ascii=False))
    for key, payloads in groups.items():
        if len(payloads) > 1:
            target = report.exact_duplicates if len(set(payloads)) == 1 else report.conflicting
            target[key] = len(payloads)
    return report
