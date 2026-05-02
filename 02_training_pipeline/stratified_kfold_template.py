import pandas as pd
from sklearn.model_selection import StratifiedKFold
import lightgbm as lgb

# 1. Read & Feature (ここはお手元のデータに合わせてね)
# 実務（工数分析など）ではここに特徴量生成ロジックが入るのね！
# train = pd.read_csv('train.csv')

# 2. Stratified K-fold Split (層化5分割の設定なのね)
skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

# 3. Training Loop (ここが実装力の見せ所なのね！)
# enumerateは「いま何回目？」を数えるカウンター係なのね
for i, (train_index, valid_index) in enumerate(skf.split(X, y)):
    print(f"Starting Fold {i+1}...")
    
    # 💡 ここにモデルの学習・バリデーション・推論のロジックを肉付けしていくのね！
    # X_train, X_valid = X.iloc[train_index], X.iloc[valid_index]
    # y_train, y_valid = y.iloc[train_index], y.iloc[valid_index]

# 4. Submit
# submission.to_csv('submission_20260502.csv', index=False)