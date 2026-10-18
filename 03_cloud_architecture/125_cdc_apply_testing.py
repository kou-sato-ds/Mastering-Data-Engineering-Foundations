"""
#125 CDC 適用の検証。
"""
import importlib.util
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent


def _mod():
    path = HERE / '125_cdc_apply.py'
    spec = importlib.util.spec_from_file_location('cdc_mod', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules['cdc_mod'] = module
    spec.loader.exec_module(module)
    return module


def test_insert_then_update_keeps_the_latest():
    mod = _mod()
    E, t = mod.ChangeEvent, mod.CdcTable()
    mod.apply_batch(t, [E('a', 'insert', 1, {'v': 1}), E('a', 'update', 2, {'v': 2})])
    assert t.rows == {'a': {'v': 2}}


def test_late_old_update_does_not_roll_back():
    """古い更新が新しい値を上書きすれば、過去に巻き戻る。"""
    mod = _mod()
    E, t = mod.ChangeEvent, mod.CdcTable()
    mod.apply_batch(t, [E('a', 'update', 3, {'v': 'new'})])
    stats = mod.apply_batch(t, [E('a', 'update', 2, {'v': 'old'})])
    assert t.rows['a'] == {'v': 'new'}
    assert stats['stale'] == 1


def test_redelivered_change_is_counted_as_duplicate():
    mod = _mod()
    E, t = mod.ChangeEvent, mod.CdcTable()
    mod.apply_batch(t, [E('a', 'insert', 1, {'v': 1})])
    stats = mod.apply_batch(t, [E('a', 'insert', 1, {'v': 1})])
    assert stats == {'applied': 0, 'duplicate': 1, 'stale': 0}


def test_deleted_row_is_not_resurrected_by_a_late_update():
    """一番気づきにくい事故。削除依頼(#109)と重なれば法的にまずい。"""
    mod = _mod()
    E, t = mod.ChangeEvent, mod.CdcTable()
    mod.apply_batch(t, [E('a', 'insert', 1, {'v': 1}), E('a', 'delete', 3)])
    mod.apply_batch(t, [E('a', 'update', 2, {'v': 2})])
    assert 'a' not in t.rows


def test_newer_insert_after_delete_is_applied():
    """墓石は「古いもの」を止めるだけ。新しい追加は通す。"""
    mod = _mod()
    E, t = mod.ChangeEvent, mod.CdcTable()
    mod.apply_batch(t, [E('a', 'insert', 1, {'v': 1}), E('a', 'delete', 2)])
    mod.apply_batch(t, [E('a', 'insert', 5, {'v': 5})])
    assert t.rows['a'] == {'v': 5}


def test_order_inside_a_batch_does_not_matter():
    mod = _mod()
    E = mod.ChangeEvent
    events = [E('a', 'insert', 1, {'v': 1}), E('b', 'insert', 2, {'v': 1}),
              E('a', 'update', 3, {'v': 2}), E('b', 'delete', 4)]
    t1, t2 = mod.CdcTable(), mod.CdcTable()
    mod.apply_batch(t1, events)
    mod.apply_batch(t2, list(reversed(events)))
    assert t1.rows == t2.rows == {'a': {'v': 2}}


def test_stats_add_up():
    mod = _mod()
    E, t = mod.ChangeEvent, mod.CdcTable()
    mod.apply_batch(t, [E('a', 'insert', 5, {'v': 1})])
    events = [E('a', 'update', 4, {'v': 0}), E('a', 'insert', 5, {'v': 1}),
              E('b', 'insert', 6, {'v': 1})]
    stats = mod.apply_batch(t, events)
    assert sum(stats.values()) == len(events)
    assert stats == {'applied': 1, 'duplicate': 1, 'stale': 1}


@pytest.mark.parametrize('kwargs', [
    {'key': 'a', 'op': 'upsert', 'seq': 1, 'data': {}},
    {'key': 'a', 'op': 'update', 'seq': 1, 'data': None},
])
def test_malformed_event_is_rejected(kwargs):
    mod = _mod()
    with pytest.raises(ValueError):
        mod.ChangeEvent(**kwargs)


def test_compaction_forgets_only_old_tombstones():
    """生きている行の seq は消さない。消せば古い更新で巻き戻る。"""
    mod = _mod()
    E, t = mod.ChangeEvent, mod.CdcTable()
    mod.apply_batch(t, [E('a', 'insert', 1, {}), E('a', 'delete', 2),
                        E('b', 'insert', 3, {}), E('b', 'delete', 9),
                        E('c', 'insert', 4, {})])
    removed = mod.compact_tombstones(t, before_seq=5)
    assert removed == 1
    assert set(t.versions) == {'b', 'c'}


def test_this_file_passes_the_type_hint_ratchet():
    """#117 のラチェット: 新しいファイルは公開関数100%型付き。"""
    spec = importlib.util.spec_from_file_location('audit_for_125', HERE / '117_type_hint_audit.py')
    audit = importlib.util.module_from_spec(spec)
    sys.modules['audit_for_125'] = audit
    spec.loader.exec_module(audit)
    assert audit.audit_file(HERE / '125_cdc_apply.py')['missing'] == []