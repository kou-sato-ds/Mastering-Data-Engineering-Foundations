"""
#107 SCD Type 2 の検証。
"""
import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent
D1 = datetime(2026, 9, 1, tzinfo=timezone.utc)
D2 = datetime(2026, 9, 15, tzinfo=timezone.utc)
D3 = datetime(2026, 9, 26, tzinfo=timezone.utc)
TRACKED = ['region']


def _mod():
    path = HERE / '107_scd_type2.py'
    spec = importlib.util.spec_from_file_location('scd2_mod', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules['scd2_mod'] = module
    spec.loader.exec_module(module)
    return module


def _customer(region='関東', name='佐藤'):
    return {'customer_id': 'c1', 'region': region, 'name': name}


def _load(mod, *batches):
    dim = []
    for rows, as_of in batches:
        dim = mod.apply_scd2(dim, rows, 'customer_id', TRACKED, as_of)
    return dim


def test_new_key_is_inserted_as_current():
    mod = _mod()
    dim = _load(mod, ([_customer()], D1))
    assert len(dim) == 1
    assert dim[0]['is_current'] is True
    assert dim[0]['valid_to'] is None


def test_tracked_change_closes_old_and_opens_new():
    """上書きすれば、過去の売上まで新しい地域で集計される。"""
    mod = _mod()
    dim = _load(mod, ([_customer('関東')], D1), ([_customer('関西')], D2))

    assert len(dim) == 2
    old, new = dim
    assert old['region'] == '関東' and old['is_current'] is False
    assert new['region'] == '関西' and new['is_current'] is True


def test_versions_have_no_gap_or_overlap():
    """閉じた時刻と開いた時刻が一致しなければ、その隙間の売上が宙に浮く。"""
    mod = _mod()
    old, new = _load(mod, ([_customer('関東')], D1), ([_customer('関西')], D2))
    assert old['valid_to'] == new['valid_from']


def test_unchanged_row_adds_nothing():
    mod = _mod()
    dim = _load(mod, ([_customer()], D1), ([_customer()], D2))
    assert len(dim) == 1


def test_same_batch_twice_is_idempotent():
    """同じ取り込みを再実行しても、履歴が水増しされないこと。"""
    mod = _mod()
    once = _load(mod, ([_customer('関東')], D1), ([_customer('関西')], D2))
    twice = mod.apply_scd2(once, [_customer('関西')], 'customer_id', TRACKED, D2)
    assert twice == once


def test_untracked_change_overwrites_in_place():
    """誤字修正まで履歴化すれば、行数だけが膨らむ。"""
    mod = _mod()
    dim = _load(mod, ([_customer(name='佐籐')], D1), ([_customer(name='佐藤')], D2))
    assert len(dim) == 1
    assert dim[0]['name'] == '佐藤'


def test_exactly_one_current_row_per_key():
    mod = _mod()
    dim = _load(
        mod,
        ([_customer('関東')], D1),
        ([_customer('関西')], D2),
        ([_customer('九州')], D3),
    )
    assert sum(1 for r in dim if r['is_current']) == 1
    assert len(dim) == 3


def test_point_in_time_lookup_returns_the_version_then_valid():
    mod = _mod()
    dim = _load(mod, ([_customer('関東')], D1), ([_customer('関西')], D2))

    before = datetime(2026, 9, 10, tzinfo=timezone.utc)
    after = datetime(2026, 9, 20, tzinfo=timezone.utc)

    assert mod.lookup_as_of(dim, 'customer_id', 'c1', before)['region'] == '関東'
    assert mod.lookup_as_of(dim, 'customer_id', 'c1', after)['region'] == '関西'


def test_lookup_at_the_switch_moment_returns_one_row():
    """半開区間でなければ、切り替わりの瞬間に2行が該当する。"""
    mod = _mod()
    dim = _load(mod, ([_customer('関東')], D1), ([_customer('関西')], D2))
    assert mod.lookup_as_of(dim, 'customer_id', 'c1', D2)['region'] == '関西'


def test_input_dimension_is_not_mutated():
    mod = _mod()
    original = _load(mod, ([_customer('関東')], D1))
    snapshot = [dict(r) for r in original]

    mod.apply_scd2(original, [_customer('関西')], 'customer_id', TRACKED, D2)

    assert original == snapshot