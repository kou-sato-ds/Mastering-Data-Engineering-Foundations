import pandas as pd
import numpy as np
from scipy import stats

# 1. データの読み込み（修行用ダミーデータ）
# 実務では train = pd.read_csv('train.csv') になるのね！
data = {
    'feature_a': [10, 12, 11, 13, 100, 11, 12, 11, 13, 12],
    'feature_b': [1, 2, 1, 2, 1, 2, 1, 2, 1, 2]
}
df = pd.DataFrame(data)

# 2. 統計量による「健康診断」
# G検定や統計検定2級でも基本となる「平均・中央値・標準偏差」を一気に確認するのね
print("---Basic Statistics ----")
print(df.describe())

# 3. Z-scoreによる外れ値検知（統計検定2級の範囲なのね！）
# 平均から「標準偏差の何倍離れているか」を計算して、異常値を見つけるのね
z_scores = np.abs(stats.zscore(df['feature_a']))
threshold = 3
outliers = np.where(z_scores > threshold)

print(f"\n--- Outler Detection (Z-score > {threshold}) ---")
print(f"Detected Outlier Indices: {outliers[0]}")
print(f"Outlier Values: {df['feature_a'].iloc[outliers[0]].values}")

# 4. 実務へのブリッジ：外れ値のクリッピング
# 統計的な異常値を、実務上の許容範囲に収める処理なのね
df['feature_a_clipped'] = df['feature_a'].clip(lower=df['feature_a'].quantile(0.05),
                                               upper=df['feature_a'].quantile(0.95))

print("\n---After Clipping ---")
print(df[['feature_a', 'feature_a_clipped']].head(5))