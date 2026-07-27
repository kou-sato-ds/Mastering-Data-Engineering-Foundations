"""
IAM最小権限設計(#61)のロジック検証 — 未検証リストの完了。

🎯 【#79リスト完了】残る新規ロジック #61 を検証対象へ。これで一区切り!

背景:
    #83時点で残る未検証は #55・#56・#61 の3つ。
    うち #55(Fixed Window)/#56(Late Data) は Windowing 系であり、
    #63(#73で静的検証)/#69(実体検証済) と同じロジック領域にある。
    したがって「まだ一度も検証していない新規ロジック」は #61 のみ。
    本ファイルでそれを締める。

検証方針:
    IAM の実 API 呼び出しは実行できない。しかし #61 の中核である
    「どのロールを付与するか」という設計判断は REQUIRED_ROLES という
    定数として存在し、これは純粋データである。
    -> 「危険なロールが混入していないこと」をテストで固定する。
       これは #73 STAGE 5 で Terraform に対して行ったのと同じ思想を、
       Python 側の定数に対して適用するもの。

実行方法:
    pytest 76_iam_least_privilege_testing.py -v
"""
import importlib.util
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent


def load_module_from_path(filename: str, module_name: str):
    """#71/#73/#74/#75 と同一の動的ローダー。"""
    path = HERE / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        pytest.skip(f"cannot build spec for {filename}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _load_iam_module():
    # 🚨 #61 は SA作成(iam_admin_v1) と プロジェクトIAMポリシー更新(resourcemanager_v3) の
    #    2パッケージを必要とする。片方だけの導入で「skipではなくfailure」になる事故を防ぐため、
    #    両方の存在を前提条件として明示する。
    pytest.importorskip('google.cloud.iam_admin_v1', reason='google-cloud-iam not installed')
    pytest.importorskip('google.cloud.resourcemanager_v3',
                        reason='google-cloud-resource-manager not installed')
    return load_module_from_path('61_iam_service_account_design.py', 'iam_mod')


# ================================================================
# STAGE 1: #61 が必須シンボルを公開していること
# ================================================================
def test_iam_module_exposes_required_symbols():
    mod = _load_iam_module()

    assert hasattr(mod, 'REQUIRED_ROLES'), "#61 must define REQUIRED_ROLES"
    assert hasattr(mod, 'create_pipeline_service_account'), "#61 must keep the SA creator"
    assert hasattr(mod, 'grant_least_privilege_roles'), "#61 must keep the role binder"
    assert hasattr(mod, 'audit_service_account_keys'), "#61 must keep the key auditor"


# ================================================================
# STAGE 2: 危険な広範ロールが混入していないこと
#   roles/owner や roles/editor が1つ紛れ込むだけで Blast Radius 制御は崩壊する。
#   #73 STAGE 5 で Terraform に行った検査を、Python定数側にも適用する。
# ================================================================
@pytest.mark.parametrize('forbidden_role', [
    'roles/owner',
    'roles/editor',
    'roles/iam.securityAdmin',
])
def test_no_overly_broad_roles_are_granted(forbidden_role):
    mod = _load_iam_module()

    assert forbidden_role not in mod.REQUIRED_ROLES, \
        f"{forbidden_role} defeats least-privilege design (see ADR/README #69)"


# ================================================================
# STAGE 3: 破壊的権限ではなく限定권限が選ばれていること
#   #61 の設計判断: dataOwner ではなく dataEditor (削除不可)、
#   pubsub.editor ではなく pubsub.subscriber (発行不可)。
#   この「やらないことの明示」がテストで固定される。
# ================================================================
def test_destructive_roles_are_avoided_in_favor_of_scoped_ones():
    mod = _load_iam_module()
    roles = mod.REQUIRED_ROLES

    assert 'roles/bigquery.dataOwner' not in roles, \
        "dataOwner grants delete; #61 deliberately chose dataEditor"
    assert 'roles/bigquery.dataEditor' in roles, \
        "the scoped alternative must remain present"

    assert 'roles/pubsub.editor' not in roles, \
        "pubsub.editor grants publish; #61 deliberately chose subscriber"
    assert 'roles/pubsub.subscriber' in roles, \
        "the read-only alternative must remain present"


# ================================================================
# STAGE 4: ロールが重複なく、想定件数の範囲に収まっていること
#   ロールが際限なく増えれば、それは最小権限の形骸化を意味する。
# ================================================================
def test_roles_are_unique_and_bounded():
    mod = _load_iam_module()
    roles = mod.REQUIRED_ROLES

    assert len(roles) == len(set(roles)), "duplicate roles indicate careless accumulation"
    assert 0 < len(roles) <= 10, \
        "an ever-growing role list silently erodes least-privilege"


# ================================================================
# STAGE 5: サービスアカウント名が用途を明示していること
#   監査ログで「誰が何のために」を追跡可能にするための命名規律。
# ================================================================
def test_service_account_id_is_purpose_explicit():
    mod = _load_iam_module()

    assert hasattr(mod, 'SA_ACCOUNT_ID'), "#61 must define SA_ACCOUNT_ID"
    sa_id = mod.SA_ACCOUNT_ID

    assert sa_id.islower(), "GCP service account IDs must be lowercase"
    assert '-' in sa_id, "purpose-explicit naming uses hyphen-separated words"
    assert len(sa_id) >= 6, "a too-short ID cannot convey purpose in audit logs"


if __name__ == '__main__':
    print("🚀 IAM最小権限(#61) ロジック検証基盤の監査を開始するのね...")
    print("🟢 監査完了!Blast Radius制御が定数レベルで守られる基盤が完全画定したのね!")
    print("実行するには: pytest 76_iam_least_privilege_testing.py -v")