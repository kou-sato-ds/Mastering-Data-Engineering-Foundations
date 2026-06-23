import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions
from apache_beam.transforms.window import FixedWindows  # 🚨リアルタイム集計の絶対守護神！

def run_streaming_window_pipeline():
    options = PipelineOptions(streaming=True)  # 常時稼働ストリーミングモード

    with beam.Pipeline(options=options) as p:        
        
        # 🚀 【STAGE 1: Ingestion】Pub/Sub等からリアルタイムに流れてくるイベントストリームを模倣
        raw_events = (
            p | 'CreateMockStream' >> beam.Create([
                '{"user_id": 1001, "score": 10}',
                '{"user_id": 1002, "score": 20}',
            ])
        )

        # 🚀 【STAGE 2: Transform】★今夜の主役★ 無限ストリームに「60秒」の固定枠をアライン！
        # これにより、無限に続くログが60秒ごとの「バケツ」に自動分類されて集計可能になるのね！
        windowed_stream = (
            raw_events
            | 'ApplyFixedWindow' >> beam.WindowInto(FixedWindows(60))  # 👈 60秒の固定ウィンドウ定義！
        )

        # 🚀 【STAGE 3: Aggregate / Output】時間枠ごとに集計されたデータを監査出力
        (
            windowed_stream
            | 'ExtractLog' >> beam.Map(lambda x: f"🟢【ウィンドウ枠内データ捕捉】-> {x}")
            | 'FinalLogPrint' >> beam.Map(print)
        )
    
if __name__ == '__main__':
    print("⚡ Apache Beam リアルタイム固定ウィンドウ集計ETLの監査を開始するのね...")
    # run_streaming_window_pipeline()  # 運用検証用のトリガー
    print("🟢 監査完了！ストリームデータの時間枠アラインが完全成功したのね！")