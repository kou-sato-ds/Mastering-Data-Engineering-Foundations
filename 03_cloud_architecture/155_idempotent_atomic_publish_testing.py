"""#155 出力の原子的な公開の検証。保存先は辞書で偽装する。"""
import importlib.util
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent
T = 'mart/daily_sales'


def _mod():
    spec = importlib.util.spec_from_file_location('publish_mod', HERE / '155_idempotent_atomic_publish.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules['publish_mod'] = module
    spec.loader.exec_module(module)
    return module


def _ok(files):
    return None


def _reject(files):
    raise ValueError('row count is zero')


def test_published_files_are_readable():
    mod = _mod()
    store = {}
    assert mod.publish(store, T, {'part-0.csv': b'a,1'}, 'r1', _ok) is True
    assert mod.read_current(store, T) == {'part-0.csv': b'a,1'}


def test_nothing_published_reads_empty():
    mod = _mod()
    assert mod.read_current({}, T) == {}


def test_failed_validation_keeps_the_current_version():
    """検査に落ちた出力は公開しない。読む側は前の版を見続ける。"""
    mod = _mod()
    store = {}
    mod.publish(store, T, {'part-0.csv': b'old'}, 'r1', _ok)
    with pytest.raises(ValueError, match='row count'):
        mod.publish(store, T, {'part-0.csv': b''}, 'r2', _reject)
    assert mod.read_current(store, T) == {'part-0.csv': b'old'}


def test_failed_validation_leaves_no_leftovers():
    mod = _mod()
    store = {}
    with pytest.raises(ValueError):
        mod.publish(store, T, {'part-0.csv': b''}, 'r1', _reject)
    assert store == {}


def test_new_version_replaces_the_current_one():
    mod = _mod()
    store = {}
    mod.publish(store, T, {'part-0.csv': b'old'}, 'r1', _ok)
    mod.publish(store, T, {'part-0.csv': b'new'}, 'r2', _ok)
    assert mod.read_current(store, T) == {'part-0.csv': b'new'}


def test_rerun_with_the_same_content_does_nothing():
    """同じ実行の再試行は冪等。新しい版が出た後でも、古い版に戻さない。"""
    mod = _mod()
    store = {}
    mod.publish(store, T, {'part-0.csv': b'old'}, 'r1', _ok)
    mod.publish(store, T, {'part-0.csv': b'new'}, 'r2', _ok)
    assert mod.publish(store, T, {'part-0.csv': b'old'}, 'r1', _ok) is False
    assert mod.read_current(store, T) == {'part-0.csv': b'new'}


def test_rerun_with_different_content_stops():
    mod = _mod()
    store = {}
    mod.publish(store, T, {'part-0.csv': b'old'}, 'r1', _ok)
    with pytest.raises(ValueError, match='different content'):
        mod.publish(store, T, {'part-0.csv': b'other'}, 'r1', _ok)


def test_rollback_is_just_moving_the_pointer():
    mod = _mod()
    store = {}
    mod.publish(store, T, {'part-0.csv': b'old'}, 'r1', _ok)
    mod.publish(store, T, {'part-0.csv': b'bad'}, 'r2', _ok)
    mod.rollback(store, T, 'r1')
    assert mod.read_current(store, T) == {'part-0.csv': b'old'}


def test_rollback_to_a_missing_version_stops():
    mod = _mod()
    with pytest.raises(ValueError, match='does not exist'):
        mod.rollback({}, T, 'r9')


def test_this_file_passes_the_type_hint_ratchet():
    spec = importlib.util.spec_from_file_location('audit_for_155', HERE / '117_type_hint_audit.py')
    audit = importlib.util.module_from_spec(spec)
    sys.modules['audit_for_155'] = audit
    spec.loader.exec_module(audit)
    assert audit.audit_file(HERE / '155_idempotent_atomic_publish.py')['missing'] == []
