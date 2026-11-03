"""
遅れて届くデータの扱い — ウォーターマークで窓を締め、許容遅延の内側なら訂正を出す。

背景:
    イベントは起きた順に届くとは限らない(圏外だった端末、再送)。
    「10:00〜10:01 の件数」をいつ締めるか、締めた後に届いた分をどうするかを決める必要がある。

方針(Apache Beam / Flink と同じ考え方):
    - ウォーターマーク = これまでに見た最大のイベント時刻 - lag(想定する遅れ)
    - 窓 [start, start + size) は、ウォーターマークが終わりを過ぎたら final を出す
    - 締めた後でも、ウォーターマークが「終わり + allowed_lateness」を過ぎるまでは受け付け、
      数え直して update(訂正版)を出す
    - それも過ぎたら too_late。数えないが、黙って捨てずに too_late に残す
    - 許容遅延を過ぎた窓の状態は消す(状態を無限に持たない)
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class WindowedCounter:
    """イベント時刻の固定幅の窓ごとに件数を数える。時刻は秒。"""
    size: float
    lag: float
    allowed_lateness: float
    watermark: float = -math.inf
    counts: dict[float, int] = field(default_factory=dict)
    closed: set[float] = field(default_factory=set)
    emitted: list[tuple[str, float, int]] = field(default_factory=list)
    too_late: list[float] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.size <= 0 or self.lag < 0 or self.allowed_lateness < 0:
            raise ValueError('size must be positive; lag and allowed_lateness must not be negative')

    def add(self, event_time: float) -> str:
        """1件を受け取り、on_time / late_update / too_late のどれだったかを返す。"""
        start = math.floor(event_time / self.size) * self.size
        if self.watermark >= start + self.size + self.allowed_lateness:
            self.too_late.append(event_time)
            return 'too_late'
        self.counts[start] = self.counts.get(start, 0) + 1
        kind = 'on_time'
        if start in self.closed:
            self.emitted.append(('update', start, self.counts[start]))
            kind = 'late_update'
        self.watermark = max(self.watermark, event_time - self.lag)
        for s in sorted(self.counts):
            if s not in self.closed and self.watermark >= s + self.size:
                self.closed.add(s)
                self.emitted.append(('final', s, self.counts[s]))
        for s in list(self.counts):
            if self.watermark >= s + self.size + self.allowed_lateness:
                del self.counts[s]
                self.closed.discard(s)
        return kind
