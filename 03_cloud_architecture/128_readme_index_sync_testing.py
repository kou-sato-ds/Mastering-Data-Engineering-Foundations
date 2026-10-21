"""
#128 README 索引表の差し替えの検証。
"""
import importlib.util
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent


def _mod():
    path = HERE / '128_readme_index_sync.py'
    spec = importlib.util.spec_from_file_location('readme_sync_mod', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules['readme_sync_mod'] = module
    spec.loader.exec_module(module)
    return module


H = '| 関心 | 項目 | 姉妹プロジェクト対応 |'
ROWS = [H, '|---|---|---|', '| testing | #126-#127 | — |']
DOC = (
    '# Title\n\n'
    f'{H}\n|---|---|---|\n| testing | #126, #127 | — |\n\n'
    '## Spark\n| 設定 | 実行時間 |\n|---|---|\n| コア数 1 | 5.64s |\n'
)


def test_only_the_index_table_is_replaced():
    """README には他の表もある。索引表以外には触らない。"""
    mod = _mod()
    out = mod.replace_table(DOC, ROWS)
    assert '| testing | #126-#127 | — |' in out
    assert '#126, #127' not in out
    assert '| コア数 1 | 5.64s |' in out


def test_replacing_twice_changes_nothing():
    mod = _mod()
    once = mod.replace_table(DOC, ROWS)
    assert mod.replace_table(once, ROWS) == once


def test_missing_header_stops():
    mod = _mod()
    with pytest.raises(ValueError, match='found 0'):
        mod.replace_table('# no table\n', ROWS)


def test_two_headers_stop():
    """どちらを差し替えるか決められない。"""
    mod = _mod()
    with pytest.raises(ValueError, match='found 2'):
        mod.replace_table(DOC + H + '\n', ROWS)


def test_rows_without_header_are_rejected():
    """生成側の出力が壊れていたら、README を壊す前に止める。"""
    mod = _mod()
    with pytest.raises(ValueError, match='must start'):
        mod.replace_table(DOC, ROWS[1:])


def test_crlf_is_preserved():
    """7月の「CRLF で343行の差分」事故を繰り返さない。"""
    mod = _mod()
    out = mod.replace_table(DOC.replace('\n', '\r\n'), ROWS)
    assert '\r\n' in out
    assert '\n' not in out.replace('\r\n', '')


def test_table_at_the_end_of_the_file():
    mod = _mod()
    text = '# T\n' + '\n'.join([H, '|---|---|---|', '| x | #1 | — |'])
    assert mod.replace_table(text, ROWS) == '# T\n' + '\n'.join(ROWS)


def test_check_mode_does_not_write(tmp_path):
    mod = _mod()
    path = tmp_path / 'README.md'
    path.write_bytes(DOC.encode('utf-8'))
    assert mod.sync_readme(path, ROWS, write=False) is True
    assert path.read_bytes() == DOC.encode('utf-8')


def test_write_then_nothing_left_to_do(tmp_path):
    """2回目は「差なし」。冪等であることの証明。"""
    mod = _mod()
    path = tmp_path / 'README.md'
    path.write_bytes(DOC.encode('utf-8'))
    assert mod.sync_readme(path, ROWS, write=True) is True
    assert mod.sync_readme(path, ROWS, write=True) is False


def test_bom_is_preserved(tmp_path):
    mod = _mod()
    path = tmp_path / 'README.md'
    path.write_bytes(b'\xef\xbb\xbf' + DOC.encode('utf-8'))
    mod.sync_readme(path, ROWS, write=True)
    assert path.read_bytes().startswith(b'\xef\xbb\xbf')


def test_generator_output_starts_with_the_header():
    mod = _mod()
    rows = mod.generated_rows()
    assert rows[0] == H
    assert len(rows) > 3


def test_this_repository_is_in_sync():
    """--check が 0 を返す = README の索引表は生成側と一致している。"""
    mod = _mod()
    assert mod.main(['--check']) == 0


def test_this_file_passes_the_type_hint_ratchet():
    """#117 のラチェット: 新しいファイルは公開関数100%型付き。"""
    spec = importlib.util.spec_from_file_location('audit_for_128', HERE / '117_type_hint_audit.py')
    audit = importlib.util.module_from_spec(spec)
    sys.modules['audit_for_128'] = audit
    spec.loader.exec_module(audit)
    assert audit.audit_file(HERE / '128_readme_index_sync.py')['missing'] == []