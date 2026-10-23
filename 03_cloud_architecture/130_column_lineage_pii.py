"""
列レベルのリネージ — 個人情報の印を変換に沿って運び、公開テーブルへの漏れを見つける。

背景:
    「分析用の公開テーブルに、個人情報が紛れ込んでいないか」は受託でよく聞かれる。
    #114 はテーブル単位の依存を見たが、個人情報は「列」に宿る。
    users.email → staging_users.contact → mart_public.contact と名前が変わると、
    列名を見ても個人情報だとは気づけない。元をたどるしかない。

    本ファイルの方針:
      - 元の列に印(pii など)を付け、変換を通して印を運ぶ。列名が変わっても印は消えない
      - 複数の列から作った列は、全部の印を引き継ぐ(姓 + 名 → 氏名 も個人情報)
      - ハッシュ化などで仮名化した列は pii を pseudonymized に変える。
        ただし公開はやはり禁止(既定)。仮名化した情報も、照合すれば個人に戻せる
      - 違反には「どの元の列から来たか」を添え、直す場所まで分かる報告にする
      - 出どころが分からない列・循環・同じ列の二重定義は止める。
        分からない流れを「安全」と扱わない

    #117 のラチェットにより、公開関数は100%型付き。
"""
from __future__ import annotations

from dataclasses import dataclass

FORBIDDEN_IN_PUBLIC = frozenset({'pii', 'pseudonymized'})


@dataclass(frozen=True)
class Transform:
    """
    1つのテーブルの作り方。

    columns: 出力列名 → 入力列("テーブル.列")の並び。並びが空なら定数や件数など。
    masked : ハッシュ化などで仮名化している出力列
    """
    table: str
    columns: dict[str, tuple[str, ...]]
    masked: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        unknown = self.masked - set(self.columns)
        if unknown:
            raise ValueError(f'masked columns not produced by {self.table}: {sorted(unknown)}')


@dataclass
class Lineage:
    """列ごとの印(tags)と、その列のおおもとの元の列(origins)。"""
    tags: dict[str, set[str]]
    origins: dict[str, set[str]]


def _produced_by(column: str, transforms: list[Transform]) -> bool:
    """まだ処理していない変換のどれかが、その列を作るか。"""
    return any(f'{t.table}.{c}' == column for t in transforms for c in t.columns)


def propagate(sources: dict[str, set[str]], transforms: list[Transform]) -> Lineage:
    """
    元の列の印を、変換に沿って運ぶ。transforms の並び順は問わない(作れるものから順に処理する)。

    sources には、印の無い列も空の集合で全部書くこと。書かれていない列は「出どころ不明」として止める。
    """
    tags = {column: set(t) for column, t in sources.items()}
    origins = {column: {column} for column in sources}
    pending = list(transforms)
    while pending:
        ready = [t for t in pending
                 if all(src in tags for srcs in t.columns.values() for src in srcs)]
        if not ready:
            missing = sorted({src for t in pending for srcs in t.columns.values() for src in srcs
                              if src not in tags and not _produced_by(src, pending)})
            if missing:
                raise ValueError(f'unknown input columns: {missing}')
            raise ValueError(f'cycle among tables: {sorted(t.table for t in pending)}')
        for transform in ready:
            for column, srcs in transform.columns.items():
                name = f'{transform.table}.{column}'
                if name in tags:
                    raise ValueError(f'column defined twice: {name}')
                merged: set[str] = set().union(*(tags[s] for s in srcs))
                if column in transform.masked and 'pii' in merged:
                    merged = (merged - {'pii'}) | {'pseudonymized'}
                tags[name] = merged
                origins[name] = set().union(*(origins[s] for s in srcs))
            pending.remove(transform)
    return Lineage(tags=tags, origins=origins)


def check_exposure(lineage: Lineage, public_tables: set[str],
                   forbidden: frozenset[str] = FORBIDDEN_IN_PUBLIC) -> list[str]:
    """
    公開テーブルの列のうち、禁止された印を持つものを返す。

    例: 'mart_public.contact: pii <- users.email'
    """
    violations: list[str] = []
    for column in sorted(lineage.tags):
        if column.split('.', 1)[0] not in public_tables:
            continue
        bad = lineage.tags[column] & forbidden
        if bad:
            violations.append(f"{column}: {', '.join(sorted(bad))} <- "
                              f"{', '.join(sorted(lineage.origins[column]))}")
    return violations