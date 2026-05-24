import apache_beam as beam

# 昨夜の極上FB：関数の入り口でタプルに明示的な名前を与える職人の型
def log_with_explicit_names(kv):
    # 1. 入り口で即座にアンパックし、変数に命（意味）を吹き込む！
    word, length = kv  
    
    # 2. 数字（インデックス）を使わず、名前で会話するので可読性が10倍に跳ね上がる
    print(f'【自己文書化】単語: {word} (解析文字数: {length}文字)')
    
    # 3. 下流のコンベアには元の綺麗なKVペアをそのままパススルー
    return kv

def run_light_pipeline():
    with beam.Pipeline() as p:        

        # モックデータ：(単語, 文字数) のKVペア
        raw_kv_pairs = p | 'CreateKVPairs' >> beam.Create([
            ('CYMBAL', 6),
            ('ECOM', 4),
            ('DATA', 4),
            ('ENGINEER', 8)
        ])

        # 完全に自己文書化された関数をチェインに組み込む
        (
            raw_kv_pairs
            # 内部で明示的に名前がついているので、DAGの流れが最高にクリア
            | 'LogWithNames' >> beam.Map(log_with_explicit_names)
            
            # 生存確認：データが壊れずに綺麗に流れてきている証拠の抽出
            | 'ExtractLength' >> beam.Map(lambda kv: kv[1])
            | 'FinalOutput' >> beam.Map(lambda length: print(f'最終ストリーム（長さ）: {length}'))
        )
    
if __name__ == '__main__':
    run_light_pipeline()