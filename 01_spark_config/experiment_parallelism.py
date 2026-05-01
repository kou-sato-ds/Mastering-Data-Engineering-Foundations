import time
from pyspark import SparkConf
from pyspark.sql import SparkSession

# 1. 実験設定：ここを '1' と '8' に書き換えて2回実行するのね！
target_cores = "8" 

conf = SparkConf() \
    .setAppName(f"Parallelism-Experiment-Cores-{target_cores}") \
    .setMaster(f"local[{target_cores}]") \
    .set("spark.default.parallelism", str(int(target_cores) * 2)) \
    .set("spark.memory.fraction", "0.6") \
    .set("spark.memory.storageFraction", "0.5")

# 2. セッション開始（この瞬間に上の設定が焼き付けられるのね）
spark = SparkSession.builder.config(conf=conf).getOrCreate()

# 3. 実験用データ（少し重めの処理をさせて差を見るのね）
start_time = time.time()
print(f"--- 実験開始（コア数: {target_cores}） ---")

# 重めの処理：100万個のデータで集計作業をさせるのね
df = spark.range(0, 1000000).withColumnRenamed("id", "num")
result = df.groupBy("num").count().count() 

end_time = time.time()
print(f"実行時間: {end_time - start_time:.2f} 秒")
print(f"--- 実験終了 ---")

spark.stop()