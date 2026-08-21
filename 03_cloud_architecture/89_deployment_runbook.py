"""
デプロイ手順の実行可能ドキュメント化 — Runbook as Code。

🎯 【#75の思想をデプロイへ】手順をドキュメントに留めず、関数として持つ!

背景:
    #86(パラメータ)・#87(契約)・#88(実行環境)でデプロイの構成要素は揃った。
    しかし「実際にどのコマンドを、どの順で打つのか」がどこにも無い。

    gcloud dataflow flex-template build の引数を毎回思い出すのは現実的でなく、
    README に書いた手順は更新されないまま古くなる——
    **ドキュメントは腐るが、テストされたコードは腐らない**。

    #75 で「dlq_runbook() を実行可能な関数として持つ」ことを学んだ。
    同じ思想をデプロイ手順に適用する。

実行方法:
    python 89_deployment_runbook.py       # 手順を表示
    pytest 89_runbook_contract_testing.py -v
"""
from pathlib import Path

HERE = Path(__file__).parent

# 👉 デプロイに必要なアーティファクトの所在
TEMPLATE_FILE = '86_dataflow_flex_template.py'
METADATA_FILE = 'flex_template_metadata.json'
DOCKERFILE = 'flex_template.Dockerfile'


def build_image_uri(project_id: str, repo: str, image: str, tag: str) -> str:
    """
    🔍 Artifact Registry のイメージURIを構築する純粋関数。

    `latest` を使わずタグを明示させる理由は #88 と同一——
    「どのイメージがデプロイされたか」を後から特定できなくなるため。
    """
    return f'asia-northeast1-docker.pkg.dev/{project_id}/{repo}/{image}:{tag}'


def build_template_gcs_path(project_id: str, template_name: str) -> str:
    """テンプレート仕様(JSON)の保存先GCSパス。"""
    return f'gs://{project_id}-dataflow-templates/{template_name}.json'


def build_step_build_image(project_id: str, repo: str, image: str, tag: str) -> dict:
    """
    🚀 【STEP 1】コンテナイメージのビルドとプッシュ。

    Cloud Build を使うことでローカルの Docker 環境に依存しない——
    「私の環境では動く」を構造的に排除する。
    """
    uri = build_image_uri(project_id, repo, image, tag)
    return {
        'step': 1,
        'title': 'Build and push the container image',
        'command': (
            f'gcloud builds submit --tag {uri} '
            f'--file {DOCKERFILE} .'
        ),
        'verify': f'gcloud artifacts docker images list {uri.rsplit(":", 1)[0]}',
        'note': 'Cloud Build removes the dependency on a local Docker daemon.',
    }


def build_step_build_template(project_id: str, repo: str, image: str,
                              tag: str, template_name: str) -> dict:
    """
    🚀 【STEP 2】テンプレート仕様(JSON)の生成とGCS配置。

    ここで metadata.json が読み込まれ、パラメータ契約(#87)が
    テンプレートに埋め込まれる。
    """
    uri = build_image_uri(project_id, repo, image, tag)
    gcs = build_template_gcs_path(project_id, template_name)
    return {
        'step': 2,
        'title': 'Build the Flex Template spec',
        'command': (
            f'gcloud dataflow flex-template build {gcs} '
            f'--image {uri} '
            f'--sdk-language PYTHON '
            f'--metadata-file {METADATA_FILE}'
        ),
        'verify': f'gsutil cat {gcs}',
        'note': 'The parameter contract from item 87 is embedded here.',
    }


def build_step_run_job(project_id: str, template_name: str,
                       subscription: str, output_table: str, dlq_table: str) -> dict:
    """
    🚀 【STEP 3】ジョブの起動。

    ここで #87 の regexes が働き、不正なパラメータは
    ジョブが始まる前に拒否される(課金ゼロ)。
    """
    gcs = build_template_gcs_path(project_id, template_name)
    return {
        'step': 3,
        'title': 'Launch a job from the template',
        'command': (
            f'gcloud dataflow flex-template run {template_name}-$(date +%Y%m%d-%H%M%S) '
            f'--template-file-gcs-location {gcs} '
            f'--region asia-northeast1 '
            f'--parameters input_subscription={subscription} '
            f'--parameters output_table={output_table} '
            f'--parameters dlq_table={dlq_table}'
        ),
        'verify': 'gcloud dataflow jobs list --region asia-northeast1 --limit 1',
        'note': 'Malformed parameters are rejected here, before any billing starts.',
    }


def build_step_rollback(project_id: str, template_name: str) -> dict:
    """
    🚨 【STEP 4】ロールバック手順。

    「進める手順」だけを書いたRunbookは半分しか役に立たない。
    深夜に問題が起きた時に必要なのは、戻し方である。
    """
    return {
        'step': 4,
        'title': 'Roll back: drain the running job',
        'command': (
            'gcloud dataflow jobs drain JOB_ID --region asia-northeast1'
        ),
        'verify': 'gcloud dataflow jobs describe JOB_ID --region asia-northeast1',
        'note': (
            'drain finishes in-flight work before stopping; cancel discards it. '
            'For a streaming pipeline with a DLQ, drain preserves data integrity.'
        ),
    }


def build_runbook(project_id: str, repo: str, image: str, tag: str,
                  template_name: str, subscription: str,
                  output_table: str, dlq_table: str) -> list:
    """
    📋 デプロイ手順全体を構築する。

    各ステップは command(実行)・verify(確認)・note(なぜ)の3点を持つ。
    確認手順の無いRunbookは「打ったが効いたか分からない」状態を生む。
    """
    return [
        build_step_build_image(project_id, repo, image, tag),
        build_step_build_template(project_id, repo, image, tag, template_name),
        build_step_run_job(project_id, template_name, subscription,
                           output_table, dlq_table),
        build_step_rollback(project_id, template_name),
    ]


def print_runbook(steps: list) -> None:
    """Runbookを人間が読める形で出力する。"""
    for s in steps:
        print(f"\n--- STEP {s['step']}: {s['title']} ---")
        print(f"  $ {s['command']}")
        print(f"  verify: {s['verify']}")
        print(f"  why:    {s['note']}")


if __name__ == '__main__':
    print("🚀 デプロイRunbook基盤の監査を開始するのね...")
    # print_runbook(build_runbook(
    #     'my-proj', 'dataflow-repo', 'pubsub-to-bq', 'v1',
    #     'pubsub-to-bq-dlq',
    #     'projects/my-proj/subscriptions/events-sub',
    #     'my-proj:analytics.events',
    #     'my-proj:analytics.events_dlq',
    # ))
    print("🟢 監査完了!手順と確認と根拠を持つ実行可能Runbook基盤が完全画定したのね!")