"""#160 値の決まりの検査の検証。"""
import importlib.util
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent


def _mod():
    spec = importlib.util.spec_from_file_location('domain_mod', HERE / '160_data_quality_domain_rules.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules['domain_mod'] = module
    spec.loader.exec_module(module)
    return module


def _rules(mod):
    R = mod.Rule
    return [R('age', 'range', (0, 130)),
            R('status', 'allowed', frozenset({'new', 'paid', 'cancelled'})),
            R('zip', 'pattern', r'\d{3}-\d{4}', nullable=True)]


def _row(**changes):
    base = {'age': 30, 'status': 'paid', 'zip': '100-0001'}
    base.update(changes)
    return base


def _summary(violations):
    return [(v.column, v.kind, v.count) for v in violations]


def test_clean_rows_have_no_violations():
    mod = _mod()
    assert mod.check([_row(), _row(age=0), _row(age=130)], _rules(mod)) == []


def test_out_of_range_value_is_counted_with_samples():
    mod = _mod()
    violations = mod.check([_row(age=-5), _row(), _row(age=200)], _rules(mod))
    assert _summary(violations) == [('age', 'range', 2)]
    assert violations[0].samples == [-5, 200]


def test_value_outside_the_allowed_set_is_counted():
    """末尾の空白は、目では見えないが別の値。"""
    mod = _mod()
    assert _summary(mod.check([_row(status='paid ')], _rules(mod))) == [('status', 'allowed', 1)]


def test_wrong_format_is_counted():
    mod = _mod()
    assert _summary(mod.check([_row(zip='1000001')], _rules(mod))) == [('zip', 'pattern', 1)]


def test_missing_required_value_is_a_null_violation():
    mod = _mod()
    row = _row()
    del row['status']
    assert _summary(mod.check([row, _row(age=None)], _rules(mod))) == [
        ('age', 'null', 1), ('status', 'null', 1)]


def test_nullable_column_accepts_empty_values():
    mod = _mod()
    assert mod.check([_row(zip=None)], _rules(mod)) == []


def test_wrong_type_is_a_violation():
    """文字列の '30' は、範囲の検査を通さない。"""
    mod = _mod()
    assert _summary(mod.check([_row(age='30'), _row(age=True)], _rules(mod))) == [('age', 'range', 2)]


def test_samples_are_capped():
    mod = _mod()
    rows = [_row(age=-i) for i in range(1, 11)]
    violations = mod.check(rows, _rules(mod), sample_size=3)
    assert violations[0].count == 10 and violations[0].samples == [-1, -2, -3]


def test_broken_rules_stop():
    mod = _mod()
    with pytest.raises(ValueError, match='unknown rule kind'):
        mod.Rule('age', 'between', (0, 1))
    with pytest.raises(Exception):
        mod.Rule('zip', 'pattern', '(')


def test_this_file_passes_the_type_hint_ratchet():
    spec = importlib.util.spec_from_file_location('audit_for_160', HERE / '117_type_hint_audit.py')
    audit = importlib.util.module_from_spec(spec)
    sys.modules['audit_for_160'] = audit
    spec.loader.exec_module(audit)
    assert audit.audit_file(HERE / '160_data_quality_domain_rules.py')['missing'] == []
