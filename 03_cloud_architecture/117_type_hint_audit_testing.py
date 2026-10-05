"""
#117 型ヒント被覆率の検証。
"""
import ast
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).parent


def _mod():
    path = HERE / '117_type_hint_audit.py'
    spec = importlib.util.spec_from_file_location('type_audit_mod', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules['type_audit_mod'] = module
    spec.loader.exec_module(module)
    return module


def _fn(source):
    return ast.parse(source).body[0]


def test_fully_annotated_function_is_detected():
    assert _mod().is_fully_annotated(_fn('def f(a: int, b: str) -> bool: ...'))


def test_missing_return_type_is_not_annotated():
    assert not _mod().is_fully_annotated(_fn('def f(a: int): ...'))


def test_missing_argument_type_is_not_annotated():
    assert not _mod().is_fully_annotated(_fn('def f(a, b: str) -> None: ...'))


def test_self_does_not_need_a_type():
    cls = ast.parse('class C:\n    def m(self, x: int) -> int: ...').body[0]
    assert _mod().is_fully_annotated(cls.body[0])


def test_private_functions_are_not_counted():
    names = [f.name for f in _mod().public_functions('def _hidden(): ...\ndef shown(): ...')]
    assert names == ['shown']


def test_unparsable_file_is_reported_not_crashed(tmp_path):
    """中身が SQL の .py(#93 で見つかったもの)があっても、計測全体を止めない。"""
    bad = tmp_path / '06_query.py'
    bad.write_text('SELECT * FROM t', encoding='utf-8')
    result = _mod().audit_file(bad)
    assert result['unparsable'] is True


def test_floor_has_been_measured():
    """下限が 0.0 のままでは、何も守っていない。"""
    assert _mod().FLOOR > 0, 'run 117_type_hint_audit.py and record the measured floor'


def test_coverage_does_not_fall_below_the_floor():
    """被覆率が下がれば赤。上げるのは自由、下げるのは許さない。"""
    mod = _mod()
    ratio = mod.audit()['ratio']
    assert ratio >= mod.FLOOR, f'type hint coverage fell to {ratio}, below {mod.FLOOR}'


def test_new_files_are_fully_annotated():
    """#117 以降に足すファイルは、公開関数を100%型付きにする。"""
    assert _mod().strict_violations() == []


def test_this_audit_is_itself_fully_annotated():
    """仕組みを導入するファイルが、仕組みの対象から漏れないこと(#104)。"""
    result = _mod().audit_file(HERE / '117_type_hint_audit.py')
    assert result['missing'] == [] and result['total'] > 0