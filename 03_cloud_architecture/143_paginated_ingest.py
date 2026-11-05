"""
ページング取得の完全性 — 「次のページ」を辿る取り込みを、途中で黙って欠けさせない。

背景:
    API の一覧は数ページに分かれて返る。カーソル(次のページの目印)を辿って全部を集めるが、
    - API の不具合で同じカーソルが返り続けると、無限ループになる
    - 取り込み中に新しいデータが入ると、ページがずれて同じ行が2回返る
    - ページ数の上限で打ち切ると、途中までしか取れていないのに成功に見える

方針:
    - 使ったカーソルを覚え、同じものが2度来たら止める
    - key(既定 id)で重複を落とし、落とした件数を数える
    - max_pages を超えたら例外。黙って打ち切らない(欠けたデータを成功として出さない)
    - 中身が空でも次のカーソルがあれば辿る(そういう API がある)
    - key の無い行は止める(重複を判定できない)
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

Page = tuple[list[dict[str, Any]], str | None]


@dataclass
class IngestResult:
    """集めた行と、ページ数・落とした重複の数。"""
    items: list[dict[str, Any]] = field(default_factory=list)
    pages: int = 0
    duplicates: int = 0


def fetch_all(fetch_page: Callable[[str | None], Page], key: str = 'id',
              max_pages: int = 1000) -> IngestResult:
    """最初のページ(カーソル None)から、次のカーソルが無くなるまで辿る。"""
    result = IngestResult()
    seen_keys: set[Any] = set()
    seen_cursors: set[str] = set()
    cursor: str | None = None
    while True:
        if result.pages >= max_pages:
            raise RuntimeError(f'more than {max_pages} pages; refusing to return a partial result')
        items, next_cursor = fetch_page(cursor)
        result.pages += 1
        for item in items:
            if key not in item:
                raise ValueError(f'item without {key!r} on page {result.pages}')
            if item[key] in seen_keys:
                result.duplicates += 1
                continue
            seen_keys.add(item[key])
            result.items.append(item)
        if not next_cursor:
            return result
        if next_cursor in seen_cursors:
            raise RuntimeError(f'cursor {next_cursor!r} was returned twice (pagination loop)')
        seen_cursors.add(next_cursor)
        cursor = next_cursor
