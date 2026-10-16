"""
重複配信の排除(時間窓つき) — 同じメッセージが2回届いても、1回として扱う。

背景:
    Pub/Sub や SQS は「少なくとも1回は届ける(at-least-once)」仕組みである。
    つまり同じメッセージが2回届くことがあり、これは仕様通りでエラーではない。
    放っておけば、同じ注文を2回数える。

    本ファイルの方針:
      - イベントID で「見たことがあるか」を覚える
      - 覚えておくのは ttl_seconds の間だけ(無限に覚えればメモリが尽きる)
      - 上限を超えて仕方なく忘れた件数を数え、報告する。
        そこから重複がすり抜ける可能性があるので、黙って忘れない。
      - ID の無いイベントは判定できない。捨てずに通し、件数を報告する。

    #66 の MERGE が「重複しても結果が変わらない」側なら、
    本ファイルは「重複をそもそも通さない」側である。
    #117 のラチェットにより、公開関数は100%型付き。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DedupStore:
    """見たイベントID と、最後に見た時刻(秒)を覚えておく箱。"""
    ttl_seconds: float
    max_entries: int
    seen: dict[str, float] = field(default_factory=dict)
    forced_evictions: int = 0

    def __post_init__(self) -> None:
        if self.ttl_seconds <= 0 or self.max_entries <= 0:
            raise ValueError('ttl_seconds and max_entries must be positive')

    def purge(self, now: float) -> int:
        """期限切れのIDを忘れ、忘れた件数を返す。"""
        expired = [k for k, t in self.seen.items() if now - t >= self.ttl_seconds]
        for k in expired:
            del self.seen[k]
        return len(expired)

    def is_duplicate(self, event_id: str, now: float) -> bool:
        """
        見たことがあれば True。無ければ覚えて False。

        上限に達したら一番古いものから忘れる。期限前に忘れたものは
        重複がすり抜ける原因になるため、forced_evictions に数える。
        """
        self.purge(now)
        if event_id in self.seen:
            return True
        while len(self.seen) >= self.max_entries:
            oldest = next(iter(self.seen))
            del self.seen[oldest]
            self.forced_evictions += 1
        self.seen[event_id] = now
        return False


def dedupe(events: list[dict[str, Any]], store: DedupStore, now: float,
           key: str = 'id') -> tuple[list[dict[str, Any]], dict[str, int]]:
    """
    重複を除いたイベントと、件数の内訳を返す。

    ID の無いイベントは判定できないので、捨てずに通して数える。
    黙って捨てれば、重複ではない正しいデータまで消える。
    """
    kept: list[dict[str, Any]] = []
    stats = {'received': len(events), 'duplicates': 0, 'without_id': 0}
    for event in events:
        event_id = event.get(key)
        if not event_id:
            stats['without_id'] += 1
            kept.append(event)
        elif store.is_duplicate(str(event_id), now):
            stats['duplicates'] += 1
        else:
            kept.append(event)
    stats['kept'] = len(kept)
    stats['forced_evictions'] = store.forced_evictions
    return kept, stats