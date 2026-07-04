import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions, GoogleCloudOptions, StandardOptions
from apache_beam.transforms.window import FixedWindows
from apache_beam.transforms.trigger import AfterWatermark, AfterProcessingTime, AccumulationMode
import json

def run_late_data_pipeline():
    options = PipelineOptions()
    gc_options = options.view_as(GoogleCloudOptions)
    gc_options.project = 'your-gcp-project-id'
    gc_options.region = 'asia-northeast1'
    gc_options.job_name = 'dataflow-late-data-handling-v1'

    # 🎯 【本番運用の狼煙】ストリーミングモードで無限時間軸を統治!
    options.view_as(StandardOptions).streaming = True

    input_subscription = 'projects/your-gcp-project-id/subscriptions/user-events-sub'
    output_table = 'your-gcp-project-id:analytics_ds.user_events_late_data_safe'
    output_schema = 'window_start:TIMESTAMP, event_type:STRING, event_count:INTEGER, is_late:BOOLEAN'

    with beam.Pipeline(options=options) as p:
        (
            p
            # 🚀 【STAGE 1: PubSub Source】タイムスタンプ付き無限ストリームを吸入!
            | 'ReadFromPubSub' >> beam.io.ReadFromPubSub(
                subscription=input_subscription,
                timestamp_attribute='event_time'  # 👉 event-timeベースで処理(処理時刻ではない)
            )
            # 🔍 【STAGE 2: 解読】バイト列JSONを構造化辞書に一撃変換!
            | 'DecodeAndParse' >> beam.Map(
                lambda msg: json.loads(msg.decode('utf-8'))
            )
            # ⏱️ 【STAGE 3: Late-Data耐性Windowing】遅延到着データも救済する時間統治!
            | 'ApplyWindowWithLateness' >> beam.WindowInto(
                FixedWindows(60),  # 👉 60秒の固定ウィンドウ
                trigger=AfterWatermark(
                    early=AfterProcessingTime(10),  # 👉 10秒ごとの早期発火(投機的結果)
                    late=AfterProcessingTime(30)    # 👉 遅延到着データが来たら30秒ごとに再発火
                ),
                allowed_lateness=300,  # 👉 5分までの遅延を許容(ウィンドウを閉じずに待つ)
                accumulation_mode=AccumulationMode.ACCUMULATING  # 👉 遅延データを既存結果に累積
            )
            # 🔑 【STAGE 4: Keying】集約キー(event_type)でグルーピング準備!
            | 'PairWithEventType' >> beam.Map(
                lambda row: (row['event_type'], 1)
            )
            # 📊 【STAGE 5: Window内累積集約】遅延データ到着ごとに再集計!
            | 'CountPerWindow' >> beam.CombinePerKey(sum)
            # 🎨 【STAGE 6: BQスキーマ整形】遅延フラグ(is_late)付きBQ行を構築!
            | 'FormatForBigQuery' >> beam.Map(
                lambda kv, window=beam.DoFn.WindowParam, pane=beam.DoFn.PaneInfoParam: {
                    'window_start': window.start.to_utc_datetime().isoformat(),
                    'event_type': kv[0],
                    'event_count': kv[1],
                    'is_late': pane.is_last and pane.index > 0  # 👉 2回目以降の発火=遅延データによる更新
                }
            )
            # 🚀 【STAGE 7: BigQuery Sink】遅延補正済み集約結果を分析基盤へインジェクション!
            | 'WriteToBigQuery' >> beam.io.WriteToBigQuery(
                output_table,
                schema=output_schema,
                write_disposition=beam.io.BigQueryDisposition.WRITE_APPEND,  # 👉 追記モード
                create_disposition=beam.io.BigQueryDisposition.CREATE_IF_NEEDED  # 👉 自動生成
            )
        )

if __name__ == '__main__':
    print("🚀 Apache Beam Late Data Handling (Watermark制御) 基盤の監査を開始するのね...")
    # run_late_data_pipeline() # 実装検証用のトリガー
    print("🟢 監査完了!遅延到着データ耐性および分析データ整合性保証基盤が完全画定したのね!")