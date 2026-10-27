"""#134 SLO バーンレート警報の検証。SLO 99.9% = バジェット 0.1%。"""
import importlib.util
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent


def _mod():
    spec = importlib.util.spec_from_file_location('burn_mod', HERE / '134_slo_burn_rate.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules['burn_mod'] = module
    spec.loader.exec_module(module)
    return module


def _w(h1, m5, h6, m30):
    """各窓の (失敗数, 全数)。"""
    return {'1h': h1, '5m': m5, '6h': h6, '30m': m30}


def test_burn_rate_is_error_ratio_over_budget():
    mod = _mod()
    assert mod.burn_rate(10, 1000, 0.999) == pytest.approx(10.0)


def test_no_traffic_means_no_burn():
    mod = _mod()
    assert mod.burn_rate(0, 0, 0.999) == 0.0


def test_page_when_both_short_and_long_windows_burn_fast():
    mod = _mod()
    alert = mod.evaluate(_w((20, 1000), (2, 100), (20, 10000), (0, 1000)), 0.999)
    assert alert.level == 'page'
    assert alert.reasons[0].startswith('1h burn 20.0')


def test_recovered_incident_stops_paging():
    """長い窓だけでは、直った後も鳴り続ける。短い窓が0なら鳴らさない。"""
    mod = _mod()
    alert = mod.evaluate(_w((20, 1000), (0, 100), (20, 10000), (0, 1000)), 0.999)
    assert alert.level == 'none'


def test_short_spike_alone_does_not_page():
    """一瞬の揺れで深夜に起こさない。"""
    mod = _mod()
    alert = mod.evaluate(_w((5, 1000), (5, 100), (10, 10000), (5, 1000)), 0.999)
    assert alert.level == 'none'


def test_slow_burn_becomes_a_ticket():
    mod = _mod()
    alert = mod.evaluate(_w((7, 1000), (1, 100), (70, 10000), (7, 1000)), 0.999)
    assert alert.level == 'ticket'


def test_page_takes_precedence_over_ticket():
    mod = _mod()
    alert = mod.evaluate(_w((50, 1000), (5, 100), (500, 10000), (50, 1000)), 0.999)
    assert alert.level == 'page'


@pytest.mark.parametrize('slo', [1.0, 0.0])
def test_invalid_slo_stops(slo):
    mod = _mod()
    with pytest.raises(ValueError, match='slo'):
        mod.burn_rate(1, 10, slo)


def test_more_errors_than_requests_stops():
    mod = _mod()
    with pytest.raises(ValueError, match='invalid counts'):
        mod.burn_rate(11, 10, 0.999)


def test_missing_window_stops():
    mod = _mod()
    with pytest.raises(ValueError, match='missing windows'):
        mod.evaluate({'1h': (0, 10), '5m': (0, 10)}, 0.999)


def test_this_file_passes_the_type_hint_ratchet():
    spec = importlib.util.spec_from_file_location('audit_for_134', HERE / '117_type_hint_audit.py')
    audit = importlib.util.module_from_spec(spec)
    sys.modules['audit_for_134'] = audit
    spec.loader.exec_module(audit)
    assert audit.audit_file(HERE / '134_slo_burn_rate.py')['missing'] == []
