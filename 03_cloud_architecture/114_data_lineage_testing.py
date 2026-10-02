"""
#114 データリネージの検証。
"""
import importlib.util
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent

# raw -> staging -> mart -> dashboard
#                \-> report
EDGES = [
    ('raw_orders', 'stg_orders'),
    ('stg_orders', 'mart_sales'),
    ('mart_sales', 'dashboard_kpi'),
    ('stg_orders', 'report_monthly'),
]
OWNERS = {
    'stg_orders': 'de-team@example.com',
    'mart_sales': 'de-team@example.com',
    'dashboard_kpi': 'sales@example.com',
}


def _mod():
    path = HERE / '114_data_lineage.py'
    spec = importlib.util.spec_from_file_location('lineage_mod', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules['lineage_mod'] = module
    spec.loader.exec_module(module)
    return module


def _graph():
    return _mod().build_graph(EDGES)


def test_direct_downstream_is_found():
    names = [n for n, _ in _mod().downstream(_graph(), 'mart_sales')]
    assert names == ['dashboard_kpi']


def test_downstream_of_downstream_is_found():
    """ダッシュボードのような末端ほど、変更の知らせが届きにくい。"""
    result = dict(_mod().downstream(_graph(), 'raw_orders'))
    assert result['dashboard_kpi'] == 3
    assert result['report_monthly'] == 2


def test_leaf_has_no_downstream():
    assert _mod().downstream(_graph(), 'dashboard_kpi') == []


def test_unknown_table_is_an_error():
    """存在しない表を「影響なし」と答えれば、名前の打ち間違いが安全に見える。"""
    with pytest.raises(KeyError):
        _mod().downstream(_graph(), 'raw_order')


def test_execution_order_puts_upstream_first():
    order = _mod().execution_order(_graph())
    assert order.index('raw_orders') < order.index('stg_orders') < order.index('mart_sales')


def test_execution_order_is_deterministic():
    mod = _mod()
    assert mod.execution_order(_graph()) == mod.execution_order(_graph())


def test_cycle_is_detected():
    """A が B を、B が A を待てば、どちらも永遠に始まらない。"""
    mod = _mod()
    graph = mod.build_graph(EDGES + [('mart_sales', 'stg_orders')])
    with pytest.raises(ValueError, match='cycle'):
        mod.execution_order(graph)


def test_impact_report_lists_contacts():
    report = _mod().impact_report(_graph(), 'stg_orders', OWNERS)
    assert report['contacts'] == ['de-team@example.com', 'sales@example.com']


def test_unowned_tables_are_flagged():
    """連絡先の無い影響先は、変更を知らせる手段が無い。"""
    report = _mod().impact_report(_graph(), 'stg_orders', OWNERS)
    assert report['unowned'] == ['report_monthly']


def test_source_itself_is_not_listed_as_affected():
    report = _mod().impact_report(_graph(), 'stg_orders', OWNERS)
    assert 'stg_orders' not in [a['table'] for a in report['affected']]