"""
サーキットブレーカー — 失敗が続く相手を呼び続けず、しばらくしたら1回だけ試す。

背景:
    外部 API が落ちているのに呼び続けると、毎回タイムアウトまで待たされ、
    処理全体が遅くなり、復旧しかけた相手にも負荷をかけ続ける。
    #116 の指数バックオフは「1回の呼び出しの中で粘る」。本ファイルは「粘っても無駄なら呼ばない」。

方針(家のブレーカーと同じ3状態):
    - closed   : 通常。連続して failure_threshold 回失敗したら open にする
    - open     : 呼ばずに即座に断る(CircuitOpenError)。reset_timeout 秒たったら half_open へ
    - half_open: 試しに1回だけ通す。成功なら closed、失敗なら open に戻して時計をやり直す
    - 途中で成功すれば失敗の数はリセットする(止めるのは「連続」のときだけ)
    - 時刻は引数で受け取る(テストで時計を自由に進めるため)
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

T = TypeVar('T')


class CircuitOpenError(Exception):
    """回路が開いているので、呼ばずに断った。"""


@dataclass
class CircuitBreaker:
    """1つの呼び出し先に1つ持つ。"""
    failure_threshold: int = 5
    reset_timeout: float = 30.0
    state: str = 'closed'
    failures: int = 0
    opened_at: float | None = None
    probing: bool = False

    def __post_init__(self) -> None:
        if self.failure_threshold < 1 or self.reset_timeout <= 0:
            raise ValueError('failure_threshold must be >= 1 and reset_timeout > 0')

    def allow(self, now: float) -> bool:
        """今、呼んでよいか。half_open では同時に1回までしか通さない。"""
        if self.state == 'open' and self.opened_at is not None and now - self.opened_at >= self.reset_timeout:
            self.state = 'half_open'
        if self.state == 'closed':
            return True
        if self.state == 'half_open' and not self.probing:
            self.probing = True
            return True
        return False

    def record_success(self) -> None:
        """成功したら回路を閉じ、失敗の数を戻す。"""
        self.state, self.failures, self.opened_at, self.probing = 'closed', 0, None, False

    def record_failure(self, now: float) -> None:
        """失敗を数え、必要なら回路を開く。"""
        self.probing = False
        if self.state == 'half_open':
            self.state, self.opened_at = 'open', now
            return
        self.failures += 1
        if self.failures >= self.failure_threshold:
            self.state, self.opened_at = 'open', now

    def call(self, fn: Callable[[], T], now: float) -> T:
        """回路を通して fn を呼ぶ。開いていれば呼ばずに CircuitOpenError。"""
        if not self.allow(now):
            raise CircuitOpenError(f'circuit is {self.state}')
        try:
            result = fn()
        except Exception:
            self.record_failure(now)
            raise
        self.record_success()
        return result
