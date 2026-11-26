"""#163 タグの付け忘れ検査の検証。plan は terraform show -json と同じ形の辞書で組み立てる。"""
import importlib.util
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent


def _mod():
    spec = importlib.util.spec_from_file_location('tags_mod', HERE / '163_terraform_required_tags.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules['tags_mod'] = module
    spec.loader.exec_module(module)
    return module


REQUIRED = {'cost_center': None, 'env': frozenset({'dev', 'stg', 'prod'}), 'owner': None}
GOOD = {'cost_center': 'cc-100', 'env': 'prod', 'owner': 'data-team'}


def _rc(address, after, actions=('create',)):
    return {'address': address, 'change': {'actions': list(actions), 'after': after}}


def _plan(*changes):
    return {'resource_changes': list(changes)}


def test_fully_tagged_resource_is_fine():
    mod = _mod()
    assert mod.check_tags(_plan(_rc('aws_s3_bucket.raw', {'tags': GOOD})), REQUIRED) == []


def test_missing_tag_is_reported():
    """タグが無ければ、誰の費用か分からない。"""
    mod = _mod()
    tags = {k: v for k, v in GOOD.items() if k != 'cost_center'}
    assert mod.check_tags(_plan(_rc('aws_s3_bucket.raw', {'tags': tags})), REQUIRED) == [
        'aws_s3_bucket.raw: missing tag cost_center']


def test_empty_value_is_reported():
    mod = _mod()
    plan = _plan(_rc('aws_s3_bucket.raw', {'tags': dict(GOOD, owner='')}))
    assert mod.check_tags(plan, REQUIRED) == ['aws_s3_bucket.raw: empty tag owner']


def test_value_outside_the_allowed_set_is_reported():
    """prd と prod は、集計で別の環境として数えられる。"""
    mod = _mod()
    plan = _plan(_rc('aws_s3_bucket.raw', {'tags': dict(GOOD, env='prd')}))
    assert mod.check_tags(plan, REQUIRED) == [
        "aws_s3_bucket.raw: tag env='prd' is not one of ['dev', 'prod', 'stg']"]


def test_google_labels_are_checked():
    mod = _mod()
    plan = _plan(_rc('google_storage_bucket.raw', {'labels': {'env': 'prod', 'owner': 'x'}}))
    assert mod.check_tags(plan, REQUIRED) == ['google_storage_bucket.raw: missing tag cost_center']


def test_null_tags_mean_every_tag_is_missing():
    mod = _mod()
    problems = mod.check_tags(_plan(_rc('aws_s3_bucket.raw', {'tags': None})), REQUIRED)
    assert len(problems) == 3


def test_resource_that_cannot_be_tagged_is_skipped():
    """タグを付けられない種類まで止めれば、検査が無視されるようになる。"""
    mod = _mod()
    plan = _plan(_rc('aws_iam_role_policy_attachment.x', {'role': 'r'}))
    assert mod.check_tags(plan, REQUIRED) == []


def test_deletes_and_no_ops_are_skipped():
    mod = _mod()
    plan = _plan(_rc('aws_s3_bucket.old', {'tags': {}}, ('delete',)),
                 _rc('aws_s3_bucket.same', {'tags': {}}, ('no-op',)))
    assert mod.check_tags(plan, REQUIRED) == []


def test_updates_and_replacements_are_checked_in_address_order():
    mod = _mod()
    plan = _plan(_rc('aws_s3_bucket.b', {'tags': {}}, ('update',)),
                 _rc('aws_s3_bucket.a', {'tags': {}}, ('delete', 'create')))
    problems = mod.check_tags(plan, {'owner': None})
    assert problems == ['aws_s3_bucket.a: missing tag owner', 'aws_s3_bucket.b: missing tag owner']
    with pytest.raises(ValueError, match='must be a list'):
        mod.check_tags({'resource_changes': {}}, REQUIRED)


def test_this_file_passes_the_type_hint_ratchet():
    spec = importlib.util.spec_from_file_location('audit_for_163', HERE / '117_type_hint_audit.py')
    audit = importlib.util.module_from_spec(spec)
    sys.modules['audit_for_163'] = audit
    spec.loader.exec_module(audit)
    assert audit.audit_file(HERE / '163_terraform_required_tags.py')['missing'] == []
