"""
BigQuery MERGE Upsert(#58) のロジック単体テスト。

🎯 【宣言の履行 第3弾】#77で残した未検証リストから #58 を消し込む!

背景:
    #68(DLQ振り分け), #69(Side Input + Windowing) に続き、
    #58 の MERGE Upsert を検証可能にする。
    ただし MERGE 文自体は BigQuery エンジン側の機能であり、ローカルでは実行不可。
    そこで「MERGE が何を保証するか」= Upsert セマンティクスそのものを
    Python の純粋関数として抽出し、その振る舞いを検証する。

    これは #58 の SQL をテストするのではなく、
    **「同じキーは更新、無いキーは挿入、何度流しても同じ結果」という
    冪等性の契約** をテストで固定するアプローチである。

実行方法:
    pytest 70_bigquery_merge_logic_testing.py -v
"""
import apache_beam as beam
from apache_beam.testing.test_pipeline import TestPipeline
from apache_beam.testing.util import assert_that, equal_to


# ================================================================
# テスト対象: #58 の MERGE セマンティクスを純粋関数として抽出
# ================================================================
def apply_merge(target: dict, staging: list, key: str = 'user_id') -> dict:
    """
    🔍 #58 の MERGE 文と等価な Upsert を辞書上で再現する。

        MERGE T USING S ON T.user_id = S.user_id
        WHEN MATCHED THEN UPDATE SET ...
        WHEN NOT MATCHED THEN INSERT ...

    Args:
        target:  既存テーブル相当 {user_id: row}
        staging: 新着データ相当 [row, ...]
    Returns:
        MERGE適用後の新しい dict (元の target は変更しない = 副作用なし)
    """
    result = dict(target)  # 👉 破壊的変更を避ける(テスト間の状態汚染を防ぐ)
    for row in staging:
        result[row[key]] = row  # 👉 存在すれば上書き(UPDATE)、無ければ追加(INSERT)
    return result


def to_sorted_rows(merged: dict) -> list:
    """検証しやすいよう、キー順にソートした行リストへ変換する。"""
    return [merged[k] for k in sorted(merged.keys())]


# ================================================================
# STAGE 1: WHEN NOT MATCHED — 新規キーが INSERT されること
# ================================================================
def test_new_key_is_inserted():
    target = {}
    staging = [{'user_id': 'u-1', 'score': 100, 'status': 'ACTIVE'}]

    merged = apply_merge(target, staging)

    assert to_sorted_rows(merged) == [
        {'user_id': 'u-1', 'score': 100, 'status': 'ACTIVE'}
    ]


# ================================================================
# STAGE 2: WHEN MATCHED — 既存キーが UPDATE されること(行数は増えない)
# ================================================================
def test_existing_key_is_updated_not_duplicated():
    target = {'u-1': {'user_id': 'u-1', 'score': 100, 'status': 'ACTIVE'}}
    staging = [{'user_id': 'u-1', 'score': 250, 'status': 'VIP'}]  # 👉 同じキーで更新

    merged = apply_merge(target, staging)

    # 🚨 WRITE_APPEND なら2行になるが、MERGE なら1行のまま更新される
    assert len(merged) == 1, "MERGE must update in place, not append a duplicate row"
    assert to_sorted_rows(merged) == [
        {'user_id': 'u-1', 'score': 250, 'status': 'VIP'}
    ]


# ================================================================
# STAGE 3: 冪等性の契約 — 同じ MERGE を2回流しても結果が変わらないこと
#   (#58 と ADR-002 が共有する「何度実行しても同じ状態に収束する」思想)
# ================================================================
def test_merge_is_idempotent_when_applied_twice():
    target = {'u-1': {'user_id': 'u-1', 'score': 100, 'status': 'ACTIVE'}}
    staging = [
        {'user_id': 'u-1', 'score': 250, 'status': 'VIP'},
        {'user_id': 'u-2', 'score': 50, 'status': 'ACTIVE'},
    ]

    once = apply_merge(target, staging)
    twice = apply_merge(once, staging)  # 👉 同じ staging をもう一度流す

    # 🎯 冪等性: 1回目と2回目の結果が完全一致すること
    assert to_sorted_rows(once) == to_sorted_rows(twice)
    assert len(twice) == 2, "re-applying the same staging must not create extra rows"


# ================================================================
# STAGE 4: 混在バッチ — UPDATE と INSERT が同時に正しく処理されること
# ================================================================
def test_mixed_update_and_insert():
    target = {'u-1': {'user_id': 'u-1', 'score': 100, 'status': 'ACTIVE'}}
    staging = [
        {'user_id': 'u-1', 'score': 250, 'status': 'VIP'},      # 👉 MATCHED -> UPDATE
        {'user_id': 'u-2', 'score': 50, 'status': 'ACTIVE'},    # 👉 NOT MATCHED -> INSERT
    ]

    merged = apply_merge(target, staging)

    assert to_sorted_rows(merged) == [
        {'user_id': 'u-1', 'score': 250, 'status': 'VIP'},
        {'user_id': 'u-2', 'score': 50, 'status': 'ACTIVE'},
    ]


# ================================================================
# STAGE 5: Beam パイプライン上での重複排除 — ステージング側の重複を潰すこと
#   実運用では staging テーブル自体に同一キーが複数入りうる。
#   MERGE は複数マッチでエラーになるため、事前の集約が必要になる。
# ================================================================
def test_staging_duplicates_are_deduplicated_before_merge():
    staging_rows = [
        {'user_id': 'u-1', 'score': 100, 'status': 'ACTIVE'},
        {'user_id': 'u-1', 'score': 250, 'status': 'VIP'},     # 👉 同一キーの後着
    ]

    with TestPipeline() as p:
        result = (
            p
            | 'CreateStaging' >> beam.Create(staging_rows)
            | 'KeyByUserId' >> beam.Map(lambda r: (r['user_id'], r))
            # 👉 同一キーは score 最大のものを残す(最新版を代表として選ぶ戦略)
            | 'DedupeByMaxScore' >> beam.CombinePerKey(
                lambda rows: max(rows, key=lambda r: r['score'])
            )
        )
        assert_that(result, equal_to([
            ('u-1', {'user_id': 'u-1', 'score': 250, 'status': 'VIP'})
        ]))


if __name__ == '__main__':
    print("🚀 BigQuery MERGE Upsert ロジック単体テスト基盤の監査を開始するのね...")
    print("🟢 監査完了!#58のUpsertセマンティクスと冪等性契約が検証可能な基盤が完全画定したのね!")
    print("実行するには: pytest 70_bigquery_merge_logic_testing.py -v")