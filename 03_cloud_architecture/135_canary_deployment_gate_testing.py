"""#135 カナリアの昇格判定の検証。"""
import importlib.util
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent


def _mod():
    spec = importlib.util.spec_from_file_location('canary_mod', HERE / '135_canary_deployment_gate.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules['canary_mod'] = module
    spec.loader.exec_module(module)
    return module


def test_clearly_worse_canary_has_a_large_z():
    mod = _mod()
    assert mod.two_proportion_z(10, 10000, 10, 1000) > 5


def test_equal_rates_give_zero_z():
    mod = _mod()
    assert mod.two_proportion_z(10, 1000, 10, 1000) == pytest.approx(0.0)


def test_no_errors_anywhere_gives_zero_z():
    mod = _mod()
    assert mod.two_proportion_z(0, 1000, 0, 1000) == 0.0


def test_too_few_requests_means_wait():
    """失敗0件でも、件数が少なければ安全の証拠にならない。"""
    mod = _mod()
    assert mod.decide((10, 10000), (0, 100)).action == 'wait'


def test_obviously_broken_canary_rolls_back_without_waiting():
    mod = _mod()
    decision = mod.decide((10, 10000), (5, 40))
    assert decision.action == 'rollback'
    assert 'exceeds' in decision.reason


def test_significantly_worse_canary_rolls_back():
    mod = _mod()
    assert mod.decide((10, 10000), (10, 1000)).action == 'rollback'


def test_similar_canary_is_promoted():
    mod = _mod()
    assert mod.decide((10, 10000), (1, 1000)).action == 'promote'


def test_significant_but_tiny_difference_is_promoted():
    """100万件規模では0.03%の差も有意になる。実務上の差が無ければ戻さない。"""
    mod = _mod()
    base, can = (1000, 1_000_000), (1300, 1_000_000)
    assert mod.two_proportion_z(*base, *can) > mod.Z_CRITICAL
    assert mod.decide(base, can).action == 'promote'


def test_noise_is_not_a_reason_to_roll_back():
    """差の基準を外しても、有意でなければ戻さない。"""
    mod = _mod()
    assert mod.decide((1, 1000), (2, 1000), abs_margin=0.0).action == 'promote'


def test_invalid_counts_stop():
    mod = _mod()
    with pytest.raises(ValueError, match='invalid counts'):
        mod.decide((5, 3), (0, 1000))


def test_this_file_passes_the_type_hint_ratchet():
    spec = importlib.util.spec_from_file_location('audit_for_135', HERE / '117_type_hint_audit.py')
    audit = importlib.util.module_from_spec(spec)
    sys.modules['audit_for_135'] = audit
    spec.loader.exec_module(audit)
    assert audit.audit_file(HERE / '135_canary_deployment_gate.py')['missing'] == []
