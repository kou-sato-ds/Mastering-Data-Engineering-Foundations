"""#148 分布のずれ検知(PSI)の検証。基準は 0〜999 の一様な値。"""
import importlib.util
import math
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent


def _mod():
    spec = importlib.util.spec_from_file_location('psi_mod', HERE / '148_distribution_drift_psi.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules['psi_mod'] = module
    spec.loader.exec_module(module)
    return module


def _base():
    return list(range(1000))


def _shift(n):
    return [v + n for v in range(1000)]


def test_edges_split_the_baseline_into_equal_counts():
    mod = _mod()
    assert mod.quantile_edges(_base(), 10) == [100, 200, 300, 400, 500, 600, 700, 800, 900]


def test_counts_cover_every_value():
    mod = _mod()
    edges = mod.quantile_edges(_base(), 10)
    assert sum(mod.bin_counts(_shift(75), edges)) == 1000


def test_identical_distribution_is_stable():
    mod = _mod()
    result = mod.evaluate(_base(), _base())
    assert result.psi == pytest.approx(0.0)
    assert result.level == 'stable'


def test_small_shift_is_stable():
    mod = _mod()
    assert mod.evaluate(_base(), _shift(50)).level == 'stable'


def test_medium_shift_is_moderate():
    mod = _mod()
    result = mod.evaluate(_base(), _shift(75))
    assert 0.1 <= result.psi < 0.25
    assert result.level == 'moderate'


def test_large_shift_is_major():
    """件数も型も正しいのに、分布だけが大きく変わった。"""
    mod = _mod()
    assert mod.evaluate(_base(), _shift(300)).level == 'major'


def test_empty_bins_do_not_make_psi_infinite():
    mod = _mod()
    assert math.isfinite(mod.evaluate(_base(), [0.0] * 1000).psi)


def test_too_few_values_stop():
    mod = _mod()
    with pytest.raises(ValueError, match='at least'):
        mod.evaluate(_base(), [1.0, 2.0])


def test_too_few_bins_stop():
    mod = _mod()
    with pytest.raises(ValueError, match='bins'):
        mod.evaluate(_base(), _base(), bins=1)


def test_this_file_passes_the_type_hint_ratchet():
    spec = importlib.util.spec_from_file_location('audit_for_148', HERE / '117_type_hint_audit.py')
    audit = importlib.util.module_from_spec(spec)
    sys.modules['audit_for_148'] = audit
    spec.loader.exec_module(audit)
    assert audit.audit_file(HERE / '148_distribution_drift_psi.py')['missing'] == []
