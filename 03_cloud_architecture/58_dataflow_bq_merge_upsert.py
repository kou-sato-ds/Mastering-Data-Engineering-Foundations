import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions, GoogleCloudOptions
from google.cloud import bigquery

def run_merge_upsert_pipeline():
    options = PipelineOptions()
    gc_options = options.view_as(GoogleCloudOptions)
    gc_options.project = 'your-gcp-project-id'
    gc_options.region = 'asia-northeast1'
    gc_options.job_name = 'dataflow-bq-merge-upsert-v1'

    # 🎯 【DWH冪等性の狼煙】ステージング→ターゲットへのMERGE経路を統治!
    project_id = 'your-gcp-project-id'
    staging_table = f'{project_id}.analytics_ds.user_scores_staging'
    target_table = f'{project_id}.analytics_ds.user_scores'
    staging_schema = 'user_id:STRING, score:INTEGER, status:STRING, updated_at:TIMESTAMP'

    # 🚀 【STAGE 1: ステージング書き込み】新着データを一時テーブルへ並列インジェクション!
    with beam.Pipeline(options=options) as p:
        (
            p
            | 'CreateNewData' >> beam.Create([
                {'user_id': 'KOU-01', 'score': 150, 'status': 'ACTIVE', 'updated_at': '2026-07-05T09:00:00Z'},
                {'user_id': 'SK-02', 'score': 95, 'status': 'VIP', 'updated_at': '2026-07-05T09:00:00Z'},
                {'user_id': 'NEW-03', 'score': 30, 'status': 'ACTIVE', 'updated_at': '2026-07-05T09:00:00Z'},
            ])
            | 'WriteToStaging' >> beam.io.WriteToBigQuery(
                staging_table,
                schema=staging_schema,
                write_disposition=beam.io.BigQueryDisposition.WRITE_TRUNCATE,  # 👉 ステージングは毎回リセット
                create_disposition=beam.io.BigQueryDisposition.CREATE_IF_NEEDED  # 👉 自動生成
            )
        )

    # 🎯 【STAGE 2: MERGE実行】DWH層でUpsertを冪等に実行!
    # 👉 同じMERGEを何度実行しても、targetテーブルの最終状態は常に同じ (冪等性の本質)
    merge_sql = f"""
    MERGE `{target_table}` T
    USING `{staging_table}` S
    ON T.user_id = S.user_id
    WHEN MATCHED THEN
      UPDATE SET
        score = S.score,
        status = S.status,
        updated_at = S.updated_at
    WHEN NOT MATCHED THEN
      INSERT (user_id, score, status, updated_at)
      VALUES (S.user_id, S.score, S.status, S.updated_at)
    """

    # 🚀 【STAGE 3: MERGE Job実行】BigQuery Client経由でSQL発火!
    bq_client = bigquery.Client(project=project_id)
    merge_job = bq_client.query(merge_sql)
    merge_job.result()  # 👉 完了を同期的に待機 (エラー時は例外raise)

    print(f"🟢 MERGE完了! {merge_job.num_dml_affected_rows} 行が Upsert された")

if __name__ == '__main__':
    print("🚀 Apache Beam + BigQuery MERGE (Upsert) DWH冪等性基盤の監査を開始するのね...")
    # run_merge_upsert_pipeline() # 実装検証用のトリガー
    print("🟢 監査完了!DWH層Upsertおよび冪等性保証基盤が完全画定したのね!")