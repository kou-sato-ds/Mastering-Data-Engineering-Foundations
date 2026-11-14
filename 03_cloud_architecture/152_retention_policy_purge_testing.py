"""#152 データ保持期限の適用の検証。access_log は 90日、contact は 365日。"""
import importlib.util
import sys
from datetime import date
from pathlib import Path

import pytest

HERE = Path(__file__).parent
TODAY = date(2026, 11, 14)


def _mod():
    spec = importlib.util.spec_from_file_location('retention_mod', HERE / '152_retention_policy_purge.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules['retention_mod'] = module
    spec.loader.exec_module(module)
    return module


def _policy():
    return {'access_log': 90, 'contact': 365}


def _plan(mod, *records):
    return mod.plan_purge(list(records), _policy(), TODAY)


def test_record_within_retention_is_kept():
    mod = _mod()
    plan = _plan(mod, mod.Record('a', 'access_log', date(2026, 11, 1)))
    assert plan.delete == []


def test_record_on_its_expiry_day_is_deleted():
    """作成日 + 90日 の日ちょうども対象。"""
    mod = _mod()
    plan = _plan(mod, mod.Record('a', 'access_log', date(2026, 8, 16)))
    assert plan.delete == ['a']


def test_record_one_day_before_expiry_is_kept():
    mod = _mod()
    plan = _plan(mod, mod.Record('a', 'access_log', date(2026, 8, 17)))
    assert plan.delete == []


def test_each_class_uses_its_own_retention():
    mod = _mod()
    created = date(2026, 1, 1)
    plan = _plan(mod, mod.Record('log', 'access_log', created), mod.Record('c', 'contact', created))
    assert plan.delete == ['log']


def test_legal_hold_keeps_an_expired_record():
    """訴訟で保全が必要なデータは、期限が来ても消さない。"""
    mod = _mod()
    plan = _plan(mod, mod.Record('a', 'access_log', date(2025, 1, 1), legal_hold=True))
    assert plan.delete == []
    assert plan.kept_on_hold == ['a']


def test_hold_on_a_record_within_retention_is_not_reported():
    mod = _mod()
    plan = _plan(mod, mod.Record('a', 'access_log', date(2026, 11, 1), legal_hold=True))
    assert plan.kept_on_hold == []


def test_unknown_class_is_never_deleted():
    """保持期限が分からないことは、消してよいことではない。"""
    mod = _mod()
    plan = _plan(mod, mod.Record('x', 'new_feature_data', date(2020, 1, 1)))
    assert plan.delete == []
    assert plan.unknown_class == ['x']


def test_invalid_retention_stops():
    mod = _mod()
    with pytest.raises(ValueError, match='at least 1 day'):
        mod.plan_purge([], {'access_log': 0}, TODAY)


def test_plan_is_sorted_and_input_is_untouched():
    mod = _mod()
    records = [mod.Record('b', 'access_log', date(2025, 1, 1)),
               mod.Record('a', 'access_log', date(2025, 1, 1))]
    snapshot = list(records)
    assert mod.plan_purge(records, _policy(), TODAY).delete == ['a', 'b']
    assert records == snapshot


def test_this_file_passes_the_type_hint_ratchet():
    spec = importlib.util.spec_from_file_location('audit_for_152', HERE / '117_type_hint_audit.py')
    audit = importlib.util.module_from_spec(spec)
    sys.modules['audit_for_152'] = audit
    spec.loader.exec_module(audit)
    assert audit.audit_file(HERE / '152_retention_policy_purge.py')['missing'] == []
