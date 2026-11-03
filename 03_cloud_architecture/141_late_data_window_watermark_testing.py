"""#141 遅れて届くデータの検証。窓 60秒・遅れ 10秒・許容遅延 30秒。"""
import importlib.util
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent


def _mod():
    spec = importlib.util.spec_from_file_location('late_mod', HERE / '141_late_data_window_watermark.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules['late_mod'] = module
    spec.loader.exec_module(module)
    return module


def _counter(mod):
    return mod.WindowedCounter(size=60, lag=10, allowed_lateness=30)


def test_window_is_finalised_when_the_watermark_passes_its_end():
    mod = _mod()
    c = _counter(mod)
    for t in (5, 20, 70):
        c.add(t)
    assert c.emitted == [('final', 0, 2)]


def test_window_is_not_closed_early():
    mod = _mod()
    c = _counter(mod)
    c.add(5)
    c.add(50)
    assert c.emitted == []


def test_out_of_order_within_lag_is_on_time():
    """順番が入れ替わっても、想定の遅れの内側なら普通に数える。"""
    mod = _mod()
    c = _counter(mod)
    c.add(55)
    c.add(65)
    assert c.add(50) == 'on_time'
    c.add(75)
    assert c.emitted == [('final', 0, 2)]


def test_late_event_within_allowed_lateness_emits_a_correction():
    mod = _mod()
    c = _counter(mod)
    c.add(5)
    c.add(75)
    assert c.add(30) == 'late_update'
    assert c.emitted == [('final', 0, 1), ('update', 0, 2)]


def test_too_late_event_is_recorded_not_silently_dropped():
    mod = _mod()
    c = _counter(mod)
    c.add(5)
    c.add(125)
    assert c.add(30) == 'too_late'
    assert c.too_late == [30]


def test_state_is_purged_after_allowed_lateness():
    """許容遅延を過ぎた窓の状態は持ち続けない。"""
    mod = _mod()
    c = _counter(mod)
    c.add(5)
    c.add(125)
    assert 0 not in c.counts
    assert 0 not in c.closed


def test_several_windows_are_finalised_in_order():
    mod = _mod()
    c = _counter(mod)
    for t in (5, 65, 130):
        c.add(t)
    assert c.emitted == [('final', 0, 1), ('final', 60, 1)]


def test_invalid_settings_stop():
    mod = _mod()
    with pytest.raises(ValueError):
        mod.WindowedCounter(size=0, lag=0, allowed_lateness=0)
    with pytest.raises(ValueError):
        mod.WindowedCounter(size=60, lag=-1, allowed_lateness=0)
    with pytest.raises(ValueError):
        mod.WindowedCounter(size=60, lag=0, allowed_lateness=-1)


def test_this_file_passes_the_type_hint_ratchet():
    spec = importlib.util.spec_from_file_location('audit_for_141', HERE / '117_type_hint_audit.py')
    audit = importlib.util.module_from_spec(spec)
    sys.modules['audit_for_141'] = audit
    spec.loader.exec_module(audit)
    assert audit.audit_file(HERE / '141_late_data_window_watermark.py')['missing'] == []
