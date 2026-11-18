"""#156 置き場所のガードの検証。最後から2番目のテストが、このリポジトリ自体を検査する。"""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).parent
REPO = HERE.parent


def _mod():
    spec = importlib.util.spec_from_file_location('stray_mod', HERE / '156_stray_file_guard.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules['stray_mod'] = module
    spec.loader.exec_module(module)
    return module


def test_clean_root_has_no_stray_files(tmp_path):
    mod = _mod()
    assert mod.find_stray_python(tmp_path) == []


def test_python_file_at_the_root_is_reported(tmp_path):
    """11/17 の事故の再現。一番上に置かれた本体とテスト。"""
    mod = _mod()
    (tmp_path / '155_idempotent_atomic_publish.py').write_text('x = 1\n', encoding='utf-8')
    (tmp_path / '155_idempotent_atomic_publish_testing.py').write_text('x = 1\n', encoding='utf-8')
    assert mod.find_stray_python(tmp_path) == [
        '155_idempotent_atomic_publish.py', '155_idempotent_atomic_publish_testing.py']


def test_files_in_subfolders_are_not_reported(tmp_path):
    mod = _mod()
    (tmp_path / '03_cloud_architecture').mkdir()
    (tmp_path / '03_cloud_architecture' / '155_x.py').write_text('x = 1\n', encoding='utf-8')
    assert mod.find_stray_python(tmp_path) == []


def test_allowed_root_files_are_not_reported(tmp_path):
    mod = _mod()
    (tmp_path / 'conftest.py').write_text('x = 1\n', encoding='utf-8')
    assert mod.find_stray_python(tmp_path, frozenset({'conftest.py'})) == []


def test_non_python_files_are_ignored(tmp_path):
    mod = _mod()
    (tmp_path / 'README.md').write_text('# x\n', encoding='utf-8')
    assert mod.find_stray_python(tmp_path) == []


def test_this_repository_has_no_stray_python_at_the_root():
    """ガード本体。pre-push フックがこのテストを走らせるので、一番上の .py は push まで届かない。"""
    mod = _mod()
    assert mod.find_stray_python(REPO) == []


def test_this_file_passes_the_type_hint_ratchet():
    spec = importlib.util.spec_from_file_location('audit_for_156', HERE / '117_type_hint_audit.py')
    audit = importlib.util.module_from_spec(spec)
    sys.modules['audit_for_156'] = audit
    spec.loader.exec_module(audit)
    assert audit.audit_file(HERE / '156_stray_file_guard.py')['missing'] == []
