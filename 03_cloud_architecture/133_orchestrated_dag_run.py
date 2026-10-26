"""
DAG の失敗の隔離 — 失敗したタスクの下流だけを止め、無関係な枝は続ける。

背景:
    取り込みが失敗したのに集計を流せば、古いデータで計算した間違った数字が「成功」として出る。
    逆に1つの失敗で全体を止めれば、無関係なレポートまで届かない。

方針:
    - 依存の順(トポロジカル順)に実行する。循環と未知の依存は止める
    - 失敗したタスクの下流は実行せず skipped にし、原因の根(最初に失敗したタスク)を記録する
    - skipped は成功ではない。ok は全タスクが success のときだけ True
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from graphlib import CycleError, TopologicalSorter


@dataclass
class DagReport:
    """タスクごとの結果。blocked_by は skipped の原因になった失敗タスク。"""
    status: dict[str, str] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)
    blocked_by: dict[str, list[str]] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        """全タスクが成功したか。"""
        return all(s == 'success' for s in self.status.values())


def _roots(task: str, report: DagReport) -> list[str]:
    """上流 task が止める原因になっている失敗タスク。"""
    state = report.status[task]
    if state == 'failed':
        return [task]
    if state == 'skipped':
        return report.blocked_by[task]
    return []


def run_dag(deps: dict[str, set[str]], run: Callable[[str], None]) -> DagReport:
    """deps は「タスク → 依存する上流の集合」。各タスクを run で実行し、結果を返す。"""
    unknown = sorted({d for ds in deps.values() for d in ds} - set(deps))
    if unknown:
        raise ValueError(f'unknown dependencies: {unknown}')
    try:
        order = list(TopologicalSorter(deps).static_order())
    except CycleError as error:
        raise ValueError(f'cycle: {error.args[1]}') from error
    report = DagReport()
    for task in order:
        roots = sorted({r for d in deps[task] for r in _roots(d, report)})
        if roots:
            report.status[task] = 'skipped'
            report.blocked_by[task] = roots
            continue
        try:
            run(task)
        except Exception as error:
            report.status[task] = 'failed'
            report.errors[task] = type(error).__name__
            continue
        report.status[task] = 'success'
    return report
