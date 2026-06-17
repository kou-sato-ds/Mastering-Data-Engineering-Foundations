import apache_beam as beam
from apache_beam.io.avroio import ReadFromAvro

def run_avro_read_pipeline():
    with beam.Pipeline() as p:        

        # 🌟【今夜の主役】ReadFromAvro はファイルの表紙からスキーマを自動解読！
        # 開発者が事前にスキーマを定義しなくても、バイナリから完璧に型を復元するのね！
        avro_stream = (
            p | 'ReadBinaryAvroLake' >> ReadFromAvro(
                file_pattern='output/analytics_avro_lake*.avro' # ターゲットファイルを指定
            )
        )

        # 🚀 【STAGE 2: Transform / Output】自動デコードされた綺麗なデータを監査出力
        # メモリ上ではすでに完全にPythonの辞書型（dict）に復元されているため、即座に安全にアクセス可能！
        (
            avro_stream
            | 'FormatAuditLog' >> beam.Map(lambda row: f"🟢【Avro逆シリアライズ成功】ユーザー: {row['user_id']} | アイテム: {row['item_name']} | 金額: {row['price']}円")
            | 'FinalLogPrint'  >> beam.Map(print)
        )
    
if __name__ == '__main__':
    print("⚡ Apache Avro行指向バイナリストレージ読み込みの監査を開始するのね...")
    run_avro_read_pipeline()
    print("🟢 監査完了！スキーマ自動デコードによる高可用性スキャンが完全成功したのね！")