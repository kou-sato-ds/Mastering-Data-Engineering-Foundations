import apache_beam as beam
from apache_beam.io.parquetio import ReadFromParquet

def run_parquet_projection_pipeline():
    with beam.Pipeline() as p:        

        # 🌟 【今朝の主役】ReadFromParquet で columns 引数を使って特定の列だけを指定！
        # これにより、ディスクから不要な列を一切読み込まず、I/O負荷を極限まで削ぎ落とすのね！
        selected_columns = ['user_id', 'price'] # 🚨 今回は 'item_name' を完全に無視してディスクスキャン！

        parquet_stream = (
            p | 'ReadSelectedColumnsOnly' >> ReadFromParquet(
                file_pattern='output/analytics_user_data*.parquet', # 前回書き出したファイルを指定
                columns=selected_columns                            # 👈 ココが鉄壁の投影（Projection）最適化！
            )
        )

        # 🚀 【STAGE 2: Transform】狙い撃ちで読み込んだ列だけで超軽量に集計処理
        # メモリ上には指定した列のデータしか乗らないため、OutOfMemoryを完全に封殺！
        (
            parquet_stream
            | 'FormatAuditLog' >> beam.Map(lambda row: f"📊【投影スキャン通過】ユーザー: {row['user_id']} | 金額: {row['price']}円")
            | 'FinalLogPrint'  >> beam.Map(print)
        )
    
if __name__ == '__main__':
    print("⚡ Apache Parquet投影（Projection）スキャン最適化の監査を開始するのね...")
    run_parquet_projection_pipeline()