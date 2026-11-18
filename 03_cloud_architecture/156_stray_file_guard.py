"""
置き場所のガード — テストの対象外の場所に置かれた .py を見つける。

背景:
    2026-11-17、貼り付けで cd が消え、#155 の本体とテストがリポジトリの一番上に作られた。
    pre-push フックは 03_cloud_architecture の中のテストしか走らせないため、
    一番上の .py はどのテストからも見えず、何も失敗しないまま push まで届いた。

方針:
    - リポジトリの一番上に直接置かれた .py を一覧にする(下のフォルダは見ない)
    - 正当な理由で一番上に置くファイル(conftest.py など)は allowed で明示する
    - このガード自身は 03_cloud_architecture のテストとして走るので、
      フックの死角を、フックが走らせるテストで塞ぐことになる
"""
from __future__ import annotations

from pathlib import Path


def find_stray_python(repo_root: Path, allowed: frozenset[str] = frozenset()) -> list[str]:
    """repo_root の直下にある .py のうち、allowed に無いものの名前を返す。"""
    return sorted(p.name for p in repo_root.glob('*.py') if p.is_file() and p.name not in allowed)
