"""
時点結合(as-of join) — 事実が起きた「その時点」の次元の版に結合する。

背景:
    SCD2(#107)で次元に履歴を持たせても、結合で最新版を引けば過去が今の値で語られる。
    (4月に東京支店で売れた注文が、7月の異動後の「大阪支店」の売上になる)

方針:
    - 版は半開区間 [valid_from, valid_to)。valid_to が None なら現在も有効
    - 事実の時刻を含む版を二分探索で引く
    - 版が見つからない行は捨てずに残し、_dim_found=False で数える(#124 と同じ)
    - 同じキーの版の期間が重なっていたら止める(どちらを引くか決められない)
"""
from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class Version:
    """次元の1つの版。"""
    key: str
    valid_from: datetime
    valid_to: datetime | None
    attrs: dict[str, Any]


def build_index(versions: list[Version]) -> dict[str, list[Version]]:
    """キーごとに valid_from 順へ並べる。期間の重なりは止める。"""
    index: dict[str, list[Version]] = {}
    for v in sorted(versions, key=lambda v: (v.key, v.valid_from)):
        rows = index.setdefault(v.key, [])
        if rows and (rows[-1].valid_to is None or rows[-1].valid_to > v.valid_from):
            raise ValueError(f'overlapping versions for {v.key} at {v.valid_from}')
        rows.append(v)
    return index


def asof_lookup(index: dict[str, list[Version]], key: str, at: datetime) -> Version | None:
    """at を含む版を返す。無ければ None。"""
    rows = index.get(key, [])
    pos = bisect_right([v.valid_from for v in rows], at) - 1
    if pos < 0:
        return None
    v = rows[pos]
    return v if v.valid_to is None or at < v.valid_to else None


def asof_join(facts: list[dict[str, Any]], index: dict[str, list[Version]],
              key_field: str, time_field: str) -> tuple[list[dict[str, Any]], int]:
    """事実ごとに時点の版の属性を足す。(結合後の行, 版が見つからなかった件数) を返す。"""
    joined: list[dict[str, Any]] = []
    missing = 0
    for fact in facts:
        v = asof_lookup(index, str(fact[key_field]), fact[time_field])
        row = dict(fact)
        row['_dim_found'] = v is not None
        if v is None:
            missing += 1
        else:
            row.update(v.attrs)
        joined.append(row)
    return joined, missing
