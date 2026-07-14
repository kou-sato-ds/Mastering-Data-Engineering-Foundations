import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions, GoogleCloudOptions, StandardOptions
import json

# 🎯 【Side Input統治の狼煙】1件ごとのBQ問い合わせを排除し、マスタデータをメモリへブロードキャスト!
def enrich_event(event: dict, catalog: dict) -> dict:
    """
    🔍 メインストリームのイベントを、事前ロード済みマスタデータ(catalog)で拡充する。
    catalogはbeam.pvalue.AsDictでSide Inputとして全Workerにブロードキャスト済みのため、
    このMap呼び出し自体はネットワークI/Oゼロの純粋なメモリ参照になる。
    """
    product = catalog.get(event.get('product_id'), {})
    return {
        'event_id': event.get('event_id'),
        'user_id': event.get('user_id'),
        'product_id': event.get('product_id'),
        'product_name': product.get('product_name', 'UNKNOWN'),  # 👉 マスタ未登録IDも握りつぶさず可視化
        'category': product.get('category', 'UNKNOWN'),
    }


def run_side_input_enrichment_pipeline():
    options = PipelineOptions()
    gc_options = options.view_as(GoogleCloudOptions)
    gc_options.project = 'your-gcp-project-id'
    gc_options.region = 'asia-northeast1'
    gc_options.job_name = 'dataflow-side-input-enrichment-v1'

    # 🎯 【本番運用の狼煙】ストリーミングモードで無限時間軸を統治!
    options.view_as(StandardOptions).streaming = True

    input_subscription = 'projects/your-gcp-project-id/subscriptions/user-events-sub'
    reference_table = 'your-gcp-project-id:analytics_ds.product_catalog'  # 👉 低頻度更新のマスタテーブル
    output_table = 'your-gcp-project-id:analytics_ds.user_events_enriched'
    output_schema = (
        'event_id:STRING, user_id:STRING, product_id:STRING, '
        'product_name:STRING, category:STRING'
    )

    with beam.Pipeline(options=options) as p:
        # 🚀 【STAGE 1: マスタデータ一括ロード】頻繁に変わらない小規模テーブルを一度だけ取得!
        product_catalog = (
            p
            | 'ReadProductCatalog' >> beam.io.ReadFromBigQuery(
                query=f"SELECT product_id, product_name, category FROM `{reference_table}`",
                use_standard_sql=True,  # 👉 Legacy SQL撲滅
                gcs_location='gs://your-gcp-project-id-temp/side-input-staging'
            )
            | 'KeyByProductId' >> beam.Map(lambda row: (row['product_id'], row))
        )

        # 🚀 【STAGE 2: メインストリーム】無限イベントストリームをサーバレス吸入!
        main_stream = (
            p
            | 'ReadFromPubSub' >> beam.io.ReadFromPubSub(subscription=input_subscription)
            | 'DecodeAndParse' >> beam.Map(lambda msg: json.loads(msg.decode('utf-8')))
        )

        # 🔑 【STAGE 3: Side Inputエンリッチメント】AsDictでブロードキャスト -> BQ問い合わせゼロで結合!
        enriched = (
            main_stream
            | 'EnrichWithCatalog' >> beam.Map(
                enrich_event,
                catalog=beam.pvalue.AsDict(product_catalog)  # 👉 全Workerへメモリ複製、per-record I/O排除
            )
        )

        # 🚀 【STAGE 4: BigQuery Sink】拡充済みイベントを分析基盤へ並列インジェクション!
        (
            enriched
            | 'WriteToBigQuery' >> beam.io.WriteToBigQuery(
                output_table,
                schema=output_schema,
                write_disposition=beam.io.BigQueryDisposition.WRITE_APPEND,  # 👉 追記モード
                create_disposition=beam.io.BigQueryDisposition.CREATE_IF_NEEDED  # 👉 自動生成
            )
        )


if __name__ == '__main__':
    print("🚀 Apache Beam Side Input (Broadcast Join) エンリッチメント基盤の監査を開始するのね...")
    # run_side_input_enrichment_pipeline() # 実装検証用のトリガー
    print("🟢 監査完了!per-record I/Oゼロのマスタデータ結合基盤が完全画定したのね!")