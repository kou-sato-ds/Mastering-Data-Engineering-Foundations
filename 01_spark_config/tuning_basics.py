# 参考URL：https://spark.apache.org/docs/latest/tuning.html」

# --- Spark Memory Tuning Training ---
# 1. spark.memory.fraction (Default: 0.6)
#    JVMヒープから300MiBを差し引いた後の、Sparkが計算(Execution)と保存(Storage)に使える割合。
#    残りの40%はユーザーのデータ構造やメタデータ、OOM防止用に予約されているのね。
conf.set("spark.memory.fraction", "0.6")

# 2. spark.memory.storageFraction (Default: 0.5)
#    上記で確保したエリア(M)のうち、どれだけを「キャッシュ聖域(R)」にするかの割合。
#    0.6(M) * 0.5 = 実質全体の30%が、計算処理に追い出されない保存領域になるのね。
conf.set("spark.memory.storageFraction", "0.5")


# [写経] Determining Memory Consumption
# 公式ドキュメントの「推測ツール」を実装する

from pyspark.sql import SparkSession

# SparkContextの取得
spark = SparkSession.builder.getOrCreate()
sc = spark.sparkContext

# 推測したいオブジェクト（例：巨大なリストや辞書など）
your_object = [i for i in range(10000)]

# SizeEstimatorを使用して、JVM上でのメモリ消費量（バイト単位）を推測
# ※ org.apache.spark.util.SizeEstimator を呼び出すのね
size_bytes = sc._jvm.org.apache.spark.util.SizeEstimator.estimate(your_object)

print(f"オブジェクトの推定メモリ消費量: {size_bytes / 1024 / 1024:.2f} MB")

# [写経] Level of Parallelism & Performance Tuning
# 公式ドキュメント：1コアあたり2-3タスクの並列度を推奨

from pyspark import SparkConf

conf = SparkConf()

# サトウコウさんの理解：コア数(作業員)に比例して袋(タスク)を増やす
# 例：ローカルPCが4コアの場合
num_cores = 4
parallelism = num_cores * 2  # 8タスク
conf.set("spark.default.parallelism", str(parallelism))

# 【実務への応用メモ：工数分析の場合】
# 1. 入力パスの並列化 (spark.hadoop.mapreduce.input.fileinputformat.list-status.num-threads)
#    工数データが大量のフォルダ（日付別など）に分かれている場合、
#    この値を増やすことで「どこにデータがあるか探す」時間を短縮できる。
conf.set("spark.hadoop.mapreduce.input.fileinputformat.list-status.num-threads", "10")

# 2. Reduce Tasksのメモリ問題解決
#    「データがメモリに乗らない」のではなく「ハッシュテーブル（集計作業台）が溢れる」場合、
#    並列度をさらに上げることで、1タスクあたりの作業量を小さくし、エラーを回避する。