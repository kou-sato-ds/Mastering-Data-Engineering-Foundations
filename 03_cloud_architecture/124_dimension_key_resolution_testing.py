"""
#124 次元キー解決の検証。
"""
import importlib.util
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent


def _mod():
    path = HERE / '124_dimension_key_resolution.py'
    spec = importlib.util.spec_from_file_location('dimkey_mod', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules['dimkey_mod'] = module
    spec.loader.exec_module(module)
    return module


DIM = [{'code': 'A', 'sk': 1}, {'code': 'B', 'sk': 2}]


def _resolve(mod, facts):
    key_map = mod.build_key_map(DIM, 'code', 'sk')
    return mod.resolve_keys(facts, key_map, 'code', 'product_sk')


def test_known_codes_are_resolved():
    mod = _mod()
    r = _resolve(mod, [{'code': 'A'}, {'code': 'B'}])
    assert [x['product_sk'] for x in r.rows] == [1, 2]
    assert r.resolved == 2


def test_unknown_code_is_kept_as_minus_one():
    """行を捨てれば、売上の合計が実際より少なくなる。"""
    mod = _mod()
    r = _resolve(mod, [{'code': 'Z', 'amount': 500}])
    assert len(r.rows) == 1
    assert r.rows[0]['product_sk'] == mod.UNKNOWN_KEY
    assert r.missing_codes == ['Z']


def test_empty_code_is_not_applicable_not_unknown():
    """「マスタが遅れている」と「最初から無い」は直し方が違う。"""
    mod = _mod()
    r = _resolve(mod, [{'code': None}, {'code': ''}, {}])
    assert all(x['product_sk'] == mod.NOT_APPLICABLE_KEY for x in r.rows)
    assert r.not_applicable == 3
    assert r.unknown == 0


def test_totals_are_preserved():
    mod = _mod()
    facts = [{'code': 'A', 'amount': 100}, {'code': 'Z', 'amount': 50},
             {'code': None, 'amount': 30}]
    r = _resolve(mod, facts)
    assert sum(x['amount'] for x in r.rows) == 180
    assert r.resolved + r.unknown + r.not_applicable == len(facts)


def test_missing_codes_are_unique_and_sorted():
    mod = _mod()
    r = _resolve(mod, [{'code': 'Z'}, {'code': 'Y'}, {'code': 'Z'}])
    assert r.missing_codes == ['Y', 'Z']
    assert r.unknown == 3


def test_input_rows_are_not_mutated():
    mod = _mod()
    facts = [{'code': 'A'}]
    _resolve(mod, facts)
    assert facts == [{'code': 'A'}]


def test_duplicate_natural_key_in_dimension_is_rejected():
    """同じコードが2行あれば、どちらに付けるか決められない。"""
    mod = _mod()
    with pytest.raises(ValueError, match='duplicate'):
        mod.build_key_map([{'code': 'A', 'sk': 1}, {'code': 'A', 'sk': 2}], 'code', 'sk')


def test_reserved_surrogate_key_is_rejected():
    mod = _mod()
    with pytest.raises(ValueError, match='reserved'):
        mod.build_key_map([{'code': 'A', 'sk': -1}], 'code', 'sk')


def test_high_unknown_ratio_stops_the_load():
    """大半が不明なら、マスタの取り込み自体が壊れている。"""
    mod = _mod()
    r = _resolve(mod, [{'code': 'Z'}, {'code': 'Y'}, {'code': 'A'}])
    mod.check_unknown_ratio(r, max_ratio=0.9)
    with pytest.raises(ValueError, match='unknown ratio'):
        mod.check_unknown_ratio(r, max_ratio=0.5)


def test_this_file_passes_the_type_hint_ratchet():
    """#117 のラチェット: 新しいファイルは公開関数100%型付き。"""
    spec = importlib.util.spec_from_file_location('audit_for_124', HERE / '117_type_hint_audit.py')
    audit = importlib.util.module_from_spec(spec)
    sys.modules['audit_for_124'] = audit
    spec.loader.exec_module(audit)
    assert audit.audit_file(HERE / '124_dimension_key_resolution.py')['missing'] == []