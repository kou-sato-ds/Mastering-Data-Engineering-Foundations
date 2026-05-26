import apache_beam as beam

# 1. 昨夜の伏線回収：集計エンジン（GroupByKey）が認識できるよう、(長さ, 単語) のペアにトランスフォームする関数
def prepare_for_groupby_length(kv):
    word, length = kv  # 入り口で即アンパック（自己文書化）
    
    # 【超重要】集計したい「長さ」を左側（Key）に配置した新しいタプルを創り出す
    return (length, word)

def run_light_pipeline():
    with beam.Pipeline() as p:        

        # モックデータ：(単語, 文字数) のペア
        raw_kv_pairs = p | 'CreateKVPairs' >> beam.Create([
            ('CYMBAL', 6),
            ('ECOM', 4),
            ('DATA', 4),
            ('ENGINEER', 8)
        ])

        # データを並び替えて、同じキー（文字数）で自動仕分けする DAG チェイン
        (
            raw_kv_pairs
            # 1. 集計用のデータ構造 (長さ, 単語) へ反転
            | 'MapToNewKV'    >> beam.Map(prepare_for_groupby_length)
            
            # 2. 【今夜の主役】左側のKey（長さ）が同じ荷物を、自動で1つのリストに集約する
            # 入力: (4, 'ECOM'), (4, 'DATA') ➔ 出力: (4, ['ECOM', 'DATA']) となる！
            | 'GroupByLength' >> beam.GroupByKey()
            
            # 3. 最終ゴールの顔つき確認
            | 'FinalOutput'   >> beam.Map(lambda result: print(f'集計結果 ➔ 文字数 {result[0]}の単語たち: {list(result[1])}'))
        )
    
if __name__ == '__main__':
    run_light_pipeline()