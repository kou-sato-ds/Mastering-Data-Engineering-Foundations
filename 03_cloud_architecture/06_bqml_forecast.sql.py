-- --- BQML：SQLだけで機械学習モデルを爆誕させる型 ---

CREATE OR REPLACE MODEL `gold_zone.user_behavior_model`
OPTIONS(model_type='linear_reg') AS
SELECT
  label_user_conversion, -- 予測したいターゲット（例：成約するか？）
  feature_access_count,  # 特徴量1：アクセス回数
  feature_stay_duration  # 特徴量2：滞在時間
FROM
  `project_id.gold_zone.refined_user_logs`
WHERE
  data_split = 'TRAIN';

-- 💡 DE軍師の補足：
-- Pythonを1行も書かずに、使い慣れたSQLだけでMLモデルが作れる。
-- これが「レイクハウス」の真骨頂。DEが作った『Gold Zone』が
-- 直接ビジネス価値を生む瞬間なのね！