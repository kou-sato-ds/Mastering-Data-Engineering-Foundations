import pandas as pd
from sklearn.preprocessing import LabelEncoder

# 1. 修行用データの作成（部署名などのカテゴリデータ）
data = {
    'department': ['IT', 'Sales', 'HR', 'IT', 'Sales', 'HR'],
    'rank': ['Junior', 'Senior', 'Manager', 'Junior', 'Manager', 'Senior'] # 順序があるデータ
}
df = pd.DataFrame(data)

# 2. One-Hot Encoding（順序がないデータに最適）
# 各部署を独立したカラムにするのね。「多重共線性」を防ぐために drop_first=True を使うのが実務の型！
df_onehot = pd.get_dummies(df, columns=['department'], drop_first=True, dtype=int)

# 3. Label Encoding（ターゲット変数や、アルゴリズムによって使う手法）
le = LabelEncoder()
df_onehot['rank_label'] = le.fit_transform(df['rank'])

# 4. Ordinal Encoding（順序に意味がある場合：手動マッピング）
# 「Junior < Senior < Manager」というランクの重みを数字に込めるのね
rank_map = {'Junior': 0, 'Senior': 1, 'Manager': 2}
df_onehot['rank_ordinal'] = df['rank'].map(rank_map)

print("--- Encoding Results ---")
print(df_onehot)

# 5. 実務の知恵：なぜ One-Hot で drop_first を使うのか？
# 「IT」と「Sales」が決まれば、自動的に「HR」かどうかが決まるから、
# 1つ列を消すことでAIの計算（行列計算）を安定させる「引き算の美学」なのね。