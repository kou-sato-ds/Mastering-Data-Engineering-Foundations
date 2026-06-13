import apache_beam as beam
from apache_beam.io.parquetio import WriteToParquet
import pyarrow as pa

def run_parquet_export_pipeline():
    # 🌟【新章の主役】Parquetファイルに埋め込む「厳密なスキーマ（型情報）」をPyArrowで定義！
    # これにより、CSVのような「インポート時の型崩れ」を100%未然に封殺するのね！
    parquet_schema = pa.schema([
        ('user_id', pa.int64()),     # ユーザーIDは堅牢な64bit整数型
        ('item_name', pa.string()),  # 商品名は文字列型
        ('price', pa.int64())        # 金額も整数型として厳密に固定！
    ])

    with beam.Pipeline() as p:        

        # 🚀 【STAGE 1: Ingestion】生データのインメモリ生成
        raw_records = p | 'CreateRawRecords' >> beam.Create([
            {'user_id': 1001, 'item_name': 'CYMBAL_MODULE', 'price': 50000},
            {'user_id': 1002, 'item_name': 'ENGINEER_CAP', 'price': 3500},
            {'user_id': 1003, 'item_name': 'DATA_CABLE', 'price': 1200}
        ])

        # 🚀 【STAGE 2: Transform】辞書型データを、Parquet書き出しに適した形にアライン
        # （実務でのクンジングやバリデーション層を想定）
        formatted_records = raw_records | 'ValidateAndFormat' >> beam.Map(lambda x: x)

        # 🌟 【本日の防衛線】列指向フォーマット「Apache Parquet」としてバルク書き出し！
        # これにより、データの容量を極限まで圧縮し、S3やGCSのストレージコストを極小化するのね！
        (
            formatted_records
            | 'ExportToParquet' >> WriteToParquet(
                file_path_prefix='output/analytics_user_data', # 出力先パスと接頭辞
                schema=parquet_schema,                         # 👈 事前に定義した厳密なスキーマを注入！
                file_name_suffix='.parquet',                   # 拡張子を明示的に指定
                num_shards=1                                   # 今回は検証のため1ファイルに集約
            )
        )
    
if __name__ == '__main__':
    print("⚡ Apache Parquet（列指向・超高圧縮）バルクETLパイプラインの監査を開始するのね...")
    run_parquet_export_pipeline()
    print("🟢 監査完了！output/ フォルダ配下に厳密なスキーマを持つParquetファイルが生成されたのね！")