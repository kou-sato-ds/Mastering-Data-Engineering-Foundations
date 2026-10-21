"""
README 索引表の差し替え — 生成した表で、README の表をブロックごと置き換える。

背景:
    README 冒頭の索引表は 90_repository_index.py の出力と一致していなければならない
    (#104 の同期チェック)。これまでは README の1行に「, #番号」を手で足していたが、
    生成側は連番を範囲にまとめる(#126, #127 → #126-#127)。
    手で足す方法は、連番が来ない間だけたまたま合っていた(10/20 に #104 が検知)。

    本ファイルの方針:
      - 手で直さない。生成側の出力を、見出しから「|」が続く範囲ごと差し替える
      - 見出しがちょうど1箇所でなければ止める(README には他の表もある)
      - 中身が同じなら書き込まない(2回実行しても何も変わらない = 冪等)
      - 改行コード(CRLF/LF)と BOM は元のファイルに合わせる。
        そのためにバイト列で読み書きする(read_text は CRLF を LF に変えてしまう)
      - --check は差があれば終了コード 1 を返す(CI や pre-push で使える)

    #117 のラチェットにより、公開関数は100%型付き。
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
README = HERE.parent / 'README.md'
GENERATOR = HERE / '90_repository_index.py'
HEADER = '| 関心 | 項目 | 姉妹プロジェクト対応 |'
_BOM = b'\xef\xbb\xbf'


def find_table(lines: list[str], header: str = HEADER) -> tuple[int, int]:
    """見出しの行から、「|」で始まる行が続く最後の行までの位置 (開始, 終了) を返す。"""
    starts = [i for i, line in enumerate(lines) if line == header]
    if len(starts) != 1:
        raise ValueError(f'expected exactly one table header, found {len(starts)}')
    start = end = starts[0]
    while end + 1 < len(lines) and lines[end + 1].startswith('|'):
        end += 1
    return start, end


def replace_table(text: str, rows: list[str], header: str = HEADER) -> str:
    """text の中の索引表を rows で置き換えた文字列を返す。改行コードは text に合わせる。"""
    if not rows or rows[0] != header:
        raise ValueError('generated rows must start with the table header')
    nl = '\r\n' if '\r\n' in text else '\n'
    lines = text.split(nl)
    start, end = find_table(lines, header)
    return nl.join(lines[:start] + rows + lines[end + 1:])


def generated_rows(generator: Path = GENERATOR) -> list[str]:
    """生成側を実行し、表の行(「|」で始まる行)だけを返す。"""
    env = {**os.environ, 'PYTHONIOENCODING': 'utf-8'}
    result = subprocess.run([sys.executable, str(generator)], cwd=generator.parent,
                            capture_output=True, text=True, encoding='utf-8',
                            env=env, check=True)
    return [line for line in result.stdout.splitlines() if line.startswith('|')]


def sync_readme(readme: Path, rows: list[str], write: bool) -> bool:
    """
    README を生成側と比べ、差があれば True を返す。

    write=True のときだけ書き込む。中身が同じなら書き込まない(冪等)。BOM は元に合わせる。
    """
    raw = readme.read_bytes()
    has_bom = raw.startswith(_BOM)
    text = (raw[len(_BOM):] if has_bom else raw).decode('utf-8')
    updated = replace_table(text, rows)
    if updated == text:
        return False
    if write:
        readme.write_bytes((_BOM if has_bom else b'') + updated.encode('utf-8'))
    return True


def main(argv: list[str] | None = None) -> int:
    """--check: 差があれば 1 を返す。指定なし: 差があれば README を書き換える。"""
    parser = argparse.ArgumentParser(description='Sync the README index table with the generator.')
    parser.add_argument('--check', action='store_true', help='report drift without writing')
    args = parser.parse_args(argv)
    changed = sync_readme(README, generated_rows(), write=not args.check)
    if args.check:
        print('README index: out of sync' if changed else 'README index: in sync')
        return 1 if changed else 0
    print('README index: updated' if changed else 'README index: already in sync')
    return 0


if __name__ == '__main__':
    sys.exit(main())