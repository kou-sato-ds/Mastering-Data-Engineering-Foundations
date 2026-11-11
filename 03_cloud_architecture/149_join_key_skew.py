"""
結合キーの偏り(スキュー)検知 — 1つのキーに行が集中して、1つの作業だけが終わらない事態を見つける。

背景:
    分散処理で結合すると、同じキーの行は同じパーティションに集まる。
    1つのキーに行が集中すると、他の作業は終わっているのに1つだけが終わらず、全体がそれを待つ。
    大口の取引先、NULL のキー(未ログインのアクセスが全部 user_id = NULL)、ダミーの値(0)が典型。

方針:
    - パーティションは zlib.crc32 で決める(Python の hash() は実行ごとに変わるので使わない)
    - 全体に占める割合が hot_share 以上のキーを「偏ったキー」として挙げる。NULL も同じく数える
    - 偏ったキーには、塩(salt)を混ぜて何個に分ければ平均的な重さになるかを出す
    - 偏りの度合い = 一番重いパーティション / 平均
"""
from __future__ import annotations

import math
import zlib
from collections import Counter
from dataclasses import dataclass, field
from typing import Any


def partition_of(key: Any, partitions: int) -> int:
    """キーが入るパーティション。実行ごとに変わらない。"""
    return zlib.crc32(repr(key).encode('utf-8')) % partitions


@dataclass
class SkewReport:
    """偏りの報告。hot_keys は (キー, 行数, 割合) の並び。"""
    total: int
    partition_loads: list[int]
    hot_keys: list[tuple[Any, int, float]] = field(default_factory=list)
    salt_factors: dict[Any, int] = field(default_factory=dict)

    @property
    def imbalance(self) -> float:
        """一番重いパーティションが、平均の何倍か。行が無ければ 1.0。"""
        if not self.total:
            return 1.0
        return max(self.partition_loads) / (self.total / len(self.partition_loads))

    @property
    def ok(self) -> bool:
        """偏ったキーが無いか。"""
        return not self.hot_keys


def skew_report(keys: list[Any], partitions: int, hot_share: float = 0.2) -> SkewReport:
    """結合キーの並びから、偏りを報告する。"""
    if partitions < 1:
        raise ValueError('partitions must be at least 1')
    if not 0 < hot_share <= 1:
        raise ValueError('hot_share must be in (0, 1]')
    counts = Counter(keys)
    report = SkewReport(total=len(keys), partition_loads=[0] * partitions)
    for key, count in counts.items():
        report.partition_loads[partition_of(key, partitions)] += count
    if not keys:
        return report
    mean = len(keys) / partitions
    for key, count in sorted(counts.items(), key=lambda kv: (-kv[1], repr(kv[0]))):
        share = count / len(keys)
        if share >= hot_share:
            report.hot_keys.append((key, count, share))
            report.salt_factors[key] = math.ceil(count / mean)
    return report
