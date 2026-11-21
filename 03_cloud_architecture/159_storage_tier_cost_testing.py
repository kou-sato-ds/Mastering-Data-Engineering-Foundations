"""#159 保存階層の損益分岐の検証。料金は説明用の架空の値(実際はその時点の料金表から渡す)。"""
import importlib.util
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent


def _mod():
    spec = importlib.util.spec_from_file_location('tier_mod', HERE / '159_storage_tier_cost.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules['tier_mod'] = module
    spec.loader.exec_module(module)
    return module


def _tiers(mod):
    T = mod.Tier
    return [T('standard', 2.5, 0.0), T('infrequent', 1.25, 1.0, 30), T('archive', 0.4, 3.0, 90)]


def test_frequently_read_data_stays_standard():
    """よく読むなら、取り出し料が保存料の節約を上回る。"""
    mod = _mod()
    best, costs = mod.cheapest(_tiers(mod), 100, 4, 12)
    assert best == 'standard'
    assert costs['standard'] == pytest.approx(3000)


def test_rarely_read_long_lived_data_goes_to_archive():
    mod = _mod()
    assert mod.cheapest(_tiers(mod), 100, 0, 12)[0] == 'archive'


def test_occasional_reads_favour_the_middle_tier():
    """月1回読むなら、取り出し料の安い中間の階層が一番安い。"""
    mod = _mod()
    best, costs = mod.cheapest(_tiers(mod), 100, 1, 12)
    assert best == 'infrequent'
    assert costs['infrequent'] == pytest.approx(2700)


def test_short_lived_data_stays_standard_despite_cheaper_rates():
    """6日で消すデータでも、最低保存期間の分まで請求される。"""
    mod = _mod()
    best, costs = mod.cheapest(_tiers(mod), 100, 0, 0.2)
    assert best == 'standard'
    assert costs['archive'] == pytest.approx(120)


def test_minimum_duration_is_billed():
    mod = _mod()
    infrequent = _tiers(mod)[1]
    assert mod.cost_over(infrequent, 100, 0, 0.5) == pytest.approx(125)


def test_tie_keeps_the_first_listed_tier():
    """同額なら、移す手間をかけない。"""
    mod = _mod()
    T = mod.Tier
    assert mod.cheapest([T('a', 1.0, 0.0), T('b', 1.0, 0.0)], 10, 0, 1)[0] == 'a'


def test_every_tier_cost_is_reported():
    mod = _mod()
    _, costs = mod.cheapest(_tiers(mod), 100, 0, 12)
    assert sorted(costs) == ['archive', 'infrequent', 'standard']


def test_invalid_inputs_stop():
    mod = _mod()
    T = mod.Tier
    with pytest.raises(ValueError, match='negative'):
        mod.cost_over(T('a', 1.0, 0.0), -1, 0, 1)
    with pytest.raises(ValueError, match='at least one'):
        mod.cheapest([], 1, 0, 1)
    with pytest.raises(ValueError, match='unique'):
        mod.cheapest([T('a', 1.0, 0.0), T('a', 2.0, 0.0)], 1, 0, 1)


def test_this_file_passes_the_type_hint_ratchet():
    spec = importlib.util.spec_from_file_location('audit_for_159', HERE / '117_type_hint_audit.py')
    audit = importlib.util.module_from_spec(spec)
    sys.modules['audit_for_159'] = audit
    spec.loader.exec_module(audit)
    assert audit.audit_file(HERE / '159_storage_tier_cost.py')['missing'] == []
