"""
バックフィルを1日の上限の中で配る — 通常の取り込みを止めずに、入れ直しを何日かに分ける。

背景:
    取り込み元の API に1日あたりの呼び出し上限があると、30日分を一度に入れ直せば上限に当たり、
    今日の通常の取り込みまで止まる。

方針:
    - 1日の枠 = daily_quota - reserve(通常の取り込み分を先に取っておく)
    - 既定は新しい日から埋める(使う人がまず見るのは最近の数字)
    - 順番は飛ばさない。次の日が入らなければ翌日へ回す。後ろの小さい日を先に詰めないので、
      どの日がいつ終わるかを約束できる
    - 1日の枠より大きい日は止める(分割しないと終わらない)
    - 結果は「n日目に入れ直す日」の並び。長さが終わるまでの日数
"""
from __future__ import annotations

from datetime import date


def schedule_backfill(slots: dict[date, int], daily_quota: int, reserve: int = 0,
                      newest_first: bool = True) -> list[list[date]]:
    """slots は「入れ直す日 → 必要な呼び出し回数」。日ごとの実行計画を返す。"""
    capacity = daily_quota - reserve
    if capacity <= 0:
        raise ValueError(f'no room for backfill: quota {daily_quota}, reserve {reserve}')
    for day, cost in slots.items():
        if cost < 0:
            raise ValueError(f'{day}: cost must not be negative')
        if cost > capacity:
            raise ValueError(f'{day} needs {cost} calls but only {capacity} fit in a day; split it')
    plan: list[list[date]] = []
    used = capacity
    for day in sorted(slots, reverse=newest_first):
        if used + slots[day] > capacity:
            plan.append([])
            used = 0
        plan[-1].append(day)
        used += slots[day]
    return plan
