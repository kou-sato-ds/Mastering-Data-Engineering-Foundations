"""
複数サービスのデプロイ順 — 呼び合うサービスを、壊れる時間を作らない順に出す。

背景:
    画面 v2 が API v2 の新機能を使うのに、画面を先に出すと、
    API が上がるまでの間「新しい画面が古い API を呼んで壊れる」時間が生まれる。
    逆に、今の API で動くのに待たせれば、デプロイ全体が無駄に長くなる。

方針:
    - サービスごとに「出す版」と「依存先に要る最低の版」を宣言する
    - 依存先の今の版が足りないときだけ、依存先を先に出す(足りていれば同時でよい)
    - 結果は波(wave)の並び。同じ波の中は同時に出してよい
    - 出す版が要求に届かない組み合わせ・知らない依存先・循環は、出す前に止める
    - 版が変わらないサービスは出さない。今まで無かったサービスは版 0 から上げる扱い
"""
from __future__ import annotations

from dataclasses import dataclass, field
from graphlib import CycleError, TopologicalSorter


@dataclass(frozen=True)
class Service:
    """出す版と、依存先ごとの最低の版。"""
    version: int
    requires: dict[str, int] = field(default_factory=dict)


def plan_waves(current: dict[str, int], targets: dict[str, Service]) -> list[list[str]]:
    """今の版 current と出す版 targets から、デプロイの波を返す。"""
    for name, svc in targets.items():
        for dep, needed in svc.requires.items():
            if dep not in targets:
                raise ValueError(f'{name} depends on unknown service {dep}')
            if targets[dep].version < needed:
                raise ValueError(f'{name} needs {dep}>={needed}, '
                                 f'but {dep} will be at {targets[dep].version}')
    changed = {n for n, s in targets.items() if s.version != current.get(n, 0)}
    graph = {n: {d for d, needed in targets[n].requires.items()
                 if d in changed and current.get(d, 0) < needed}
             for n in changed}
    sorter = TopologicalSorter(graph)
    try:
        sorter.prepare()
    except CycleError as error:
        raise ValueError(f'circular upgrade: {error.args[1]}') from error
    waves: list[list[str]] = []
    while sorter.is_active():
        ready = sorted(sorter.get_ready())
        waves.append(ready)
        sorter.done(*ready)
    return waves
