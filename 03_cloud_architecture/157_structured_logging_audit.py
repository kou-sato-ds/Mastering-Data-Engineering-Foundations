"""
構造化ログの点検 — 深夜に辿れるログか、漏らしてはいけないものが出ていないかを確かめる。

背景:
    相関 ID が無いと同じ処理の前後のログを繋げられず、エラーの種類が無いと何が起きたか分からない。
    逆にメールアドレスやパスワードがログに出れば、ログそのものが情報漏洩になる。
    本命 ADR-004 / ADR-005(構造化ログ + 相関 ID)の約束を、機械で点検できる形にする。

方針:
    - 1行1件の JSON を点検する。JSON でない行も問題として数える
    - 必須項目: timestamp / level / event / correlation_id
    - level は決められた値だけ(Error や err の揺れは検索から漏れる)
    - ERROR 以上には error_type を必須にする
    - password / token などの項目名、値の中のメールアドレスは問題にする
"""
from __future__ import annotations

import json
import re
from typing import Any

REQUIRED = ('timestamp', 'level', 'event', 'correlation_id')
LEVELS = frozenset({'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'})
SECRET_KEYS = frozenset({'password', 'token', 'secret', 'api_key', 'authorization'})
_EMAIL = re.compile(r'[\w.+-]+@[\w-]+\.[\w.-]+')


def audit_record(record: dict[str, Any]) -> list[str]:
    """1件のログを点検し、問題の一覧を返す。"""
    problems = [f'missing {field}' for field in REQUIRED if not record.get(field)]
    level = record.get('level')
    if level and level not in LEVELS:
        problems.append(f'invalid level {level!r}')
    if level in ('ERROR', 'CRITICAL') and not record.get('error_type'):
        problems.append('error without error_type')
    for key, value in record.items():
        if key.lower() in SECRET_KEYS:
            problems.append(f'secret field {key}')
        elif isinstance(value, str) and _EMAIL.search(value):
            problems.append(f'possible email address in {key}')
    return problems


def audit_lines(lines: list[str]) -> dict[int, list[str]]:
    """複数行を点検し、問題のある行だけを {行番号(1始まり): 問題} で返す。"""
    report: dict[int, list[str]] = {}
    for number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            report[number] = ['not JSON']
            continue
        if not isinstance(record, dict):
            report[number] = ['not a JSON object']
            continue
        problems = audit_record(record)
        if problems:
            report[number] = problems
    return report
