"""
SLO のバーンレート警報 — エラーバジェットを使い切る速さで、鳴らすかどうかを決める。

背景:
    「エラーが1件出たら通知」では深夜に鳴りっぱなしになり、誰も警報を見なくなる。
    SLO 99.9% なら、失敗は 0.1% まで許される(エラーバジェット)。
    問題は失敗の有無ではなく、そのバジェットを「どれだけの速さで」使っているかである。

方針(Google SRE の複数窓・複数バーンレート):
    - バーンレート = 失敗率 / (1 - SLO)。1.0 なら期間ちょうどでバジェットを使い切る速さ
    - 1時間と5分がどちらも 14.4倍以上 → page(今すぐ起こす)
    - 6時間と30分がどちらも 6倍以上  → ticket(翌営業日に対応)
    - 長い窓は一瞬の揺れを無視するため、短い窓は「今も続いているか」を確かめるため。
      長い窓だけだと、直った後も鳴り続ける
"""
from __future__ import annotations

from dataclasses import dataclass

PAGE = (14.4, '1h', '5m')
TICKET = (6.0, '6h', '30m')
REQUIRED_WINDOWS = frozenset({'1h', '5m', '6h', '30m'})


def burn_rate(errors: int, total: int, slo: float) -> float:
    """失敗率をエラーバジェットで割った値。リクエストが無ければ 0.0。"""
    if not 0 < slo < 1:
        raise ValueError(f'slo must be between 0 and 1: {slo}')
    if errors < 0 or total < 0 or errors > total:
        raise ValueError(f'invalid counts: errors={errors}, total={total}')
    if total == 0:
        return 0.0
    return (errors / total) / (1 - slo)


@dataclass(frozen=True)
class Alert:
    """警報の判定。level は page / ticket / none。"""
    level: str
    reasons: tuple[str, ...] = ()


def evaluate(windows: dict[str, tuple[int, int]], slo: float) -> Alert:
    """windows は「窓 → (失敗数, 全数)」。page を ticket より優先して判定する。"""
    missing = sorted(REQUIRED_WINDOWS - set(windows))
    if missing:
        raise ValueError(f'missing windows: {missing}')
    rates = {w: burn_rate(e, t, slo) for w, (e, t) in windows.items()}
    for level, (threshold, long_w, short_w) in (('page', PAGE), ('ticket', TICKET)):
        if rates[long_w] >= threshold and rates[short_w] >= threshold:
            return Alert(level, (f'{long_w} burn {rates[long_w]:.1f} >= {threshold}',
                                 f'{short_w} burn {rates[short_w]:.1f} >= {threshold}'))
    return Alert('none')
