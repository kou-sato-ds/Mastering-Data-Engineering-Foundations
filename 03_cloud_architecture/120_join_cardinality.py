"""
結合の行数爆発(ファンアウト)検知 — 「JOINしたら売上が2倍」を防ぐ。

背景:
    「数字が合わない」の原因として最も多いものの1つ。
    注文(多)に商品マスタ(一)を結合するつもりが、マスタ側でキーが重複していると、
    1行が2行に増え、売上の合計が静かに膨らむ。エラーは出ない。

    本ファイルは結合の前後で3つを確かめる:
      - 一のはずの側で、キーが本当に一意か(多対一のつもりが多対多になっていないか)
      - 結合後の行数を事前に計算し、想定と一致するか
      - キー以外の列名が衝突していないか(衝突すれば、片方の値が黙って上書きされる)

    #117 のラチェットにより、公開関数は100%型付き。
"""
from __future__ import annotations

from collections import Counter
from typing import Any

Row = dict[str, Any]

CARDINALITIES = {'one_to_one', 'many_to_one'}


def key_counts(rows: list[Row], key: str) -> Counter[Any]:
    """キーごとの出現回数を数える。"""
    return Counter(r[key] for r in rows)


def duplicated_keys(rows: list[Row], key: str) -> list[Any]:
    """2回以上出現するキーを返す。"""
    return sorted(k for k, c in key_counts(rows, key).items() if c > 1)


def expected_inner_rows(left: list[Row], right: list[Row], key: str) -> int:
    """
    内部結合の結果行数を、結合する前に計算する。

    キーごとに (左の件数 x 右の件数) を足したもの。
    右で重複していれば、ここで左より大きい数字になる。
    """
    lc, rc = key_counts(left, key), key_counts(right, key)
    return sum(lc[k] * rc[k] for k in lc if k in rc)


def check_cardinality(left: list[Row], right: list[Row], key: str,
                      expected: str = 'many_to_one') -> list[str]:
    """
    想定した対応関係が守られているか確かめ、違反を返す。

    many_to_one: 右(マスタ側)のキーが一意であること
    one_to_one : 左右とも一意であること
    """
    if expected not in CARDINALITIES:
        raise ValueError(f'unknown cardinality: {expected}')

    violations: list[str] = []
    right_dup = duplicated_keys(right, key)
    if right_dup:
        violations.append(f'right side has duplicated keys {right_dup[:5]}; rows would multiply')
    if expected == 'one_to_one':
        left_dup = duplicated_keys(left, key)
        if left_dup:
            violations.append(f'left side has duplicated keys {left_dup[:5]}')
    return violations


def overlapping_columns(left: list[Row], right: list[Row], key: str) -> list[str]:
    """キー以外で、左右に同じ名前で存在する列を返す。"""
    lcols = set().union(*(r.keys() for r in left)) if left else set()
    rcols = set().union(*(r.keys() for r in right)) if right else set()
    return sorted((lcols & rcols) - {key})


def safe_join(left: list[Row], right: list[Row], key: str,
              expected: str = 'many_to_one', how: str = 'inner') -> list[Row]:
    """
    対応関係と列名を確かめてから結合する。違反があれば結合しない。

    how='left' のとき、右に相手が無い行も残す(右の列は付かない)。
    """
    problems = check_cardinality(left, right, key, expected)
    clash = overlapping_columns(left, right, key)
    if clash:
        problems.append(f'columns {clash} exist on both sides and would be overwritten')
    if problems:
        raise ValueError('; '.join(problems))

    index = {r[key]: r for r in right}
    joined: list[Row] = []
    for row in left:
        match = index.get(row[key])
        if match is not None:
            joined.append({**row, **match})
        elif how == 'left':
            joined.append(dict(row))
    return joined


def unmatched_keys(left: list[Row], right: list[Row], key: str) -> list[Any]:
    """右に相手の無い左のキー。内部結合では、この行が黙って消える。"""
    rkeys = set(key_counts(right, key))
    return sorted({r[key] for r in left} - rkeys)