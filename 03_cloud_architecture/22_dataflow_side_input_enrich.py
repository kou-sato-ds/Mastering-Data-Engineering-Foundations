import apache_beam as beam

# 1. サイドインプットを使ってデータを動的に拡充（Enrich）する関数
# 第2引数として、サイドインプットの「マスタ辞書（lang_map）」をスマートに受け取る！
def enrich_word_with_language(kv, lang_map):
    # 入り口ですぐにアンパックして命（名前）を吹き込む！
    word, length = kv  
    
    # 【超重要】サイドインプットとして届いた辞書マスタから、単語に対応する言語名を取得
    # マスタに存在しない場合の防衛策として .get() でデフォルト値 'UNKNOWN' をセットするプロの技！
    language_name = lang_map.get(word, 'UNKNOWN')
    
    # 元の情報（word, length）に、新しい情報（language_name）をガチャンと結合して返す！
    return (word, length, language_name)

def run_enrichment_pipeline():
    with beam.Pipeline() as p:        

        # 🌟 【サイドインプット用の辞書マスタ】別コンベアで「単語 ➔ 言語」の対応マスタを用意
        # PCollectionを辞書型として扱うために、あらかじめ(Key, Value)のペアで作成するのね！
        lang_master_pcoll = p | 'CreateLangMaster' >> beam.Create([
            ('CYMBAL', 'English'),
            ('ENGINEER', 'French_Origin')
        ])

        # 🚀 【メインストリーム】処理対象のデータコンベア
        raw_kv_pairs = p | 'CreateMainData' >> beam.Create([
            ('CYMBAL', 6),
            ('ENGINEER', 8),
            ('UNKNOWN_WORD', 12)  # 🚨 マスタに載っていないデータ（防衛運転のテスト用）
        ])

        # メインコンベアに横から辞書マスタを結合するDAGチェイン
        (
            raw_kv_pairs
            # 【今朝の主役】beam.Mapに、pvalue.AsDict でマスタを「辞書（dict）」として注入！
            | 'EnrichData'   >> beam.Map(
                enrich_word_with_language, 
                lang_map=beam.pvalue.AsDict(lang_master_pcoll)
            )
            
            # 最終ゴールの顔つき確認（マスタの情報が綺麗に結合されているはずなのね！）
            | 'FinalOutput'  >> beam.Map(lambda res: print(f'【データ拡充完了】単語: {res[0]} | 長さ: {res[1]} | 言語属性: {res[2]}'))
        )
    
if __name__ == '__main__':
    run_enrichment_pipeline()