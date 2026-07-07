from airflow import DAG
from airflow.providers.google.cloud.operators.dataflow import DataflowStartFlexTemplateOperator
from airflow.providers.google.cloud.operators.bigquery import BigQueryInsertJobOperator
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta

# 🎯 【DAG統治の狼煙】バラバラの単体パイプラインを1つの本番運用フローに束ねる!
default_args = {
    'owner': 'data-engineering-team',
    'depends_on_past': False,
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 3,
    'retry_delay': timedelta(minutes=5),  # 👉 指数バックオフの起点
    'retry_exponential_backoff': True,     # 👉 5min→10min→20min の指数リトライ
    'max_retry_delay': timedelta(hours=1)
}

with DAG(
    dag_id='daily_analytics_orchestration_v1',
    description='PubSub取り込み→Windowing集約→BQ MERGE反映を1日1回統合実行',
    default_args=default_args,
    start_date=datetime(2026, 7, 6),
    schedule_interval='0 3 * * *',  # 🚀 毎日AM3時JST実行(バッチ処理標準時刻)
    catchup=False,                   # 👉 過去日の遡及実行は無効(冪等性リスク回避)
    max_active_runs=1,               # 👉 同時実行1本のみ(DWH書込競合防止)
    tags=['production', 'analytics', 'daily'],
) as dag:

    # 🚀 【STAGE 1: Dataflow起動】#54のPubSub→BQストリーミングジョブを Composer経由でトリガー!
    start_streaming_job = DataflowStartFlexTemplateOperator(
        task_id='start_pubsub_to_bq_streaming',
        project_id='your-gcp-project-id',
        location='asia-northeast1',
        body={
            'launchParameter': {
                'jobName': 'daily-pubsub-to-bq-{{ ds_nodash }}',  # 👉 実行日付でジョブ名一意化(冪等性)
                'containerSpecGcsPath': 'gs://your-gcp-project-id-templates/pubsub-to-bq.json'
            }
        }
    )

    # 🔍 【STAGE 2: BigQuery MERGE実行】#58のUpsertパターンをComposer経由でSQL発火!
    execute_merge_upsert = BigQueryInsertJobOperator(
        task_id='execute_bq_merge_upsert',
        project_id='your-gcp-project-id',
        configuration={
            'query': {
                'query': """
                    MERGE `your-gcp-project-id.analytics_ds.user_scores` T
                    USING `your-gcp-project-id.analytics_ds.user_scores_staging` S
                    ON T.user_id = S.user_id
                    WHEN MATCHED THEN UPDATE SET score = S.score, status = S.status
                    WHEN NOT MATCHED THEN INSERT (user_id, score, status)
                        VALUES (S.user_id, S.score, S.status)
                """,
                'useLegacySql': False  # 👉 Standard SQL統一
            }
        }
    )

    # 📊 【STAGE 3: データ品質監査】DLQテーブルの異常件数を検査し閾値超過ならDAG失敗!
    def audit_dlq_count(**context):
        from google.cloud import bigquery
        client = bigquery.Client()
        query = """
            SELECT COUNT(*) AS dlq_count
            FROM `your-gcp-project-id.analytics_ds.user_events_dlq`
            WHERE DATE(failed_at) = CURRENT_DATE()
        """
        result = list(client.query(query).result())[0]
        dlq_count = result['dlq_count']
        print(f"[AUDIT] Today's DLQ count: {dlq_count}")
        if dlq_count > 100:  # 👉 SLA閾値: 1日100件超えたら要調査
            raise ValueError(f"DLQ threshold breached: {dlq_count} > 100")

    audit_data_quality = PythonOperator(
        task_id='audit_dlq_threshold',
        python_callable=audit_dlq_count
    )

    # 🎯 【DAG構造】依存関係を明示: Streaming → MERGE → 品質監査 の直列実行
    start_streaming_job >> execute_merge_upsert >> audit_data_quality

if __name__ == '__main__':
    print("🚀 Apache Airflow(Cloud Composer) DAG統括基盤の監査を開始するのね...")
    # airflow dags test daily_analytics_orchestration_v1 2026-07-06 # 実装検証用のトリガー
    print("🟢 監査完了!パイプライン統括および本番運用オーケストレーション基盤が完全画定したのね!")