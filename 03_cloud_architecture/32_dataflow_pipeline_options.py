import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions
from apache_beam.options.pipeline_options import StandardOptions
from apache_beam.options.pipeline_options import GoogleCloudOptions

def run_scaling_governance_pipeline():
    # 🌟【今日の主役】本番Dataflow運用のリソース・コストを完全統治するオプション辞書
    # 通常はコマンドライン引数から渡す設定を、コード内で明示的に防衛アライン！
    options_dict = {
        # 1. 実行環境の指定（実務では 'DataflowRunner' を指定してGCPへ投げるのね！）
        'runner': 'DirectRunner', 
        'project': 'mock-gcp-project-id',
        'temp_location': 'gs://mock-bucket/temp',
        
        # 🚨【インフラ防衛線】オートスケーリングのアルゴリズムをスループットベースに設定
        'autoscaling_algorithm': 'THROUGHPUT_BASED',
        
        # 🚨【コスト絶対防衛線】どんなに大スパイクが来ても、最大「3台」までしか Worker を増やさない！
        # これにより、想定外のバグデータ流入によるクラウド高額請求（破産）を100%未然に防ぐ！
        'max_num_workers': 3,
        
        # 3. 初期起動ワーカー数（まずは最低限の1台から静かにスタートさせる）
        'num_workers': 1
    }
    
    # 辞書からBeam専用の PipelineOptions オブジェクトを生成
    options = PipelineOptions.from_dictionary(options_dict)
    
    # ストリーミングモードを明示的に有効化（運用完全統治の基本）
    options.view_as(StandardOptions).streaming = True

    # 構築したオプションを引数に渡して、防衛パイプラインを起動！
    with beam.Pipeline(options=options) as p:        

        # 🚀 【STAGE 1: Ingestion】リアルタイムのデータスパイクを模したストリーム
        raw_stream = p | 'CreateSpikeStream' >> beam.Create([
            'CYMBAL', 'CYMBAL', 'ENGINEER', 'DATA', 'DATA', 'CYMBAL'
        ])

        # 🚀 【STAGE 2: Transform】おなじみのアンパック＆クレンジング
        processed_stream = (
            raw_stream
            | 'CleanAndPair' >> beam.Map(lambda word: (word.strip().upper(), 1))
            | 'AggregatePerWord' >> beam.CombinePerKey(sum)
        )

        # 🚀 【STAGE 3: Output】監査ログの出力
        (
            processed_stream
            | 'FormatLog' >> beam.Map(lambda kv: f"🟢【インフラ統治ライン通過】キー: {kv[0]} | カウント: {kv[1]}")
            | 'FinalOutput' >> beam.Map(print)
        )
    
if __name__ == '__main__':
    # 運用オプションの検証のため、本番同様のシミュレーションを実行！
    print("⚡ Dataflowパイプラインオプション（最大ワーカー数: 3）の監査を開始するのね...")
    run_scaling_governance_pipeline()