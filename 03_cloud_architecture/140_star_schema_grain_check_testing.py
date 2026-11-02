"""#140 ファクトの粒度検査の検証。粒度 = 日付 × 店舗。"""
import importlib.util
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent


def _mod():
    spec = importlib.util.spec_from_file_location('grain_mod', HERE / '140_star_schema_grain_check.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules['grain_mod'] = module
    spec.loader.exec_module(module)
    return module


def _row(date, store, amount):
    return {'date': date, 'store': store, 'amount': amount}


def test_unique_grain_is_ok():
    mod = _mod()
    rows = [_row('2026-11-01', 'A', 100), _row('2026-11-01', 'B', 200), _row('2026-11-02', 'A', 50)]
    report = mod.check_grain(rows, ('date', 'store'))
    assert report.ok
    assert report.extra_rows == 0


def test_duplicate_rows_inflate_the_sum():
    """なぜ検査が要るか: 二重取り込みで SUM が黙って倍になる。"""
    rows = [_row('2026-11-01', 'A', 100), _row('2026-11-01', 'A', 100)]
    assert sum(r['amount'] for r in rows) == 200


def test_exact_duplicate_is_separated():
    mod = _mod()
    rows = [_row('2026-11-01', 'A', 100), _row('2026-11-01', 'A', 100)]
    report = mod.check_grain(rows, ('date', 'store'))
    assert report.exact_duplicates == {('2026-11-01', 'A'): 2}
    assert report.conflicting == {}
    assert report.extra_rows == 1


def test_conflicting_duplicate_is_separated():
    """どちらが正しいか分からない。勝手に片方を捨てない。"""
    mod = _mod()
    rows = [_row('2026-11-01', 'A', 100), _row('2026-11-01', 'A', 120)]
    report = mod.check_grain(rows, ('date', 'store'))
    assert report.conflicting == {('2026-11-01', 'A'): 2}
    assert report.exact_duplicates == {}


def test_three_copies_count_as_two_extra_rows():
    mod = _mod()
    rows = [_row('2026-11-01', 'A', 100)] * 3
    assert mod.check_grain(rows, ('date', 'store')).extra_rows == 2


def test_empty_grain_value_is_counted_separately():
    mod = _mod()
    rows = [_row('2026-11-01', None, 100), _row('', 'A', 100), _row('2026-11-01', 'A', 100)]
    report = mod.check_grain(rows, ('date', 'store'))
    assert report.null_key_rows == 2
    assert not report.ok


def test_missing_grain_column_is_treated_as_empty():
    mod = _mod()
    report = mod.check_grain([{'date': '2026-11-01', 'amount': 1}], ('date', 'store'))
    assert report.null_key_rows == 1


def test_finer_grain_resolves_the_duplicate():
    """粒度の宣言が粗すぎても重複に見える。商品まで含めれば1行ずつ。"""
    mod = _mod()
    rows = [dict(_row('2026-11-01', 'A', 100), item='x'), dict(_row('2026-11-01', 'A', 30), item='y')]
    assert not mod.check_grain(rows, ('date', 'store')).ok
    assert mod.check_grain(rows, ('date', 'store', 'item')).ok


def test_empty_grain_declaration_stops():
    mod = _mod()
    with pytest.raises(ValueError, match='grain'):
        mod.check_grain([_row('2026-11-01', 'A', 1)], ())


def test_this_file_passes_the_type_hint_ratchet():
    spec = importlib.util.spec_from_file_location('audit_for_140', HERE / '117_type_hint_audit.py')
    audit = importlib.util.module_from_spec(spec)
    sys.modules['audit_for_140'] = audit
    spec.loader.exec_module(audit)
    assert audit.audit_file(HERE / '140_star_schema_grain_check.py')['missing'] == []
