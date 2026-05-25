import apache_beam as beam

# 1. ログ出力用関数（入り口で即アンパック＆パススルー）
def log_with_explicit_names(kv):
    word, length = kv  
    print(f'【自己文書化】単語: {word} (解析文字数: {length}文字)')
    return kv

# 2. 昨日のFB：抽出用関数（下流のラムダ式のインデックス直書きを卒業する型）
def extract_length_only(kv):
    # ここでも入り口で即バラすことで、マジックナンバー（[1]など）の生存を許さない！
    word, length = kv  
    return length      # 文字数（Value）だけをクリーンに次段へ流す

def run_light_pipeline():
    with beam.Pipeline() as p:        

        # モックデータ：(単語, 文字数) のKVペア
        raw_kv_pairs = p | 'CreateKVPairs' >> beam.Create([
            ('CYMBAL', 6),
            ('ECOM', 4),
            ('DATA', 4),
            ('ENGINEER', 8)
        ])

        # すべての工程が「名前付き関数」で繋がれた、副作用なき強固なチェイン
        (
            raw_kv_pairs
            # ログを出力してそのまま流す
            | 'LogWithNames'   >> beam.Map(log_with_explicit_names)
            
            # 昨日のFB反映：ラムダ式を使わず、関数内で安全に文字数を抽出
            | 'ExtractLength'  >> beam.Map(extract_length_only)
            
            # 最終ゴール
            | 'FinalOutput'    >> beam.Map(lambda length: print(f'最終ストリーム（長さのみ）: {length}'))
        )
    
if __name__ == '__main__':
    run_light_pipeline()