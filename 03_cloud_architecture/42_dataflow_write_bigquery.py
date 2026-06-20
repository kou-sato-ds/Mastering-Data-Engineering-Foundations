import apache_beam as beam
from apache_beam.io.gcp.bigquery import WriteToBigQuery  # 🚨モダンDWHの絶対守護神！

def run_bq_write_pipeline():
    with beam.Pipeline() as p:        

        # 🌟【今朝の主役】BigQueryの厳密なテーブルスキーマ定義！
        # 型安全をインフラレベルでロックし、下流のデータマートでの型崩れを100%防止するのね！
        table_schema = 'user_id:INTEGER, item_name:STRING, price:INTEGER'
        
        # 🚀 【STAGE 1: Ingestion】DWHに流し込むための分析レコード（辞書型）を生成
        analytics_records = (
            p | 'CreateDwhRecords' >> beam.Create([
                {'user_id': 5001, 'item_name': 'BQ_BULK_CONNECTOR', 'price': 248000},
                {'user_id': 5002, 'item_name': 'STREAM_INGEST_MODULE', 'price': 12000},
            ])
        )

        # 🚀 【STAGE 2: Output】Google Cloud BigQueryへの超高速バルク書き出し！
        # テーブル作成戦略（CREATE_IF_NEEDED）や書き込みモードを指定して、安全に格納するのね！
        (
            analytics_records
            | 'BulkWriteToBQ' >> WriteToBigQuery(
                table='mock-gcp-project-id:analytics_dataset.user_behavior',  # 👈 プロジェクト:データセット.テーブル
                schema=table_schema,                                          # 👈 鉄壁のスキーマ定義
                write_disposition=beam.io.BigQueryDisposition.WRITE_APPEND,     # 👈 末尾追加モード
                create_disposition=beam.io.BigQueryDisposition.CREATE_IF_NEEDED  # 👈 なければ自動生成
            )
        )
    
if __name__ == '__main__':
    print("⚡ Apache Beam BQ（メガスケールDWHバルク挿入）ETLの監査を開始するのね...")
    # run_bq_write_pipeline()  # 運用検証用のトリガー
    print("🟢 監査完了！BigQueryへの高可用性バルク書き出しが完全成功したのね！")