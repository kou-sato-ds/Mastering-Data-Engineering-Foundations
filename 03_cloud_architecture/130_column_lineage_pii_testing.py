"""
#130 列レベルのリネージの検証。
"""
import importlib.util
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent


def _mod():
    path = HERE / '130_column_lineage_pii.py'
    spec = importlib.util.spec_from_file_location('column_lineage_mod', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules['column_lineage_mod'] = module
    spec.loader.exec_module(module)
    return module


def _sources():
    return {
        'users.id': set(),
        'users.email': {'pii'},
        'users.last_name': {'pii'},
        'users.first_name': {'pii'},
        'orders.user_id': set(),
        'orders.amount': set(),
    }


def _pipeline(mod):
    """users → staging_users → mart_public。列名は途中で変わる。"""
    T = mod.Transform
    return [
        T('staging_users', {'uid': ('users.id',), 'contact': ('users.email',)}),
        T('mart_public', {'uid': ('staging_users.uid',), 'contact': ('staging_users.contact',)}),
    ]


def test_tag_follows_a_renamed_column():
    """列名が変わっても、印は消えない。"""
    mod = _mod()
    lin = mod.propagate(_sources(), _pipeline(mod))
    assert lin.tags['staging_users.contact'] == {'pii'}
    assert lin.tags['staging_users.uid'] == set()


def test_multi_hop_keeps_the_original_source():
    mod = _mod()
    lin = mod.propagate(_sources(), _pipeline(mod))
    assert lin.tags['mart_public.contact'] == {'pii'}
    assert lin.origins['mart_public.contact'] == {'users.email'}


def test_derived_column_inherits_every_input_tag():
    """姓 + 名 → 氏名 も個人情報。"""
    mod = _mod()
    t = mod.Transform('people', {'full_name': ('users.last_name', 'users.first_name')})
    lin = mod.propagate(_sources(), [t])
    assert lin.tags['people.full_name'] == {'pii'}
    assert lin.origins['people.full_name'] == {'users.last_name', 'users.first_name'}


def test_masked_column_becomes_pseudonymized():
    mod = _mod()
    t = mod.Transform('hashed', {'email_hash': ('users.email',), 'uid': ('users.id',)},
                      masked=frozenset({'email_hash'}))
    lin = mod.propagate(_sources(), [t])
    assert lin.tags['hashed.email_hash'] == {'pseudonymized'}


def test_masking_affects_only_the_listed_column():
    mod = _mod()
    t = mod.Transform('half', {'email_hash': ('users.email',), 'raw': ('users.email',)},
                      masked=frozenset({'email_hash'}))
    lin = mod.propagate(_sources(), [t])
    assert lin.tags['half.raw'] == {'pii'}


def test_column_without_inputs_has_no_tags():
    """件数や定数は、元の列を持たない。"""
    mod = _mod()
    t = mod.Transform('daily', {'order_count': (), 'total': ('orders.amount',)})
    lin = mod.propagate(_sources(), [t])
    assert lin.tags['daily.order_count'] == set()
    assert lin.origins['daily.order_count'] == set()


def test_transform_order_does_not_matter():
    mod = _mod()
    forward = mod.propagate(_sources(), _pipeline(mod))
    backward = mod.propagate(_sources(), list(reversed(_pipeline(mod))))
    assert forward.tags == backward.tags


def test_unknown_input_column_stops():
    """出どころの分からない列を「安全」と扱わない。"""
    mod = _mod()
    t = mod.Transform('x', {'col': ('ghost.secret',)})
    with pytest.raises(ValueError, match='unknown input columns'):
        mod.propagate(_sources(), [t])


def test_cycle_stops():
    mod = _mod()
    T = mod.Transform
    with pytest.raises(ValueError, match='cycle'):
        mod.propagate({}, [T('a', {'x': ('b.y',)}), T('b', {'y': ('a.x',)})])


def test_column_defined_twice_stops():
    mod = _mod()
    T = mod.Transform
    with pytest.raises(ValueError, match='defined twice'):
        mod.propagate(_sources(), [T('s', {'c': ('users.id',)}), T('s', {'c': ('users.email',)})])


def test_masked_column_must_exist():
    mod = _mod()
    with pytest.raises(ValueError, match='masked columns'):
        mod.Transform('t', {'a': ('users.id',)}, masked=frozenset({'typo'}))


def test_exposure_reports_the_origin():
    """「どこを直せばいいか」まで分かる報告。"""
    mod = _mod()
    lin = mod.propagate(_sources(), _pipeline(mod))
    assert mod.check_exposure(lin, {'mart_public'}) == ['mart_public.contact: pii <- users.email']


def test_pseudonymized_is_still_not_public_by_default():
    """仮名化した情報も、照合すれば個人に戻せる。"""
    mod = _mod()
    t = mod.Transform('mart_public', {'email_hash': ('users.email',)},
                      masked=frozenset({'email_hash'}))
    lin = mod.propagate(_sources(), [t])
    assert mod.check_exposure(lin, {'mart_public'}) == [
        'mart_public.email_hash: pseudonymized <- users.email']
    assert mod.check_exposure(lin, {'mart_public'}, forbidden=frozenset({'pii'})) == []


def test_private_tables_are_not_reported():
    mod = _mod()
    lin = mod.propagate(_sources(), _pipeline(mod))
    assert mod.check_exposure(lin, {'some_other_public_table'}) == []


def test_this_file_passes_the_type_hint_ratchet():
    """#117 のラチェット: 新しいファイルは公開関数100%型付き。"""
    spec = importlib.util.spec_from_file_location('audit_for_130', HERE / '117_type_hint_audit.py')
    audit = importlib.util.module_from_spec(spec)
    sys.modules['audit_for_130'] = audit
    spec.loader.exec_module(audit)
    assert audit.audit_file(HERE / '130_column_lineage_pii.py')['missing'] == []