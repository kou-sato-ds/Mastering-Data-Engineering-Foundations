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
    
    # 💡 実装の肉付けイメージ
    dtrain = lgb.Dataset(X.iloc[train_index], label=y.iloc[train_index])
    dvalid = lgb.Dataset(X.iloc[valid_index], label=y.iloc[valid_index])

    params = {
        'objective': 'binary',
        'metric': 'auc',
        'verbosity': -1,
        'boosting_type': 'gbdt',
        'random_state': 42
    }

    model = lgb.train(params, dtrain, valid_sets=[dtrain, dvalid])

# 4. Submit
# submission.to_csv('submission_20260502.csv', index=False)