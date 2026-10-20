"""
#127 上書きされた定義のガードの検証。最後から2番目のテストが、このディレクトリ自体を検査する。
"""
import importlib.util
import sys
from pathlib import Path
from textwrap import dedent

import pytest

HERE = Path(__file__).parent


def _mod():
    path = HERE / '127_shadowed_definition_guard.py'
    spec = importlib.util.spec_from_file_location('shadow_mod', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules['shadow_mod'] = module
    spec.loader.exec_module(module)
    return module


def _find(mod, source):
    return mod.find_shadowed(dedent(source))


def test_runtime_keeps_only_the_last_definition():
    """なぜガードが要るか: 実行すると前の定義は跡形もなく消える。"""
    namespace: dict = {}
    exec(dedent('''
        def check():
            return 'first'

        def check():
            return 'second'
    '''), namespace)
    assert namespace['check']() == 'second'


def test_duplicate_test_function_is_reported():
    """前の test_total は pytest に集められず、一度も走らない。"""
    mod = _mod()
    found = _find(mod, '''
        def test_total():
            assert 1

        def test_total():
            assert 2
    ''')
    assert len(found) == 1
    s = found[0]
    assert (s.name, s.kind, s.scope, s.first_line, s.line) == ('test_total', 'function', '<module>', 2, 5)


def test_duplicate_method_reports_its_class():
    mod = _mod()
    found = _find(mod, '''
        class Repo:
            def load(self):
                return 1

            def load(self):
                return 2
    ''')
    assert [(s.name, s.scope) for s in found] == [('load', 'Repo')]


def test_duplicate_class_is_reported():
    mod = _mod()
    found = _find(mod, '''
        class Config:
            pass

        class Config:
            pass
    ''')
    assert [(s.name, s.kind) for s in found] == [('Config', 'class')]


def test_async_function_is_checked():
    mod = _mod()
    found = _find(mod, '''
        async def fetch():
            return 1

        async def fetch():
            return 2
    ''')
    assert [s.name for s in found] == ['fetch']


def test_nested_function_reports_its_parent_scope():
    mod = _mod()
    found = _find(mod, '''
        def outer():
            def helper():
                return 1
            def helper():
                return 2
            return helper()
    ''')
    assert [(s.name, s.scope) for s in found] == [('helper', 'outer')]


def test_same_name_in_different_scopes_is_fine():
    """モジュールの load とクラスの load は別物。"""
    mod = _mod()
    assert _find(mod, '''
        def load():
            return 1

        class Repo:
            def load(self):
                return 2
    ''') == []


def test_property_setter_is_allowed():
    mod = _mod()
    assert _find(mod, '''
        class Box:
            @property
            def size(self):
                return 1

            @size.setter
            def size(self, value):
                pass

            @size.deleter
            def size(self):
                pass
    ''') == []


def test_overload_declarations_are_allowed():
    mod = _mod()
    assert _find(mod, '''
        from typing import overload

        @overload
        def parse(x: int) -> int: ...
        @overload
        def parse(x: str) -> str: ...
        def parse(x):
            return x
    ''') == []


def test_underscore_for_singledispatch_is_allowed():
    mod = _mod()
    assert _find(mod, '''
        @handle.register
        def _(x: int):
            return 1

        @handle.register
        def _(x: str):
            return 2
    ''') == []


def test_conditional_definitions_are_not_checked():
    """if と else で同じ名前を定義するのは、条件で片方だけ使う正しい書き方。"""
    mod = _mod()
    assert _find(mod, '''
        import sys
        if sys.version_info >= (3, 11):
            def now():
                return 1
        else:
            def now():
                return 2
    ''') == []


def test_marked_redefinition_is_allowed():
    mod = _mod()
    assert _find(mod, '''
        def handler():
            return 1

        def handler():  # dup-ok: 学習用に、上書きされる様子を残している
            return 2
    ''') == []


def test_audit_directory_lists_only_files_with_findings(tmp_path):
    mod = _mod()
    (tmp_path / 'clean.py').write_text('def a():\n    pass\n', encoding='utf-8')
    (tmp_path / 'dirty.py').write_text('def a():\n    pass\n\ndef a():\n    pass\n', encoding='utf-8')
    report = mod.audit_directory(tmp_path)
    assert list(report) == ['dirty.py']
    assert 'dirty.py:4: function a in <module> shadows line 1' in mod.format_report(report)


def test_syntax_error_is_not_swallowed():
    """読めないファイルを「問題なし」にはしない(#126 と同じ態度)。"""
    mod = _mod()
    with pytest.raises(SyntaxError):
        mod.find_shadowed('def broken(:', filename='broken.py')


def test_this_directory_has_no_shadowed_definitions():
    """ガード本体。前のテストが黙って消えている箇所を、二度と作らない。"""
    mod = _mod()
    report = mod.audit_directory(HERE)
    assert report == {}, '\n' + mod.format_report(report)


def test_this_file_passes_the_type_hint_ratchet():
    """#117 のラチェット: 新しいファイルは公開関数100%型付き。"""
    spec = importlib.util.spec_from_file_location('audit_for_127', HERE / '117_type_hint_audit.py')
    audit = importlib.util.module_from_spec(spec)
    sys.modules['audit_for_127'] = audit
    spec.loader.exec_module(audit)
    assert audit.audit_file(HERE / '127_shadowed_definition_guard.py')['missing'] == []