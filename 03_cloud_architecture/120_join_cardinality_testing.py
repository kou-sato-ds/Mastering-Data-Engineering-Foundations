"""
#120 結合ファンアウト検知の検証。
"""
import importlib.util
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent

ORDERS = [
    {'order_id': 'o1', 'product_id': 'p1', 'amount': 100},
    {'order_id': 'o2', 'product_id': 'p2', 'amount': 200},
    {'order_id': 'o3', 'product_id': 'p9', 'amount': 300},
]
PRODUCTS = [
    {'product_id': 'p1', 'category': 'book'},
    {'product_id': 'p2', 'category': 'food'},
]


def _mod():
    path = HERE / '120_join_cardinality.py'
    spec = importlib.util.spec_from_file_location('join_mod', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules['join_mod'] = module
    spec.loader.exec_module(module)
    return module


def test_clean_many_to_one_join_keeps_row_count():
    out = _mod().safe_join(ORDERS, PRODUCTS, 'product_id', how='left')
    assert len(out) == len(ORDERS)


def test_duplicated_master_key_is_rejected():
    """マスタでキーが重複すれば、1行が2行になり売上が膨らむ。"""
    mod = _mod()
    dup = PRODUCTS + [{'product_id': 'p1', 'category': 'magazine'}]
    with pytest.raises(ValueError, match='duplicated keys'):
        mod.safe_join(ORDERS, dup, 'product_id')


def test_expected_rows_reveal_the_fanout_before_joining():
    mod = _mod()
    dup = PRODUCTS + [{'product_id': 'p1', 'category': 'magazine'}]
    assert mod.expected_inner_rows(ORDERS, PRODUCTS, 'product_id') == 2
    assert mod.expected_inner_rows(ORDERS, dup, 'product_id') == 3


def test_naive_join_would_double_the_total():
    """チェックなしで結合した場合に何が起きるかを、数字で示す。"""
    mod = _mod()
    dup = PRODUCTS + [{'product_id': 'p1', 'category': 'magazine'}]
    naive = [{**o, **p} for o in ORDERS for p in dup if o['product_id'] == p['product_id']]
    assert sum(r['amount'] for r in naive) == 400
    assert sum(o['amount'] for o in ORDERS if o['product_id'] in {'p1', 'p2'}) == 300


def test_one_to_one_also_checks_the_left():
    mod = _mod()
    left = [{'k': 1}, {'k': 1}]
    right = [{'k': 1, 'v': 'x'}]
    assert mod.check_cardinality(left, right, 'k', 'many_to_one') == []
    assert mod.check_cardinality(left, right, 'k', 'one_to_one')


def test_column_name_clash_is_rejected():
    """同じ名前の列があれば、片方の値が黙って上書きされる。"""
    mod = _mod()
    right = [{'product_id': 'p1', 'amount': 999}]
    with pytest.raises(ValueError, match='overwritten'):
        mod.safe_join(ORDERS, right, 'product_id')


def test_inner_join_drops_unmatched_rows():
    out = _mod().safe_join(ORDERS, PRODUCTS, 'product_id')
    assert [r['order_id'] for r in out] == ['o1', 'o2']


def test_unmatched_keys_are_reported():
    """内部結合では、マスタに無い注文が黙って消える。"""
    assert _mod().unmatched_keys(ORDERS, PRODUCTS, 'product_id') == ['p9']


def test_unknown_cardinality_is_an_error():
    with pytest.raises(ValueError):
        _mod().check_cardinality(ORDERS, PRODUCTS, 'product_id', 'many_to_many')


def test_this_file_passes_the_type_hint_ratchet():
    """#117 のラチェット: 新しいファイルは公開関数100%型付き。"""
    spec = importlib.util.spec_from_file_location('audit_for_120', HERE / '117_type_hint_audit.py')
    audit = importlib.util.module_from_spec(spec)
    sys.modules['audit_for_120'] = audit
    spec.loader.exec_module(audit)
    assert audit.audit_file(HERE / '120_join_cardinality.py')['missing'] == []