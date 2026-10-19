"""
#126 重複定義ガードの検証。最後から2番目のテストが、このディレクトリ自体を検査する。
"""
import importlib.util
import sys
from pathlib import Path
from textwrap import dedent

import pytest

HERE = Path(__file__).parent


def _mod():
    path = HERE / '126_duplicate_definition_guard.py'
    spec = importlib.util.spec_from_file_location('dupguard_mod', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules['dupguard_mod'] = module
    spec.loader.exec_module(module)
    return module


def _find(mod, source):
    return mod.find_duplicates(dedent(source))


def test_duplicate_dict_key_is_reported_with_both_lines():
    """後ろの値が黙って勝つ。前の行を直しても効かない事故の元。"""
    mod = _mod()
    found = _find(mod, '''
        CONCERN_MAP = {
            'lineage': [114],
            'modeling': [107],
            'lineage': [114],
        }
    ''')
    assert len(found) == 1
    assert found[0].kind == 'dict_key'
    assert found[0].value == "'lineage'"
    assert found[0].name == 'CONCERN_MAP'
    assert (found[0].first_line, found[0].line) == (3, 5)


def test_dict_key_inside_a_function_is_also_checked():
    """辞書の重複キーは、どこにあってもバグ。"""
    mod = _mod()
    found = _find(mod, '''
        def build():
            return {'a': 1, 'b': 2, 'a': 3}
    ''')
    assert [d.kind for d in found] == ['dict_key']
    assert found[0].name is None


def test_distinct_keys_are_clean():
    mod = _mod()
    assert _find(mod, "D = {'a': 1, 'b': 2}\n") == []


def test_repeated_rule_in_a_constant_list_is_reported():
    """後ろのコピーは、前の同じルールに必ず先を越されるので一度も使われない。"""
    mod = _mod()
    found = _find(mod, '''
        RULES = [
            (r'(dedup|duplicate_delivery)', 'idempotency'),
            (r'(type_hint|annotation)', 'testing'),
            (r'(dedup|duplicate_delivery)', 'idempotency'),
        ]
    ''')
    assert len(found) == 1
    assert found[0].kind == 'list_item'
    assert found[0].name == 'RULES'
    assert (found[0].first_line, found[0].line) == (3, 5)


def test_list_nested_in_a_constant_dict_is_checked():
    mod = _mod()
    found = _find(mod, "CONCERN_MAP = {'testing': [68, 69, 68]}\n")
    assert [(d.kind, d.value, d.name) for d in found] == [('list_item', '68', 'CONCERN_MAP')]


def test_lowercase_list_is_data_not_a_definition():
    """関数の中の [0, 0, 0] は初期値。定義ではないので見ない。"""
    mod = _mod()
    assert _find(mod, '''
        def init():
            counts = [0, 0, 0]
            return counts
    ''') == []


def test_tuple_items_are_not_checked():
    """タプルは位置に意味がある。(255, 255, 255) の繰り返しは正常。"""
    mod = _mod()
    assert _find(mod, 'WHITE = (255, 255, 255)\n') == []


def test_set_inside_frozenset_call_is_checked():
    """集合は実行すると1つに潰れる。辞書のキーと同じ。"""
    mod = _mod()
    found = _find(mod, 'RETRYABLE = frozenset({429, 500, 429})\n')
    assert [(d.kind, d.value) for d in found] == [('set_item', '429')]


def test_non_literal_keys_are_not_judged():
    """f() は実行しないと分からない。分からないものは報告しない。"""
    mod = _mod()
    assert _find(mod, 'D = {f(): 1, f(): 2}\n') == []


def test_dict_unpacking_does_not_crash():
    mod = _mod()
    assert _find(mod, "D = {**base, 'a': 1}\n") == []


def test_marked_repetition_is_allowed():
    """意図した繰り返しには dup-ok を付ける。理由はコメントに書く。"""
    mod = _mod()
    assert _find(mod, '''
        WEEKLY = [
            1, 1, 1, 1, 1,  # dup-ok: 平日は毎日1
            0, 0,           # dup-ok: 週末は0
        ]
    ''') == []


def test_audit_directory_lists_only_files_with_findings(tmp_path):
    mod = _mod()
    (tmp_path / 'clean.py').write_text("D = {'a': 1}\n", encoding='utf-8')
    (tmp_path / 'dirty.py').write_text("D = {'a': 1, 'a': 2}\n", encoding='utf-8')
    report = mod.audit_directory(tmp_path)
    assert list(report) == ['dirty.py']
    assert 'dirty.py:1: dict_key' in mod.format_report(report)


def test_file_with_a_bom_is_read(tmp_path):
    """Windows で付きがちな BOM を、構文エラーにしない。"""
    mod = _mod()
    path = tmp_path / 'bom.py'
    path.write_bytes(b'\xef\xbb\xbf' + b"D = {'a': 1, 'a': 2}\n")
    assert len(mod.audit_file(path)) == 1


def test_syntax_error_is_not_swallowed():
    """読めないファイルを「問題なし」にはしない。"""
    mod = _mod()
    with pytest.raises(SyntaxError):
        mod.find_duplicates('D = {', filename='broken.py')


def test_this_directory_has_no_duplicate_definitions():
    """ガード本体。索引と分類ルールで見つけた重複を、二度と起こさない。"""
    mod = _mod()
    report = mod.audit_directory(HERE)
    assert report == {}, '\n' + mod.format_report(report)


def test_this_file_passes_the_type_hint_ratchet():
    """#117 のラチェット: 新しいファイルは公開関数100%型付き。"""
    spec = importlib.util.spec_from_file_location('audit_for_126', HERE / '117_type_hint_audit.py')
    audit = importlib.util.module_from_spec(spec)
    sys.modules['audit_for_126'] = audit
    spec.loader.exec_module(audit)
    assert audit.audit_file(HERE / '126_duplicate_definition_guard.py')['missing'] == []