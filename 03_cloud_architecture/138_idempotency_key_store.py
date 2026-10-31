"""
冪等キー — 同じ依頼が2回届いても、実行は1回、答えは同じにする。

背景:
    通信が切れると、クライアントは結果を受け取れずに同じ依頼を再送する。
    サーバー側では1回目が成功していることがあり、素直に実行すれば請求や書き込みが二重になる。
    決済 API が使う Idempotency-Key の型である。

方針:
    - 依頼の中身は fingerprint(キーの並び順に依存しないハッシュ)で比べる
    - 同じキー・同じ中身・完了済み → 保存した結果を返す(実行しない)
    - 同じキー・違う中身 → IdempotencyConflict。黙って前の結果を返さない
    - 同じキー・処理中 → RequestInProgress。同時に2回走らせない
    - 失敗した依頼は記録を消す。再送で実行し直せるようにするため
      (action 自体が途中まで外部に書き込む場合は、その先も冪等である必要がある)
    - 記録は ttl_seconds で忘れる。無限に保存しない
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


class IdempotencyConflict(Exception):
    """同じキーが、違う中身の依頼に使われた。"""


class RequestInProgress(Exception):
    """同じキーの依頼が、まだ処理中。"""


def fingerprint(payload: dict[str, Any]) -> str:
    """依頼の中身のハッシュ。キーの並び順は結果に影響しない。"""
    text = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False, default=str)
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


@dataclass
class Record:
    """1つのキーの記録。response が None なら処理中。"""
    fingerprint: str
    created_at: float
    response: dict[str, Any] | None = None


@dataclass
class IdempotencyStore:
    """キー → 記録。本番では DynamoDB などの条件付き書き込みで同じことをする。"""
    ttl_seconds: float = 86400.0
    records: dict[str, Record] = field(default_factory=dict)

    def purge(self, now: float) -> int:
        """期限切れの記録を消し、消した件数を返す。"""
        old = [k for k, r in self.records.items() if now - r.created_at >= self.ttl_seconds]
        for key in old:
            del self.records[key]
        return len(old)


def execute(store: IdempotencyStore, key: str, payload: dict[str, Any],
            action: Callable[[dict[str, Any]], dict[str, Any]], now: float) -> tuple[dict[str, Any], bool]:
    """(結果, 保存した結果を返したか) を返す。"""
    if not key:
        raise ValueError('idempotency key is required')
    store.purge(now)
    fp = fingerprint(payload)
    existing = store.records.get(key)
    if existing is not None:
        if existing.fingerprint != fp:
            raise IdempotencyConflict(f'key {key} was used for a different request')
        if existing.response is None:
            raise RequestInProgress(f'key {key} is still being processed')
        return existing.response, True
    store.records[key] = Record(fingerprint=fp, created_at=now)
    try:
        response = action(payload)
    except Exception:
        del store.records[key]
        raise
    store.records[key].response = response
    return response, False
