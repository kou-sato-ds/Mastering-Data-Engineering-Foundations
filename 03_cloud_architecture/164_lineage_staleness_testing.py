"""#164 鮮度の伝わり方の検証。今は 11/27 9:00。"""
import importlib.util
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

HERE = Path(__file__).parent
NOW = datetime(2026, 11, 27, 9)


def _mod():
    spec = importlib.util.spec_from_file_location('staleness_mod', HERE / '164_lineage_staleness.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules['staleness_mod'] = module
    spec.loader.exec_module(module)
    return module


def _t(day, hour):
    return datetime(2026, 11, day, hour)


TABLES = {'staging.orders': ('raw.orders',), 'mart.sales': ('staging.orders', 'raw.prices')}
BUILT = {'staging.orders': _t(27, 6), 'mart.sales': _t(27, 7)}


def test_source_is_as_of_its_last_update():
    mod = _mod()
    out = mod.data_as_of({'raw.orders': _t(27, 5)}, {}, {})
    assert out['raw.orders'] == (_t(27, 5), 'raw.orders')


def test_rebuilt_today_on_yesterdays_data_is_yesterdays_data():
    """作り直した時刻ではなく、材料の時点がデータの時点。"""
    mod = _mod()
    out = mod.data_as_of({'raw.orders': _t(26, 9), 'raw.prices': _t(27, 5)}, TABLES, BUILT)
    assert out['mart.sales'] == (_t(26, 9), 'raw.orders')


def test_the_oldest_input_decides():
    mod = _mod()
    out = mod.data_as_of({'raw.orders': _t(27, 5), 'raw.prices': _t(25, 0)}, TABLES, BUILT)
    assert out['mart.sales'] == (_t(25, 0), 'raw.prices')


def test_table_not_rebuilt_since_the_source_changed_is_as_of_its_build():
    """元が更新されても、作り直すまでは古いまま。"""
    mod = _mod()
    out = mod.data_as_of({'raw.orders': _t(27, 8)}, {'staging.orders': ('raw.orders',)},
                         {'staging.orders': _t(27, 6)})
    assert out['staging.orders'] == (_t(27, 6), 'staging.orders')


def test_stale_report_names_the_root_cause():
    """「mart が古い」ではなく「raw.orders が止まっている」と言う。"""
    mod = _mod()
    out = mod.data_as_of({'raw.orders': _t(26, 9), 'raw.prices': _t(27, 5)}, TABLES, BUILT)
    assert mod.stale_tables(out, NOW, timedelta(hours=6)) == [
        'mart.sales: 24h old <- raw.orders', 'raw.orders: 24h old <- raw.orders',
        'staging.orders: 24h old <- raw.orders']


def test_fresh_pipeline_reports_nothing():
    mod = _mod()
    out = mod.data_as_of({'raw.orders': _t(27, 5), 'raw.prices': _t(27, 5)}, TABLES, BUILT)
    assert mod.stale_tables(out, NOW, timedelta(hours=6)) == []


def test_age_equal_to_the_limit_is_not_stale():
    mod = _mod()
    out = mod.data_as_of({'raw.orders': _t(27, 3)}, {}, {})
    assert mod.stale_tables(out, NOW, timedelta(hours=6)) == []


def test_unknown_input_or_missing_build_time_stops():
    mod = _mod()
    with pytest.raises(ValueError, match='unknown input'):
        mod.data_as_of({}, {'mart.x': ('raw.ghost',)}, {'mart.x': NOW})
    with pytest.raises(ValueError, match='missing build time'):
        mod.data_as_of({'raw.orders': NOW}, {'mart.x': ('raw.orders',)}, {})


def test_cycle_stops():
    mod = _mod()
    with pytest.raises(ValueError, match='cycle'):
        mod.data_as_of({}, {'a': ('b',), 'b': ('a',)}, {'a': NOW, 'b': NOW})


def test_this_file_passes_the_type_hint_ratchet():
    spec = importlib.util.spec_from_file_location('audit_for_164', HERE / '117_type_hint_audit.py')
    audit = importlib.util.module_from_spec(spec)
    sys.modules['audit_for_164'] = audit
    spec.loader.exec_module(audit)
    assert audit.audit_file(HERE / '164_lineage_staleness.py')['missing'] == []
