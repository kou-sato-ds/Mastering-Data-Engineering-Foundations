"""#153 集計の加法性の検証。"""
import importlib.util
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent


def _mod():
    spec = importlib.util.spec_from_file_location('additivity_mod', HERE / '153_star_schema_measure_additivity.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules['additivity_mod'] = module
    spec.loader.exec_module(module)
    return module


def _measures(mod):
    M = mod.Measure
    return {'sales': M('sales', 'additive'), 'balance': M('balance', 'semi_additive'),
            'cvr': M('cvr', 'non_additive')}


def test_summing_daily_balances_inflates_the_number():
    """なぜ要るか: 毎日100円の残高を3日足すと300円になる。"""
    daily_balance = [100, 100, 100]
    assert sum(daily_balance) == 300
    assert daily_balance[-1] == 100


def test_averaging_ratios_is_not_the_true_ratio():
    """1/10 と 90/100 の率の平均は50%だが、本当は 91/110 = 82.7%。"""
    assert (1 / 10 + 90 / 100) / 2 == pytest.approx(0.5)
    assert (1 + 90) / (10 + 100) == pytest.approx(0.827, abs=0.001)


def test_additive_measure_can_be_summed_over_time():
    mod = _mod()
    assert mod.check_aggregation(_measures(mod), {'sales': 'sum'}, {'date', 'store'}) == []


def test_balance_can_be_summed_across_stores():
    mod = _mod()
    assert mod.check_aggregation(_measures(mod), {'balance': 'sum'}, {'store'}) == []


def test_balance_summed_over_time_is_a_problem():
    mod = _mod()
    problems = mod.check_aggregation(_measures(mod), {'balance': 'sum'}, {'date'})
    assert problems == ['balance: summing a balance over date double counts; use last, avg, min or max']


def test_balance_last_over_time_is_fine():
    mod = _mod()
    assert mod.check_aggregation(_measures(mod), {'balance': 'last'}, {'date'}) == []


def test_ratio_must_be_recomputed():
    mod = _mod()
    assert mod.check_aggregation(_measures(mod), {'cvr': 'avg'}, {'date'}) != []
    assert mod.check_aggregation(_measures(mod), {'cvr': 'recompute'}, {'date'}) == []


def test_several_problems_are_listed_in_order():
    mod = _mod()
    problems = mod.check_aggregation(_measures(mod), {'cvr': 'sum', 'balance': 'sum', 'sales': 'sum'},
                                     {'date'})
    assert [p.split(':')[0] for p in problems] == ['balance', 'cvr']


def test_unknown_names_stop():
    mod = _mod()
    with pytest.raises(ValueError, match='unknown measure'):
        mod.check_aggregation(_measures(mod), {'profit': 'sum'}, set())
    with pytest.raises(ValueError, match='unknown function'):
        mod.check_aggregation(_measures(mod), {'sales': 'median'}, set())
    with pytest.raises(ValueError, match='unknown kind'):
        mod.Measure('x', 'additiv')


def test_this_file_passes_the_type_hint_ratchet():
    spec = importlib.util.spec_from_file_location('audit_for_153', HERE / '117_type_hint_audit.py')
    audit = importlib.util.module_from_spec(spec)
    sys.modules['audit_for_153'] = audit
    spec.loader.exec_module(audit)
    assert audit.audit_file(HERE / '153_star_schema_measure_additivity.py')['missing'] == []
