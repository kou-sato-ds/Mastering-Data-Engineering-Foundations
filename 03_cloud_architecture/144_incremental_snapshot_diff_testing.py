"""#144 スナップショット差分の検証。"""
import importlib.util
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent


def _mod():
    spec = importlib.util.spec_from_file_location('snapdiff_mod', HERE / '144_incremental_snapshot_diff.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules['snapdiff_mod'] = module
    spec.loader.exec_module(module)
    return module


def _old():
    return [{'id': 1, 'name': '佐藤', 'loaded_at': 'd1'},
            {'id': 2, 'name': '鈴木', 'loaded_at': 'd1'},
            {'id': 3, 'name': '高橋', 'loaded_at': 'd1'}]


def test_new_key_is_an_insert():
    mod = _mod()
    new = _old() + [{'id': 4, 'name': '田中', 'loaded_at': 'd1'}]
    d = mod.diff_snapshots(_old(), new)
    assert [r['id'] for r in d.inserted] == [4]
    assert d.unchanged == 3


def test_missing_key_is_a_delete():
    mod = _mod()
    d = mod.diff_snapshots(_old(), _old()[:2])
    assert [r['id'] for r in d.deleted] == [3]


def test_changed_value_is_an_update_with_its_columns():
    mod = _mod()
    new = _old()
    new[1] = {'id': 2, 'name': '鈴木(旧姓)', 'loaded_at': 'd1'}
    d = mod.diff_snapshots(_old(), new)
    assert [(before['id'], cols) for before, _, cols in d.updated] == [(2, ['name'])]


def test_ignored_column_does_not_make_every_row_an_update():
    """取り込み日時のように毎回変わる列を比べると、全行が更新に見える。"""
    mod = _mod()
    new = [dict(r, loaded_at='d2') for r in _old()]
    assert len(mod.diff_snapshots(_old(), new).updated) == 3
    d = mod.diff_snapshots(_old(), new, ignore=frozenset({'loaded_at'}))
    assert d.updated == [] and d.unchanged == 3


def test_new_column_counts_as_a_change():
    mod = _mod()
    new = _old()
    new[0] = dict(new[0], email='sato@example.com')
    d = mod.diff_snapshots(_old(), new)
    assert d.updated[0][2] == ['email']


def test_duplicate_key_stops():
    mod = _mod()
    with pytest.raises(ValueError, match='duplicate'):
        mod.diff_snapshots(_old(), _old() + [{'id': 1, 'name': '別人'}])


def test_row_without_key_stops():
    mod = _mod()
    with pytest.raises(ValueError, match="without 'id'"):
        mod.diff_snapshots(_old(), [{'name': 'x'}])


def test_empty_new_snapshot_stops():
    """昨日3件・今日0件を「3件削除」として実行しない。"""
    mod = _mod()
    with pytest.raises(ValueError, match='empty'):
        mod.diff_snapshots(_old(), [])


def test_too_many_deletes_stop_unless_allowed():
    """途中で切れたファイルが来ても、テーブルを消さない。"""
    mod = _mod()
    with pytest.raises(ValueError, match='would be deleted'):
        mod.diff_snapshots(_old(), _old()[:1])
    d = mod.diff_snapshots(_old(), _old()[:1], max_delete_ratio=0.8)
    assert len(d.deleted) == 2


def test_this_file_passes_the_type_hint_ratchet():
    spec = importlib.util.spec_from_file_location('audit_for_144', HERE / '117_type_hint_audit.py')
    audit = importlib.util.module_from_spec(spec)
    sys.modules['audit_for_144'] = audit
    spec.loader.exec_module(audit)
    assert audit.audit_file(HERE / '144_incremental_snapshot_diff.py')['missing'] == []
