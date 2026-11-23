"""
値の決まりの検査(ドメイン制約) — 列ごとに「入ってよい値」を宣言し、外れた行を数える。

背景:
    型の検査(数値か文字か)だけでは、年齢 -5、都道府県「東京都 」(末尾の空白)、
    郵便番号「1000001」(ハイフン無し)は全部すり抜ける。

方針:
    - 決まりは4種類: range(範囲、両端を含む) / allowed(選択肢) / pattern(形式、全体一致) / null
    - 空(None・列が無い)は nullable=True でなければ違反(kind = 'null')
    - 型が合わない値(range に文字列、pattern に数値)も違反として数える
    - 違反は件数と実例(sample_size 件まで)を返す。実物を見せれば上流はすぐ原因が分かる
    - 決まりの書き間違い(知らない種類・壊れた正規表現)は止める
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

KINDS = frozenset({'range', 'allowed', 'pattern'})


@dataclass(frozen=True)
class Rule:
    """1つの列の決まり。arg は range なら (下限, 上限)、allowed なら値の集合、pattern なら正規表現。"""
    column: str
    kind: str
    arg: Any
    nullable: bool = False

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise ValueError(f'unknown rule kind: {self.kind}')
        if self.kind == 'pattern':
            re.compile(self.arg)


@dataclass
class Violation:
    """1つの決まりへの違反の件数と実例。"""
    column: str
    kind: str
    count: int = 0
    samples: list[Any] = field(default_factory=list)


def _ok(rule: Rule, value: Any) -> bool:
    if rule.kind == 'range':
        low, high = rule.arg
        return isinstance(value, (int, float)) and not isinstance(value, bool) and low <= value <= high
    if rule.kind == 'allowed':
        return value in rule.arg
    return isinstance(value, str) and re.fullmatch(rule.arg, value) is not None


def check(rows: list[dict[str, Any]], rules: list[Rule], sample_size: int = 3) -> list[Violation]:
    """違反のあった決まりだけを、決まりの順に返す。"""
    found: dict[tuple[str, str], Violation] = {}
    for row in rows:
        for rule in rules:
            value = row.get(rule.column)
            if value is None:
                if rule.nullable:
                    continue
                kind = 'null'
            elif _ok(rule, value):
                continue
            else:
                kind = rule.kind
            v = found.setdefault((rule.column, kind), Violation(rule.column, kind))
            v.count += 1
            if len(v.samples) < sample_size:
                v.samples.append(value)
    order = {(r.column, k): i for i, r in enumerate(rules) for k in (r.kind, 'null')}
    return sorted(found.values(), key=lambda v: order[(v.column, v.kind)])
