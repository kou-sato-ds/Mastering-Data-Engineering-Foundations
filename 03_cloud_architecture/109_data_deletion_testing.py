"""
#109 削除依頼と保持期限の検証。
"""
import importlib.util
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).parent
SECRET = 'test-secret-not-for-production'
NOW = datetime(2026, 9, 28, tzinfo=timezone.utc)


def _mod():
    path = HERE / '109_data_deletion.py'
    spec = importlib.util.spec_from_file_location('deletion_mod', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules['deletion_mod'] = module
    spec.loader.exec_module(module)
    return module


def _rows(mod):
    sato = mod.subject_token('sato@example.com', SECRET)
    suzuki = mod.subject_token('suzuki@example.com', SECRET)
    return [
        {'email': sato, 'amount': 100},
        {'email': suzuki, 'amount': 200},
        {'email': sato, 'amount': 300},
    ]


def test_token_matches_the_pseudonymized_data():
    """#108 と同じ関数で計算しなければ、該当行を探せない。"""
    mod = _mod()
    pii = mod._pii()
    assert mod.subject_token('sato@example.com', SECRET) == pii.pseudonymize('sato@example.com', SECRET)


def test_all_rows_of_the_subject_are_removed():
    mod = _mod()
    kept, audit = mod.delete_subject(_rows(mod), 'email', 'sato@example.com', SECRET, NOW)

    assert len(kept) == 1
    assert audit['deleted'] == 2


def test_other_subjects_are_untouched():
    mod = _mod()
    kept, _ = mod.delete_subject(_rows(mod), 'email', 'sato@example.com', SECRET, NOW)
    assert kept[0]['amount'] == 200


def test_lookup_is_case_insensitive():
    """依頼文の表記揺れで、消し漏れが起きないこと。"""
    mod = _mod()
    kept, _ = mod.delete_subject(_rows(mod), 'email', ' SATO@Example.com ', SECRET, NOW)
    assert len(kept) == 1


def test_audit_record_contains_no_raw_email():
    """削除の記録に元のアドレスを書けば、消したはずの個人情報が残り続ける。"""
    mod = _mod()
    _, audit = mod.delete_subject(_rows(mod), 'email', 'sato@example.com', SECRET, NOW)
    assert 'sato@example.com' not in str(audit)


def test_repeated_request_is_idempotent():
    mod = _mod()
    once, _ = mod.delete_subject(_rows(mod), 'email', 'sato@example.com', SECRET, NOW)
    twice, audit = mod.delete_subject(once, 'email', 'sato@example.com', SECRET, NOW)

    assert twice == once
    assert audit['deleted'] == 0


def test_verification_confirms_removal():
    mod = _mod()
    rows = _rows(mod)
    kept, _ = mod.delete_subject(rows, 'email', 'sato@example.com', SECRET, NOW)

    assert mod.verify_deleted(rows, 'email', 'sato@example.com', SECRET) is False
    assert mod.verify_deleted(kept, 'email', 'sato@example.com', SECRET) is True


def test_expired_rows_are_removed():
    mod = _mod()
    rows = [{'ts': NOW - timedelta(days=100)}, {'ts': NOW - timedelta(days=10)}]
    kept, report = mod.apply_retention(rows, 'ts', NOW)

    assert len(kept) == 1
    assert report['expired'] == 1


def test_row_exactly_at_the_cutoff_is_kept():
    """1日早く消す誤りは取り返しがつかない。"""
    mod = _mod()
    rows = [{'ts': NOW - timedelta(days=90)}]
    kept, _ = mod.apply_retention(rows, 'ts', NOW)
    assert len(kept) == 1


def test_undated_rows_are_kept_but_reported():
    """黙って残し続ければ、期限の無いデータが溜まっていく。"""
    mod = _mod()
    kept, report = mod.apply_retention([{'ts': None}], 'ts', NOW)

    assert len(kept) == 1
    assert report['undated'] == 1


def test_retention_default_matches_item_64():
    """BigQuery 側の90日期限と食い違えば、層ごとに消える時期がずれる。"""
    mod = _mod()
    assert mod.DEFAULT_RETENTION_DAYS == 90