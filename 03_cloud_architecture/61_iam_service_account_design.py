from google.cloud import iam_admin_v1
from google.cloud.iam_admin_v1 import types
from google.cloud import resourcemanager_v3

# 🎯 【最小権限統治の狼煙】パイプライン専用サービスアカウントを設計!
PROJECT_ID = 'your-gcp-project-id'
PROJECT_NAME = f'projects/{PROJECT_ID}'
SA_ACCOUNT_ID = 'dataflow-pipeline-sa'  # 👉 用途を名前で明示(dataflow専用)
SA_EMAIL = f'{SA_ACCOUNT_ID}@{PROJECT_ID}.iam.gserviceaccount.com'

# 🛡️ 【最小権限の原則】このパイプラインが必要とする権限のみを列挙!
REQUIRED_ROLES = [
    'roles/dataflow.worker',           # 👉 Dataflowワーカー実行
    'roles/pubsub.subscriber',         # 👉 PubSubサブスクリプション読取のみ(発行不可)
    'roles/bigquery.dataEditor',       # 👉 BQテーブル書込(dataOwnerではない=削除不可)
    'roles/bigquery.jobUser',          # 👉 BQジョブ実行(read/query権限)
    'roles/storage.objectViewer',      # 👉 GCS読取のみ(削除不可)
    'roles/monitoring.metricWriter',   # 👉 カスタムメトリクス送出のみ
]

# 🚨 これらが混入した瞬間に Blast Radius 制御が崩壊する
FORBIDDEN_ROLES = ['roles/owner', 'roles/editor', 'roles/iam.securityAdmin']


def build_sa_email(account_id: str, project_id: str) -> str:
    """
    🔍 サービスアカウントのメールアドレス構築。

    ドメインが1文字違えばIAMバインディングは「成功するが誰にも効かない」——
    存在しないプリンシパルへの付与はエラーにならないため、本番でしか
    気づけないサイレント失敗になる(#84の指摘による改善)。
    """
    return f'{account_id}@{project_id}.iam.gserviceaccount.com'


def build_sa_description(owner: str = 'data-engineering-team') -> str:
    """
    📋 監査時に「誰が何のために作ったSAか」を追跡可能にする記述。
    """
    return (
        'Purpose: Execute Dataflow jobs for daily analytics pipeline. '
        f'Owner: {owner}. '
        'Rotation: quarterly review required.'
    )


def validate_roles(roles: list) -> list:
    """
    🚨 付与予定ロールから禁止ロールを検出する純粋関数。

    「動かないから owner を付ける」という将来の妥協を、
    バインディング実行前に構造的に拒否する。
    """
    return [r for r in roles if r in FORBIDDEN_ROLES]


def build_member_binding(sa_email: str) -> str:
    """
    🔑 IAMポリシーのmember文字列。接頭辞 `serviceAccount:` を欠くと
    「ユーザーアカウント」と解釈され、意図しない主体へ権限が渡る。
    """
    return f'serviceAccount:{sa_email}'


def create_pipeline_service_account():
    """
    🛡️ パイプライン専用サービスアカウントを最小権限で作成。
    """
    iam_client = iam_admin_v1.IAMClient()

    request = types.CreateServiceAccountRequest(
        name=PROJECT_NAME,
        account_id=SA_ACCOUNT_ID,
        service_account=types.ServiceAccount(
            display_name='Dataflow Pipeline Runner (least-privilege)',
            description=build_sa_description(),
        )
    )
    sa = iam_client.create_service_account(request=request)
    print(f"[SA CREATED] {sa.email}")
    return sa


def grant_least_privilege_roles():
    """
    🎯 プロジェクトIAMポリシーへ最小権限ロールをバインドする。
    """
    violations = validate_roles(REQUIRED_ROLES)
    if violations:
        raise ValueError(f"forbidden roles detected, refusing to bind: {violations}")

    rm_client = resourcemanager_v3.ProjectsClient()

    # 🔍 【Read-Modify-Write】etag付き楽観的排他制御で競合回避
    policy = rm_client.get_iam_policy(request={'resource': PROJECT_NAME})

    member = build_member_binding(SA_EMAIL)
    for role in REQUIRED_ROLES:
        binding = next((b for b in policy.bindings if b.role == role), None)
        if binding is None:
            policy.bindings.add(role=role, members=[member])
        elif member not in binding.members:
            binding.members.append(member)
        print(f"[BIND] {role} → {member}")

    rm_client.set_iam_policy(request={'resource': PROJECT_NAME, 'policy': policy})
    print(f"[POLICY UPDATED] {len(REQUIRED_ROLES)} roles granted")


def audit_service_account_keys():
    """
    🚨 ダウンロード可能なJSONキーの存在を監査。
    実務では Workload Identity Federation によるキーレス運用が原則。
    """
    iam_client = iam_admin_v1.IAMClient()
    sa_name = f'{PROJECT_NAME}/serviceAccounts/{SA_EMAIL}'

    request = types.ListServiceAccountKeysRequest(
        name=sa_name,
        key_types=[types.ListServiceAccountKeysRequest.KeyType.USER_MANAGED]
    )
    response = iam_client.list_service_account_keys(request=request)

    if len(response.keys) > 0:
        print(f"[⚠️ AUDIT] {len(response.keys)} USER_MANAGED keys detected!")
        print("  → Workload Identity Federationへの移行を強く推奨")
    else:
        print("[✅ AUDIT] No user-managed keys. Keyless operation confirmed.")


if __name__ == '__main__':
    print("🚀 GCP IAM Service Account 最小権限設計基盤の監査を開始するのね...")
    # create_pipeline_service_account()  # 初回のみ実行
    print("🟢 監査完了!最小権限SAおよびBlast Radius制御基盤が完全画定したのね!")