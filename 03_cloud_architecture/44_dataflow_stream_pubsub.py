import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions
from apache_beam.io.gcp.pubsub import ReadFromPubSub  # 🚨リアルタイムストリーミングの絶対核心！

def run_pubsub_streaming_pipeline():
    # 🌟 ストリーミングジョブとして常時稼働させるための必須オプション！
    options = PipelineOptions(streaming=True)

    with beam.Pipeline(options=options) as p:
        
        # 🚀 【STAGE 1: Ingestion】GCP Pub/Subトピックからリアルタイムデータを常時吸い上げ
        # 24時間365日、データが届いた瞬間にこのパイプラインへ自動インジェクションされるのね！
        pubsub_stream = (
            p | 'ReadFromEventHub' >> ReadFromPubSub(
                topic='projects/mock-gcp-project-id/topics/user-click-events'
            )
        )

        # 🚀 【STAGE 2: Transform / Output】ミリ秒で流れてくるバイナリデータをデコードして監査出力
        (
            pubsub_stream
            | 'DecodeByteToString' >> beam.Map(lambda payload: payload.decode('utf-8'))
            | 'FormatStreamLog' >> beam.Map(lambda event_str: f"⚡【リアルタイムイベント検知】-> {event_str}")
            | 'FinalLogPrint' >> beam.Map(print)
        )

if __name__ == '__main__':
    print("🚀 Apache Beam リアルタイムPub/SubストリーミングETL（常時接続モード）の監査を開始するのね...")
    # run_pubsub_streaming_pipeline()  # 夜の実装検証トリガー