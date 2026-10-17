"""
ファクトの次元キー解決 — マスタに無いコードが来ても、売上を捨てない。

背景:
    スター・スキーマでは、ファクト(売上など)の「商品コード」を
    次元(商品マスタ)の通し番号(サロゲートキー)に置き換えて格納する。
    ところがマスタの更新が売上より遅いと、まだ載っていないコードが来る。

    - 行を捨てる   → 売上の合計が実際より少なくなる(一番まずい)
    - 処理を止める → マスタ1件の遅れで、全部の売上が届かない
    - 本ファイル   → 「不明(-1)」に付け替えて数える。合計は正しいまま。

    値がそもそも空の行は「該当なし(-2)」に分ける。
    「マスタが遅れている」と「最初から無い」は、直し方が違うからである。
    #117 のラチェットにより、公開関数は100%型付き。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

UNKNOWN_KEY = -1
NOT_APPLICABLE_KEY = -2


@dataclass
class ResolveResult:
    """解決後の行と、件数の内訳。"""
    rows: list[dict[str, Any]]
    resolved: int = 0
    unknown: int = 0
    not_applicable: int = 0
    missing_codes: list[str] = field(default_factory=list)

    @property
    def unknown_ratio(self) -> float:
        """不明の割合。行が無ければ 0.0。"""
        return self.unknown / len(self.rows) if self.rows else 0.0


def build_key_map(dim_rows: list[dict[str, Any]], natural_key: str,
                  surrogate_key: str) -> dict[str, int]:
    """
    次元の行から「コード → 通し番号」の対応表を作る。

    同じコードが2行あれば、どちらに付けるか決められないので止める。
    予約した -1 / -2 を通し番号に使っている行も止める。
    """
    key_map: dict[str, int] = {}
    for row in dim_rows:
        code = str(row[natural_key])
        sk = int(row[surrogate_key])
        if sk in (UNKNOWN_KEY, NOT_APPLICABLE_KEY):
            raise ValueError(f'surrogate key {sk} is reserved')
        if code in key_map:
            raise ValueError(f'duplicate natural key in dimension: {code}')
        key_map[code] = sk
    return key_map


def resolve_keys(facts: list[dict[str, Any]], key_map: dict[str, int],
                 fact_key: str, out_key: str) -> ResolveResult:
    """
    ファクトのコードを通し番号に置き換える。入力の行は書き換えない。

    マスタに無いコードは UNKNOWN_KEY、空の値は NOT_APPLICABLE_KEY にする。
    どの行も捨てない。
    """
    result = ResolveResult(rows=[])
    missing: set[str] = set()
    for fact in facts:
        row = dict(fact)
        code = fact.get(fact_key)
        if code is None or code == '':
            row[out_key] = NOT_APPLICABLE_KEY
            result.not_applicable += 1
        elif str(code) in key_map:
            row[out_key] = key_map[str(code)]
            result.resolved += 1
        else:
            row[out_key] = UNKNOWN_KEY
            result.unknown += 1
            missing.add(str(code))
        result.rows.append(row)
    result.missing_codes = sorted(missing)
    return result


def check_unknown_ratio(result: ResolveResult, max_ratio: float) -> None:
    """
    不明の割合が上限を超えたら止める。

    数件なら「マスタが少し遅れている」で済むが、
    大半が不明ならマスタの取り込み自体が壊れている。
    """
    if result.unknown_ratio > max_ratio:
        raise ValueError(
            f'unknown ratio {result.unknown_ratio:.1%} exceeds {max_ratio:.1%}; '
            f'missing codes: {result.missing_codes[:5]}'
        )