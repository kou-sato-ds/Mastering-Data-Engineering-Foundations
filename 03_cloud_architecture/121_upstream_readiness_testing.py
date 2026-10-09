"""
#121 上流レディネス判定の検証。
"""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).parent


def _mod():
    path = HERE / '121_upstream_readiness.py'
    spec = importlib.util.spec_from_file_location('readiness_mod', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules['readiness_mod'] = module
    spec.loader.exec_module(module)
    return module


def _u(mod, name='orders', exists=True, marker=True, rows=1000, min_rows=100):
    return mod.Upstream(name=name, partition_exists=exists, has_success_marker=marker,
                        row_count=rows, min_rows=min_rows)


def test_ready_upstreams_run():
    mod = _mod()
    assert mod.decide([_u(mod), _u(mod, 'products')], 0, 3600) == mod.RUN


def test_missing_partition_waits():
    mod = _mod()
    assert mod.decide([_u(mod, exists=False)], 60, 3600) == mod.WAIT


def test_missing_marker_waits_even_with_enough_rows():
    """行数が十分に見えても、完了マーカーが無ければ書きかけかもしれない。"""
    mod = _mod()
    assert mod.decide([_u(mod, marker=False, rows=5000)], 60, 3600) == mod.WAIT


def test_too_few_rows_waits():
    mod = _mod()
    assert mod.decide([_u(mod, rows=10)], 60, 3600) == mod.WAIT


def test_timeout_fails_instead_of_running_partially():
    """欠けた数字を配るより、届かないことを伝える方が正しい。"""
    mod = _mod()
    ups = [_u(mod), _u(mod, 'products', exists=False)]
    assert mod.decide(ups, 3600, 3600) == mod.FAIL


def test_never_runs_when_any_upstream_is_not_ready():
    mod = _mod()
    ups = [_u(mod), _u(mod, 'products', marker=False)]
    for waited in (0, 1800, 3599, 3600, 9999):
        assert mod.decide(ups, waited, 3600) != mod.RUN


def test_no_registered_upstream_fails():
    """何を待つべきか分からない状態で走らせない。"""
    mod = _mod()
    assert mod.decide([], 0, 3600) == mod.FAIL


def test_poll_never_waits_past_the_deadline():
    mod = _mod()
    assert mod.next_poll(0, 300, 3600) == 300
    assert mod.next_poll(3500, 300, 3600) == 100
    assert mod.next_poll(4000, 300, 3600) == 0


def test_status_lists_what_is_missing():
    mod = _mod()
    ups = [_u(mod, 'products', exists=False)]
    text = mod.render_status(ups, mod.FAIL)
    assert 'fail' in text and 'products: partition has not arrived' in text


def test_this_file_passes_the_type_hint_ratchet():
    """#117 のラチェット: 新しいファイルは公開関数100%型付き。"""
    spec = importlib.util.spec_from_file_location('audit_for_121', HERE / '117_type_hint_audit.py')
    audit = importlib.util.module_from_spec(spec)
    sys.modules['audit_for_121'] = audit
    spec.loader.exec_module(audit)
    assert audit.audit_file(HERE / '121_upstream_readiness.py')['missing'] == []