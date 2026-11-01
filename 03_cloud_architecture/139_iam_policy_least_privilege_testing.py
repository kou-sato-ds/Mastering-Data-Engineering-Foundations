"""#139 IAM ポリシーの最小権限チェックの検証。"""
import importlib.util
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent


def _mod():
    spec = importlib.util.spec_from_file_location('iam_mod', HERE / '139_iam_policy_least_privilege.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules['iam_mod'] = module
    spec.loader.exec_module(module)
    return module


def _policy(*statements):
    return {'Version': '2012-10-17', 'Statement': list(statements)}


def _severities(findings):
    return sorted(f.severity for f in findings)


def test_scoped_policy_is_clean():
    mod = _mod()
    p = _policy({'Sid': 'ReadRaw', 'Effect': 'Allow', 'Action': ['s3:GetObject'],
                 'Resource': 'arn:aws:s3:::news-raw/*'})
    assert mod.audit_policy(p) == []


def test_star_action_is_high():
    mod = _mod()
    findings = mod.audit_policy(_policy({'Effect': 'Allow', 'Action': '*', 'Resource': '*'}))
    assert 'high' in _severities(findings)
    assert mod.has_blocking(findings)


def test_service_wildcard_is_medium():
    """s3:* は DeleteBucket まで含む。"""
    mod = _mod()
    findings = mod.audit_policy(_policy(
        {'Sid': 'S3', 'Effect': 'Allow', 'Action': 's3:*', 'Resource': 'arn:aws:s3:::news-raw'}))
    assert [(f.severity, f.statement) for f in findings] == [('medium', 'S3')]
    assert not mod.has_blocking(findings)


def test_star_resource_with_write_is_medium():
    mod = _mod()
    findings = mod.audit_policy(_policy({'Effect': 'Allow', 'Action': 's3:PutObject', 'Resource': '*'}))
    assert [f.message for f in findings] == ['Resource "*" with write actions']


def test_star_resource_with_read_only_actions_is_fine():
    """一覧系には * でしか指定できない操作がある。止めすぎない。"""
    mod = _mod()
    p = _policy({'Effect': 'Allow', 'Action': ['ec2:DescribeInstances', 's3:ListAllMyBuckets'],
                 'Resource': '*'})
    assert mod.audit_policy(p) == []


def test_allow_with_not_action_is_high():
    """「書いたもの以外は全部許可」。新サービスが出るたびに権限が増える。"""
    mod = _mod()
    findings = mod.audit_policy(_policy(
        {'Effect': 'Allow', 'NotAction': 'iam:*', 'Resource': 'arn:aws:s3:::x'}))
    assert mod.has_blocking(findings)


def test_public_principal_needs_a_condition():
    mod = _mod()
    public = {'Effect': 'Allow', 'Principal': {'AWS': '*'}, 'Action': 's3:GetObject',
              'Resource': 'arn:aws:s3:::x/*'}
    assert mod.has_blocking(mod.audit_policy(_policy(public)))
    limited = dict(public, Condition={'StringEquals': {'aws:SourceVpce': 'vpce-1'}})
    assert mod.audit_policy(_policy(limited)) == []


def test_deny_statements_are_not_flagged():
    """Deny は権限を狭める側。広すぎても安全。"""
    mod = _mod()
    assert mod.audit_policy(_policy({'Effect': 'Deny', 'Action': '*', 'Resource': '*'})) == []


def test_single_statement_object_is_accepted():
    mod = _mod()
    p = {'Version': '2012-10-17',
         'Statement': {'Effect': 'Allow', 'Action': 's3:*', 'Resource': 'arn:aws:s3:::x'}}
    assert [f.statement for f in mod.audit_policy(p)] == ['#0']


def test_malformed_statement_stops():
    mod = _mod()
    with pytest.raises(ValueError, match='Statement'):
        mod.audit_policy({'Statement': 'oops'})


def test_this_file_passes_the_type_hint_ratchet():
    spec = importlib.util.spec_from_file_location('audit_for_139', HERE / '117_type_hint_audit.py')
    audit = importlib.util.module_from_spec(spec)
    sys.modules['audit_for_139'] = audit
    spec.loader.exec_module(audit)
    assert audit.audit_file(HERE / '139_iam_policy_least_privilege.py')['missing'] == []
