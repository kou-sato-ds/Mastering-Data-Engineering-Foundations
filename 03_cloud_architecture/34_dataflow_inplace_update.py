import apache_beam as beam

def run_update_compatible_pipeline():
    # 🌟 本番Dataflowの無停止アップデート（In-place Update）に完全対応したパイプライン
    with beam.Pipeline() as p:        

        # 🚀 【STAGE 1: Ingestion】
        # 🚨 全てのステップに必ず '明示的かつ一意の名前'（Stable Unique IDs）を付与する！
        # これにより、本番ジョブの起動中にコードを上書きデプロイしても、Dataflowが状態を正しく引き継げるのね！
        raw_data = p | 'IngestLiveStream' >> beam.Create([
            'CYMBAL', 'ENGINEER', 'SUCCESS'
        ])

        # 🚀 【STAGE 2: Transform】
        # 将来的にラムダ式の中身（ロジック）を修正して上書きアップデートしても、
        # ステップ名（'CleanAndMapText'）さえ変わっていなければ、ジョブは1秒も止まらずに最新ロジックへ移行する！
        processed_data = (
            raw_data
            | 'CleanAndMapText' >> beam.Map(lambda word: word.strip().upper()) # 👈 ココの名前を絶対に変えない！
            | 'PairWithConstant' >> beam.Map(lambda word: (word, 1))           # 👈 ココも固定！
        )

        # 🚀 【STAGE 3: Output】
        (
            processed_data
            | 'FormatLogOutput' >> beam.Map(lambda kv: f"✨【無停止統治ライン通過】{kv[0]}: {kv[1]}")
            | 'FinalLogPrint'   >> beam.Map(print)
        )
    
if __name__ == '__main__':
    print("⚡ Dataflowインプレース・アップデート（互換性ID検証）の監査を開始するのね...")
    run_update_compatible_pipeline()