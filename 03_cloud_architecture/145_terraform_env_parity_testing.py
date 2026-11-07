"""#145 環境間の設定の一致検査の検証。"""
import importlib.util
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent


def _mod():
    spec = importlib.util.spec_from_file_location('parity_mod', HERE / '145_terraform_env_parity.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules['parity_mod'] = module
    spec.loader.exec_module(module)
    return module


def _prod():
    return {'bucket': 'news-prod', 'retention_days': 30,
            'db': {'engine_version': '15.4', 'size': {'cpu': 4, 'memory_gb': 16}}}


def _dev(**changes):
    config = {'bucket': 'news-dev', 'retention_days': 30,
              'db': {'engine_version': '15.4', 'size': {'cpu': 1, 'memory_gb': 2}}}
    config.update(changes)
    return config


ALLOW = frozenset({'bucket', 'db.size.*'})


def test_nested_settings_are_flattened():
    mod = _mod()
    assert mod.flatten({'db': {'size': {'cpu': 4}}}) == {'db.size.cpu': 4}


def test_expected_differences_are_not_problems():
    """バケット名やサーバーの大きさは、違っていて当然。"""
    mod = _mod()
    report = mod.compare_envs({'prod': _prod(), 'dev': _dev()}, ALLOW)
    assert report.ok


def test_must_match_setting_that_differs_is_reported():
    """保持日数が違えば、検証で見えない不具合が本番で出る。"""
    mod = _mod()
    report = mod.compare_envs({'prod': _prod(), 'dev': _dev(retention_days=7)}, ALLOW)
    assert report.problems == ['dev: retention_days = 7, prod = 30']


def test_nested_must_match_setting_is_reported():
    mod = _mod()
    dev = _dev(db={'engine_version': '14.9', 'size': {'cpu': 1, 'memory_gb': 2}})
    report = mod.compare_envs({'prod': _prod(), 'dev': dev}, ALLOW)
    assert report.problems == ["dev: db.engine_version = '14.9', prod = '15.4'"]


def test_missing_setting_is_reported():
    mod = _mod()
    dev = _dev()
    del dev['retention_days']
    assert mod.compare_envs({'prod': _prod(), 'dev': dev}, ALLOW).problems == ['dev: missing retention_days']


def test_extra_setting_is_reported_even_if_allowed_to_differ():
    """値ではなく構造のずれ。許可リストでは隠さない。"""
    mod = _mod()
    report = mod.compare_envs({'prod': _prod(), 'dev': _dev(debug=True)}, ALLOW)
    assert report.problems == ['dev: extra debug (not in prod)']


def test_every_environment_is_compared_with_the_baseline():
    mod = _mod()
    envs = {'prod': _prod(), 'dev': _dev(retention_days=7), 'stg': _dev(retention_days=14)}
    assert [p.split(':')[0] for p in mod.compare_envs(envs, ALLOW).problems] == ['dev', 'stg']


def test_allowance_that_matches_nothing_is_stale():
    """打ち間違いの許可を残すと、次に入った設定を黙って通す。"""
    mod = _mod()
    report = mod.compare_envs({'prod': _prod(), 'dev': _dev()}, ALLOW | {'instance_typo'})
    assert report.stale_allowances == ['instance_typo']


def test_missing_baseline_stops():
    mod = _mod()
    with pytest.raises(ValueError, match='baseline'):
        mod.compare_envs({'dev': _dev()})


def test_this_file_passes_the_type_hint_ratchet():
    spec = importlib.util.spec_from_file_location('audit_for_145', HERE / '117_type_hint_audit.py')
    audit = importlib.util.module_from_spec(spec)
    sys.modules['audit_for_145'] = audit
    spec.loader.exec_module(audit)
    assert audit.audit_file(HERE / '145_terraform_env_parity.py')['missing'] == []
