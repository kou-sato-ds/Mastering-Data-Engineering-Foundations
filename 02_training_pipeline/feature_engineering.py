import pandas as pd
import numpy as np
from sklearn.preprocessing import PolynomialFeatures

# 1. 修行用データの作成
data = {
    'experience_years': [1, 2, 3, 4, 5, 6],
    'skill_score': [10, 20, 30, 40, 50, 60]
}
df = pd.DataFrame(data)

# 2. 交互作用項の作成（融合召喚！）
# 「経験年数」と「スキル」の相乗効果（掛け算）を新しい特徴量として生み出すのね。
poly = PolynomialFeatures(degree=2, interaction_only=True, include_bias=False)
poly_features = poly.fit_transform(df)

# カラム名を付けてデータフレーム化
df_poly = pd.DataFrame(poly_features, columns=['years', 'skill', 'years_x_skill'])

# 3. ビニング（離散化：レベル分け）
# 細かい数値を「初心者(0)」「中堅(1)」「達人(2)」というランクに変えるのね。
df_poly['skill_level'] = pd.cut(df_poly['skill'], bins=[0, 25, 45, 100], labels=[0, 1, 2])

print("--- Feature Engineering Results ---")
print(df_poly)

# 4. 実務での注意点：次元の呪い
# 掛け算を増やしすぎると、カードが多すぎてデッキが回らなくなる（計算が終わらない・過学習する）のね。
# 「意味のある組み合わせ」をドメイン知識で選ぶのが、DEの腕の見せ所なのね！