-- --- BigQuery：コスト削減と高速化を両立するプロの最適化コード (修正版) ---

CREATE OR REPLACE TABLE `project_id.gold_zone.optimized_events`
-- 1. パーティショニング：日付でデータを切り分け、スキャン量を激減させる（コスト削減）
-- 修正ポイント: PARTITION (T の後ろは I なのね！)
PARTITION BY DATE(event_timestamp)
-- 2. クラスタリング：よく検索する列でデータを整列させ、応答速度を上げる（高速化）
CLUSTER BY user_id, event_type
AS
SELECT
  event_timestamp,
  user_id,
  event_type,
  event_payload
FROM
  `project_id.silver_zone.raw_events`
WHERE
  event_timestamp >= '2026-01-01';