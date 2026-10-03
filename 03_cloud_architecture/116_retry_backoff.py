"""
リトライ方針 — 指数バックオフとジッターで、相手を倒さずに再試行する。

背景:
    本プロジェクトの査読原則には「指数バックオフ付きのリトライはあるか」がある。
    素朴なリトライは3つの事故を起こす:
      1. すぐ再試行する -> 相手が回復する前に叩き続け、障害を長引かせる
      2. 全員が同じ秒数待つ -> 全員が同時に再突撃し、回復した相手をまた倒す
      3. 何でもリトライする -> 入力が不正な呼び出しを100回繰り返し、時間と課金だけ失う

    本ファイルは:
      - 待ち時間を倍々に伸ばし、上限で止める(指数バックオフ)
      - 0〜その値の間でばらつかせる(フルジッター)
      - 直る見込みのある失敗だけ再試行する
      - 全体の締切を超えるなら、待たずに諦める
"""
import random

RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class TransientError(Exception):
    """時間を置けば直る見込みのある失敗(タイムアウト、一時的な過負荷など)。"""


class PermanentError(Exception):
    """何度やっても同じ結果になる失敗(入力不正、権限不足など)。"""


def is_retryable(error):
    """
    再試行すべきかを判定する。

    判定できないものは再試行しない。
    知らない種類の失敗を繰り返せば、原因の調査より先に課金が積み上がる。
    """
    if isinstance(error, TransientError):
        return True
    if isinstance(error, PermanentError):
        return False
    status = getattr(error, 'status', None)
    return status in RETRYABLE_STATUS


def backoff_delay(attempt, base=1.0, cap=30.0, rng=None):
    """
    attempt 回目(0始まり)の待ち時間を返す。

    上限 = min(cap, base * 2^attempt)、実際の待ち時間は 0〜上限 の一様乱数(フルジッター)。
    rng を渡せば結果を再現できる(テスト用)。
    """
    ceiling = min(cap, base * (2 ** attempt))
    rng = rng or random
    return rng.uniform(0, ceiling)


def retry_call(fn, max_attempts=5, base=1.0, cap=30.0, deadline=60.0,
               sleep=None, rng=None):
    """
    fn を再試行付きで呼ぶ。

    - 再試行しない失敗はその場で投げ直す
    - 次に待つと締切を超えるなら、待たずに最後の失敗を投げる
      (Lambda のタイムアウトを越えて待てば、成功しても結果を返せない)
    - 試行の記録を返し、何回目で成功したかを観測できるようにする
    """
    sleep = sleep or (lambda s: None)
    waited = 0.0
    attempts = []

    for attempt in range(max_attempts):
        try:
            result = fn()
            attempts.append({'attempt': attempt + 1, 'ok': True})
            return {'result': result, 'attempts': attempts, 'waited': round(waited, 3)}
        except Exception as error:
            attempts.append({'attempt': attempt + 1, 'ok': False, 'error': type(error).__name__})
            if not is_retryable(error) or attempt == max_attempts - 1:
                raise
            delay = backoff_delay(attempt, base, cap, rng)
            if waited + delay > deadline:
                raise
            sleep(delay)
            waited += delay