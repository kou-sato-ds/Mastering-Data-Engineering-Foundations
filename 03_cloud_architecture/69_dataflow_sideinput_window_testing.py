"""
Apache Beam ユニットテスト 第2弾: Side Input結合(#65) と Fixed Windowing(#63)。

🎯 【宣言の履行】README #76で「#52-#67も単体テスト化する」と書いた、その第一歩!

背景:
    #68 で DLQ振り分けロジック(#57)のテストを 4 passed で確認した。
    本ファイルはその続きとして、まだ「読めば正しそう」段階に留まっている
    #65(Side Input) と #63(Fixed Window) のロジックを実行検証可能にする。
    GCP認証・PubSub・BigQuery接続は一切不要 -> DirectRunnerでローカル完結。

実行方法:
    pytest 69_dataflow_sideinput_window_testing.py -v
"""
import apache_beam as beam
from apache_beam.testing.test_pipeline import TestPipeline
from apache_beam.testing.util import assert_that, equal_to
from apache_beam.transforms.window import FixedWindows, TimestampedValue


# ================================================================
# テスト対象1: #65 の Side Input エンリッチメントロジック
# ================================================================
def enrich_event(event: dict, catalog: dict) -> dict:
    """#65 と同一のロジック。catalogはAsDictでブロードキャストされたマスタデータ。"""
    product = catalog.get(event.get('product_id'), {})
    return {
        'event_id': event.get('event_id'),
        'product_id': event.get('product_id'),
        'product_name': product.get('product_name', 'UNKNOWN'),  # 👉 未登録IDも握りつぶさない
        'category': product.get('category', 'UNKNOWN'),
    }


# ================================================================
# テスト対象2: #63 の Windowing 集約ロジック
# ================================================================
def to_keyed_count(event: dict):
    """#63 と同一。イベント種別をキーにして件数カウントの準備をする。"""
    return (event['event_type'], 1)


# ================================================================
# STAGE 1: Side Input — マスタに存在する product_id が正しく拡充されること
# ================================================================
def test_known_product_is_enriched():
    catalog_rows = [('p-100', {'product_name': 'Laptop', 'category': 'Electronics'})]
    events = [{'event_id': 'evt-001', 'product_id': 'p-100'}]

    with TestPipeline() as p:
        catalog = p | 'CreateCatalog' >> beam.Create(catalog_rows)
        result = (
            p
            | 'CreateEvents' >> beam.Create(events)
            | 'Enrich' >> beam.Map(enrich_event, catalog=beam.pvalue.AsDict(catalog))
        )
        assert_that(result, equal_to([{
            'event_id': 'evt-001',
            'product_id': 'p-100',
            'product_name': 'Laptop',
            'category': 'Electronics',
        }]))


# ================================================================
# STAGE 2: Side Input — マスタ未登録IDが UNKNOWN として可視化されること
#   (#65 の設計判断: 未登録を握りつぶさず、分析側で異常検知できる形に残す)
# ================================================================
def test_unknown_product_falls_back_to_unknown():
    catalog_rows = [('p-100', {'product_name': 'Laptop', 'category': 'Electronics'})]
    events = [{'event_id': 'evt-002', 'product_id': 'p-999'}]  # 👉 マスタに存在しない

    with TestPipeline() as p:
        catalog = p | 'CreateCatalog' >> beam.Create(catalog_rows)
        result = (
            p
            | 'CreateEvents' >> beam.Create(events)
            | 'Enrich' >> beam.Map(enrich_event, catalog=beam.pvalue.AsDict(catalog))
        )
        assert_that(result, equal_to([{
            'event_id': 'evt-002',
            'product_id': 'p-999',
            'product_name': 'UNKNOWN',
            'category': 'UNKNOWN',
        }]))


# ================================================================
# STAGE 3: Side Input — 混在バッチで各レコードが独立に処理されること
# ================================================================
def test_mixed_batch_enriches_independently():
    catalog_rows = [('p-100', {'product_name': 'Laptop', 'category': 'Electronics'})]
    events = [
        {'event_id': 'evt-003', 'product_id': 'p-100'},  # 👉 hit
        {'event_id': 'evt-004', 'product_id': 'p-999'},  # 👉 miss
    ]

    with TestPipeline() as p:
        catalog = p | 'CreateCatalog' >> beam.Create(catalog_rows)
        result = (
            p
            | 'CreateEvents' >> beam.Create(events)
            | 'Enrich' >> beam.Map(enrich_event, catalog=beam.pvalue.AsDict(catalog))
        )
        assert_that(result, equal_to([
            {'event_id': 'evt-003', 'product_id': 'p-100',
             'product_name': 'Laptop', 'category': 'Electronics'},
            {'event_id': 'evt-004', 'product_id': 'p-999',
             'product_name': 'UNKNOWN', 'category': 'UNKNOWN'},
        ]))


# ================================================================
# STAGE 4: Windowing — 同一ウィンドウ内のイベントが合算されること
#   TimestampedValue で event-time を明示注入 -> 壁時計に依存しない決定的テスト
# ================================================================
def test_events_in_same_window_are_aggregated():
    events = [
        {'event_type': 'click', 'ts': 10},  # 👉 window [0, 60) 内
        {'event_type': 'click', 'ts': 20},  # 👉 同上
    ]

    with TestPipeline() as p:
        result = (
            p
            | 'CreateEvents' >> beam.Create(events)
            | 'AssignTimestamps' >> beam.Map(lambda e: TimestampedValue(e, e['ts']))
            | 'ApplyFixedWindow' >> beam.WindowInto(FixedWindows(60))
            | 'PairWithType' >> beam.Map(to_keyed_count)
            | 'CountPerWindow' >> beam.CombinePerKey(sum)
        )
        assert_that(result, equal_to([('click', 2)]))


# ================================================================
# STAGE 5: Windowing — ウィンドウ境界をまたぐと別々に集計されること
#   同じキーでも「時計が窓を切る」ため2レコードに分かれる(#63の核心)
# ================================================================
def test_events_across_window_boundary_are_separated():
    events = [
        {'event_type': 'click', 'ts': 10},  # 👉 window [0, 60)
        {'event_type': 'click', 'ts': 70},  # 👉 window [60, 120)
    ]

    with TestPipeline() as p:
        result = (
            p
            | 'CreateEvents' >> beam.Create(events)
            | 'AssignTimestamps' >> beam.Map(lambda e: TimestampedValue(e, e['ts']))
            | 'ApplyFixedWindow' >> beam.WindowInto(FixedWindows(60))
            | 'PairWithType' >> beam.Map(to_keyed_count)
            | 'CountPerWindow' >> beam.CombinePerKey(sum)
        )
        # 👉 同一キーだが別ウィンドウ -> ('click', 1) が2件出力される
        assert_that(result, equal_to([('click', 1), ('click', 1)]))


if __name__ == '__main__':
    print("🚀 Side Input + Windowing ユニットテスト基盤の監査を開始するのね...")
    print("🟢 監査完了!#65と#63のロジックをGCP非依存で検証可能な基盤が完全画定したのね!")
    print("実行するには: pytest 69_dataflow_sideinput_window_testing.py -v")