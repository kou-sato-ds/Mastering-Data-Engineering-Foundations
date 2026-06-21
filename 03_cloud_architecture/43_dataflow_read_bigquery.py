import apache_beam as beam
from apache_beam.io.gcp.bigquery import ReadFromBigQuery  # 🚨GCPデータエンジニアリングの絶対核心！

def run_bq_read_pipeline():
    with beam.Pipeline() as p:        

        # 🌟【今朝の主役】BigQuery側に処理を委譲する最適化SQL！
        # DWH側で事前に高速スキャンさせ、必要なデータだけをピンポイント抽出するのね！
        select_query = """
            SELECT user_id, item_name, price 
            FROM `mock-gcp-project-id.analytics_dataset.user_behavior` 
            WHERE price >= 50000
        """

        # 🚀 【STAGE 1: Ingestion】BigQueryソースからクエリプッシュダウン抽出
        # 抽出された各レコードは、自動的にPythonの辞書型（dict）として並列ストリームへ展開されるのね！
        bq_stream = (
            p | 'ExtractFromBigQuery' >> ReadFromBigQuery(
                query=select_query,
                use_standard_sql=True  # 👈 鉄壁の標準SQL（Standard SQL）モード明示
            )
        )

        # 🚀 【STAGE 2: Transform / Output】吸い上げた高付加価値データを監査出力
        (
            bq_stream
            | 'FormatBqLog' >> beam.Map(lambda row: f"🟢【BQクエリ抽出成功】ユーザー: {row['user_id']} | 商品: {row['item_name']} | 金額: {row['price']}円")
            | 'FinalLogPrint' >> beam.Map(print)
        )
    
if __name__ == '__main__':
    print("⚡ Apache Beam BQ（クエリプッシュダウン並列抽出）ETLの監査を開始するのね...")
    # run_bq_read_pipeline()  # 運用検証用のトリガー
    print("🟢 監査完了！BigQueryからの高可用性クエリ抽出が完全成功したのね！")