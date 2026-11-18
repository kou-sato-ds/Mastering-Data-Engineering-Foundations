"""#157 構造化ログの点検の検証。"""
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent


def _mod():
    spec = importlib.util.spec_from_file_location('logaudit_mod', HERE / '157_structured_logging_audit.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules['logaudit_mod'] = module
    spec.loader.exec_module(module)
    return module


def _rec(**changes):
    base = {'timestamp': '2026-11-19T08:00:00+09:00', 'level': 'INFO',
            'event': 'articles parsed', 'correlation_id': 'evt-123', 'count': 20}
    base.update(changes)
    return base


def test_well_formed_record_has_no_problems():
    mod = _mod()
    assert mod.audit_record(_rec()) == []


def test_missing_correlation_id_is_reported():
    """相関IDが無いと、同じ処理の前後のログを繋げられない。"""
    mod = _mod()
    record = _rec()
    del record['correlation_id']
    assert mod.audit_record(record) == ['missing correlation_id']


def test_unknown_level_is_reported():
    """Error や err の揺れは、エラーの検索から漏れる。"""
    mod = _mod()
    assert mod.audit_record(_rec(level='Error')) == ["invalid level 'Error'"]


def test_error_needs_an_error_type():
    mod = _mod()
    assert mod.audit_record(_rec(level='ERROR')) == ['error without error_type']
    assert mod.audit_record(_rec(level='ERROR', error_type='TimeoutError')) == []


def test_secret_field_is_reported():
    """ログは鍵の置き場所ではない。"""
    mod = _mod()
    assert mod.audit_record(_rec(api_key='sk-xxx')) == ['secret field api_key']


def test_email_in_a_value_is_reported():
    mod = _mod()
    assert mod.audit_record(_rec(message='sent to sato@example.com')) == [
        'possible email address in message']


def test_lines_report_only_the_problem_lines():
    mod = _mod()
    lines = [json.dumps(_rec()), json.dumps(_rec(level='warn')), '', json.dumps(_rec())]
    assert mod.audit_lines(lines) == {2: ["invalid level 'warn'"]}


def test_non_json_line_is_reported():
    mod = _mod()
    assert mod.audit_lines(['RSS fetch start']) == {1: ['not JSON']}


def test_json_that_is_not_an_object_is_reported():
    mod = _mod()
    assert mod.audit_lines(['[1, 2, 3]']) == {1: ['not a JSON object']}


def test_this_file_passes_the_type_hint_ratchet():
    spec = importlib.util.spec_from_file_location('audit_for_157', HERE / '117_type_hint_audit.py')
    audit = importlib.util.module_from_spec(spec)
    sys.modules['audit_for_157'] = audit
    spec.loader.exec_module(audit)
    assert audit.audit_file(HERE / '157_structured_logging_audit.py')['missing'] == []
