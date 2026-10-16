"""
#123 重複配信排除の検証。時刻は数値で渡す。
"""
import importlib.util
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent


def _mod():
    path = HERE / '123_dedup_window.py'
    spec = importlib.util.spec_from_file_location('dedup_mod', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules['dedup_mod'] = module
    spec.loader.exec_module(module)
    return module


def _store(mod, ttl=60.0, max_entries=100):
    return mod.DedupStore(ttl_seconds=ttl, max_entries=max_entries)


def test_redelivered_message_is_dropped():
    """at-least-once では同じメッセージが2回届く。仕様通りであり、エラーではない。"""
    mod = _mod()
    events = [{'id': 'e1'}, {'id': 'e2'}, {'id': 'e1'}]
    kept, stats = mod.dedupe(events, _store(mod), now=0.0)
    assert [e['id'] for e in kept] == ['e1', 'e2']
    assert stats['duplicates'] == 1


def test_duplicates_across_batches_are_caught():
    mod = _mod()
    store = _store(mod)
    mod.dedupe([{'id': 'e1'}], store, now=0.0)
    kept, _ = mod.dedupe([{'id': 'e1'}], store, now=10.0)
    assert kept == []


def test_memory_expires_after_ttl():
    """無限に覚えればメモリが尽きる。窓の外の再送は新しいものとして扱う。"""
    mod = _mod()
    store = _store(mod, ttl=60.0)
    mod.dedupe([{'id': 'e1'}], store, now=0.0)
    kept, _ = mod.dedupe([{'id': 'e1'}], store, now=60.0)
    assert len(kept) == 1


def test_forced_eviction_is_counted():
    """上限で仕方なく忘れた件数は、重複がすり抜ける可能性として報告する。"""
    mod = _mod()
    store = _store(mod, max_entries=2)
    _, stats = mod.dedupe([{'id': 'a'}, {'id': 'b'}, {'id': 'c'}], store, now=0.0)
    assert stats['forced_evictions'] == 1
    assert len(store.seen) == 2


def test_forced_eviction_can_let_a_duplicate_through():
    """数える理由を、実際にすり抜ける例で示す。"""
    mod = _mod()
    store = _store(mod, max_entries=2)
    mod.dedupe([{'id': 'a'}, {'id': 'b'}, {'id': 'c'}], store, now=0.0)
    kept, _ = mod.dedupe([{'id': 'a'}], store, now=1.0)
    assert len(kept) == 1


def test_event_without_id_is_kept_and_counted():
    """判定できないものを捨てれば、正しいデータまで消える。"""
    mod = _mod()
    kept, stats = mod.dedupe([{'value': 1}, {'id': ''}], _store(mod), now=0.0)
    assert len(kept) == 2
    assert stats['without_id'] == 2


def test_stats_add_up():
    mod = _mod()
    events = [{'id': 'a'}, {'id': 'a'}, {'x': 1}]
    _, s = mod.dedupe(events, _store(mod), now=0.0)
    assert s['received'] == s['kept'] + s['duplicates']


def test_invalid_store_is_rejected():
    mod = _mod()
    with pytest.raises(ValueError):
        mod.DedupStore(ttl_seconds=0, max_entries=10)


def test_this_file_passes_the_type_hint_ratchet():
    """#117 のラチェット: 新しいファイルは公開関数100%型付き。"""
    spec = importlib.util.spec_from_file_location('audit_for_123', HERE / '117_type_hint_audit.py')
    audit = importlib.util.module_from_spec(spec)
    sys.modules['audit_for_123'] = audit
    spec.loader.exec_module(audit)
    assert audit.audit_file(HERE / '123_dedup_window.py')['missing'] == []