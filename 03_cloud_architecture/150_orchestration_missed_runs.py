"""
スケジュール実行の取りこぼし検知 — 「毎時実行」が本当に毎時1回ずつ成功しているかを確かめる。

背景:
    サーバー停止・デプロイ中・スケジューラーの不具合で1回分が抜けても、次の回は普通に動く。
    ログに失敗が出ないので、抜けた時刻のデータが欠けていることに誰も気づかない。

方針:
    - 予定の時刻(slot)を [start, end) の半開区間で interval ごとに並べる
    - 実行記録を slot ごとにまとめ、5種類を報告する:
        missing     : 記録が1件も無い
        failed_only : 記録はあるが全部失敗(再実行が要る)
        duplicate   : 成功が2回以上(冪等でなければ二重計上)
        late        : 最初の成功が slot + max_delay より後に始まった
        unknown     : 予定に無い時刻の記録(時刻のずれ・記録漏れ)
    - 失敗の後に再試行で成功していれば問題にしない
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta


@dataclass(frozen=True)
class Run:
    """実行記録1件。slot は予定の時刻、started_at は実際に始まった時刻。"""
    slot: datetime
    started_at: datetime
    status: str


@dataclass
class RunAudit:
    """取りこぼし検知の結果。"""
    missing: list[datetime] = field(default_factory=list)
    failed_only: list[datetime] = field(default_factory=list)
    duplicate: list[datetime] = field(default_factory=list)
    late: list[datetime] = field(default_factory=list)
    unknown: list[datetime] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """全ての予定が、ちょうど1回、時間内に成功したか。"""
        return not (self.missing or self.failed_only or self.duplicate or self.late or self.unknown)


def expected_slots(start: datetime, end: datetime, interval: timedelta) -> list[datetime]:
    """[start, end) の予定の時刻。"""
    if interval <= timedelta(0):
        raise ValueError('interval must be positive')
    slots: list[datetime] = []
    cursor = start
    while cursor < end:
        slots.append(cursor)
        cursor += interval
    return slots


def audit_runs(runs: list[Run], start: datetime, end: datetime, interval: timedelta,
               max_delay: timedelta) -> RunAudit:
    """実行記録を予定と突き合わせる。"""
    slots = expected_slots(start, end, interval)
    by_slot: dict[datetime, list[Run]] = {s: [] for s in slots}
    audit = RunAudit()
    for run in runs:
        if run.slot in by_slot:
            by_slot[run.slot].append(run)
        else:
            audit.unknown.append(run.slot)
    for slot in slots:
        records = by_slot[slot]
        successes = sorted((r for r in records if r.status == 'success'), key=lambda r: r.started_at)
        if not records:
            audit.missing.append(slot)
        elif not successes:
            audit.failed_only.append(slot)
        else:
            if len(successes) > 1:
                audit.duplicate.append(slot)
            if successes[0].started_at > slot + max_delay:
                audit.late.append(slot)
    audit.unknown.sort()
    return audit
