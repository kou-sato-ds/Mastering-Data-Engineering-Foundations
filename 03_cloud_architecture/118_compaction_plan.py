"""
小さなファイルの統合(コンパクション)計画 — 数が増えすぎたファイルをまとめる。

背景:
    データレイクに毎時・毎分書き込むと、数KBのファイルが何万個も溜まる。
    保存容量は小さくても、読むたびにファイルの数だけリクエストが飛び、
    クエリは遅く、課金は高くなる(TCO)。

    本ファイルはまとめ方の計画を立てる。実際の読み書きはしない。
    計画と実行を分けるのは、計画を人が確認してから実行できるようにするため。

    守ること:
      - パーティションをまたいで混ぜない(#64 の日付による絞り込みが効かなくなる)
      - 書き込み中の新しいファイルには触らない(遅れて届くデータと衝突する)
      - 小さいファイルが1個しか無いパーティションは対象外(まとめても数が減らない)

    #117 のラチェットにより、本ファイルは公開関数を100%型付きにしている。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

MB = 1024 * 1024
SMALL_FILE_THRESHOLD = 32 * MB
TARGET_SIZE = 128 * MB
MIN_AGE = timedelta(hours=1)


@dataclass(frozen=True)
class FileInfo:
    path: str
    partition: str
    size_bytes: int
    modified_at: datetime


@dataclass(frozen=True)
class Batch:
    partition: str
    paths: tuple[str, ...]
    total_bytes: int


def is_small(f: FileInfo, threshold: int = SMALL_FILE_THRESHOLD) -> bool:
    """閾値未満のファイルを「小さい」とみなす。"""
    return f.size_bytes < threshold


def is_settled(f: FileInfo, now: datetime, min_age: timedelta = MIN_AGE) -> bool:
    """
    書き込みが落ち着いたファイルか。

    書き込み直後のファイルをまとめると、遅れて届くデータの追記と衝突する。
    """
    return now - f.modified_at >= min_age


def candidates(files: list[FileInfo], now: datetime) -> dict[str, list[FileInfo]]:
    """パーティションごとに、まとめ候補(小さく、落ち着いたファイル)を返す。"""
    grouped: dict[str, list[FileInfo]] = {}
    for f in files:
        if is_small(f) and is_settled(f, now):
            grouped.setdefault(f.partition, []).append(f)
    return grouped


def pack(files: list[FileInfo], target: int = TARGET_SIZE) -> list[list[FileInfo]]:
    """
    目標サイズを超えない範囲で詰める(大きい順に詰める貪欲法)。

    1個しか入らなかったまとまりは捨てる。まとめても数が減らない。
    """
    bins: list[list[FileInfo]] = []
    sizes: list[int] = []
    for f in sorted(files, key=lambda x: (-x.size_bytes, x.path)):
        for i, used in enumerate(sizes):
            if used + f.size_bytes <= target:
                bins[i].append(f)
                sizes[i] += f.size_bytes
                break
        else:
            bins.append([f])
            sizes.append(f.size_bytes)
    return [b for b in bins if len(b) > 1]


def plan_compaction(files: list[FileInfo], now: datetime,
                    target: int = TARGET_SIZE) -> list[Batch]:
    """パーティションをまたがないまとめ計画を返す。順序は毎回同じにする。"""
    grouped = candidates(files, now)
    plan: list[Batch] = []
    for partition in sorted(grouped):
        for group in pack(grouped[partition], target):
            plan.append(Batch(
                partition=partition,
                paths=tuple(sorted(f.path for f in group)),
                total_bytes=sum(f.size_bytes for f in group),
            ))
    return plan


def summarize(files: list[FileInfo], plan: list[Batch]) -> dict[str, int]:
    """まとめた後にファイル数がいくつ減るかを返す。"""
    merged = sum(len(b.paths) for b in plan)
    return {
        'files_before': len(files),
        'files_after': len(files) - merged + len(plan),
        'reduced_by': merged - len(plan),
    }