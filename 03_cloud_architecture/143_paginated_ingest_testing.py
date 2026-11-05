"""#143 ページング取得の完全性の検証。API は「カーソル → (行, 次のカーソル)」の辞書で偽装する。"""
import importlib.util
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent


def _mod():
    spec = importlib.util.spec_from_file_location('paging_mod', HERE / '143_paginated_ingest.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules['paging_mod'] = module
    spec.loader.exec_module(module)
    return module


def _api(pages, calls=None):
    def fetch(cursor):
        if calls is not None:
            calls.append(cursor)
        return pages[cursor]
    return fetch


def _ids(result):
    return [item['id'] for item in result.items]


def test_all_pages_are_collected_in_order():
    mod = _mod()
    pages = {None: ([{'id': 1}, {'id': 2}], 'c2'), 'c2': ([{'id': 3}], 'c3'), 'c3': ([{'id': 4}], None)}
    result = mod.fetch_all(_api(pages))
    assert _ids(result) == [1, 2, 3, 4]
    assert result.pages == 3


def test_single_page_without_cursor():
    mod = _mod()
    result = mod.fetch_all(_api({None: ([{'id': 1}], None)}))
    assert _ids(result) == [1] and result.pages == 1


def test_returned_cursor_is_passed_to_the_next_call():
    mod = _mod()
    calls = []
    pages = {None: ([{'id': 1}], 'c2'), 'c2': ([{'id': 2}], None)}
    mod.fetch_all(_api(pages, calls))
    assert calls == [None, 'c2']


def test_rows_shifted_between_pages_are_counted_once():
    """取り込み中に新しい行が入ると、前のページの最後の行が次のページにも現れる。"""
    mod = _mod()
    pages = {None: ([{'id': 1}, {'id': 2}], 'c2'), 'c2': ([{'id': 2}, {'id': 3}], None)}
    result = mod.fetch_all(_api(pages))
    assert _ids(result) == [1, 2, 3]
    assert result.duplicates == 1


def test_cursor_loop_stops():
    """同じカーソルが返り続けると、無限ループで時間切れになる。"""
    mod = _mod()
    pages = {None: ([{'id': 1}], 'c2'), 'c2': ([{'id': 2}], 'c2')}
    with pytest.raises(RuntimeError, match='returned twice'):
        mod.fetch_all(_api(pages))


def test_page_limit_is_an_error_not_a_truncation():
    """途中までしか取れていないのに、成功として返さない。"""
    mod = _mod()
    pages = {None: ([{'id': 1}], 'c2'), 'c2': ([{'id': 2}], 'c3'), 'c3': ([{'id': 3}], None)}
    with pytest.raises(RuntimeError, match='partial result'):
        mod.fetch_all(_api(pages), max_pages=2)


def test_empty_page_with_a_next_cursor_is_followed():
    mod = _mod()
    pages = {None: ([], 'c2'), 'c2': ([{'id': 1}], None)}
    assert _ids(mod.fetch_all(_api(pages))) == [1]


def test_item_without_key_stops():
    mod = _mod()
    with pytest.raises(ValueError, match="without 'id'"):
        mod.fetch_all(_api({None: ([{'name': 'x'}], None)}))


def test_this_file_passes_the_type_hint_ratchet():
    spec = importlib.util.spec_from_file_location('audit_for_143', HERE / '117_type_hint_audit.py')
    audit = importlib.util.module_from_spec(spec)
    sys.modules['audit_for_143'] = audit
    spec.loader.exec_module(audit)
    assert audit.audit_file(HERE / '143_paginated_ingest.py')['missing'] == []
