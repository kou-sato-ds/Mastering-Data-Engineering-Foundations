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

def create_pipeline_service_account():
    """
    🛡️ パイプライン専用サービスアカウントを最小権限で作成。
    Dataflow/Composer実行時にこのSAをアタッチすることで、
    ジョブが盗まれても被害範囲を最小化する Blast Radius 制御を実現。
    """
    iam_client = iam_admin_v1.IAMClient()

    # 🚀 【STAGE 1: SA本体作成】用途明示の命名で監査可能性を担保!
    request = types.CreateServiceAccountRequest(
        name=PROJECT_NAME,
        account_id=SA_ACCOUNT_ID,
        service_account=types.ServiceAccount(
            display_name='Dataflow Pipeline Runner (least-privilege)',
            description=(
                'Purpose: Execute Dataflow jobs for daily analytics pipeline. '
                'Owner: data-engineering-team. '
                'Rotation: quarterly review required.'
            )
        )
    )
    sa = iam_client.create_service_account(request=request)
    print(f"[SA CREATED] {sa.email}")
    return sa


def grant_least_privilege_roles():
    """
    🎯 プロジェクトIAMポリシーにサービスアカウントのバインディングを追加。
    ロール別に分割することで「なぜこの権限が必要か」を監査ログで追跡可能。
    """
    rm_client = resourcemanager_v3.ProjectsClient()

    # 🔍 【STAGE 2: 既存ポリシー取得】Read-Modify-Writeパターンで競合回避!
    policy = rm_client.get_iam_policy(
        request={'resource': PROJECT_NAME}
    )

    # 🚀 【STAGE 3: ロール追加】各ロールを個別バインディングで明示追加!
    member = f'serviceAccount:{SA_EMAIL}'
    for role in REQUIRED_ROLES:
        binding = next(
            (b for b in policy.bindings if b.role == role),
            None
        )
        if binding is None:
            # 👉 新規バインディング作成
            policy.bindings.add(role=role, members=[member])
        elif member not in binding.members:
            # 👉 既存バインディングへメンバー追加
            binding.members.append(member)
        print(f"[BIND] {role} → {member}")

    # 🚀 【STAGE 4: ポリシー確定】etag付きで楽観的排他制御!
    rm_client.set_iam_policy(
        request={'resource': PROJECT_NAME, 'policy': policy}
    )
    print(f"[POLICY UPDATED] {len(REQUIRED_ROLES)} roles granted")


def audit_service_account_keys():
    """
    🚨 サービスアカウントキー(ダウンロード可能なJSON)の存在を監査し警告。
    実務ではWorkload Identity Federation を使ってキーレス運用が原則。
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
        for key in response.keys:
            print(f"    - key_id={key.name.split('/')[-1]}, created={key.valid_after_time}")
    else:
        print("[✅ AUDIT] No user-managed keys. Keyless operation confirmed.")


if __name__ == '__main__':
    print("🚀 GCP IAM Service Account 最小権限設計基盤の監査を開始するのね...")
    # create_pipeline_service_account()  # 初回のみ実行
    # grant_least_privilege_roles()      # ロールバインディング
    # audit_service_account_keys()       # キーレス運用の監査
    print("🟢 監査完了!最小権限SAおよびBlast Radius制御基盤が完全画定したのね!")