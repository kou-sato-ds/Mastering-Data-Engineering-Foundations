import apache_beam as beam

# 1. 集計用データ構造 (長さ, 単語) へ反転する関数
def prepare_for_groupby_length(kv):
    word, length = kv  
    return (length, word)

# 2. 昨夜のFB回収：GroupByKeyの出力結果を安全にアンパックし、個数をカウントする関数
def count_aggregated_words(length_words_pair):
    # 【超重要】集計結果のペア（Key, Iterable）を受け取った瞬間に命（名前）を吹き込む！
    length, words = length_words_pair  
    
    # wordsの中身（イテレータ）をリストに変換して、その要素数（個数）を安全に算出
    words_list = list(words)
    word_count = len(words_list)
    
    # 最終出力や下流の処理が扱いやすいように、(文字数, 単語数) の新たな結果ペアを返す
    return (length, word_count)

def run_light_pipeline():
    with beam.Pipeline() as p:        

        # モックデータ：(単語, 文字数) のペア
        raw_kv_pairs = p | 'CreateKVPairs' >> beam.Create([
            ('CYMBAL', 6),
            ('ECOM', 4),
            ('DATA', 4),
            ('ENGINEER', 8)
        ])

        # すべての工程からマジックナンバーを追放した集計完了までの DAG チェイン
        (
            raw_kv_pairs
            # 1. (長さ, 単語) にトランスフォーム
            | 'MapToNewKV'       >> beam.Map(prepare_for_groupby_length)
            
            # 2. 同じ文字数（Key）で自動仕分け ➔ 出力型: (長さ, [単語1, 単語2, ...])
            | 'GroupByLength'    >> beam.GroupByKey()
            
            # 3. 昨夜のFB反映：インデックス直書きを卒業し、安全に要素数をカウント
            | 'CountWords'       >> beam.Map(count_aggregated_words)
            
            # 4. 最終ゴールの顔つき確認（ここも名前付き引数で安全にログ出力）
            | 'FinalOutput'      >> beam.Map(lambda res: print(f'【集計完了】文字数 {res[0]} の単語は、合計 {res[1]} 個存在するのね！'))
        )
    
if __name__ == '__main__':
    run_light_pipeline()