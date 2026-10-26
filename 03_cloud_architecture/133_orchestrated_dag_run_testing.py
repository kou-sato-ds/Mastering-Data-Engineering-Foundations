"""#133 DAG の失敗の隔離の検証。"""
import importlib.util
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent


def _mod():
    spec = importlib.util.spec_from_file_location('dag_mod', HERE / '133_orchestrated_dag_run.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules['dag_mod'] = module
    spec.loader.exec_module(module)
    return module


def _failing(*names):
    def run(task):
        if task in names:
            raise RuntimeError(task)
    return run


def test_all_success_is_ok():
    mod = _mod()
    report = mod.run_dag({'ingest': set(), 'agg': {'ingest'}}, _failing())
    assert report.ok


def test_downstream_of_a_failure_is_skipped():
    """古いデータで集計した数字を「成功」として出さない。"""
    mod = _mod()
    deps = {'ingest': set(), 'clean': {'ingest'}, 'agg': {'clean'}}
    report = mod.run_dag(deps, _failing('ingest'))
    assert report.status == {'ingest': 'failed', 'clean': 'skipped', 'agg': 'skipped'}
    assert report.blocked_by['agg'] == ['ingest']
    assert not report.ok


def test_independent_branch_keeps_running():
    """1つの失敗で、無関係なレポートまで止めない。"""
    mod = _mod()
    deps = {'sales': set(), 'sales_report': {'sales'}, 'hr': set(), 'hr_report': {'hr'}}
    report = mod.run_dag(deps, _failing('sales'))
    assert report.status['hr_report'] == 'success'
    assert report.status['sales_report'] == 'skipped'


def test_diamond_with_one_failed_parent_is_skipped():
    mod = _mod()
    deps = {'a': set(), 'b': {'a'}, 'c': {'a'}, 'd': {'b', 'c'}}
    report = mod.run_dag(deps, _failing('b'))
    assert report.status['c'] == 'success'
    assert report.blocked_by['d'] == ['b']


def test_every_failed_root_is_listed():
    mod = _mod()
    deps = {'x': set(), 'y': set(), 'join': {'x', 'y'}}
    report = mod.run_dag(deps, _failing('x', 'y'))
    assert report.blocked_by['join'] == ['x', 'y']
    assert report.errors == {'x': 'RuntimeError', 'y': 'RuntimeError'}


def test_tasks_run_after_their_upstream():
    mod = _mod()
    calls = []
    mod.run_dag({'c': {'b'}, 'b': {'a'}, 'a': set()}, calls.append)
    assert calls == ['a', 'b', 'c']


def test_cycle_stops():
    mod = _mod()
    with pytest.raises(ValueError, match='cycle'):
        mod.run_dag({'a': {'b'}, 'b': {'a'}}, _failing())


def test_unknown_dependency_stops():
    mod = _mod()
    with pytest.raises(ValueError, match='unknown dependencies'):
        mod.run_dag({'a': {'ghost'}}, _failing())


def test_this_file_passes_the_type_hint_ratchet():
    spec = importlib.util.spec_from_file_location('audit_for_133', HERE / '117_type_hint_audit.py')
    audit = importlib.util.module_from_spec(spec)
    sys.modules['audit_for_133'] = audit
    spec.loader.exec_module(audit)
    assert audit.audit_file(HERE / '133_orchestrated_dag_run.py')['missing'] == []
