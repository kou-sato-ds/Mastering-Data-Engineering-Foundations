"""
#113 データ契約の検証。
"""
import importlib.util
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).parent
NOW = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)

CONTRACT = {
    'name': 'orders',
    'version': '1.0',
    'owner': 'data-provider@example.com',
    'freshness_hours': 24,
    'fields': {
        'order_id': {'type': 'string', 'required': True},
        'quantity': {'type': 'integer', 'required': True},
        'price': {'type': 'number', 'required': True},
        'gift': {'type': 'boolean', 'required': False},
    },
}


def _mod():
    path = HERE / '113_data_contract.py'
    spec = importlib.util.spec_from_file_location('contract_mod', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules['contract_mod'] = module
    spec.loader.exec_module(module)
    return module


def _row(**overrides):
    base = {'order_id': 'o1', 'quantity': 2, 'price': 9.5}
    base.update(overrides)
    return base


def _deliver(rows, hours_ago=1):
    return _mod().check_delivery(CONTRACT, rows, NOW - timedelta(hours=hours_ago), NOW)


def test_valid_delivery_is_accepted():
    assert _deliver([_row()])['decision'] == 'accept'


def test_contract_without_owner_is_not_a_contract():
    """違反を見つけても、誰に伝えればよいか分からなければ直らない。"""
    contract = {k: v for k, v in CONTRACT.items() if k != 'owner'}
    assert any('owner' in e for e in _mod().validate_contract(contract))


def test_missing_required_field_is_rejected():
    rows = [{k: v for k, v in _row().items() if k != 'quantity'}]
    result = _deliver(rows)
    assert result['decision'] == 'reject'
    assert any('quantity is required' in r for r in result['reasons'])


def test_missing_optional_field_is_fine():
    assert _deliver([_row()])['decision'] == 'accept'


def test_wrong_type_is_rejected():
    result = _deliver([_row(quantity='2')])
    assert any('quantity should be integer' in r for r in result['reasons'])


def test_boolean_is_not_accepted_as_integer():
    """Python では bool が int の仲間なので、素朴に書くと True が数量として通る。"""
    result = _deliver([_row(quantity=True)])
    assert result['decision'] == 'reject'


def test_integer_is_accepted_as_number():
    assert _deliver([_row(price=10)])['decision'] == 'accept'


def test_extra_field_warns_but_does_not_reject():
    """列の追加は後方互換(#105)。止めれば、上流の改善のたびに取り込みが止まる。"""
    result = _deliver([_row(channel='web')])
    assert result['decision'] == 'accept'
    assert result['warnings']


def test_stale_delivery_is_rejected_even_if_rows_are_valid():
    """古いデータを正しく処理しても、古い結果を配るだけである。"""
    result = _deliver([_row()], hours_ago=30)
    assert result['decision'] == 'reject'
    assert any('older than' in r for r in result['reasons'])


def test_empty_delivery_is_rejected():
    assert _deliver([])['decision'] == 'reject'


def test_rejection_notice_names_who_to_contact():
    mod = _mod()
    result = _deliver([_row(quantity='x')])
    notice = mod.render_notice(CONTRACT, result)
    assert 'data-provider@example.com' in notice
    assert 'quantity' in notice