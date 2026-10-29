"""#136 型の拡張の安全判定の検証。"""
import importlib.util
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent


def _mod():
    spec = importlib.util.spec_from_file_location('widen_mod', HERE / '136_schema_evolution_type_widening.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules['widen_mod'] = module
    spec.loader.exec_module(module)
    return module


def test_same_type_is_same():
    mod = _mod()
    assert mod.check_type_change('int64', 'int64').kind == 'same'


@pytest.mark.parametrize('old, new', [
    ('int32', 'int64'), ('int32', 'float64'), ('float32', 'float64'), ('date', 'timestamp'),
])
def test_true_widenings_are_safe(old, new):
    mod = _mod()
    assert mod.check_type_change(old, new).kind == 'safe'


def test_int64_to_float64_is_unsafe():
    """2**53 を超えると、隣の整数と区別できなくなる。"""
    mod = _mod()
    assert float(2**53 + 1) == float(2**53)
    verdict = mod.check_type_change('int64', 'float64')
    assert verdict.kind == 'unsafe'
    assert '2**53' in verdict.reason


def test_narrowing_is_unsafe():
    mod = _mod()
    assert mod.check_type_change('float64', 'int64').kind == 'unsafe'


def test_string_to_number_is_unsafe():
    mod = _mod()
    assert mod.check_type_change('string', 'int64').kind == 'unsafe'


def test_decimal_widening_is_safe():
    mod = _mod()
    assert mod.check_type_change('decimal(10,2)', 'decimal(12,2)').kind == 'safe'
    assert mod.check_type_change('decimal(10,2)', 'decimal(12, 4)').kind == 'safe'


def test_decimal_losing_digits_is_unsafe():
    """小数部が減っても、整数部が減っても値が変わる。"""
    mod = _mod()
    assert mod.check_type_change('decimal(10,4)', 'decimal(12,2)').kind == 'unsafe'
    assert mod.check_type_change('decimal(10,2)', 'decimal(10,4)').kind == 'unsafe'


def test_unknown_type_stops():
    mod = _mod()
    with pytest.raises(ValueError, match='unknown type'):
        mod.check_type_change('int64', 'bigint_ish')


def test_nullability_tightening_is_unsafe_and_loosening_is_safe():
    mod = _mod()
    assert mod.check_column('int64', True, 'int64', False).kind == 'unsafe'
    assert mod.check_column('int64', False, 'int64', True).kind == 'safe'


def test_review_reports_only_unsafe_changes_on_shared_columns():
    """列の追加・削除は #105 の担当。ここでは見ない。"""
    mod = _mod()
    old = {'id': ('int64', False), 'amount': ('decimal(10,2)', True), 'gone': ('string', True)}
    new = {'id': ('float64', False), 'amount': ('decimal(12,2)', True), 'added': ('string', True)}
    assert mod.review_schema(old, new) == ['id: float64 holds integers exactly only up to 2**53']


def test_this_file_passes_the_type_hint_ratchet():
    spec = importlib.util.spec_from_file_location('audit_for_136', HERE / '117_type_hint_audit.py')
    audit = importlib.util.module_from_spec(spec)
    sys.modules['audit_for_136'] = audit
    spec.loader.exec_module(audit)
    assert audit.audit_file(HERE / '136_schema_evolution_type_widening.py')['missing'] == []
