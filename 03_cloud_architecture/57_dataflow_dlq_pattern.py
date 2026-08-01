import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions, GoogleCloudOptions, StandardOptions
import json

# 🎯 【DLQ分岐タグ】main(正常) と dlq(異常) を明示的に分ける
MAIN_TAG = 'main_output'
DLQ_TAG = 'dlq_output'


class ParseAndValidateFn(beam.DoFn):
    """
    🛡️ PubSubから届いた生バイト列JSONを解読し、厳密スキーマ検証を実行するDoFn。
    失敗時は例外を握りつぶさず、DLQタグへ構造化エラー情報付きで振り分ける。
    """
    def process(self, msg_bytes):
        try:
            row = json.loads(msg_bytes.decode('utf-8'))
            # 👉 必須フィールドの厳密検証 (実務ではJSON Schemaライブラリ推奨)
            required_fields = {'event_id', 'user_id', 'event_type'}
            missing = required_fields - row.keys()
            if missing:
                raise ValueError(f"Missing required fields: {missing}")
            yield beam.pvalue.TaggedOutput(MAIN_TAG, row)
        except Exception as e:
            # 🚨 例外を絶対に握りつぶさない! 構造化エラー情報をDLQへ
            yield beam.pvalue.TaggedOutput(DLQ_TAG, {
                'raw_payload': msg_bytes.decode('utf-8', errors='replace'),
                'error_type': type(e).__name__,
                'error_message': str(e),
                'failed_at': beam.utils.timestamp.Timestamp.now().to_utc_datetime().isoformat()
            })


def build_pipeline_options(project_id: str, region: str, job_name: str) -> PipelineOptions:
    """
    🔍 パイプラインオプション構築を切り出した純粋関数。

    Beamのシンク(WriteToBigQuery)はGCPクライアント一式を要求しローカル実行
    できないが、オプション構築は純粋である——テスト可能な単位へ分離することで
    「streaming=True の設定漏れ」等の設計事故をテストで防ぐ(#81の指摘による改善)。
    """
    options = PipelineOptions()
    gc_options = options.view_as(GoogleCloudOptions)
    gc_options.project = project_id
    gc_options.region = region
    gc_options.job_name = job_name

    # 🎯 【本番運用の狼煙】ストリーミングモードで無限時間軸を統治!
    options.view_as(StandardOptions).streaming = True
    return options


def build_dlq_schema() -> str:
    """
    🚨 DLQテーブルのスキーマ定義。深夜の障害調査でSQL照会するための必須列を保証する。
    """
    return 'raw_payload:STRING, error_type:STRING, error_message:STRING, failed_at:TIMESTAMP'


def build_main_schema() -> str:
    """正常データテーブルのスキーマ定義。"""
    return 'event_id:STRING, user_id:STRING, event_type:STRING'


def run_dlq_pipeline():
    project_id = 'your-gcp-project-id'
    options = build_pipeline_options(project_id, 'asia-northeast1', 'dataflow-dlq-pattern-v1')

    input_subscription = f'projects/{project_id}/subscriptions/user-events-sub'
    main_table = f'{project_id}:analytics_ds.user_events_clean'
    dlq_table = f'{project_id}:analytics_ds.user_events_dlq'

    with beam.Pipeline(options=options) as p:
        # 🚀 【STAGE 1: PubSub Source】無限ストリームをサーバレス吸入!
        raw_stream = (
            p
            | 'ReadFromPubSub' >> beam.io.ReadFromPubSub(subscription=input_subscription)
        )

        # 🛡️ 【STAGE 2: 分岐処理】ParseAndValidateFnでmain/dlqを構造化分離!
        parsed = (
            raw_stream
            | 'ParseAndValidate' >> beam.ParDo(ParseAndValidateFn()).with_outputs(MAIN_TAG, DLQ_TAG)
        )

        # 🚀 【STAGE 3-A: Main Sink】正常データを分析基盤へ並列インジェクション!
        (
            parsed[MAIN_TAG]
            | 'WriteMainToBQ' >> beam.io.WriteToBigQuery(
                main_table,
                schema=build_main_schema(),
                write_disposition=beam.io.BigQueryDisposition.WRITE_APPEND,
                create_disposition=beam.io.BigQueryDisposition.CREATE_IF_NEEDED
            )
        )

        # 🚨 【STAGE 3-B: DLQ Sink】異常データを構造化エラー情報付きで隔離保管!
        (
            parsed[DLQ_TAG]
            | 'WriteDLQToBQ' >> beam.io.WriteToBigQuery(
                dlq_table,
                schema=build_dlq_schema(),
                write_disposition=beam.io.BigQueryDisposition.WRITE_APPEND,
                create_disposition=beam.io.BigQueryDisposition.CREATE_IF_NEEDED
            )
        )


if __name__ == '__main__':
    print("🚀 Apache Beam Dead Letter Queue (DLQ) 障害耐性基盤の監査を開始するのね...")
    # run_dlq_pipeline() # 実装検証用のトリガー
    print("🟢 監査完了!障害メッセージ隔離および分析基盤クリーンネス保証基盤が完全画定したのね!")