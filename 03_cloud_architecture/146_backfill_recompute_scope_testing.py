"""#146 再計算の範囲の検証。"""
import importlib.util
import sys
from datetime import date
from pathlib import Path

import pytest

HERE = Path(__file__).parent
UNTIL = date(2026, 11, 30)


def _mod():
    spec = importlib.util.spec_from_file_location('scope_mod', HERE / '146_backfill_recompute_scope.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules['scope_mod'] = module
    spec.loader.exec_module(module)
    return module


def _d(day):
    return date(2026, 11, day)


def test_same_day_table_recomputes_only_that_day():
    mod = _mod()
    out = mod.recompute_scope({'raw': {_d(3)}}, {'daily': mod.Derived(('raw',))}, UNTIL)
    assert out['daily'] == [_d(3)]


def test_rolling_window_recomputes_the_following_days():
    """7日移動平均は、直した日から後ろ7日分が変わる。"""
    mod = _mod()
    out = mod.recompute_scope({'raw': {_d(3)}}, {'avg7': mod.Derived(('raw',), 7)}, UNTIL)
    assert out['avg7'] == [_d(d) for d in range(3, 10)]


def test_days_after_until_are_not_recomputed():
    mod = _mod()
    out = mod.recompute_scope({'raw': {_d(3)}}, {'avg7': mod.Derived(('raw',), 7)}, _d(5))
    assert out['avg7'] == [_d(3), _d(4), _d(5)]


def test_change_flows_down_a_chain():
    mod = _mod()
    tables = {'avg7': mod.Derived(('daily',), 7), 'daily': mod.Derived(('raw',))}
    out = mod.recompute_scope({'raw': {_d(3)}}, tables, UNTIL)
    assert out['daily'] == [_d(3)]
    assert out['avg7'] == [_d(d) for d in range(3, 10)]


def test_two_upstreams_are_combined():
    mod = _mod()
    out = mod.recompute_scope({'sales': {_d(3)}, 'returns': {_d(5)}},
                              {'net': mod.Derived(('sales', 'returns'))}, UNTIL)
    assert out['net'] == [_d(3), _d(5)]


def test_overlapping_changes_are_not_duplicated():
    mod = _mod()
    out = mod.recompute_scope({'raw': {_d(3), _d(4)}}, {'avg3': mod.Derived(('raw',), 3)}, UNTIL)
    assert out['avg3'] == [_d(3), _d(4), _d(5), _d(6)]


def test_untouched_source_recomputes_nothing():
    mod = _mod()
    out = mod.recompute_scope({'raw': set()}, {'daily': mod.Derived(('raw',))}, UNTIL)
    assert out['daily'] == []


def test_invalid_definitions_stop():
    mod = _mod()
    with pytest.raises(ValueError, match='lookback'):
        mod.recompute_scope({'raw': set()}, {'x': mod.Derived(('raw',), 0)}, UNTIL)
    with pytest.raises(ValueError, match='unknown upstream'):
        mod.recompute_scope({}, {'x': mod.Derived(('ghost',))}, UNTIL)


def test_this_file_passes_the_type_hint_ratchet():
    spec = importlib.util.spec_from_file_location('audit_for_146', HERE / '117_type_hint_audit.py')
    audit = importlib.util.module_from_spec(spec)
    sys.modules['audit_for_146'] = audit
    spec.loader.exec_module(audit)
    assert audit.audit_file(HERE / '146_backfill_recompute_scope.py')['missing'] == []
