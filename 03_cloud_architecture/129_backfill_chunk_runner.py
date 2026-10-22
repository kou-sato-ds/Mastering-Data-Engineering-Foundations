"""
バックフィルの分割実行 — 途中で落ちても続きから再開でき、壊れた上流を叩き続けない。

背景:
    「過去1年分を入れ直してほしい」は受託でほぼ確実に来る依頼である。
    1年分を1回で流せば、300日目の失敗で最初からやり直しになる。
    失敗しても全部続ければ、上流が落ちているのに残り全部を叩き、
    エラーと費用だけが積み上がる。

    本ファイルの方針:
      - 期間を日数単位の塊(チャンク)に分ける。区間は半開区間 [開始, 終了)。
        隙間も重なりも作らない(#119 と同じ約束)
      - 終わった塊を完了マーカー(completed)に記録し、次回は飛ばす。
        何度実行しても残りだけをやる(冪等・再開可能)。
        completed の保存先(S3 のファイルなど)は呼び出し側が決める
      - 1つ失敗しても他は続ける。ただし連続して max_consecutive_failures 回
        失敗したら止める(上流が落ちているなら叩かない = サーキットブレーカー)
      - 失敗した塊は完了にしない。次回の実行で自然に再挑戦される
      - 並列にしない。上流への負荷と費用を読めるようにするため

    #117 のラチェットにより、公開関数は100%型付き。
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, timedelta

Chunk = tuple[date, date]


def chunk_range(start: date, end: date, days: int) -> list[Chunk]:
    """[start, end) を days 日ずつの半開区間に分ける。最後の塊だけ短くてよい。"""
    if days <= 0:
        raise ValueError('days must be positive')
    if end <= start:
        raise ValueError(f'empty range: {start} to {end}')
    chunks: list[Chunk] = []
    cursor = start
    while cursor < end:
        upper = min(cursor + timedelta(days=days), end)
        chunks.append((cursor, upper))
        cursor = upper
    return chunks


def chunk_id(chunk: Chunk) -> str:
    """完了マーカーに書く名前。例: 2026-01-01_2026-01-08"""
    return f'{chunk[0].isoformat()}_{chunk[1].isoformat()}'


@dataclass
class BackfillReport:
    """1回の実行結果。done + skipped + failed + not_attempted = total。"""
    total: int
    done: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    failed: dict[str, str] = field(default_factory=dict)
    not_attempted: list[str] = field(default_factory=list)
    stopped_early: bool = False

    @property
    def ok(self) -> bool:
        """全部が終わっているときだけ True。呼び出し側はこれが False なら異常終了させる。"""
        return not self.failed and not self.not_attempted


def run_backfill(chunks: list[Chunk], run_chunk: Callable[[date, date], None],
                 completed: set[str], max_consecutive_failures: int = 3,
                 newest_first: bool = False) -> BackfillReport:
    """
    塊を1つずつ実行し、結果を返す。completed は成功した塊の分だけ書き足される。

    newest_first=True なら新しい期間から埋める(最近のデータほど早く使えるようにしたい場合)。
    連続失敗が上限に達したら、残りは実行せず not_attempted に入れて止める。
    """
    if max_consecutive_failures <= 0:
        raise ValueError('max_consecutive_failures must be positive')
    order = sorted(chunks, reverse=newest_first)
    report = BackfillReport(total=len(order))
    streak = 0
    for index, chunk in enumerate(order):
        cid = chunk_id(chunk)
        if cid in completed:
            report.skipped.append(cid)
            continue
        try:
            run_chunk(*chunk)
        except Exception as error:
            report.failed[cid] = type(error).__name__
            streak += 1
            if streak >= max_consecutive_failures:
                report.stopped_early = True
                report.not_attempted = [chunk_id(c) for c in order[index + 1:]
                                        if chunk_id(c) not in completed]
                break
            continue
        completed.add(cid)
        report.done.append(cid)
        streak = 0
    return report