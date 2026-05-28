import apache_beam as beam

# 1. フィルタリング用関数（条件に合うものだけを True で通す関門の型）
def filter_long_words_only(kv):
    # 入り口で即アンパック（マジックナンバーの生存を許さない！）
    word, length = kv  
    
    # 条件式：文字数が4文字より大きい（5文字以上）データだけをTrueとして通過させる
    # Trueを返した要素だけが次のコンベアへ進み、Falseの要素はここで安全に破棄されるのね！
    return length > 4

def run_light_pipeline():
    with beam.Pipeline() as p:        

        # モックデータ：(単語, 文字数) のペア
        raw_kv_pairs = p | 'CreateKVPairs' >> beam.Create([
            ('CYMBAL', 6),
            ('ECOM', 4),
            ('DATA', 4),
            ('ENGINEER', 8)
        ])

        # 条件に合う綺麗なデータだけを抽出する DAG チェイン
        (
            raw_kv_pairs
            # 【今夜の主役】beam.Filter に名前付き関数をガチッとハメ込む！
            | 'FilterShortWords' >> beam.Filter(filter_long_words_only)
            
            # 最終ゴールの顔つき確認（4文字以下の ECOM と DATA は消滅しているはず！）
            | 'FinalOutput'     >> beam.Map(lambda res: print(f'【検疫通過】5文字以上のエリートデータ: {res[0]} ({res[1]}文字)'))
        )
    
if __name__ == '__main__':
    run_light_pipeline()