"""#132 時点結合の検証。"""
import importlib.util
import sys
from datetime import datetime
from pathlib import Path

import pytest

HERE = Path(__file__).parent


def _mod():
    spec = importlib.util.spec_from_file_location('asof_mod', HERE / '132_asof_join.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules['asof_mod'] = module
    spec.loader.exec_module(module)
    return module


def _index(mod):
    V = mod.Version
    return mod.build_index([
        V('e1', datetime(2026, 4, 1), datetime(2026, 7, 1), {'branch': '東京'}),
        V('e1', datetime(2026, 7, 1), None, {'branch': '大阪'}),
    ])


def test_fact_gets_the_version_valid_at_that_time():
    """4月の売上は、異動後でも東京のまま。"""
    mod = _mod()
    rows, _ = mod.asof_join([{'emp': 'e1', 'at': datetime(2026, 5, 10)}], _index(mod), 'emp', 'at')
    assert rows[0]['branch'] == '東京'


def test_boundary_belongs_to_the_next_version():
    """半開区間: 7/1 0:00 は新しい版。"""
    mod = _mod()
    assert mod.asof_lookup(_index(mod), 'e1', datetime(2026, 7, 1)).attrs['branch'] == '大阪'


def test_open_ended_current_version():
    mod = _mod()
    assert mod.asof_lookup(_index(mod), 'e1', datetime(2030, 1, 1)).attrs['branch'] == '大阪'


def test_before_first_version_is_kept_and_counted():
    """行を捨てれば合計が減る。"""
    mod = _mod()
    rows, missing = mod.asof_join([{'emp': 'e1', 'at': datetime(2026, 1, 1)}], _index(mod), 'emp', 'at')
    assert len(rows) == 1 and rows[0]['_dim_found'] is False and missing == 1


def test_unknown_key_is_kept_and_counted():
    mod = _mod()
    rows, missing = mod.asof_join([{'emp': 'zz', 'at': datetime(2026, 5, 1)}], _index(mod), 'emp', 'at')
    assert rows[0]['_dim_found'] is False and missing == 1


def test_gap_between_versions_is_not_matched():
    mod = _mod()
    V = mod.Version
    index = mod.build_index([
        V('e2', datetime(2026, 1, 1), datetime(2026, 2, 1), {'b': 'A'}),
        V('e2', datetime(2026, 3, 1), None, {'b': 'B'}),
    ])
    assert mod.asof_lookup(index, 'e2', datetime(2026, 2, 15)) is None


def test_overlapping_versions_stop():
    """どちらの版を引くか決められない。"""
    mod = _mod()
    V = mod.Version
    with pytest.raises(ValueError, match='overlapping'):
        mod.build_index([
            V('e3', datetime(2026, 1, 1), datetime(2026, 6, 1), {}),
            V('e3', datetime(2026, 5, 1), None, {}),
        ])


def test_input_facts_are_not_mutated():
    mod = _mod()
    facts = [{'emp': 'e1', 'at': datetime(2026, 5, 1)}]
    mod.asof_join(facts, _index(mod), 'emp', 'at')
    assert facts == [{'emp': 'e1', 'at': datetime(2026, 5, 1)}]


def test_mixed_batch_counts_add_up():
    mod = _mod()
    facts = [{'emp': 'e1', 'at': datetime(2026, 5, 1)}, {'emp': 'e1', 'at': datetime(2026, 8, 1)},
             {'emp': 'zz', 'at': datetime(2026, 8, 1)}]
    rows, missing = mod.asof_join(facts, _index(mod), 'emp', 'at')
    assert [r.get('branch') for r in rows] == ['東京', '大阪', None]
    assert missing == 1


def test_this_file_passes_the_type_hint_ratchet():
    spec = importlib.util.spec_from_file_location('audit_for_132', HERE / '117_type_hint_audit.py')
    audit = importlib.util.module_from_spec(spec)
    sys.modules['audit_for_132'] = audit
    spec.loader.exec_module(audit)
    assert audit.audit_file(HERE / '132_asof_join.py')['missing'] == []
