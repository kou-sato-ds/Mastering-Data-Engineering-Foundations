"""
保存階層の損益分岐 — 保存料・取り出し料・最低保存期間を全部足して、一番安い階層を選ぶ。

背景:
    オブジェクトストレージには、よく読む用(高い・取り出し無料)と
    めったに読まない用(安い・取り出しに料金・最低保存期間あり)の階層がある。
    「古いものは安い階層へ」と一律に移すと、取り出し料や最低保存期間でかえって高くつく。

方針:
    - 料金は Tier として引数で渡す(料金は変わるので、コードに埋め込まない)
    - 保存料は max(残りの月数, 最低保存期間) の分を払う(早く消しても最低期間分は請求される)
    - 取り出し料は、サイズ × 月あたりの読み出し回数 × 月数
    - 一番安い階層を選ぶ。同額なら、先に並べた階層を選ぶ(移す手間をかけない)
"""
from __future__ import annotations

from dataclasses import dataclass

DAYS_PER_MONTH = 30


@dataclass(frozen=True)
class Tier:
    """保存階層の料金。単位は GB と月(取り出しは GB あたり)。"""
    name: str
    storage_per_gb_month: float
    retrieval_per_gb: float
    min_days: int = 0


def cost_over(tier: Tier, size_gb: float, reads_per_month: float, months: float) -> float:
    """残りの months か月でかかる合計の費用。"""
    if size_gb < 0 or reads_per_month < 0 or months < 0:
        raise ValueError('size, reads and months must not be negative')
    billed_months = max(months, tier.min_days / DAYS_PER_MONTH)
    storage = size_gb * tier.storage_per_gb_month * billed_months
    retrieval = size_gb * tier.retrieval_per_gb * reads_per_month * months
    return storage + retrieval


def cheapest(tiers: list[Tier], size_gb: float, reads_per_month: float,
             months: float) -> tuple[str, dict[str, float]]:
    """(一番安い階層の名前, 階層ごとの費用) を返す。"""
    if not tiers:
        raise ValueError('at least one tier is required')
    names = [t.name for t in tiers]
    if len(set(names)) != len(names):
        raise ValueError('tier names must be unique')
    costs = {t.name: cost_over(t, size_gb, reads_per_month, months) for t in tiers}
    best = min(tiers, key=lambda t: costs[t.name])
    return best.name, costs
