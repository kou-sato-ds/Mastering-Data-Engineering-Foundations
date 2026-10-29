"""
型の拡張の安全判定 — 列の型を変えるとき、データを失わない「広げ方」だけを通す。

背景:
    #105 は列の追加・削除を互換性で分類した。本ファイルは「同じ列の型を変える」場合を見る。
    int32 → int64 は全ての値がそのまま入るが、int64 → float64 は一見同じ「広げ方」でも危ない。
    float64 が整数を正確に持てるのは 2**53 までで、ID や金額の下の桁が黙って変わる。

方針:
    - 判定は same / safe / unsafe の3つ。unsafe には理由を付ける
    - safe は「古い型の全ての値が、新しい型で同じ値のまま表せる」ものだけ
    - decimal(p, s) は、小数部(s)も整数部(p - s)も減らないときだけ safe
    - nullable → 必須 は unsafe(既に入っている null の行が壊れる)。逆は safe
    - 知らない型は止める(分からないものを safe と扱わない)
    - 列の追加・削除は #105 の担当。ここでは両方に存在する列だけを見る
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_SIMPLE = frozenset({'bool', 'int32', 'int64', 'float32', 'float64', 'string', 'date', 'timestamp'})
_SAFE = frozenset({('int32', 'int64'), ('int32', 'float64'), ('float32', 'float64'), ('date', 'timestamp')})
_DECIMAL = re.compile(r'decimal\((\d+),(\d+)\)')


@dataclass(frozen=True)
class Verdict:
    """判定。kind は same / safe / unsafe。"""
    kind: str
    reason: str = ''


def _decimal(type_name: str) -> tuple[int, int] | None:
    """decimal(p,s) なら (p, s)、そうでなければ None。"""
    m = _DECIMAL.fullmatch(type_name.replace(' ', ''))
    return (int(m.group(1)), int(m.group(2))) if m else None


def check_type_change(old: str, new: str) -> Verdict:
    """型の変更だけを判定する。"""
    for t in (old, new):
        if t not in _SIMPLE and _decimal(t) is None:
            raise ValueError(f'unknown type: {t}')
    if old == new:
        return Verdict('same')
    d_old, d_new = _decimal(old), _decimal(new)
    if d_old and d_new:
        (p1, s1), (p2, s2) = d_old, d_new
        if s2 >= s1 and p2 - s2 >= p1 - s1:
            return Verdict('safe', 'decimal widened')
        return Verdict('unsafe', f'decimal({p1},{s1}) -> decimal({p2},{s2}) loses digits')
    if (old, new) in _SAFE:
        return Verdict('safe', f'{old} widens to {new}')
    if (old, new) == ('int64', 'float64'):
        return Verdict('unsafe', 'float64 holds integers exactly only up to 2**53')
    return Verdict('unsafe', f'{old} -> {new} is not a widening')


def check_column(old_type: str, old_nullable: bool, new_type: str, new_nullable: bool) -> Verdict:
    """型と null 許容をまとめて判定する。"""
    verdict = check_type_change(old_type, new_type)
    if verdict.kind == 'unsafe':
        return verdict
    if old_nullable and not new_nullable:
        return Verdict('unsafe', 'nullable -> required breaks rows that already hold nulls')
    if verdict.kind == 'same' and old_nullable == new_nullable:
        return Verdict('same')
    return Verdict('safe', verdict.reason or 'required -> nullable')


def review_schema(old: dict[str, tuple[str, bool]], new: dict[str, tuple[str, bool]]) -> list[str]:
    """両方にある列のうち、unsafe な変更だけを「列名: 理由」で返す。"""
    problems: list[str] = []
    for name in sorted(set(old) & set(new)):
        verdict = check_column(*old[name], *new[name])
        if verdict.kind == 'unsafe':
            problems.append(f'{name}: {verdict.reason}')
    return problems
