# --- クラウドデータ基盤の「型」を整理する修行 ---

# 1. データレイク (Cloud Storage)
# 特徴：スキーマレス。何でも放り込める放牧場。
data_lake = {
    "concept": "Schema-on-Read",
    "advantage": "低コストで膨大な生データを保存",
    "risk": "管理を怠ると『データスワンプ（泥沼化）』"
}

# 2. データウェアハウス (BigQuery)
# 特徴：構造化データに特化。高速クエリを放つ最強の厩舎。
data_warehouse = {
    "concept": "Schema-on-Write",
    "advantage": "BI分析や高速な集計に最適",
    "limitation": "非構造化データ（画像など）の直接処理は苦手"
}

# 3. データレイクハウス (BigQuery + BigLake)
# 特徴：レイクの柔軟性とDWHの統制を「融合」させた究極の形態。
data_lakehouse = {
    "concept": "Unified Platform",
    "advantage": "データサイロ（情報の分断）を解消し、1つの場所でBIもAIも実行可能",
    "best_practice": "メタデータとガバナンスレイヤを共通化する"
}

# 修行の結論：
# 単なるDWH（BigQuery）だけでは、AI/ML用の生データにアクセスできず、
# 会社のすべてのニーズ（BI+AI）を満たすことはできない。
# だからこそ「レイクハウス」という統合されたアーキテクチャが必要なのね！