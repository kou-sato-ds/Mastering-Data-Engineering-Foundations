"""
環境間の設定の一致検査 — 開発・検証・本番で、揃っているべき設定がずれていないか。

背景:
    設定が環境ごとに少しずつずれると「検証では動いたのに本番で壊れた」が起きる。
    ただし、バケット名やサーバーの大きさのように、違っていて当然の設定もある。

方針:
    - 入れ子の設定は "db.engine_version" のような点区切りの名前に平らにして比べる
    - 基準の環境(既定 prod)と、他の各環境を比べる
    - may_differ(fnmatch のパターン)に当たる設定は、値が違っても報告しない
    - 片方にしか無い設定は、may_differ に当たっても報告する(値ではなく構造のずれ)
    - may_differ のうち、どの設定名にも当たらないパターンは「古い許可」として報告する
      (打ち間違いや消えた設定。残せば、次に入った設定を黙って通す)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from fnmatch import fnmatchcase
from typing import Any


def flatten(config: dict[str, Any], prefix: str = '') -> dict[str, Any]:
    """{"db": {"engine_version": "15"}} → {"db.engine_version": "15"}。"""
    out: dict[str, Any] = {}
    for key, value in config.items():
        path = f'{prefix}{key}'
        if isinstance(value, dict) and value:
            out.update(flatten(value, f'{path}.'))
        else:
            out[path] = value
    return out


@dataclass
class ParityReport:
    """一致検査の結果。problems が空なら揃っている。"""
    problems: list[str] = field(default_factory=list)
    stale_allowances: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """揃っているべき設定が全て揃っているか。"""
        return not self.problems


def compare_envs(envs: dict[str, dict[str, Any]], may_differ: frozenset[str] = frozenset(),
                 baseline: str = 'prod') -> ParityReport:
    """基準の環境と、他の各環境を比べる。"""
    if baseline not in envs:
        raise ValueError(f'baseline environment {baseline!r} is missing')
    base = flatten(envs[baseline])
    report = ParityReport()
    for name in sorted(envs):
        if name == baseline:
            continue
        other = flatten(envs[name])
        for key in sorted(set(base) | set(other)):
            if key not in other:
                report.problems.append(f'{name}: missing {key}')
            elif key not in base:
                report.problems.append(f'{name}: extra {key} (not in {baseline})')
            elif other[key] != base[key] and not any(fnmatchcase(key, p) for p in may_differ):
                report.problems.append(f'{name}: {key} = {other[key]!r}, {baseline} = {base[key]!r}')
    report.stale_allowances = sorted(p for p in may_differ if not any(fnmatchcase(k, p) for k in base))
    return report
