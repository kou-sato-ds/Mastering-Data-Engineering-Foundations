import apache_beam as beam
from apache_beam.io.avroio import WriteToAvro

def run_avro_write_pipeline():
    with beam.Pipeline() as p:        

        # 🌟【今夜の主役】JSON文字列で厳密なスキーマ定義をアライン！
        # これが将来のデータ構造変更を安全に統治する「スキーマ進化」の絶対防衛線なのね！
        avro_schema = {
            "type": "record",
            "name": "UserTransaction",
            "namespace": "com.analytics.avro",
            "fields": [
                {"name": "user_id", "type": "long"},
                {"name": "item_name", "type": "string"},
                {"name": "price", "type": "long"}
            ]
        }

        # 🚀 【STAGE 1: Ingestion】生データのインメモリ生成
        raw_records = (
            p | 'CreateRawRecords' >> beam.Create([
                {'user_id': 2001, 'item_name': 'AVRO_CORE', 'price': 85000},
                {'user_id': 2002, 'item_name': 'EVOLUTION_MODULE', 'price': 4200},
            ])
        )

        # 🚀 【STAGE 2: Output】高効率バイナリで行指向バルク書き出し！
        # 拡張子は `.avro` を明示指定し、スキーマを完全に内包したバイナリファイルを生成するのね！
        (
            raw_records
            | 'ExportToAvro' >> WriteToAvro(
                file_path_prefix='output/analytics_avro_lake',
                schema=avro_schema,                         # 👈 ココが鉄壁のAvroスキーマ・ロック！
                file_name_suffix='.avro',
                num_shards=1                                # 検証のため1ファイルに集約
            )
        )
    
if __name__ == '__main__':
    print("⚡ Apache Avro行指向バイナリストレージETLの監査を開始するのね...")
    run_avro_write_pipeline()
    print("🟢 監査完了！スキーマ内包型の超軽量Avroファイルが完全出力されたのね！")