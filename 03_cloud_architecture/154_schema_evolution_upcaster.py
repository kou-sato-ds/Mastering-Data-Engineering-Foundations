"""
スキーマの読み替え(アップキャスト) — 古い版のイベントを、1段ずつ最新の形に読み替える。

背景:
    イベントの形は時間とともに変わる(氏名を姓と名に分ける、通貨の列を足す)。
    キューや保存先には古い形が残り続けるので、読む側で最新の形に読み替える必要がある。
    #105 は列の追加・削除の互換性、#136 は型の拡張を見た。本ファイルは「古い形をどう読むか」。

方針:
    - 読み替えは「版 v → v+1」の関数を1段ずつ積み重ねる(v1 → v2 → v3)
    - 途中の段が無ければ止める(どう読むか分からない)
    - 読む側より新しい版は止める。黙って読めば、知らない列を捨てることになる
    - 版の印(schema_version)が無い・1未満なら止める
    - 入力のイベントは書き換えない(浅いコピーを読み替える)
    - check_chain で、起動時に段の抜けを確かめられる
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

Event = dict[str, Any]
Upcaster = Callable[[Event], Event]


def check_chain(upcasters: dict[int, Upcaster], latest: int) -> list[int]:
    """1 から latest まで読み替えるのに足りない段(その段の元の版)を返す。"""
    return [v for v in range(1, latest) if v not in upcasters]


def upcast(event: Event, upcasters: dict[int, Upcaster], latest: int) -> Event:
    """event を latest の形に読み替えた新しい辞書を返す。"""
    if 'schema_version' not in event:
        raise ValueError('event has no schema_version')
    version = event['schema_version']
    if not isinstance(version, int) or version < 1:
        raise ValueError(f'invalid schema_version: {version!r}')
    if version > latest:
        raise ValueError(f'schema_version {version} is newer than this reader ({latest}); upgrade the reader')
    body = dict(event)
    while version < latest:
        if version not in upcasters:
            raise ValueError(f'no upcaster from version {version} to {version + 1}')
        body = upcasters[version](body)
        version += 1
        body['schema_version'] = version
    return body
