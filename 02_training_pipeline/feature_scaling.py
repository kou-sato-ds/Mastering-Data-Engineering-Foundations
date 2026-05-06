import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler, MinMaxScaler

# 1. 修行用データの作成（単位がバラバラなデータ）
# income(給与)は数千、age(年齢)は数十。このままだとAIが「数字が大きい方」を過大評価しちゃうのね！
data = {
    'income': [300, 400, 500, 800, 1200, 450, 550, 600],
    'age': [25, 30, 35, 40, 45, 28, 32, 38]
}
df = pd.DataFrame(data)

# 2. 標準化 (Standardization / Z-score Normalization)
# 統計検定2級の目玉！「平均 0, 標準偏差 1」に変換するのね。
# 外れ値がある程度あっても、データの「相対的な位置」を保つのに強いのね。
scaler_std = StandardScaler()
df['income_std'] = scaler_std.fit_transform(df[['income']])

# 3. 正規化 (Normalization / Min-Max Scaling)
# データを「0 から 1」の間にギュッと閉じ込めるのね。
# 画像処理や、データの範囲を厳格に決めたい時に使う「型」なのね。
scaler_minmax = MinMaxScaler()
df['income_minmax'] = scaler_minmax.fit_transform(df[['income']])

# 4. 実務での注意点：テストデータへの適用
# 訓練データで「物差し(fit)」を作り、テストデータは「当てる(transform)」だけ！
# これを混ぜると「データリーク」という大惨事になるのね。
test_data = pd.DataFrame({'income': [700]})
test_scaled = scaler_std.transform(test_data[['income']]) # fitはしない！

print("--- Scaling Results ---")
print(df.head())

print("\n--- Summary Statistics after Standardization ---")
print(f"Mean: {df['income_std'].mean():.1f}")  # ほぼ 0 になるはず
print(f"Std:  {df['income_std'].std():.1f}")   # ほぼ 1 になるはず