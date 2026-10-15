"""
レート制限 — トークンバケットと Retry-After で、相手の API に締め出されない。

背景:
    API からデータを取り込むとき、相手には「1秒に10回まで」のような制限がある。
    超えれば 429 Too Many Requests で弾かれ、繰り返せば一定時間締め出される。

    本ファイルの方針:
      - トークンバケット: 一定の速さで補充される通行券を使い切ったら待つ。
        短い集中(バースト)は許し、平均の速さは守る。
      - 相手が Retry-After で待ち時間を指定したら、自分の計算より優先する。
        相手の都合を一番よく知っているのは相手である。
      - 相手が壊れた値や極端な値を返しても、上限で切って暴走しない。

    #116 のリトライが「失敗した後にどう待つか」なら、本ファイルは
    「失敗しないようにどう間隔を空けるか」を扱う。
    #117 のラチェットにより、公開関数は100%型付き。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

# 相手がどんな値を返しても、これ以上は待たない(暴走防止)。
MAX_WAIT_SECONDS = 300.0


@dataclass
class TokenBucket:
    """
    capacity 個まで貯まる通行券。毎秒 refill_per_sec 個ずつ補充される。

    時刻は外から渡す(テストで時間を進められるようにするため)。
    """
    capacity: float
    refill_per_sec: float
    tokens: float = field(default=-1.0)
    updated_at: float = 0.0

    def __post_init__(self) -> None:
        if self.capacity <= 0 or self.refill_per_sec <= 0:
            raise ValueError('capacity and refill_per_sec must be positive')
        if self.tokens < 0:
            self.tokens = self.capacity

    def refill(self, now: float) -> None:
        """経過時間分だけ補充する。capacity を超えて貯めない。"""
        elapsed = max(now - self.updated_at, 0.0)
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_per_sec)
        self.updated_at = now

    def try_acquire(self, now: float, cost: float = 1.0) -> bool:
        """通行券があれば1枚使って True、無ければ何もせず False。"""
        self.refill(now)
        if self.tokens >= cost:
            self.tokens -= cost
            return True
        return False

    def wait_time(self, now: float, cost: float = 1.0) -> float:
        """次の1回が通るまでに待つべき秒数。"""
        self.refill(now)
        shortage = cost - self.tokens
        return 0.0 if shortage <= 0 else shortage / self.refill_per_sec


def parse_retry_after(value: str | None, now: datetime) -> float | None:
    """
    Retry-After ヘッダを秒数に直す。

    形式は2通りある: 秒数("120") と 日時("Wed, 21 Oct 2026 07:28:00 GMT")。
    解釈できなければ None を返し、呼び出し側の計算に任せる。
    過去の日時なら 0(今すぐ再試行してよい)。
    """
    if value is None or not value.strip():
        return None
    text = value.strip()
    if text.isdigit():
        return float(text)
    try:
        when = parsedate_to_datetime(text)
    except (TypeError, ValueError):
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return max((when - now).total_seconds(), 0.0)


def decide_wait(retry_after: float | None, own_estimate: float,
                cap: float = MAX_WAIT_SECONDS) -> float:
    """
    実際に待つ秒数を決める。

    相手の指定があればそれを優先する(自分の見積もりより短くても長くても)。
    どちらの場合も cap で切る。相手が 99999 を返しても1日待ったりはしない。
    """
    chosen = retry_after if retry_after is not None else own_estimate
    return min(max(chosen, 0.0), cap)