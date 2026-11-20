"""
セッション化 — 1人のユーザーの操作を、間隔で「ひと続き」に区切る。

背景:
    アクセス解析の基本だが、素直に書くと黙って数字がずれる。
    ログは届いた順に並んでおらず、境界(ちょうど30分)の扱いは人によって違い、
    ボットは24時間操作し続けて1セッションが無限に伸びる。

方針:
    - ユーザーごとに、起きた時刻の順に並べ直してから区切る(届いた順は問わない)
    - 前の操作から gap 秒を「超えたら」別のセッション(ちょうど gap は同じセッション)
    - max_length を指定すれば、開始からそれを超えた時点で区切る(ボット対策)
    - セッション ID は「ユーザー:開始時刻」。何度作っても同じ ID になる(冪等)
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Session:
    """1つのセッション。時刻は秒。"""
    user: str
    start: float
    end: float
    count: int

    @property
    def session_id(self) -> str:
        """何度作っても同じになる ID。"""
        return f'{self.user}:{int(self.start)}'


def sessionize(events: list[tuple[str, float]], gap: float = 1800.0,
               max_length: float | None = None) -> list[Session]:
    """(ユーザー, 時刻) の並びからセッションを作り、(ユーザー, 開始) の順で返す。"""
    if gap <= 0:
        raise ValueError('gap must be positive')
    if max_length is not None and max_length <= 0:
        raise ValueError('max_length must be positive')
    by_user: dict[str, list[float]] = {}
    for user, ts in events:
        by_user.setdefault(user, []).append(ts)
    sessions: list[Session] = []
    for user in sorted(by_user):
        times = sorted(by_user[user])
        start = prev = times[0]
        count = 1
        for ts in times[1:]:
            too_long = max_length is not None and ts - start > max_length
            if ts - prev > gap or too_long:
                sessions.append(Session(user, start, prev, count))
                start, count = ts, 0
            prev = ts
            count += 1
        sessions.append(Session(user, start, prev, count))
    return sessions
