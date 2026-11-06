"""
スナップショット差分 — 昨日と今日の「全件」を比べて、追加・更新・削除を割り出す。

背景:
    取り込み元に変更ログ(CDC, #125)が無く、毎日「全件のファイル」しかもらえないことは多い。
    その場合、前回の全件と今回の全件を key で突き合わせて、差分を自分で作る。

方針:
    - key の無い行・同じ key が2行ある全件は止める(差分が決められない)
    - ignore に挙げた列(取り込み日時など毎回変わる列)は比べない。比べると全行が「更新」に見える
    - 更新には「どの列が変わったか」を付ける
    - 今回が空、または削除の割合が max_delete_ratio を超えたら止める。
      取り込み元の不具合で空や途中までのファイルが来たとき、素直に適用するとテーブルが消える
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

Row = dict[str, Any]


@dataclass
class SnapshotDiff:
    """差分。updated は (前, 後, 変わった列) の並び。"""
    inserted: list[Row] = field(default_factory=list)
    updated: list[tuple[Row, Row, list[str]]] = field(default_factory=list)
    deleted: list[Row] = field(default_factory=list)
    unchanged: int = 0


def _index(rows: list[Row], key: str, side: str) -> dict[Any, Row]:
    """key → 行。key の欠けと重複は止める。"""
    out: dict[Any, Row] = {}
    for row in rows:
        if key not in row:
            raise ValueError(f'{side} snapshot has a row without {key!r}')
        if row[key] in out:
            raise ValueError(f'{side} snapshot has duplicate {key}={row[key]!r}')
        out[row[key]] = row
    return out


def diff_snapshots(old: list[Row], new: list[Row], key: str = 'id',
                   ignore: frozenset[str] = frozenset(),
                   max_delete_ratio: float = 0.5) -> SnapshotDiff:
    """前回 old と今回 new の差分を返す。"""
    before, after = _index(old, key, 'old'), _index(new, key, 'new')
    if before and not after:
        raise ValueError('new snapshot is empty; refusing to delete every row')
    result = SnapshotDiff()
    for k, row in after.items():
        if k not in before:
            result.inserted.append(row)
            continue
        prev = before[k]
        changed = sorted(c for c in (set(prev) | set(row)) - ignore if prev.get(c) != row.get(c))
        if changed:
            result.updated.append((prev, row, changed))
        else:
            result.unchanged += 1
    result.deleted = [row for k, row in before.items() if k not in after]
    if before and len(result.deleted) / len(before) > max_delete_ratio:
        raise ValueError(f'{len(result.deleted)} of {len(before)} rows would be deleted '
                         f'(> {max_delete_ratio:.0%}); check the source before applying')
    return result
