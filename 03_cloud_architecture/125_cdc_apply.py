"""
CDC(変更データキャプチャ)の適用 — 届く順番が乱れても、消した行を生き返らせない。

背景:
    業務DBの「追加・更新・削除」の記録(変更ログ)を受け取り、
    分析側のテーブルに同じ状態を再現する。落とし穴は3つある。

    - 順番が入れ替わって届く → 古い更新が新しい値を上書きし、過去に巻き戻る
    - 同じ変更が2回届く      → #123 と同じ(at-least-once)
    - 削除の後に古い更新が遅れて届く → 消したはずの行が生き返る

    本ファイルの方針:
      - 変更ごとの通し番号(seq)をキーごとに覚え、それ以下の変更は適用しない
      - 削除した行も「何番で消したか」だけは覚えておく(墓石 = tombstone)
      - 1回に受け取った分(バッチ)の中は seq 順に並べてから適用する。
        バッチを跨いで遅れて届いたものは「古い(stale)」として数える

    #117 のラチェットにより、公開関数は100%型付き。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

VALID_OPS = frozenset({'insert', 'update', 'delete'})


@dataclass(frozen=True)
class ChangeEvent:
    """変更ログの1件。seq は発生源での通し番号(大きいほど新しい)。"""
    key: str
    op: str
    seq: int
    data: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.op not in VALID_OPS:
            raise ValueError(f'unknown op: {self.op}')
        if self.op != 'delete' and self.data is None:
            raise ValueError(f'{self.op} requires data: key={self.key}')


@dataclass
class CdcTable:
    """
    再現先のテーブル。

    rows     : 今ある行
    versions : キーごとに最後に適用した seq。削除した行の分も残す(墓石)。
    """
    rows: dict[str, dict[str, Any]] = field(default_factory=dict)
    versions: dict[str, int] = field(default_factory=dict)

    def apply(self, event: ChangeEvent) -> str:
        """
        1件を適用し、結果を 'applied' / 'duplicate' / 'stale' で返す。

        最後に適用した seq と同じなら重複、小さければ古い変更として何もしない。
        削除の後に古い更新が来ても、墓石の seq より小さいので生き返らない。
        """
        last = self.versions.get(event.key)
        if last is not None and event.seq == last:
            return 'duplicate'
        if last is not None and event.seq < last:
            return 'stale'
        if event.op == 'delete':
            self.rows.pop(event.key, None)
        else:
            self.rows[event.key] = dict(event.data or {})
        self.versions[event.key] = event.seq
        return 'applied'


def apply_batch(table: CdcTable, events: list[ChangeEvent]) -> dict[str, int]:
    """
    バッチを seq 順に並べてから適用し、結果の件数を返す。

    バッチの中の順番の乱れはここで直る。
    バッチを跨いで遅れて届いたものは 'stale' に数えられる。
    """
    stats = {'applied': 0, 'duplicate': 0, 'stale': 0}
    for event in sorted(events, key=lambda e: e.seq):
        stats[table.apply(event)] += 1
    return stats


def compact_tombstones(table: CdcTable, before_seq: int) -> int:
    """
    before_seq より古い墓石を忘れ、忘れた件数を返す。

    墓石を無限に残せば version 表が膨らみ続ける。ただし忘れた後に、
    それより古い更新が遅れて届けば行が生き返る。before_seq は
    「これより古い変更はもう届かない」と言える番号にすること。
    """
    old = [k for k, seq in table.versions.items()
           if k not in table.rows and seq < before_seq]
    for key in old:
        del table.versions[key]
    return len(old)