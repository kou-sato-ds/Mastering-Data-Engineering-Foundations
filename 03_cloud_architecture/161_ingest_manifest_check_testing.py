"""#161 取り込みファイルの到着検査の検証。"""
import importlib.util
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent


def _mod():
    spec = importlib.util.spec_from_file_location('manifest_mod', HERE / '161_ingest_manifest_check.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules['manifest_mod'] = module
    spec.loader.exec_module(module)
    return module


FILES = {'orders.csv': b'id,amount\n1,500\n', 'customers.csv': b'id,name\n1,sato\n'}


def _manifest(mod):
    return [mod.Entry(n, len(d), mod.sha256_of(d)) for n, d in FILES.items()]


def test_complete_delivery_is_ok():
    mod = _mod()
    assert mod.check_arrival(_manifest(mod), dict(FILES)).ok


def test_missing_file_is_reported():
    mod = _mod()
    report = mod.check_arrival(_manifest(mod), {'orders.csv': FILES['orders.csv']})
    assert report.missing == ['customers.csv'] and not report.ok


def test_unexpected_file_is_reported():
    """置き間違いや古いファイルの残り。"""
    mod = _mod()
    report = mod.check_arrival(_manifest(mod), {**FILES, 'orders_old.csv': b'x'})
    assert report.unexpected == ['orders_old.csv']


def test_empty_file_is_reported():
    mod = _mod()
    report = mod.check_arrival(_manifest(mod), {**FILES, 'orders.csv': b''})
    assert report.empty == ['orders.csv']


def test_truncated_file_is_a_size_mismatch():
    """途中で切れた転送。"""
    mod = _mod()
    report = mod.check_arrival(_manifest(mod), {**FILES, 'orders.csv': FILES['orders.csv'][:5]})
    assert report.size_mismatch == ['orders.csv'] and report.checksum_mismatch == []


def test_same_size_but_different_content_is_a_checksum_mismatch():
    mod = _mod()
    changed = FILES['orders.csv'].replace(b'500', b'900')
    report = mod.check_arrival(_manifest(mod), {**FILES, 'orders.csv': changed})
    assert report.checksum_mismatch == ['orders.csv']


def test_several_problems_are_reported_together():
    mod = _mod()
    report = mod.check_arrival(_manifest(mod), {'orders.csv': b'', 'extra.csv': b'x'})
    assert (report.missing, report.empty, report.unexpected) == (
        ['customers.csv'], ['orders.csv'], ['extra.csv'])


def test_duplicate_names_in_the_manifest_stop():
    mod = _mod()
    entry = _manifest(mod)[0]
    with pytest.raises(ValueError, match='duplicate'):
        mod.check_arrival([entry, entry], dict(FILES))


def test_empty_manifest_with_files_reports_them_all_as_unexpected():
    mod = _mod()
    assert mod.check_arrival([], dict(FILES)).unexpected == ['customers.csv', 'orders.csv']


def test_this_file_passes_the_type_hint_ratchet():
    spec = importlib.util.spec_from_file_location('audit_for_161', HERE / '117_type_hint_audit.py')
    audit = importlib.util.module_from_spec(spec)
    sys.modules['audit_for_161'] = audit
    spec.loader.exec_module(audit)
    assert audit.audit_file(HERE / '161_ingest_manifest_check.py')['missing'] == []
