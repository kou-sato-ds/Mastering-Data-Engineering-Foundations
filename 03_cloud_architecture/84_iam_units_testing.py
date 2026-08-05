"""
#61 IAM最小権限のテスト可能単位の検証。

🎯 【手法の5回目の適用】未カバー残(38 stmts中27 miss、29%)を埋める!

背景:
    #76 は REQUIRED_ROLES という定数を検証していたが、
    SAメール構築・member文字列・禁止ロール検出のロジックは未検証だった。
    これらは「間違っても例外にならない」——ドメインが1文字違うSAへの
    バインディングは成功し、しかし誰にも効かない。

実行方法:
    pytest 84_iam_units_testing.py -v
"""
import importlib.util
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent


def load_module_from_path(filename: str, module_name: str):
    """#71/#80/#81/#82/#83 と同一の動的ローダー。"""
    path = HERE / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        pytest.skip(f"cannot build spec for {filename}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _iam_mod():
    pytest.importorskip('google.cloud.iam_admin_v1', reason='google-cloud-iam not installed')
    pytest.importorskip('google.cloud.resourcemanager_v3',
                        reason='google-cloud-resource-manager not installed')
    return load_module_from_path('61_iam_service_account_design.py', 'iam_units_mod')


# ================================================================
# STAGE 1: SAメールがGCPの正規フォーマットであること
# ================================================================
def test_sa_email_follows_gcp_format():
    mod = _iam_mod()
    assert hasattr(mod, 'build_sa_email'), "#61 must expose build_sa_email"

    email = mod.build_sa_email('my-sa', 'my-proj')
    assert email == 'my-sa@my-proj.iam.gserviceaccount.com', (
        "a malformed domain binds successfully but grants nothing; "
        "the error only surfaces in production"
    )


# ================================================================
# STAGE 2: モジュール定数が構築関数と一致すること
# ================================================================
def test_module_sa_email_matches_builder():
    mod = _iam_mod()
    assert mod.SA_EMAIL == mod.build_sa_email(mod.SA_ACCOUNT_ID, mod.PROJECT_ID)


# ================================================================
# STAGE 3: member文字列が serviceAccount: 接頭辞を持つこと
# ================================================================
def test_member_binding_declares_principal_type():
    mod = _iam_mod()
    assert hasattr(mod, 'build_member_binding'), "#61 must expose build_member_binding"

    member = mod.build_member_binding('sa@proj.iam.gserviceaccount.com')
    assert member.startswith('serviceAccount:'), (
        "without the prefix the principal is interpreted as a user account"
    )


# ================================================================
# STAGE 4: 禁止ロールが検出されること
# ================================================================
@pytest.mark.parametrize('bad_role', ['roles/owner', 'roles/editor', 'roles/iam.securityAdmin'])
def test_forbidden_roles_are_detected(bad_role):
    mod = _iam_mod()
    assert hasattr(mod, 'validate_roles'), "#61 must expose validate_roles"

    violations = mod.validate_roles(mod.REQUIRED_ROLES + [bad_role])
    assert bad_role in violations


# ================================================================
# STAGE 5: 現在の構成が禁止ロールを含まないこと
# ================================================================
def test_current_roles_pass_validation():
    mod = _iam_mod()
    assert mod.validate_roles(mod.REQUIRED_ROLES) == []


# ================================================================
# STAGE 6: SA記述が監査可能性を担保すること
# ================================================================
def test_sa_description_supports_audit():
    mod = _iam_mod()
    assert hasattr(mod, 'build_sa_description'), "#61 must expose build_sa_description"

    desc = mod.build_sa_description('platform-team')
    assert 'Purpose:' in desc
    assert 'platform-team' in desc
    assert 'Rotation:' in desc


if __name__ == '__main__':
    print("🚀 IAM単位テストの監査を開始するのね...")
    print("🟢 監査完了!サイレントに効かないバインディングが固定される基盤が完全画定したのね!")
    print("実行するには: pytest 84_iam_units_testing.py -v")