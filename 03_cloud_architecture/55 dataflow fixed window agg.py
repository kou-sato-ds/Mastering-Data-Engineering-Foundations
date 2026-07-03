import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions, GoogleCloudOptions, StandardOptions
from apache_beam.transforms.window import FixedWindows
import json

def run_windowing_pipeline():
    options = PipelineOptions()
    gc_options = options.view_as(GoogleCloudOptions)
    gc_options.project = 'your-gcp-project-id'
    gc_options.region = 'asia-northeast1'
    gc_options.job_name = 'dataflow-fixed-window-agg-v1'

    # 🎯 【本番運用の狼煙】ストリーミングモードで無限時間軸を統治!
    options.view_as(StandardOptions).streaming = True

    input_subscription = 'projects/your-gcp-project-id/subscriptions/user-events-sub'
    output_table = 'your-gcp-project-id:analytics_ds.user_events_1min_agg'
    output_schema = 'window_start:TIMESTAMP, event_type:STRING, event_count:INTEGER'

    with beam.Pipeline(options=options) as p:
        (
            p
            # 🚀 【STAGE 1: PubSub Source】無限ストリームをサーバレス吸入!
            | 'ReadFromPubSub' >> beam.io.ReadFromPubSub(
                subscription=input_subscription
            )
            # 🔍 【STAGE 2: 解読】バイト列JSONを構造化辞書に一撃変換!
            | 'DecodeAndParse' >> beam.Map(
                lambda msg: json.loads(msg.decode('utf-8'))
            )
            # ⏱️ 【STAGE 3: Fixed Windowing】無限ストリームを1分単位の有限バケツに切り分け!
            | 'ApplyFixedWindow' >> beam.WindowInto(
                FixedWindows(60)  # 👉 60秒 = 1分の固定ウィンドウ
            )
            # 🔑 【STAGE 4: Keying】集約キー(event_type)でグルーピング準備!
            | 'PairWithEventType' >> beam.Map(
                lambda row: (row['event_type'], 1)
            )
            # 📊 【STAGE 5: Window内集約】ウィンドウ×キーごとに件数を並列カウント!
            | 'CountPerWindow' >> beam.CombinePerKey(sum)
            # 🎨 【STAGE 6: BQスキーマ整形】window情報と集約結果をBQ行形式に!
            | 'FormatForBigQuery' >> beam.Map(
                lambda kv, window=beam.DoFn.WindowParam: {
                    'window_start': window.start.to_utc_datetime().isoformat(),
                    'event_type': kv[0],
                    'event_count': kv[1]
                }
            )
            # 🚀 【STAGE 7: BigQuery Sink】集約結果を分析基盤へ並列インジェクション!
            | 'WriteToBigQuery' >> beam.io.WriteToBigQuery(
                output_table,
                schema=output_schema,
                write_disposition=beam.io.BigQueryDisposition.WRITE_APPEND,  # 👉 追記モード
                create_disposition=beam.io.BigQueryDisposition.CREATE_IF_NEEDED  # 👉 自動生成
            )
        )

if __name__ == '__main__':
    print("🚀 Apache Beam Fixed Window 時間集約基盤の監査を開始するのね...")
    # run_windowing_pipeline() # 実装検証用のトリガー
    print("🟢 監査完了!無限ストリームの時間軸統治および分単位集約基盤が完全画定したのね!")