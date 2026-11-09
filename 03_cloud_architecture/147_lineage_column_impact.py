"""
列の変更の影響範囲 — ある列を消す・名前を変える前に、下流のどの列が壊れるかを一覧にする。

背景:
    取り込み元の列を変えると、名前を変えながら流れた先の列まで壊れる。
    users.email → staging_users.contact → mart.contact のように名前が違うと、grep では見つからない。
    #114 はテーブル単位、#130 は個人情報の流れを見た。本ファイルは「この列を変えたら何が壊れるか」。

方針:
    - columns は「出力列 → 入力列の並び」(列名は "テーブル.列")
    - 変える列から下流へ幅優先で辿り、壊れる列と「どの経路で壊れるか」を返す
    - 経路は最短のものを残す(説明に使うため)
    - 知らない列は止める(打ち間違いを「影響なし」と扱わない)
    - 循環があっても無限に辿らない
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass


@dataclass
class Impact:
    """壊れる列と、変えた列からの経路。"""
    broken: list[str]
    paths: dict[str, list[str]]

    @property
    def tables(self) -> list[str]:
        """壊れる列を持つテーブル。"""
        return sorted({column.split('.', 1)[0] for column in self.broken})


def impact_of(changed: str, columns: dict[str, tuple[str, ...]]) -> Impact:
    """changed を変えたときに壊れる下流の列を返す。"""
    known = set(columns) | {s for srcs in columns.values() for s in srcs}
    if changed not in known:
        raise ValueError(f'unknown column: {changed}')
    children: dict[str, list[str]] = {}
    for out, srcs in columns.items():
        for src in srcs:
            children.setdefault(src, []).append(out)
    paths: dict[str, list[str]] = {changed: [changed]}
    queue = deque([changed])
    while queue:
        current = queue.popleft()
        for child in sorted(children.get(current, [])):
            if child not in paths:
                paths[child] = paths[current] + [child]
                queue.append(child)
    del paths[changed]
    return Impact(sorted(paths), paths)
