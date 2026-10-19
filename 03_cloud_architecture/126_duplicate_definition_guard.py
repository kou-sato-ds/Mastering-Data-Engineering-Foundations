"""
重複定義ガード — 実行すると1つに潰れて見えなくなる重複を、ソースのまま検出する。

背景:
    辞書リテラルに同じキーを2回書いても、Python は後ろの値を黙って採用する。
    リストに同じ要素が2回あっても、エラーにはならない。
    どちらも実行すれば消えて見えないため、
    「前の行だけ直したのに効かない」「後ろのコピーは一度も使われない」が起きる。
    索引(90)と分類ルール(95)で、同じ中身のコピーがテスト緑のまま潜んでいた事故の再発防止。

    本ファイルの方針:
      - ソースを ast で読み、実行せずに「書き方」を調べる
      - 辞書の同じキーは、どこにあっても報告する(場所を問わずバグ)
      - リストと集合の同じ要素は、大文字の定数(= 定義・登録表)の中だけ報告する。
        関数の中の [0, 0, 0] は初期値であって定義ではない
      - タプルは見ない。(255, 255, 255) のように位置に意味があり、繰り返しは正常
      - 判定するのはリテラルだけ。f() や変数は実行しないと分からないので報告しない
        (分からないものを扱わないのは、再試行の判定と同じ態度)
      - 比べるのは「書き方」。1 と True は実行時に同じキーになるが、書き方が違うので見ない
      - 意図した繰り返しには MARKER を付ける。付けた行は見ない。理由はコメントに書くこと

    #110(未記入ガード)・#117(型ヒントのラチェット)と同じく、ソースを対象にした検査。
    #117 のラチェットにより、公開関数は100%型付き。
"""
from __future__ import annotations

import ast
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

MARKER = 'dup-ok'


@dataclass(frozen=True)
class Duplicate:
    """見つかった重複1件。line は2回目の行、first_line は最初に書かれた行。"""
    kind: str
    value: str
    first_line: int
    line: int
    name: str | None = None


def _is_literal(node: ast.expr) -> bool:
    """実行せずに値が決まる書き方か。f() や変数は含めない。"""
    if isinstance(node, ast.Constant):
        return True
    if isinstance(node, ast.UnaryOp):
        return isinstance(node.op, (ast.USub, ast.UAdd)) and isinstance(node.operand, ast.Constant)
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        return all(_is_literal(e) for e in node.elts)
    if isinstance(node, ast.Dict):
        return all(k is not None and _is_literal(k) and _is_literal(v)
                   for k, v in zip(node.keys, node.values))
    return False


def _repeated(nodes: Sequence[ast.expr | None], kind: str, name: str | None,
              lines: list[str]) -> list[Duplicate]:
    """同じ書き方のリテラルが2回以上あれば、2回目以降を報告する。MARKER の行は見ない。"""
    found: list[Duplicate] = []
    first_seen: dict[str, int] = {}
    for node in nodes:
        if node is None or not _is_literal(node) or MARKER in lines[node.lineno - 1]:
            continue
        shape = ast.dump(node)
        if shape in first_seen:
            found.append(Duplicate(kind, ast.unparse(node), first_seen[shape], node.lineno, name))
        else:
            first_seen[shape] = node.lineno
    return found


def _constant_name(node: ast.Assign | ast.AnnAssign) -> str | None:
    """大文字の名前(= 定義・登録表)への代入なら、その名前を返す。"""
    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
    for target in targets:
        if isinstance(target, ast.Name) and target.id.isupper():
            return target.id
    return None


def find_duplicates(source: str, filename: str = '<string>') -> list[Duplicate]:
    """
    ソース文字列から重複定義を探し、行番号順に返す。

    辞書のキーは場所を問わず見る。リストと集合の要素は、
    大文字の定数に代入された値の中だけ見る。
    """
    tree = ast.parse(source, filename=filename)
    lines = source.splitlines()
    found: list[Duplicate] = []
    named: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            name = _constant_name(node)
            if name is None or node.value is None:
                continue
            for inner in ast.walk(node.value):
                if isinstance(inner, ast.Dict):
                    named.add(id(inner))
                    found.extend(_repeated(inner.keys, 'dict_key', name, lines))
                elif isinstance(inner, ast.List):
                    found.extend(_repeated(inner.elts, 'list_item', name, lines))
                elif isinstance(inner, ast.Set):
                    found.extend(_repeated(inner.elts, 'set_item', name, lines))
        elif isinstance(node, ast.Dict) and id(node) not in named:
            found.extend(_repeated(node.keys, 'dict_key', None, lines))
    return sorted(found, key=lambda d: (d.line, d.first_line, d.kind))


def audit_file(path: Path) -> list[Duplicate]:
    """1ファイルを調べる。BOM は読み飛ばし、構文エラーはそのまま止める(読めないものを「問題なし」にしない)。"""
    return find_duplicates(path.read_text(encoding='utf-8-sig'), filename=str(path))


def audit_directory(directory: Path, pattern: str = '*.py') -> dict[str, list[Duplicate]]:
    """ディレクトリ直下のファイルを調べ、重複のあるファイルだけを {ファイル名: 一覧} で返す。"""
    report: dict[str, list[Duplicate]] = {}
    for path in sorted(directory.glob(pattern)):
        found = audit_file(path)
        if found:
            report[path.name] = found
    return report


def format_report(report: dict[str, list[Duplicate]]) -> str:
    """
    人が読む形にする。1行で「どのファイルの何行目が、何行目の繰り返しか」が分かる。

    例: 90_repository_index.py:51: dict_key 'incremental' repeats line 47 in CONCERN_MAP
    """
    rows: list[str] = []
    for filename, dups in report.items():
        for d in dups:
            where = f' in {d.name}' if d.name else ''
            rows.append(f'{filename}:{d.line}: {d.kind} {d.value} repeats line {d.first_line}{where}')
    return '\n'.join(rows)