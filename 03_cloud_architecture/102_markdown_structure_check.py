"""
README の Markdown 構造検証 — 見出しが見出しとして描画されるか。

🎯 【昨日の45件を二度と起こさない】引用に沈んだ見出しを検知する!

背景:
    #61 から #108 まで **45個の見出しが `> ` 付き**で書かれていた。
    GitHub 上では引用ブロック内の文字列として灰色に沈み、
    右側の目次には1つも載らない——
    **採用担当者が「どこに何があるか」を掴めない状態**が1ヶ月以上続いた。

    #98 で索引を、#100 で問答を作り、テストで守ってきた。
    しかし **「見出しが見出しとして描画されるか」は誰も検証していなかった**。
    テストは Markdown の構造を見ていなかったのである。

    ADR-006(姉妹プロジェクト)に「壊れたことより、壊れたと気づけない
    仕組みの方が危険」と書いたが、まさにそれが起きた。

    本ファイルは Markdown の構造そのものを検証する。

実行方法:
    python 102_markdown_structure_check.py       # 構造レポートを表示
    pytest 102_markdown_structure_testing.py -v
"""
import re
from pathlib import Path

HERE = Path(__file__).parent
README = HERE.parent / 'README.md'


def read_lines() -> list:
    """README を行リストとして読む。"""
    return README.read_text(encoding='utf-8').splitlines()


def find_quoted_headings(lines: list) -> list:
    """
    🚨 引用ブロック内の見出しを検出する。

    `> ## タイトル` は GitHub では見出しにならず、
    引用文として描画され目次にも載らない。
    **書いた本人には見出しに見えるため、最も気づきにくい事故**である。
    """
    return [
        {'line': i + 1, 'text': line.strip()}
        for i, line in enumerate(lines)
        if re.match(r'^>\s*#{1,6}\s', line)
    ]


def extract_headings(lines: list) -> list:
    """
    🔍 正しく描画される見出しだけを抽出する。

    コードブロック内の `#` はコメントであり見出しではないため除外する——
    これを含めると、Python のコメント行が全て見出しとして数えられる。
    """
    headings = []
    in_code_block = False

    for i, line in enumerate(lines):
        if line.strip().startswith('```'):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue

        match = re.match(r'^(#{1,6})\s+(.*)', line)
        if match:
            headings.append({
                'line': i + 1,
                'level': len(match.group(1)),
                'text': match.group(2).strip(),
            })
    return headings


def find_level_jumps(headings: list) -> list:
    """
    🚨 見出しレベルが飛んでいる箇所を検出する。

    `##` の次に `####` が来ると、目次の階層が崩れて
    読者が構造を誤解する。1段ずつ深くするのが規約である。
    """
    jumps = []
    previous = None

    for h in headings:
        if previous is not None and h['level'] > previous + 1:
            jumps.append({
                'line': h['line'],
                'text': h['text'],
                'from': previous,
                'to': h['level'],
            })
        previous = h['level']
    return jumps


def find_malformed_tables(lines: list) -> list:
    """
    🚨 列数が揃っていないテーブル行を検出する。

    Markdown のテーブルは列数が不一致でもエラーにならず、
    **崩れた表として描画される**——#98 の索引テーブルが
    静かに壊れても誰も気づかない。
    """
    issues = []
    in_code_block = False
    header_columns = None

    for i, line in enumerate(lines):
        stripped = line.strip()

        if stripped.startswith('```'):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue

        if not stripped.startswith('|'):
            header_columns = None
            continue

        columns = stripped.count('|')

        if header_columns is None:
            header_columns = columns
            continue

        # 👉 区切り行(|---|---|)はスキップ
        if set(stripped) <= set('|-: '):
            continue

        if columns != header_columns:
            issues.append({
                'line': i + 1,
                'expected': header_columns,
                'actual': columns,
            })

    return issues


def check_structure() -> dict:
    """📋 全チェックをまとめて実行する。"""
    lines = read_lines()
    headings = extract_headings(lines)

    return {
        'total_lines': len(lines),
        'heading_count': len(headings),
        'quoted_headings': find_quoted_headings(lines),
        'level_jumps': find_level_jumps(headings),
        'malformed_tables': find_malformed_tables(lines),
    }


def summarise_issues(report: dict) -> list:
    """🚨 対処が必要な項目だけを抜き出す。"""
    issues = []

    if report['quoted_headings']:
        lines = [q['line'] for q in report['quoted_headings']]
        issues.append(
            f"{len(lines)} headings are trapped in blockquotes at lines {lines[:5]}"
            f"{'...' if len(lines) > 5 else ''}"
        )

    if report['level_jumps']:
        for j in report['level_jumps']:
            issues.append(
                f"line {j['line']}: heading level jumps from "
                f"{j['from']} to {j['to']}"
            )

    if report['malformed_tables']:
        lines = [t['line'] for t in report['malformed_tables']]
        issues.append(f"{len(lines)} table rows have mismatched columns: {lines[:5]}")

    return issues


if __name__ == '__main__':
    print("🚀 README構造検証の監査を開始するのね...")
    report = check_structure()
    print(f"  行数: {report['total_lines']}, 見出し: {report['heading_count']}")
    issues = summarise_issues(report)
    print('  問題なし' if not issues else '  ' + '\n  '.join(issues))
    print("🟢 監査完了!見出しが見出しとして描画される基盤が完全画定したのね!")