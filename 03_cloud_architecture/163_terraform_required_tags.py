"""
タグの付け忘れ検査 — 作る・変える資源に、費用を分けるためのタグが揃っているか。

背景:
    クラウドの請求は、タグで「どのチームの・どの環境の」費用かを分ける。
    タグの無い資源は誰の費用か分からず、止めてよいのかも判断できない。
    env = "prd" のような揺れも、集計で別の環境として数えられてしまう。

方針:
    - terraform show -json の plan を読む(#131 と同じ入力)
    - 作る・変える資源(actions に create か update を含む)だけを見る
    - AWS の tags と Google Cloud の labels を見る。どちらの項目も無い資源は
      タグを付けられない種類として見ない(止めすぎない)
    - required は「タグ名 → 許される値の集合」。None なら空でなければ何でもよい
    - 問題は「住所: 内容」の形で、住所とタグ名の順に返す
"""
from __future__ import annotations

from typing import Any


def _tags_of(after: dict[str, Any]) -> dict[str, Any] | None:
    """資源のタグ。タグを付けられない種類なら None。"""
    for key in ('tags', 'labels'):
        if key in after:
            return after[key] or {}
    return None


def check_tags(plan: dict[str, Any], required: dict[str, frozenset[str] | None]) -> list[str]:
    """必須タグの欠け・空・決められていない値を返す。空なら問題なし。"""
    changes = plan.get('resource_changes', [])
    if not isinstance(changes, list):
        raise ValueError('resource_changes must be a list')
    problems: list[str] = []
    for rc in sorted(changes, key=lambda c: c['address']):
        actions = rc['change']['actions']
        if 'create' not in actions and 'update' not in actions:
            continue
        tags = _tags_of(rc['change'].get('after') or {})
        if tags is None:
            continue
        for key in sorted(required):
            value = tags.get(key)
            allowed = required[key]
            if key not in tags:
                problems.append(f"{rc['address']}: missing tag {key}")
            elif not value:
                problems.append(f"{rc['address']}: empty tag {key}")
            elif allowed is not None and value not in allowed:
                problems.append(f"{rc['address']}: tag {key}={value!r} is not one of {sorted(allowed)}")
    return problems
