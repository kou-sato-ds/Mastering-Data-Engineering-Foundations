"""#158 セッション化の検証。間隔は30分(1800秒)。"""
import importlib.util
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent
MIN = 60


def _mod():
    spec = importlib.util.spec_from_file_location('session_mod', HERE / '158_session_window.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules['session_mod'] = module
    spec.loader.exec_module(module)
    return module


def _spans(sessions):
    return [(s.user, s.start, s.end, s.count) for s in sessions]


def test_continuous_activity_is_one_session():
    mod = _mod()
    events = [('u1', 0), ('u1', 10 * MIN), ('u1', 25 * MIN)]
    assert _spans(mod.sessionize(events)) == [('u1', 0, 25 * MIN, 3)]


def test_a_long_pause_starts_a_new_session():
    mod = _mod()
    events = [('u1', 0), ('u1', 5 * MIN), ('u1', 60 * MIN)]
    assert _spans(mod.sessionize(events)) == [('u1', 0, 5 * MIN, 2), ('u1', 60 * MIN, 60 * MIN, 1)]


def test_a_pause_of_exactly_the_gap_stays_in_the_session():
    """境界は「超えたら」別。ちょうど30分は同じセッション。"""
    mod = _mod()
    events = [('u1', 0), ('u1', 30 * MIN)]
    assert len(mod.sessionize(events)) == 1
    assert len(mod.sessionize([('u1', 0), ('u1', 30 * MIN + 1)])) == 2


def test_arrival_order_does_not_matter():
    """ログは届いた順に並んでいない。"""
    mod = _mod()
    ordered = [('u1', 0), ('u1', 5 * MIN), ('u1', 60 * MIN)]
    shuffled = [('u1', 60 * MIN), ('u1', 0), ('u1', 5 * MIN)]
    assert _spans(mod.sessionize(shuffled)) == _spans(mod.sessionize(ordered))


def test_users_are_sessionised_independently():
    mod = _mod()
    events = [('u2', 0), ('u1', 0), ('u2', 10 * MIN), ('u1', 50 * MIN)]
    assert [(s.user, s.count) for s in mod.sessionize(events)] == [('u1', 1), ('u1', 1), ('u2', 2)]


def test_max_length_splits_a_session_that_never_pauses():
    """ボットが24時間操作し続けても、1セッションを無限に伸ばさない。"""
    mod = _mod()
    events = [('bot', t * 10 * MIN) for t in range(13)]
    sessions = mod.sessionize(events, max_length=60 * MIN)
    assert len(mod.sessionize(events)) == 1
    assert [s.start for s in sessions] == [0, 70 * MIN]


def test_session_id_is_the_same_on_every_run():
    """何度作っても同じIDなので、下流への書き込みが冪等になる。"""
    mod = _mod()
    events = [('u1', 1700000000), ('u1', 1700000300)]
    first = [s.session_id for s in mod.sessionize(events)]
    second = [s.session_id for s in mod.sessionize(list(reversed(events)))]
    assert first == second == ['u1:1700000000']


def test_no_events_give_no_sessions():
    mod = _mod()
    assert mod.sessionize([]) == []


def test_invalid_settings_stop():
    mod = _mod()
    with pytest.raises(ValueError, match='gap'):
        mod.sessionize([('u1', 0)], gap=0)
    with pytest.raises(ValueError, match='max_length'):
        mod.sessionize([('u1', 0)], max_length=0)


def test_this_file_passes_the_type_hint_ratchet():
    spec = importlib.util.spec_from_file_location('audit_for_158', HERE / '117_type_hint_audit.py')
    audit = importlib.util.module_from_spec(spec)
    sys.modules['audit_for_158'] = audit
    spec.loader.exec_module(audit)
    assert audit.audit_file(HERE / '158_session_window.py')['missing'] == []
