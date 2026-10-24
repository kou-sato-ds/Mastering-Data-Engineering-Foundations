"""
#131 Terraform の「消える変更」検査の検証。plan は terraform show -json と同じ形の辞書で組み立てる。
"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent


def _mod():
    path = HERE / '131_terraform_destroy_check.py'
    spec = importlib.util.spec_from_file_location('tf_destroy_mod', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules['tf_destroy_mod'] = module
    spec.loader.exec_module(module)
    return module


def _rc(address, type_, actions):
    return {'address': address, 'type': type_, 'change': {'actions': actions}}


def _plan(*changes):
    return {'format_version': '1.2', 'resource_changes': list(changes)}


@pytest.mark.parametrize('actions, expected', [
    (['no-op'], 'no-op'),
    (['create'], 'create'),
    (['read'], 'read'),
    (['update'], 'update'),
    (['delete'], 'delete'),
    (['delete', 'create'], 'replace'),
    (['create', 'delete'], 'replace'),
])
def test_actions_are_classified(actions, expected):
    """create_before_destroy の並び(create, delete)も置き換え。"""
    mod = _mod()
    assert mod.classify(actions) == expected


def test_unknown_action_stops():
    mod = _mod()
    with pytest.raises(ValueError, match='unknown actions'):
        mod.classify(['update', 'delete'])


def test_counts_match_the_plan_summary():
    mod = _mod()
    review = mod.review_plan(_plan(
        _rc('aws_lambda_function.fetch', 'aws_lambda_function', ['update']),
        _rc('aws_iam_role.fetch', 'aws_iam_role', ['create']),
        _rc('aws_sqs_queue.dlq', 'aws_sqs_queue', ['no-op']),
    ))
    assert review.counts['update'] == 1
    assert review.counts['create'] == 1
    assert review.ok


def test_destroying_a_data_bucket_is_blocked():
    mod = _mod()
    review = mod.review_plan(_plan(_rc('aws_s3_bucket.raw', 'aws_s3_bucket', ['delete'])))
    assert review.blocked == ['aws_s3_bucket.raw (delete)']
    assert not review.ok


def test_replacement_is_treated_as_destruction():
    """-/+ は「変更」に紛れるが、中身は削除と作成。データは戻らない。"""
    mod = _mod()
    review = mod.review_plan(_plan(
        _rc('google_bigquery_dataset.mart', 'google_bigquery_dataset', ['delete', 'create'])))
    assert review.blocked == ['google_bigquery_dataset.mart (replace)']


def test_in_place_update_of_a_data_bucket_is_fine():
    mod = _mod()
    review = mod.review_plan(_plan(_rc('aws_s3_bucket.raw', 'aws_s3_bucket', ['update'])))
    assert review.ok


def test_destroying_a_stateless_resource_is_fine():
    """設定だけの資源は、消えても作り直せる。"""
    mod = _mod()
    review = mod.review_plan(_plan(
        _rc('aws_lambda_function.old', 'aws_lambda_function', ['delete'])))
    assert review.ok
    assert review.counts['delete'] == 1


def test_approval_unblocks_only_that_address():
    """種類単位ではなく住所単位。tmp を許しても raw は止まる。"""
    mod = _mod()
    review = mod.review_plan(_plan(
        _rc('aws_s3_bucket.tmp', 'aws_s3_bucket', ['delete']),
        _rc('aws_s3_bucket.raw', 'aws_s3_bucket', ['delete']),
    ), approvals={'aws_s3_bucket.tmp'})
    assert review.approved == ['aws_s3_bucket.tmp (delete)']
    assert review.blocked == ['aws_s3_bucket.raw (delete)']


def test_unused_approval_is_reported_as_stale():
    """使われない承認が残れば、次の誤操作をそのまま通してしまう。"""
    mod = _mod()
    review = mod.review_plan(_plan(_rc('aws_s3_bucket.raw', 'aws_s3_bucket', ['update'])),
                             approvals={'aws_s3_bucket.raw', 'aws_s3_bucket.gone'})
    assert review.stale_approvals == ['aws_s3_bucket.gone', 'aws_s3_bucket.raw']


def test_plan_without_changes_is_fine():
    mod = _mod()
    review = mod.review_plan({'format_version': '1.2'})
    assert review.ok
    assert sum(review.counts.values()) == 0


def test_malformed_resource_changes_stop():
    mod = _mod()
    with pytest.raises(ValueError, match='must be a list'):
        mod.review_plan({'resource_changes': {'oops': 1}})


def test_summary_lists_blocked_and_stale_items():
    mod = _mod()
    review = mod.review_plan(_plan(
        _rc('aws_s3_bucket.raw', 'aws_s3_bucket', ['delete', 'create'])),
        approvals={'aws_s3_bucket.old'})
    text = mod.format_summary(review)
    assert text.splitlines()[0] == 'Plan: 0 to add, 0 to change, 1 to replace, 0 to destroy'
    assert 'BLOCKED: aws_s3_bucket.raw (replace)' in text
    assert 'stale approval (remove it): aws_s3_bucket.old' in text


def test_cli_exit_code_stops_ci(tmp_path, capsys):
    """止めるべき変更があれば 1。承認すれば 0。"""
    mod = _mod()
    path = tmp_path / 'plan.json'
    path.write_text(json.dumps(_plan(_rc('aws_s3_bucket.raw', 'aws_s3_bucket', ['delete']))),
                    encoding='utf-8')
    assert mod.main([str(path)]) == 1
    assert mod.main([str(path), '--approve', 'aws_s3_bucket.raw']) == 0
    assert 'BLOCKED' in capsys.readouterr().out


def test_this_file_passes_the_type_hint_ratchet():
    """#117 のラチェット: 新しいファイルは公開関数100%型付き。"""
    spec = importlib.util.spec_from_file_location('audit_for_131', HERE / '117_type_hint_audit.py')
    audit = importlib.util.module_from_spec(spec)
    sys.modules['audit_for_131'] = audit
    spec.loader.exec_module(audit)
    assert audit.audit_file(HERE / '131_terraform_destroy_check.py')['missing'] == []