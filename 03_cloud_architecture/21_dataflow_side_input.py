import apache_beam as beam

# 1. サイドインプットを受け取る検疫関数
# 引数の第2属性として、メインコンベアのデータの横に「外部マスタ（bad_words）」を並べて受け取る！
def filter_with_master_list(kv, bad_words):
    # メインのデータは入り口ですぐにアンパックして命（名前）を吹き込む！
    word, length = kv  
    
    # 【超重要】サイドインプットとして届いたNGワードマスタ（bad_words）の中に、
    # 今流れてきた単語が含まれているかを動的にチェックする（ブラックリスト判定）
    is_bad_word = word in bad_words
    
    # NGワードリストに含まれて「いない（not）」クリーンなデータだけを下流に通すのね！
    return not is_bad_word

def run_side_input_pipeline():
    with beam.Pipeline() as p:        

        # 🌟 【サイドインプット用のマスタデータ】別コンベアで「NGワードリスト」を用意する
        bad_words_pcoll = p | 'CreateBadWords' >> beam.Create([
            'ECOM', 
            'SPAM_DATA'
        ])

        # 🚀 【メインストリーム】処理対象のデータコンベア
        raw_kv_pairs = p | 'CreateMainData' >> beam.Create([
            ('CYMBAL', 6),
            ('ECOM', 4),         # 🚨 NGワードマスタに載っているので弾かれるはず！
            ('ENGINEER', 8)
        ])

        # メインコンベアに横からマスタを合流させるDAGチェイン
        (
            raw_kv_pairs
            # 【今朝の主役】beam.Filterに、pvalue.AsSet でマスタをセット（Side Input）として注入！
            | 'FilterByMaster' >> beam.Filter(
                filter_with_master_list, 
                bad_words=beam.pvalue.AsSet(bad_words_pcoll)
            )
            
            # 最終ゴールの顔つき確認（マスタに記載されていた ECOM は綺麗に消滅しているのね！）
            | 'FinalOutput'    >> beam.Map(lambda res: print(f'【マスタ検疫通過】安全が確認されたデータ: {res[0]}'))
        )
    
if __name__ == '__main__':
    run_side_input_pipeline()