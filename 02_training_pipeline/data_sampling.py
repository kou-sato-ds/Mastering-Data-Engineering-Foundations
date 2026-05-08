import pandas as pd
from sklearn.datasets import make_classification
from imblearn.over_sampling import SMOTE
from collections import Counter

# 1. 修行用データの作成（不均衡なデータのシミュレーション）
# 1000件中、990件が「正常(0)」、10件だけが「異常(1)」という超偏ったデータなのね！
X, y = make_classification(n_samples=1000, n_features=2, n_redundant=0,
                           n_clasters_per_class=1, weights=[0.99],
                           flip_y=0, random_state=1)

print(f"Original dataset shape: {Counter(y)}")

# 2. SMOTEによるオーバーサンプリング
# 少ない方のデータを「点と点の間を埋める」ように新しく作り出す魔法なのね。
sm = SMOTE(random_state=42)
X_res, y_res = sm.fit_resample(X, y)

print(f"Resampled dataset shape: {Counter(y_res)}")

# 3. 実務での注意点：サンプリングのタイミング
# 必ず「訓練データ」だけに適用するのね！
# テストデータまでサンプリングしちゃうと、現実の評価ができなくなる「禁忌」なのね。

# 4. まとめ
# - Undersampling: 大事なデータを捨てるリスクがある
# - Oversampling (SMOTE): 偽物のデータを作るので、過学習に注意が必要