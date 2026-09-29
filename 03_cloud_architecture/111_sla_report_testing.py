"""
#111 運用レポートの検証。
"""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).parent


def _mod():
    path = HERE / '111_sla_report.py'
    spec = importlib.util.spec_from_file_location('sla_mod', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules['sla_mod'] = module
    spec.loader.exec_module(module)
    return module


def _runs(ok=100, failed=0, seconds=10):
    return [{'ok': True, 'seconds': seconds}] * ok + [{'ok': False, 'seconds': 0}] * failed


def test_p95_reveals_rare_slow_runs():
    """平均では、たまに1時間待たされる体験が見えない。"""
    mod = _mod()
    values = [10] * 94 + [3600] * 6
    assert sum(values) / len(values) < 300
    assert mod.percentile(values, 95) == 3600


def test_percentile_of_empty_is_none():
    assert _mod().percentile([], 95) is None


def test_summary_counts_runs():
    s = _mod().summarize_runs(_runs(ok=98, failed=2))
    assert s['total'] == 100
    assert s['success_rate'] == 0.98


def test_error_budget_shows_remaining_failures():
    mod = _mod()
    budget = mod.error_budget(mod.summarize_runs(_runs(ok=199, failed=1)))
    assert budget == {'allowed': 2, 'used': 1, 'remaining': 1}


def test_healthy_period_is_ok():
    mod = _mod()
    assert mod.evaluate(mod.summarize_runs(_runs()))['status'] == 'ok'


def test_low_success_rate_is_a_breach():
    mod = _mod()
    verdict = mod.evaluate(mod.summarize_runs(_runs(ok=95, failed=5)))
    assert verdict['status'] == 'breach'
    assert any('success rate' in b for b in verdict['breaches'])


def test_slow_p95_is_a_breach():
    mod = _mod()
    verdict = mod.evaluate(mod.summarize_runs(_runs(seconds=600)))
    assert any('p95' in b for b in verdict['breaches'])


def test_waiting_dlq_is_a_breach():
    """成功率が高くても、DLQ に残っていれば誰かのデータが届いていない。"""
    mod = _mod()
    verdict = mod.evaluate(mod.summarize_runs(_runs()), dlq_depth=3)
    assert verdict['status'] == 'breach'


def test_no_runs_is_not_reported_as_success():
    """止まっていた期間を「失敗0件=100%」と報告すれば、停止が隠れる。"""
    mod = _mod()
    summary = mod.summarize_runs([])
    assert summary['success_rate'] is None
    assert mod.evaluate(summary)['status'] == 'no_data'


def test_report_contains_the_numbers_a_client_needs():
    mod = _mod()
    summary = mod.summarize_runs(_runs(ok=199, failed=1))
    report = mod.render_report('2026-09', summary, mod.error_budget(summary), mod.evaluate(summary))
    assert '成功率' in report
    assert 'p95' in report
    assert 'エラーバジェット残' in report