"""
#112 月額見積もりの検証。単価はテスト用の架空値であり、実際の料金ではない。
"""
import importlib.util
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).parent
TODAY = date(2026, 9, 30)

PRICES = {
    'as_of': date(2026, 9, 1),
    'unit': {'scan_tib': 5.0, 'storage_gib': 0.02, 'worker_hours': 0.1},
}
USAGE = {'scan_tib': 2, 'storage_gib': 500, 'worker_hours': 100}


def _mod():
    path = HERE / '112_cost_estimate.py'
    spec = importlib.util.spec_from_file_location('cost_estimate_mod', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules['cost_estimate_mod'] = module
    spec.loader.exec_module(module)
    return module


def test_line_items_are_quantity_times_unit_price():
    est = _mod().estimate(USAGE, PRICES)
    amounts = {i['item']: i['amount'] for i in est['items']}
    assert amounts == {'scan_tib': 10.0, 'storage_gib': 10.0, 'worker_hours': 10.0}
    assert est['subtotal'] == 30.0


def test_buffer_is_shown_separately():
    """予備費を合計に黙って混ぜれば、隠れた上乗せになる。"""
    result = _mod().with_buffer(30.0)
    assert result == {'subtotal': 30.0, 'buffer': 6.0, 'total': 36.0}


def test_missing_unit_price_blocks_the_quote():
    """単価の無い項目を0円で計算すれば、見積もりが安く出る。"""
    mod = _mod()
    usage = {**USAGE, 'egress_gib': 50}
    quote = mod.build_quote(usage, PRICES, TODAY)
    assert quote['valid'] is False
    assert any('egress_gib' in e for e in quote['errors'])


def test_price_sheet_without_date_is_rejected():
    mod = _mod()
    prices = {'unit': PRICES['unit']}
    quote = mod.build_quote(USAGE, prices, TODAY)
    assert quote['valid'] is False


def test_stale_prices_raise_a_warning():
    """料金改定を見落としたまま見積もらない。"""
    mod = _mod()
    prices = {**PRICES, 'as_of': date(2026, 1, 1)}
    quote = mod.build_quote(USAGE, prices, TODAY)
    assert quote['valid'] is True
    assert quote['warnings']


def test_fresh_prices_raise_no_warning():
    assert _mod().build_quote(USAGE, PRICES, TODAY)['warnings'] == []


def test_growth_scenario_is_included():
    """データが増えてから驚かせない。"""
    quote = _mod().build_quote(USAGE, PRICES, TODAY)
    totals = {s['factor']: s['total'] for s in quote['scenarios']}
    assert totals == {1: 36.0, 2: 72.0}


def test_quote_states_when_prices_were_valid():
    mod = _mod()
    text = mod.render_quote(mod.build_quote(USAGE, PRICES, TODAY))
    assert '2026-09-01 時点' in text


def test_invalid_quote_shows_no_amount():
    """不備があるまま金額を出せば、その数字が一人歩きする。"""
    mod = _mod()
    text = mod.render_quote(mod.build_quote({'unknown': 1}, PRICES, TODAY))
    assert '見積もり不可' in text
    assert 'USD' not in text


def test_no_prices_are_hard_coded():
    """料金は改定される。コードに書いた単価は、いつか黙って古くなる。"""
    source = (HERE / '112_cost_estimate.py').read_text(encoding='utf-8')
    assert 'unit_price =' not in source
    assert "'unit': {" not in source