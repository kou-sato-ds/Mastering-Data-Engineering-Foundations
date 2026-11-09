"""#147 列の変更の影響範囲の検証。"""
import importlib.util
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent


def _mod():
    spec = importlib.util.spec_from_file_location('colimpact_mod', HERE / '147_lineage_column_impact.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules['colimpact_mod'] = module
    spec.loader.exec_module(module)
    return module


def _columns():
    return {
        'staging_users.contact': ('users.email',),
        'staging_users.uid': ('users.id',),
        'mart.contact': ('staging_users.contact',),
        'mart.contact_domain': ('staging_users.contact',),
        'mart.uid': ('staging_users.uid',),
        'people.full_name': ('users.last_name', 'users.first_name'),
    }


def test_direct_dependent_breaks():
    mod = _mod()
    assert 'staging_users.contact' in mod.impact_of('users.email', _columns()).broken


def test_renamed_columns_downstream_also_break():
    """名前が違っても、流れを辿れば見つかる。"""
    mod = _mod()
    impact = mod.impact_of('users.email', _columns())
    assert impact.broken == ['mart.contact', 'mart.contact_domain', 'staging_users.contact']
    assert impact.paths['mart.contact'] == ['users.email', 'staging_users.contact', 'mart.contact']


def test_unrelated_columns_are_untouched():
    mod = _mod()
    assert 'mart.uid' not in mod.impact_of('users.email', _columns()).broken


def test_column_built_from_several_inputs_breaks_when_one_goes():
    mod = _mod()
    assert mod.impact_of('users.first_name', _columns()).broken == ['people.full_name']


def test_affected_tables_are_listed():
    mod = _mod()
    assert mod.impact_of('users.email', _columns()).tables == ['mart', 'staging_users']


def test_leaf_column_breaks_nothing():
    mod = _mod()
    impact = mod.impact_of('mart.uid', _columns())
    assert impact.broken == [] and impact.tables == []


def test_unknown_column_stops():
    """打ち間違いを「影響なし」と扱わない。"""
    mod = _mod()
    with pytest.raises(ValueError, match='unknown column'):
        mod.impact_of('users.emial', _columns())


def test_cycle_does_not_loop_forever():
    mod = _mod()
    cyclic = {'a.x': ('b.y',), 'b.y': ('a.x',)}
    assert mod.impact_of('a.x', cyclic).broken == ['b.y']


def test_this_file_passes_the_type_hint_ratchet():
    spec = importlib.util.spec_from_file_location('audit_for_147', HERE / '117_type_hint_audit.py')
    audit = importlib.util.module_from_spec(spec)
    sys.modules['audit_for_147'] = audit
    spec.loader.exec_module(audit)
    assert audit.audit_file(HERE / '147_lineage_column_impact.py')['missing'] == []
