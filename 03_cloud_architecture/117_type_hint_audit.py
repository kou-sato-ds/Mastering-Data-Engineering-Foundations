"""
型ヒントの被覆率とラチェット — 「型ヒントは完璧か」に、実測で答える。

背景:
    査読原則の1つに「型ヒント(typing)と Docstring は完璧か」がある。
    しかし過去のファイルを一度に書き換えれば、差分が大きすぎて
    レビューも検証もできなくなる。

    そこで #86 のカバレッジと同じ方法を取る:
      - 今の被覆率を実測する(推測で「型付き」と書かない)
      - 実測値を下限として固定する -> 下がったら赤
      - #117 以降に足すファイルは、公開関数を100%型付きにする
      - このファイル自身も100%型付きにする(#104: 仕組み自身が対象から漏れる罠)

    mypy のような新しい依存は入れず、標準ライブラリの ast で数える。
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

HERE = Path(__file__).parent

# 実測後に書き換える下限。0.0 のままでは何も守らない。
FLOOR = 0.4

# この番号以降のファイルは公開関数を100%型付きにする。
STRICT_FROM = 117

NUMBERED = re.compile(r'^(\d+)_.+\.py$')
TEST_SUFFIX = re.compile(r'_(testing|validation)\.py$')


def item_number(path: Path) -> int | None:
    """ファイル名先頭の番号を返す。番号が無ければ None。"""
    match = NUMBERED.match(path.name)
    return int(match.group(1)) if match else None


def is_target(path: Path) -> bool:
    """番号付きの本体ファイルだけを対象にする。テストファイルは除く。"""
    return item_number(path) is not None and not TEST_SUFFIX.search(path.name)


def public_functions(source: str) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    """名前が _ で始まらない関数・メソッドを返す。"""
    tree = ast.parse(source)
    return [
        node for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not node.name.startswith('_')
    ]


def is_fully_annotated(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """
    全ての引数と戻り値に型が付いているか。

    メソッドの self / cls は型を書かないのが慣例なので除く。
    """
    args = fn.args
    params = list(args.posonlyargs) + list(args.args) + list(args.kwonlyargs)
    if params and params[0].arg in ('self', 'cls'):
        params = params[1:]
    if args.vararg:
        params.append(args.vararg)
    if args.kwarg:
        params.append(args.kwarg)
    return fn.returns is not None and all(p.annotation is not None for p in params)


def audit_file(path: Path) -> dict:
    """
    1ファイルの被覆を数える。

    Python として読めないファイル(中身が SQL の .py など、#93 で見つかったもの)は
    落とさずに unparsable として報告する。
    """
    try:
        fns = public_functions(path.read_text(encoding='utf-8'))
    except SyntaxError:
        return {'file': path.name, 'total': 0, 'annotated': 0, 'missing': [], 'unparsable': True}
    missing = [f.name for f in fns if not is_fully_annotated(f)]
    return {
        'file': path.name,
        'total': len(fns),
        'annotated': len(fns) - len(missing),
        'missing': missing,
        'unparsable': False,
    }


def audit(directory: Path = HERE) -> dict:
    """対象ファイル全体の被覆率を返す。"""
    files = [audit_file(p) for p in sorted(directory.glob('*.py')) if is_target(p)]
    total = sum(f['total'] for f in files)
    annotated = sum(f['annotated'] for f in files)
    return {
        'files': files,
        'total': total,
        'annotated': annotated,
        'ratio': round(annotated / total, 4) if total else 0.0,
        'unparsable': [f['file'] for f in files if f['unparsable']],
    }


def strict_violations(directory: Path = HERE, strict_from: int = STRICT_FROM) -> list[str]:
    """STRICT_FROM 以降のファイルで、型の無い公開関数を返す。"""
    violations = []
    for p in sorted(directory.glob('*.py')):
        number = item_number(p)
        if is_target(p) and number is not None and number >= strict_from:
            violations += [f'{p.name}:{name}' for name in audit_file(p)['missing']]
    return violations


if __name__ == '__main__':
    result = audit()
    print(f"coverage={result['ratio']}")
    print(f"annotated {result['annotated']} / {result['total']} public functions")
    print(f"unparsable: {result['unparsable']}")