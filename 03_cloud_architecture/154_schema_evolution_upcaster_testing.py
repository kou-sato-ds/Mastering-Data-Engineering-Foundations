"""#154 スキーマの読み替えの検証。v1: 氏名 → v2: 姓と名 → v3: 通貨を追加。"""
import importlib.util
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent


def _mod():
    spec = importlib.util.spec_from_file_location('upcast_mod', HERE / '154_schema_evolution_upcaster.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules['upcast_mod'] = module
    spec.loader.exec_module(module)
    return module


def _v1_to_v2(event):
    family, given = event.pop('name').split(' ', 1)
    event['family_name'], event['given_name'] = family, given
    return event


def _v2_to_v3(event):
    event.setdefault('currency', 'JPY')
    return event


def _chain():
    return {1: _v1_to_v2, 2: _v2_to_v3}


def test_latest_event_is_unchanged():
    mod = _mod()
    event = {'schema_version': 3, 'family_name': '佐藤', 'given_name': '太郎', 'currency': 'USD'}
    assert mod.upcast(event, _chain(), 3) == event


def test_oldest_event_is_upcast_step_by_step():
    mod = _mod()
    out = mod.upcast({'schema_version': 1, 'name': '佐藤 太郎', 'amount': 500}, _chain(), 3)
    assert out == {'schema_version': 3, 'family_name': '佐藤', 'given_name': '太郎',
                   'amount': 500, 'currency': 'JPY'}


def test_middle_version_runs_only_the_remaining_steps():
    mod = _mod()
    out = mod.upcast({'schema_version': 2, 'family_name': '鈴木', 'given_name': '花子'}, _chain(), 3)
    assert out['currency'] == 'JPY' and out['family_name'] == '鈴木'


def test_input_event_is_not_mutated():
    mod = _mod()
    event = {'schema_version': 1, 'name': '佐藤 太郎'}
    mod.upcast(event, _chain(), 3)
    assert event == {'schema_version': 1, 'name': '佐藤 太郎'}


def test_newer_version_than_the_reader_stops():
    """黙って読めば、知らない列を捨てることになる。読む側を更新する合図。"""
    mod = _mod()
    with pytest.raises(ValueError, match='upgrade the reader'):
        mod.upcast({'schema_version': 4}, _chain(), 3)


def test_missing_version_stops():
    mod = _mod()
    with pytest.raises(ValueError, match='no schema_version'):
        mod.upcast({'name': '佐藤 太郎'}, _chain(), 3)


def test_invalid_version_stops():
    mod = _mod()
    with pytest.raises(ValueError, match='invalid schema_version'):
        mod.upcast({'schema_version': 0}, _chain(), 3)


def test_gap_in_the_chain_stops_and_is_reported():
    mod = _mod()
    broken = {1: _v1_to_v2}
    with pytest.raises(ValueError, match='from version 2 to 3'):
        mod.upcast({'schema_version': 1, 'name': '佐藤 太郎'}, broken, 3)
    assert mod.check_chain(broken, 3) == [2]


def test_complete_chain_has_no_gaps():
    mod = _mod()
    assert mod.check_chain(_chain(), 3) == []


def test_this_file_passes_the_type_hint_ratchet():
    spec = importlib.util.spec_from_file_location('audit_for_154', HERE / '117_type_hint_audit.py')
    audit = importlib.util.module_from_spec(spec)
    sys.modules['audit_for_154'] = audit
    spec.loader.exec_module(audit)
    assert audit.audit_file(HERE / '154_schema_evolution_upcaster.py')['missing'] == []
