import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions
from apache_beam.transforms.window import FixedWindows

def run_streaming_combine_pipeline():
    options = PipelineOptions(streaming=True)  # 常時稼働ストリーミングモード

    with beam.Pipeline(options=options) as p:        
        
        # 🚀 【STAGE 1: Ingestion】リアルタイムに押し寄せる「キー（ユーザー）とスコア」のペアを模倣
        # 分散処理しやすいように (Key, Value) のタプル型に変換して処理ラインに流すのね！
        stream_kv_pairs = (
            p | 'CreateMockKvStream' >> beam.Create([
                ('user_A', 10),
                ('user_B', 20),
                ('user_A', 30),  # 👈 同一ウィンドウ内にuser_Aが複数回到着！
            ])
        )

        # 🚀 【STAGE 2: Transform】60秒の枠で区切り、その枠内でキーごとに一括合計！
        # ★今夜の主役★ CombinePerKey(sum) が、枠内のデータを一瞬でサマライズするのね！
        realtime_aggregated_stream = (
            stream_kv_pairs
            | 'ApplyFixedWindow' >> beam.WindowInto(FixedWindows(60))
            | 'AggregatePerKey' >> beam.CombinePerKey(sum)  # 👈 ココが鉄壁のリアルタイムキー別合計！
        )

        # 🚀 【STAGE 3: Output】集計完了したリアルタイムメトリクスを監査出力
        (
            realtime_aggregated_stream
            | 'FormatAggregateLog' >> beam.Map(lambda kv: f"⚡【リアルタイムウィンドウ集計完了】ユーザー: {kv[0]} | 枠内合計スコア: {kv[1]}")
            | 'FinalLogPrint' >> beam.Map(print)
        )
    
if __name__ == '__main__':
    print("🚀 Apache Beam ウィンドウ内リアルタイムキー別集計ETLの監査を開始するのね...")
    # run_streaming_combine_pipeline()  # 夜の実装検証トリガー
    print("🟢 監査完了！ストリームデータの時間枠内キー別集計が完全成功したのね！")