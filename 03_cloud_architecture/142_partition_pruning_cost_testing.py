"""#142 パーティション刈り込みの検査の検証。10/1〜11/9 の40日分、1日 1000 バイト。"""
import importlib.util
import sys
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).parent


def _mod():
    spec = importlib.util.spec_from_file_location('prune_mod', HERE / '142_partition_pruning_cost.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules['prune_mod'] = module
    spec.loader.exec_module(module)
    return module


def _table():
    first = date(2026, 10, 1)
    return {first + timedelta(days=i): 1000 for i in range(40)}


def test_range_filter_reads_only_matching_days():
    mod = _mod()
    f = mod.Filter('dt', date(2026, 11, 1), date(2026, 11, 4))
    plan = mod.plan_scan(_table(), 'dt', [f])
    assert plan.partitions == [date(2026, 11, 1), date(2026, 11, 2), date(2026, 11, 3)]
    assert plan.bytes_scanned == 3000
    assert plan.pruned


def test_no_filter_is_a_full_scan():
    mod = _mod()
    plan = mod.plan_scan(_table(), 'dt', [])
    assert len(plan.partitions) == 40
    assert mod.review(plan, 40, 10**9) == ['no usable partition filter: full scan of 40 partitions']


def test_filter_on_another_column_does_not_prune():
    mod = _mod()
    plan = mod.plan_scan(_table(), 'dt', [mod.Filter('user_id')])
    assert not plan.pruned
    assert plan.bytes_scanned == 40000


def test_wrapped_partition_column_does_not_prune():
    """CAST(dt AS STRING) LIKE '2026-11%' は、絞っているつもりで全期間を読む。"""
    mod = _mod()
    f = mod.Filter('dt', date(2026, 11, 1), None, prunable=False)
    plan = mod.plan_scan(_table(), 'dt', [f])
    problems = mod.review(plan, 40, 10**9)
    assert len(plan.partitions) == 40
    assert 'filter on dt cannot prune (wrapped in an expression)' in problems


def test_two_filters_intersect():
    mod = _mod()
    filters = [mod.Filter('dt', date(2026, 10, 20), None), mod.Filter('dt', None, date(2026, 10, 22))]
    plan = mod.plan_scan(_table(), 'dt', filters)
    assert plan.partitions == [date(2026, 10, 20), date(2026, 10, 21)]


def test_open_ended_range_reads_until_the_latest_day():
    mod = _mod()
    plan = mod.plan_scan(_table(), 'dt', [mod.Filter('dt', date(2026, 11, 8), None)])
    assert plan.partitions == [date(2026, 11, 8), date(2026, 11, 9)]


def test_pruned_query_can_still_exceed_the_limit():
    mod = _mod()
    plan = mod.plan_scan(_table(), 'dt', [mod.Filter('dt', date(2026, 10, 1), date(2026, 10, 31))])
    assert mod.review(plan, 40, 20000) == ['scans 30000 bytes (> 20000)']


def test_clean_query_has_no_problems():
    mod = _mod()
    plan = mod.plan_scan(_table(), 'dt', [mod.Filter('dt', date(2026, 11, 1), date(2026, 11, 2))])
    assert mod.review(plan, 40, 10**9) == []


def test_empty_range_reads_nothing():
    mod = _mod()
    plan = mod.plan_scan(_table(), 'dt', [mod.Filter('dt', date(2026, 11, 5), date(2026, 11, 5))])
    assert plan.partitions == [] and plan.bytes_scanned == 0


def test_this_file_passes_the_type_hint_ratchet():
    spec = importlib.util.spec_from_file_location('audit_for_142', HERE / '117_type_hint_audit.py')
    audit = importlib.util.module_from_spec(spec)
    sys.modules['audit_for_142'] = audit
    spec.loader.exec_module(audit)
    assert audit.audit_file(HERE / '142_partition_pruning_cost.py')['missing'] == []
