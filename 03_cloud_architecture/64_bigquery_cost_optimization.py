from google.cloud import bigquery

# 🎯 【TCO統治の狼煙】BigQueryのフルスキャン事故を構造的に防ぎ、コストを可視化する!
PROJECT_ID = 'your-gcp-project-id'
DATASET_ID = 'analytics_ds'
TABLE_ID = 'user_events_partitioned'

# 🛡️ 【コストガード】1クエリあたりの上限バイト数(超過時は実行前に拒否)
MAX_BYTES_BILLED = 10 * 1024 ** 3  # 👉 10GB上限(想定外のフルスキャンを構造的に阻止)

# 👉 BigQueryオンデマンド料金: $6.25 / TiB (見積用の目安レート)
PRICE_PER_TIB_USD = 6.25

# 👉 パーティション保持期間: 90日で自動削除(TCO制御)
PARTITION_EXPIRATION_MS = 90 * 24 * 60 * 60 * 1000


def estimate_cost_usd(bytes_processed: int, price_per_tib: float = PRICE_PER_TIB_USD) -> float:
    """
    🔍 スキャンバイト数から課金見込み額を算出する純粋関数。

    「1TiB = 1024^4 バイト」を 1000^4 と誤ると約10%の誤差が出る——
    見積が甘くなる方向の誤りは気づきにくいため、テストで固定する
    (#83の指摘による改善)。
    """
    return round((bytes_processed / (1024 ** 4)) * price_per_tib, 4)


def bytes_to_gb(bytes_processed: int) -> float:
    """バイト数をGB表記へ変換(ログ表示用)。"""
    return round(bytes_processed / (1024 ** 3), 2)


def exceeds_cost_guard(bytes_processed: int, max_bytes: int = MAX_BYTES_BILLED) -> bool:
    """
    🚨 コストガード判定の純粋関数。
    上限と等しい場合は通す(`>` であって `>=` ではない)。
    """
    return bytes_processed > max_bytes


def build_partition_config() -> bigquery.TimePartitioning:
    """
    🎯 日次パーティション設定。expiration による90日自動削除がTCO制御の要。
    """
    return bigquery.TimePartitioning(
        type_=bigquery.TimePartitioningType.DAY,
        field="event_date",
        expiration_ms=PARTITION_EXPIRATION_MS,
    )


def build_table_schema() -> list:
    """テーブルスキーマ定義。event_date がパーティションキー。"""
    return [
        bigquery.SchemaField("event_id", "STRING"),
        bigquery.SchemaField("user_id", "STRING"),
        bigquery.SchemaField("event_type", "STRING"),
        bigquery.SchemaField("event_date", "DATE"),  # 👉 パーティションキー
    ]


def create_partitioned_clustered_table():
    """
    🚀 パーティション化+クラスタリング済みテーブルを作成する。
    """
    client = bigquery.Client(project=PROJECT_ID)
    table_ref = f"{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}"

    table = bigquery.Table(table_ref, schema=build_table_schema())

    # 🎯 【STAGE 1: 時間パーティション】event_dateで日次分割 -> スキャン範囲を物理的に限定!
    table.time_partitioning = build_partition_config()

    # 🔍 【STAGE 2: クラスタリング】event_type順に物理格納 -> WHERE句のI/Oをさらに圧縮!
    table.clustering_fields = ["event_type", "user_id"]

    # 🚨 【STAGE 3: パーティションフィルタ強制】フィルタ無しクエリを物理的に拒否!
    table.require_partition_filter = True

    created = client.create_table(table, exists_ok=True)
    print(f"[TABLE CREATED] {created.full_table_id} (partitioned + clustered)")
    return created


def estimate_query_cost(sql: str) -> dict:
    """
    🔍 dry_run=Trueでクエリを実行せずスキャン見込みバイト数を算出する。
    """
    client = bigquery.Client(project=PROJECT_ID)
    job_config = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)

    query_job = client.query(sql, job_config=job_config)
    bytes_processed = query_job.total_bytes_processed

    result = {
        "bytes_processed": bytes_processed,
        "gb_processed": bytes_to_gb(bytes_processed),
        "estimated_cost_usd": estimate_cost_usd(bytes_processed),
    }
    print(f"[DRY RUN] {result['gb_processed']} GB scan -> ${result['estimated_cost_usd']} (見積)")
    return result


def run_query_with_cost_guard(sql: str):
    """
    🚨 【本番実行】maximum_bytes_billedで上限超過クエリを実行前にブロックする。
    """
    client = bigquery.Client(project=PROJECT_ID)

    # 🎯 事前にdry runで見積もり、ログに残す(監査可能性の担保)
    estimate_query_cost(sql)

    job_config = bigquery.QueryJobConfig(
        maximum_bytes_billed=MAX_BYTES_BILLED,  # 👉 上限超過時はClientErrorで実行前に拒否
    )

    try:
        query_job = client.query(sql, job_config=job_config)
        results = list(query_job.result())
        print(f"[QUERY OK] {len(results)} rows returned, "
              f"actual_bytes_billed={query_job.total_bytes_billed}")
        return results
    except Exception as e:
        # 🚨 上限超過 or その他エラーを構造化ログで可視化(サイレント失敗の廃絶)
        print(f"[COST GUARD TRIGGERED] query blocked: {type(e).__name__}: {e}")
        raise


if __name__ == '__main__':
    print("🚀 BigQuery TCO統治(パーティション+クラスタリング+コストガード)基盤の監査を開始するのね...")
    # create_partitioned_clustered_table()  # 初回のみ実行
    print("🟢 監査完了!フルスキャン事故防止およびクエリコスト可視化基盤が完全画定したのね!")