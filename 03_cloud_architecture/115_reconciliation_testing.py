"""
#115 データ突合の検証。
"""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).parent


def _mod():
    path = HERE / '115_reconciliation.py'
    spec = importlib.util.spec_from_file_location('recon_mod', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules['recon_mod'] = module
    spec.loader.exec_module(module)
    return module


SOURCE = [
    {'id': 'a', 'amount': 100},
    {'id': 'b', 'amount': 200},
    {'id': 'c', 'amount': 300},
]


def _run(target, measures=('amount',), tolerance=0.0):
    return _mod().reconcile(SOURCE, target, 'id', list(measures), tolerance)


def test_identical_data_matches():
    assert _run([dict(r) for r in SOURCE])['status'] == 'match'


def test_missing_row_is_detected():
    result = _run(SOURCE[:2])
    assert result['status'] == 'mismatch'
    assert any('missing' in r for r in result['reasons'])


def test_same_count_with_missing_and_duplicate_is_a_mismatch():
    """件数だけで合格にすれば、欠落と重複が打ち消し合ったケースを見逃す。"""
    target = [SOURCE[0], SOURCE[1], SOURCE[1]]
    result = _run(target)
    assert result['source_rows'] == result['target_rows']
    assert result['status'] == 'mismatch'
    assert any('duplicated' in r for r in result['reasons'])
    assert any('missing' in r for r in result['reasons'])


def test_unexpected_row_is_detected():
    result = _run(SOURCE + [{'id': 'z', 'amount': 0}])
    assert any('unexpected' in r for r in result['reasons'])


def test_total_difference_is_detected_even_when_keys_match():
    """件数もキーも合っていても、金額が丸められていれば合計がずれる。"""
    target = [dict(r) for r in SOURCE]
    target[2]['amount'] = 299
    result = _run(target)
    assert result['status'] == 'mismatch'
    assert any('total of amount differs by -1' in r for r in result['reasons'])


def test_tolerance_absorbs_float_noise():
    mod = _mod()
    src = [{'id': 'a', 'rate': 0.1}, {'id': 'b', 'rate': 0.2}]
    tgt = [{'id': 'a', 'rate': 0.1}, {'id': 'b', 'rate': 0.2000000001}]
    assert mod.reconcile(src, tgt, 'id', ['rate'], tolerance=1e-6)['status'] == 'match'


def test_zero_tolerance_catches_float_noise():
    mod = _mod()
    src = [{'id': 'a', 'rate': 0.1}]
    tgt = [{'id': 'a', 'rate': 0.1000001}]
    assert mod.reconcile(src, tgt, 'id', ['rate'])['status'] == 'mismatch'


def test_samples_are_limited():
    """10万件を全部並べても、誰も読めない。"""
    mod = _mod()
    source = [{'id': f'k{i:03d}', 'amount': 1} for i in range(50)]
    result = mod.reconcile(source, [], 'id', ['amount'])
    missing_line = next(r for r in result['reasons'] if 'missing' in r)
    assert missing_line.startswith('50 keys missing')
    assert missing_line.count("'k") == mod.SAMPLE_LIMIT


def test_null_measure_counts_as_zero():
    mod = _mod()
    src = [{'id': 'a', 'amount': None}]
    tgt = [{'id': 'a', 'amount': 0}]
    assert mod.reconcile(src, tgt, 'id', ['amount'])['status'] == 'match'


def test_summary_shows_verdict_and_counts():
    mod = _mod()
    text = mod.render_summary(_run(SOURCE[:2]), 'orders 移行')
    assert 'mismatch' in text
    assert '移行元 3 / 移行先 2' in text