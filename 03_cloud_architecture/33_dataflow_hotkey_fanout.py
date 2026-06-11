import apache_beam as beam

def run_fanout_pipeline():
    with beam.Pipeline() as p:        

        # 🚀 【STAGE 1: Ingestion】特定のキー「CYMBAL」だけに極端にデータが集中したスパイク状態
        raw_stream = p | 'CreateHotKeyStream' >> beam.Create([
            ('CYMBAL', 1), ('CYMBAL', 1), ('CYMBAL', 1), # 🚨 これが特定のWorkerを殺す「ホットキー」！
            ('CYMBAL', 1), ('CYMBAL', 1), ('ENGINEER', 1)
        ])

        # 🌟 【今夜の主役】with_fanout を使い、裏側の集計ラインを「3並列」に強制分散！
        # 1台のWorkerにデータが集中する前に、中間Worker3台で小分けに先制集計（Combine）させるのね！
        aggregated_stream = (
            raw_stream
            | 'AggregateWithFanout' >> beam.CombinePerKey(sum).with_fanout(3) # 👈 ココが鉄壁の防衛線！
        )

        # 🚀 【STAGE 2: Output】分散集計された結果を安全に回収してクリーン出力
        (
            aggregated_stream
            | 'FormatLog' >> beam.Map(lambda kv: f"🔥【ホットキー分散統治通過】単語: {kv[0]} | 総カウント: {kv[1]}回")
            | 'FinalOutput' >> beam.Map(print)
        )
    
if __name__ == '__main__':
    print("⚡ Dataflowホットキー自動分散（Fan-out数: 3）の監査を開始するのね...")
    run_fanout_pipeline()