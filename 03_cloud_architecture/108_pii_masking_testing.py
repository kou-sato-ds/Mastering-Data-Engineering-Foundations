"""
#108 PII 仮名化・マスキングの検証。
"""
import hashlib
import importlib.util
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent
SECRET = 'test-secret-not-for-production'


def _mod():
    path = HERE / '108_pii_masking.py'
    spec = importlib.util.spec_from_file_location('pii_mod', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules['pii_mod'] = module
    spec.loader.exec_module(module)
    return module


POLICY = {
    'customer_id': 'keep',
    'email': 'pseudonymize',
    'phone': 'mask',
    'name': 'drop',
    'note': 'keep',
}


def _row(**overrides):
    base = {
        'customer_id': 'c1',
        'email': 'sato@example.com',
        'phone': '090-1234-5678',
        'name': '佐藤',
        'note': '配送希望は午前',
    }
    base.update(overrides)
    return base


def test_same_value_yields_same_token():
    """同じ人が同じトークンになるから、仮名化後も JOIN できる。"""
    mod = _mod()
    assert mod.pseudonymize('sato@example.com', SECRET) == mod.pseudonymize('sato@example.com', SECRET)


def test_token_ignores_case_and_whitespace():
    """表記揺れで別人扱いになれば、集計が割れる。"""
    mod = _mod()
    assert mod.pseudonymize(' Sato@Example.com ', SECRET) == mod.pseudonymize('sato@example.com', SECRET)


def test_token_is_not_a_plain_hash():
    """単純ハッシュなら、候補を片端から計算して元の値を特定できる。"""
    mod = _mod()
    plain = hashlib.sha256(b'sato@example.com').hexdigest()[:24]
    assert mod.pseudonymize('sato@example.com', SECRET) != 'pii_' + plain


def test_different_secret_yields_different_token():
    mod = _mod()
    assert mod.pseudonymize('sato@example.com', 'a') != mod.pseudonymize('sato@example.com', 'b')


def test_empty_secret_is_rejected():
    mod = _mod()
    with pytest.raises(ValueError):
        mod.pseudonymize('sato@example.com', '')


def test_masking_keeps_only_a_hint():
    mod = _mod()
    assert mod.mask_email('sato@example.com') == 's***@example.com'
    assert mod.mask_phone('090-1234-5678') == '*******5678'


def test_policy_is_applied_per_column():
    mod = _mod()
    result = mod.apply_policy(_row(), POLICY, SECRET)

    assert 'name' not in result
    assert result['email'].startswith('pii_')
    assert result['phone'].endswith('5678')
    assert result['customer_id'] == 'c1'


def test_raw_values_do_not_survive():
    mod = _mod()
    flattened = str(mod.apply_policy(_row(), POLICY, SECRET))
    assert 'sato@example.com' not in flattened
    assert '佐藤' not in flattened
    assert '090-1234-5678' not in flattened


def test_undeclared_column_is_rejected():
    """上流が列を追加した瞬間に、個人情報が素通りする事故を防ぐ。"""
    mod = _mod()
    with pytest.raises(ValueError, match='without a declared action'):
        mod.apply_policy(_row(address='東京都…'), POLICY, SECRET)


def test_unknown_action_is_rejected():
    mod = _mod()
    policy = {**POLICY, 'email': 'encrypt'}
    assert mod.validate_policy(_row().keys(), policy)


def test_pii_hidden_in_free_text_is_reported():
    """メモ欄は個人情報の列として宣言されないまま、連絡先を含みがちである。"""
    mod = _mod()
    rows = [_row(note='折り返しは 080-9999-0000 か sato2@example.com へ')]
    findings = mod.audit_kept_text(rows, POLICY)

    assert findings == [{'row': 0, 'column': 'note', 'count': 2}]


def test_clean_free_text_reports_nothing():
    mod = _mod()
    assert mod.audit_kept_text([_row()], POLICY) == []