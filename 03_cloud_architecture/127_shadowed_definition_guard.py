"""
上書きされた定義のガード — 同じ名前の def が2つあると、前の方は黙って消える。

背景:
    同じスコープに同じ名前の関数を2回書くと、Python は後ろの定義で前を上書きする。
    エラーも警告も出ない。テストファイルで起きると致命的で、
    def test_x が2つあれば pytest は後ろの1件しか集めず、前のテストは一度も走らない。
    件数が1減るだけなので、緑のまま気づけない。

    #126(重複定義ガード)が「辞書のキー・定数の要素」を見たのに対し、
    本ファイルは「関数・クラスの名前」を見る兄弟の型。

    本ファイルの方針:
      - ソースを ast で読み、モジュール・クラス・関数の各スコープの「直下」を調べる
      - if / try の中の定義は見ない。
        if と else で同じ名前を定義するのは、条件で片方だけ使う正しい書き方
      - 意図した上書きは報告しない:
          @property の後の @x.setter / @x.getter / @x.deleter
          @overload の型だけの宣言
          @f.register で使う名前 _
      - それ以外の意図した上書きには MARKER を def の行に付け、理由をコメントに書く

    #117 のラチェットにより、公開関数は100%型付き。
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

MARKER = 'dup-ok'
_ACCESSORS = frozenset({'setter', 'getter', 'deleter'})
_Definition = ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef


@dataclass(frozen=True)
class Shadowed:
    """上書きされた定義1件。first_line の定義が、line の定義で消された。"""
    name: str
    kind: str
    scope: str
    first_line: int
    line: int


def _is_intended(node: _Definition, lines: list[str]) -> bool:
    """同じ名前を繰り返すのが Python の作法である定義か。"""
    if node.name == '_' or MARKER in lines[node.lineno - 1]:
        return True
    for deco in node.decorator_list:
        if isinstance(deco, ast.Name) and deco.id == 'overload':
            return True
        if isinstance(deco, ast.Attribute):
            if deco.attr == 'overload':
                return True
            if (deco.attr in _ACCESSORS and isinstance(deco.value, ast.Name)
                    and deco.value.id == node.name):
                return True
    return False


def _check_scope(body: list[ast.stmt], scope: str, lines: list[str],
                 found: list[Shadowed]) -> None:
    """1つのスコープの直下を調べ、中の関数・クラスにも潜る。if / try の中は見ない。"""
    first_seen: dict[str, int] = {}
    for node in body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if not _is_intended(node, lines):
            if node.name in first_seen:
                kind = 'class' if isinstance(node, ast.ClassDef) else 'function'
                found.append(Shadowed(node.name, kind, scope, first_seen[node.name], node.lineno))
            else:
                first_seen[node.name] = node.lineno
        inner = node.name if scope == '<module>' else f'{scope}.{node.name}'
        _check_scope(node.body, inner, lines, found)


def find_shadowed(source: str, filename: str = '<string>') -> list[Shadowed]:
    """ソース文字列から、上書きされた定義を行番号順に返す。"""
    tree = ast.parse(source, filename=filename)
    found: list[Shadowed] = []
    _check_scope(tree.body, '<module>', source.splitlines(), found)
    return sorted(found, key=lambda s: (s.line, s.first_line))


def audit_file(path: Path) -> list[Shadowed]:
    """1ファイルを調べる。BOM は読み飛ばし、構文エラーはそのまま止める(読めないものを「問題なし」にしない)。"""
    return find_shadowed(path.read_text(encoding='utf-8-sig'), filename=str(path))


def audit_directory(directory: Path, pattern: str = '*.py') -> dict[str, list[Shadowed]]:
    """ディレクトリ直下のファイルを調べ、上書きのあるファイルだけを {ファイル名: 一覧} で返す。"""
    report: dict[str, list[Shadowed]] = {}
    for path in sorted(directory.glob(pattern)):
        found = audit_file(path)
        if found:
            report[path.name] = found
    return report


def format_report(report: dict[str, list[Shadowed]]) -> str:
    """
    人が読む形にする。1行で「何行目の定義が、何行目で消されたか」が分かる。

    例: 85_collection_guard_testing.py:120: function test_x in <module> shadows line 40
    """
    rows: list[str] = []
    for filename, items in report.items():
        for s in items:
            rows.append(f'{filename}:{s.line}: {s.kind} {s.name} in {s.scope} shadows line {s.first_line}')
    return '\n'.join(rows)