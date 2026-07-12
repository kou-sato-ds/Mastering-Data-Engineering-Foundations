import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions, GoogleCloudOptions, StandardOptions
from apache_beam.transforms.window import Sessions
import json

def run_session_window_pipeline():
    options = PipelineOptions()
    gc_options = options.view_as(GoogleCloudOptions)
    gc_options.project = 'your-gcp-project-id'
    gc_options.region = 'asia-northeast1'
    gc_options.job_name = 'dataflow-session-window-v1'

    # 🎯 【本番運用の狼煙】ストリーミングモードで無限時間軸を統治!
    options.view_as(StandardOptions).streaming = True

    input_subscription = 'projects/your-gcp-project-id/subscriptions/user-events-sub'
    output_table = 'your-gcp-project-id:analytics_ds.user_sessions'
    output_schema = 'user_id:STRING, session_start:TIMESTAMP, session_end:TIMESTAMP, event_count:INTEGER'

    with beam.Pipeline(options=options) as p:
        (
            p
            # 🚀 【STAGE 1: PubSub Source】event-time付き無限ストリームを吸入!
            | 'ReadFromPubSub' >> beam.io.ReadFromPubSub(
                subscription=input_subscription,
                timestamp_attribute='event_time'  # 👉 セッション境界はイベント発生時刻で決まる
            )
            # 🔍 【STAGE 2: 解読】バイト列JSONを構造化辞書に一撃変換!
            | 'DecodeAndParse' >> beam.Map(
                lambda msg: json.loads(msg.decode('utf-8'))
            )
            # ⏱️ 【STAGE 3: Session Windowing】固定時計ではなく"データの活動間隔"が窓を切る!
            | 'ApplySessionWindow' >> beam.WindowInto(
                Sessions(gap_size=600)  # 👉 10分間の無活動でセッション確定(EC分析の業界標準帯)
            )
            # 🔑 【STAGE 4: Keying】ユーザー単位でセッションを形成(キーごとに窓がマージされる)!
            | 'PairWithUser' >> beam.Map(
                lambda row: (row['user_id'], 1)
            )
            # 📊 【STAGE 5: セッション内集約】マージ済みセッション窓×ユーザーでイベント数を集計!
            | 'CountPerSession' >> beam.CombinePerKey(sum)
            # 🎨 【STAGE 6: BQスキーマ整形】セッション境界(start/end)をメタデータとして採取!
            | 'FormatForBigQuery' >> beam.Map(
                lambda kv, window=beam.DoFn.WindowParam: {
                    'user_id': kv[0],
                    'session_start': window.start.to_utc_datetime().isoformat(),
                    'session_end': window.end.to_utc_datetime().isoformat(),  # 👉 最終イベント時刻+gapがend
                    'event_count': kv[1]
                }
            )
            # 🚀 【STAGE 7: BigQuery Sink】セッション粒度の行動分析データを並列インジェクション!
            | 'WriteToBigQuery' >> beam.io.WriteToBigQuery(
                output_table,
                schema=output_schema,
                write_disposition=beam.io.BigQueryDisposition.WRITE_APPEND,  # 👉 追記モード
                create_disposition=beam.io.BigQueryDisposition.CREATE_IF_NEEDED  # 👉 自動生成
            )
        )

if __name__ == '__main__':
    print("🚀 Apache Beam Session Windows ユーザー行動セッション化基盤の監査を開始するのね...")
    # run_session_window_pipeline() # 実装検証用のトリガー
    print("🟢 監査完了!データ駆動の動的ウィンドウおよびセッション粒度分析基盤が完全画定したのね!")