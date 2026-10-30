"""
毒メッセージの隔離 — 必ず失敗するメッセージ1件で、キュー全体を詰まらせない。

背景:
    壊れた JSON や必須項目の欠けたメッセージは、何度処理しても必ず失敗する(毒メッセージ)。
    バッチ全体を失敗にすると、正常なメッセージまで一緒に再配信され、永遠に詰まる。

方針:
    - 1件ずつ処理し、失敗した分だけを retry に返す。成功分は ack する
      (Lambda の部分バッチ応答 ReportBatchItemFailures と同じ考え方)
    - 恒久的な失敗(PERMANENT)は1回目で即 DLQ。何度やっても直らないので再試行しない
    - 一時的な失敗は max_receives 回まで再試行し、超えたら DLQ
    - attempts(受信回数)は呼び出し側が保存する。ack と DLQ で消し、膨らませない
    - DLQ には「何の例外で、何回目に諦めたか」を残す(後で調べて再投入するため)
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

PERMANENT: tuple[type[BaseException], ...] = (ValueError, KeyError, TypeError)


@dataclass(frozen=True)
class Message:
    """キューの1件。"""
    id: str
    body: dict[str, Any]


@dataclass
class BatchResult:
    """acked + retry + dead_lettered = バッチの件数。"""
    acked: list[str] = field(default_factory=list)
    retry: list[str] = field(default_factory=list)
    dead_lettered: dict[str, str] = field(default_factory=dict)


def process_batch(messages: list[Message], handler: Callable[[dict[str, Any]], None],
                  attempts: dict[str, int], max_receives: int = 3,
                  permanent: tuple[type[BaseException], ...] = PERMANENT) -> BatchResult:
    """メッセージを1件ずつ処理し、ack / retry / DLQ に振り分ける。"""
    if max_receives <= 0:
        raise ValueError('max_receives must be positive')
    result = BatchResult()
    for message in messages:
        count = attempts.get(message.id, 0) + 1
        attempts[message.id] = count
        try:
            handler(message.body)
        except permanent as error:
            result.dead_lettered[message.id] = f'{type(error).__name__} (permanent, attempt {count})'
            attempts.pop(message.id)
            continue
        except Exception as error:
            if count >= max_receives:
                result.dead_lettered[message.id] = f'{type(error).__name__} (gave up after {count} attempts)'
                attempts.pop(message.id)
            else:
                result.retry.append(message.id)
            continue
        attempts.pop(message.id)
        result.acked.append(message.id)
    return result
