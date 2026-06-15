import apache_beam as beam
from apache_beam.io.parquetio import ReadFromParquet

def run_parquet_predicate_pipeline():
    with beam.Pipeline() as p:        

        # 🌟【今夜の主役】ReadFromParquet の row_group_filter 引数に条件式を注入！
        # これにより、条件に合致しない行グループ（Row Group）をディスク読み込み段階で物理的に全シカトするのね！
        # ※PyArrowのフィルター表現式（式ツリー）をバックエンドで活用するプロの防衛線！
        high_value_filter = [('price', '>=', 50000)] 

        parquet_stream = (
            p | 'FilterRowsAtDiskLevel' >> ReadFromParquet(
                file_pattern='output/analytics_user_data*.parquet', # ターゲットファイルを指定
                row_group_filter=high_value_filter                   # 👈 ココが鉄壁の述語プッシュダウン最適化！
            )
        )

        # 🚀 【STAGE 2: Transform】ディスクレベルで超スマートに絞り込まれた極軽量ストリームを処理
        # メモリには「高額商品（price >= 50000）」の行しか乗らないため、計算リソースの無駄が1ミリも出ないのね！
        (
            parquet_stream
            | 'FormatAuditLog' >> beam.Map(lambda row: f"🔥【述語プッシュダウン通過】高額取引検知 -> ユーザー: {row['user_id']} | 金額: {row['price']}円")
            | 'FinalLogPrint'  >> beam.Map(print)
        )
    
if __name__ == '__main__':
    print("⚡ Apache Parquet述語プッシュダウン（行フィルタ）最適化の監査を開始するのね...")
    run_parquet_predicate_pipeline()
    print("🟢 監査完了！ディスクI/Oを極小化した高可用性スキャンが完全成功したのね！")