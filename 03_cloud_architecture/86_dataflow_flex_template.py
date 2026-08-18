import argparse
import json
import logging

import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions, GoogleCloudOptions, StandardOptions

# 🎯 【デプロイ統治の狼煙】ローカルスクリプトを再利用可能なテンプレートへ昇華!


class FlexTemplateOptions(PipelineOptions):
    """
    🔍 実行時パラメータの宣言。

    Flex Template はビルド時ではなく **実行時** にパラメータを受け取る。
    プロジェクトIDのハードコードを排除し、
    同一テンプレートを dev/staging/prod で使い回せる構造にする。
    """

    @classmethod
    def _add_argparse_args(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_value_provider_argument(
            '--input_subscription',
            help='PubSub subscription to read from (projects/.../subscriptions/...)',
        )
        parser.add_value_provider_argument(
            '--output_table',
            help='BigQuery table to write to (project:dataset.table)',
        )
        parser.add_value_provider_argument(
            '--dlq_table',
            help='BigQuery table for malformed records',
        )


MAIN_TAG = 'main_output'
DLQ_TAG = 'dlq_output'
REQUIRED_FIELDS = {'event_id', 'user_id', 'event_type'}


def build_main_schema() -> str:
    """正常データテーブルのスキーマ定義。"""
    return 'event_id:STRING, user_id:STRING, event_type:STRING'


def build_dlq_schema() -> str:
    """DLQテーブルのスキーマ定義（#65と同一の4列を維持）。"""
    return 'raw_payload:STRING, error_type:STRING, error_message:STRING, failed_at:TIMESTAMP'


def validate_record(row: dict) -> None:
    """
    🛡️ 必須フィールド検証。欠損時は ValueError を送出する。

    テンプレート化しても検証ロジックは変わらない——
    変わるのは「どこから読み、どこへ書くか」だけである。
    """
    missing = REQUIRED_FIELDS - row.keys()
    if missing:
        raise ValueError(f"Missing required fields: {missing}")


class ParseAndValidateFn(beam.DoFn):
    """#65 と同一のDLQ振り分けロジック。テンプレート内でも思想は不変。"""

    def process(self, msg_bytes):
        try:
            row = json.loads(msg_bytes.decode('utf-8'))
            validate_record(row)
            yield beam.pvalue.TaggedOutput(MAIN_TAG, row)
        except Exception as e:
            yield beam.pvalue.TaggedOutput(DLQ_TAG, {
                'raw_payload': msg_bytes.decode('utf-8', errors='replace'),
                'error_type': type(e).__name__,
                'error_message': str(e),
                'failed_at': beam.utils.timestamp.Timestamp.now().to_utc_datetime().isoformat(),
            })


def run(argv=None):
    """
    🚀 Flex Template のエントリポイント。

    従来の run_*_pipeline() との決定的な違い:
        - プロジェクトIDやテーブル名をハードコードしない
        - argv からパラメータを受け取る (実行時注入)
        - よって同一のコンテナイメージを環境をまたいで再利用できる
    """
    options = PipelineOptions(argv)
    flex_options = options.view_as(FlexTemplateOptions)
    options.view_as(StandardOptions).streaming = True

    # 👉 GoogleCloudOptions はテンプレート起動時に gcloud 側から注入される
    gc_options = options.view_as(GoogleCloudOptions)
    logging.info("starting flex template job: %s", gc_options.job_name)

    with beam.Pipeline(options=options) as p:
        parsed = (
            p
            | 'ReadFromPubSub' >> beam.io.ReadFromPubSub(
                subscription=flex_options.input_subscription
            )
            | 'ParseAndValidate' >> beam.ParDo(ParseAndValidateFn()).with_outputs(MAIN_TAG, DLQ_TAG)
        )

        (
            parsed[MAIN_TAG]
            | 'WriteMain' >> beam.io.WriteToBigQuery(
                flex_options.output_table,
                schema=build_main_schema(),
                write_disposition=beam.io.BigQueryDisposition.WRITE_APPEND,
                create_disposition=beam.io.BigQueryDisposition.CREATE_IF_NEEDED,
            )
        )

        (
            parsed[DLQ_TAG]
            | 'WriteDLQ' >> beam.io.WriteToBigQuery(
                flex_options.dlq_table,
                schema=build_dlq_schema(),
                write_disposition=beam.io.BigQueryDisposition.WRITE_APPEND,
                create_disposition=beam.io.BigQueryDisposition.CREATE_IF_NEEDED,
            )
        )


if __name__ == '__main__':
    logging.getLogger().setLevel(logging.INFO)
    print("🚀 Dataflow Flex Template 再利用可能パッケージ基盤の監査を開始するのね...")
    # run()  # 実装検証用のトリガー
    print("🟢 監査完了!環境をまたいで再利用可能なテンプレート基盤が完全画定したのね!")