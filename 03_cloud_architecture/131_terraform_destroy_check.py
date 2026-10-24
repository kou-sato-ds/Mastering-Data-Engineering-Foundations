"""
Terraform の「消える変更」を止める — データを持つ資源の削除と置き換えを、apply の前に検出する。

背景:
    設定を少し直して apply したら、本番データの入った S3 バケットが消えて作り直された。
    plan の「-/+」(消してから作る = 置き換え)は、数百行の中では「変更」に紛れて見落とされる。
    設定だけの資源(IAM ポリシーなど)は消えても作り直せるが、データは作り直せない。

    Terraform には lifecycle の prevent_destroy があるが、それは資源ブロックの「中」に書く設定である。
    リファクタでブロックごとコードから消すと、守りも一緒に消える。
    そこで「terraform show -json」で出した plan そのものを検査する。

    本ファイルの方針:
      - データを持つ資源(PROTECTED_TYPES)の delete と replace を止める
      - replace(delete と create の組)は、見た目が変更でも削除と同じ扱い
      - 承認は資源の住所(address)単位で明示的に渡す。種類単位の許可はしない
      - 使われなかった承認は「古い承認」として報告する(残せば次の誤操作を通す)
      - 知らない action は止める(分からないものを安全と扱わない)

    使い方(CI):
        terraform plan -out=plan.out
        terraform show -json plan.out > plan.json
        python 131_terraform_destroy_check.py plan.json --approve aws_s3_bucket.tmp

    #117 のラチェットにより、公開関数は100%型付き。
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PROTECTED_TYPES = frozenset({
    'aws_s3_bucket', 'aws_dynamodb_table', 'aws_db_instance', 'aws_rds_cluster',
    'aws_glue_catalog_database', 'aws_glue_catalog_table', 'aws_kinesis_stream',
    'google_bigquery_dataset', 'google_bigquery_table', 'google_storage_bucket',
})
DANGEROUS = frozenset({'delete', 'replace'})
_SINGLE = frozenset({'no-op', 'create', 'read', 'update', 'delete'})


def classify(actions: list[str]) -> str:
    """
    plan の actions を1語にする。

    ["delete", "create"] と ["create", "delete"](create_before_destroy)は、どちらも replace。
    """
    key = tuple(actions)
    if key in (('delete', 'create'), ('create', 'delete')):
        return 'replace'
    if len(key) == 1 and key[0] in _SINGLE:
        return key[0]
    raise ValueError(f'unknown actions: {actions}')


@dataclass
class PlanReview:
    """plan の検査結果。blocked が空のときだけ apply してよい。"""
    counts: Counter[str] = field(default_factory=Counter)
    blocked: list[str] = field(default_factory=list)
    approved: list[str] = field(default_factory=list)
    stale_approvals: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """止めるべき変更が無いか。"""
        return not self.blocked


def review_plan(plan: dict[str, Any], approvals: set[str] | None = None,
                protected: frozenset[str] = PROTECTED_TYPES) -> PlanReview:
    """
    plan(terraform show -json の結果)を検査する。

    approvals に住所があれば、その資源の削除・置き換えだけを通す。
    使われなかった承認は stale_approvals に入る。
    """
    approvals = approvals or set()
    changes = plan.get('resource_changes', [])
    if not isinstance(changes, list):
        raise ValueError('resource_changes must be a list')
    review = PlanReview()
    used: set[str] = set()
    for rc in changes:
        address = rc['address']
        action = classify(rc['change']['actions'])
        review.counts[action] += 1
        if action in DANGEROUS and rc['type'] in protected:
            entry = f'{address} ({action})'
            if address in approvals:
                review.approved.append(entry)
                used.add(address)
            else:
                review.blocked.append(entry)
    review.stale_approvals = sorted(approvals - used)
    return review


def format_summary(review: PlanReview) -> str:
    """人が読む形。1行目は terraform plan の要約と同じ並び。"""
    c = review.counts
    lines = [f"Plan: {c['create']} to add, {c['update']} to change, "
             f"{c['replace']} to replace, {c['delete']} to destroy"]
    lines += [f'BLOCKED: {e}' for e in review.blocked]
    lines += [f'approved: {e}' for e in review.approved]
    lines += [f'stale approval (remove it): {a}' for a in review.stale_approvals]
    return '\n'.join(lines)


def main(argv: list[str] | None = None) -> int:
    """plan.json を検査し、止めるべき変更があれば 1 を返す(CI で apply を止める)。"""
    parser = argparse.ArgumentParser(description='Block destroy/replace of stateful resources.')
    parser.add_argument('plan_json', type=Path)
    parser.add_argument('--approve', action='append', default=[],
                        help='resource address allowed to be destroyed or replaced')
    args = parser.parse_args(argv)
    plan = json.loads(args.plan_json.read_text(encoding='utf-8'))
    review = review_plan(plan, set(args.approve))
    print(format_summary(review))
    return 0 if review.ok else 1


if __name__ == '__main__':
    sys.exit(main())
