"""#162 複数サービスのデプロイ順の検証。"""
import importlib.util
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent


def _mod():
    spec = importlib.util.spec_from_file_location('release_mod', HERE / '162_deployment_release_order.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules['release_mod'] = module
    spec.loader.exec_module(module)
    return module


def test_nothing_changed_means_no_waves():
    mod = _mod()
    S = mod.Service
    assert mod.plan_waves({'api': 1, 'web': 1}, {'api': S(1), 'web': S(1)}) == []


def test_independent_services_go_out_together():
    mod = _mod()
    S = mod.Service
    assert mod.plan_waves({'api': 1, 'batch': 1}, {'api': S(2), 'batch': S(2)}) == [['api', 'batch']]


def test_consumer_waits_for_the_new_provider():
    """新しい画面が、まだ古いAPIを呼んで壊れる時間を作らない。"""
    mod = _mod()
    S = mod.Service
    targets = {'api': S(2), 'web': S(2, {'api': 2})}
    assert mod.plan_waves({'api': 1, 'web': 1}, targets) == [['api'], ['web']]


def test_consumer_that_works_with_the_current_provider_does_not_wait():
    """今のAPIで動くなら、無駄に待たせない。"""
    mod = _mod()
    S = mod.Service
    targets = {'api': S(2), 'web': S(2, {'api': 1})}
    assert mod.plan_waves({'api': 1, 'web': 1}, targets) == [['api', 'web']]


def test_chain_becomes_one_wave_per_step():
    mod = _mod()
    S = mod.Service
    targets = {'db': S(2), 'api': S(2, {'db': 2}), 'web': S(2, {'api': 2})}
    assert mod.plan_waves({'db': 1, 'api': 1, 'web': 1}, targets) == [['db'], ['api'], ['web']]


def test_unchanged_dependency_is_not_redeployed():
    mod = _mod()
    S = mod.Service
    targets = {'api': S(3), 'web': S(2, {'api': 3})}
    assert mod.plan_waves({'api': 3, 'web': 1}, targets) == [['web']]


def test_new_service_is_deployed_before_its_consumers():
    mod = _mod()
    S = mod.Service
    targets = {'search': S(1), 'web': S(2, {'search': 1})}
    assert mod.plan_waves({'web': 1}, targets) == [['search'], ['web']]


def test_requirement_that_the_release_cannot_meet_stops():
    """存在しない組み合わせは、出す前に止める。"""
    mod = _mod()
    S = mod.Service
    with pytest.raises(ValueError, match='needs api>=3'):
        mod.plan_waves({'api': 1, 'web': 1}, {'api': S(2), 'web': S(2, {'api': 3})})


def test_unknown_dependency_and_cycle_stop():
    mod = _mod()
    S = mod.Service
    with pytest.raises(ValueError, match='unknown service'):
        mod.plan_waves({}, {'web': S(1, {'ghost': 1})})
    with pytest.raises(ValueError, match='circular'):
        mod.plan_waves({'a': 1, 'b': 1}, {'a': S(2, {'b': 2}), 'b': S(2, {'a': 2})})


def test_this_file_passes_the_type_hint_ratchet():
    spec = importlib.util.spec_from_file_location('audit_for_162', HERE / '117_type_hint_audit.py')
    audit = importlib.util.module_from_spec(spec)
    sys.modules['audit_for_162'] = audit
    spec.loader.exec_module(audit)
    assert audit.audit_file(HERE / '162_deployment_release_order.py')['missing'] == []
