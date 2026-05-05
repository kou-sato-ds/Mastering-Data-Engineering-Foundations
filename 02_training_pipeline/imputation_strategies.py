import pandas as pd
import numpy as np

# 1. 欠損値を含む修行用データの作成
# 実務では現場から届くデータは穴だらけ（欠損だらけ）なのが日常茶飯事なのね！
data = {
    'income': [500, 600, np.nan, 800, 550, 10000, 620, np.nan], # 10000は外れ値
    'department': ['IT', 'IT', 'Sales', 'Sales', 'IT', 'Sales', 'IT', 'Sales']
}
df = pd.DataFrame(data)

# 2. 単純な平均値埋め（統計検定2級でも出てくる基本）
# 外れ値（10000）に引きずられて、平均が実態より高くなってしまう罠があるのね
mean_val = df['income'].mean()
df['income_mean'] = df['income'].fillna(mean_val)

# 3. 中央値埋め（実務でよく使われる堅実な手法）
# 外れ値の影響を受けにくい「頑健（ロバスト）」な統計量なのね
median_val = df['income'].median()
df['income_median'] = df['income'].fillna(median_val)

# 4. グループ別の中央値埋め（より実務的で高度な「型」）
# IT部ならIT部の、営業なら営業の中央値で埋める、納得感の高い方法なのね
df['income_group_median'] = df.groupby('department')['income'].transform(
    lambda x: x.fillna(x.median())
)

print("--- Imputation Results ---")
print(df[['department', 'income', 'income_mean', 'income_median', 'income_group_median']])

# 5. 統計的な確認
print("\n--- Summary Statistics Comparison ---")
print(f"Original Mean (w/ nan): {df['income'].mean():.2f}")
print(f"Mean Imputed Mean: {df['income_mean'].mean():.2f}")
print(f"Group Median Imputed Mean: {df['income_group_median'].mean():.2f}")