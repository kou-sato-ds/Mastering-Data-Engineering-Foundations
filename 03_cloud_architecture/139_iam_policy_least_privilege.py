"""
IAM ポリシーの最小権限チェック — 権限を広げすぎる書き方を、適用の前に見つける。

背景:
    「とりあえず s3:* で動かした」ポリシーが、そのまま本番に残るのは定番の事故である。
    動いている間は誰も困らないため、漏洩や誤削除が起きて初めて気づく。

方針(Allow の文だけを見る。Deny は権限を狭める側なので広すぎても安全):
    - high  : Action "*" / Allow + NotAction / Principal "*" で Condition 無し
    - medium: "サービス:*" / Resource "*" で書き込み操作を含む
    - Resource "*" でも List・Describe・Get だけなら問題にしない
      (一覧系には * でしか指定できない操作がある。止めすぎるチェックは信号の意味を失う)
    - Statement の形が想定外なら止める(読めないものを「問題なし」にしない)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

READ_PREFIXES = ('List', 'Describe', 'Get')


@dataclass(frozen=True)
class Finding:
    """1件の指摘。statement は Sid、無ければ #番号。"""
    severity: str
    statement: str
    message: str


def _as_list(value: Any) -> list[str]:
    """文字列1つでも、並びでも、並びにそろえる。"""
    if value is None:
        return []
    return [value] if isinstance(value, str) else list(value)


def _is_public(principal: Any) -> bool:
    """Principal が誰でも(*)を含むか。"""
    if principal == '*':
        return True
    if isinstance(principal, dict):
        return '*' in _as_list(principal.get('AWS'))
    return False


def _read_only(actions: list[str]) -> bool:
    """全ての操作が List・Describe・Get で始まるか。"""
    return bool(actions) and all(
        ':' in a and a.split(':', 1)[1].startswith(READ_PREFIXES) for a in actions)


def audit_policy(policy: dict[str, Any]) -> list[Finding]:
    """ポリシー JSON を検査し、指摘を返す。"""
    statements = policy.get('Statement')
    if isinstance(statements, dict):
        statements = [statements]
    if not isinstance(statements, list):
        raise ValueError('Statement must be an object or a list')
    findings: list[Finding] = []
    for i, st in enumerate(statements):
        if st.get('Effect') != 'Allow':
            continue
        sid = st.get('Sid') or f'#{i}'
        actions, resources = _as_list(st.get('Action')), _as_list(st.get('Resource'))
        if 'NotAction' in st:
            findings.append(Finding('high', sid, 'Allow with NotAction grants everything not listed'))
        if '*' in actions:
            findings.append(Finding('high', sid, 'Action "*" grants every action'))
        for action in actions:
            if action != '*' and action.endswith(':*'):
                findings.append(Finding('medium', sid, f'{action} grants every action of the service'))
        if '*' in resources and not _read_only(actions):
            findings.append(Finding('medium', sid, 'Resource "*" with write actions'))
        if _is_public(st.get('Principal')) and not st.get('Condition'):
            findings.append(Finding('high', sid, 'Principal "*" without Condition is public'))
    return findings


def has_blocking(findings: list[Finding]) -> bool:
    """high が1つでもあれば、適用を止めるべき。"""
    return any(f.severity == 'high' for f in findings)
