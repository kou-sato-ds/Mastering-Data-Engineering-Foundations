import apache_beam as beam

# 1. CoGroupByKeyで結合された複雑な構造を安全にアンパックして処理する関数
def joiined_data_processor(grouped_element):
    # CoGroupByKeyの出力は (Key, 辞書) の形で届くので、入り口ですぐにアンパック！
    word, grouped_dict = grouped_element
    
    # 🚨 辞書の中身は「リスト」形式で入っているため、安全に1件目を取り出す防衛運転！
    # 万が一マスタが欠落していた場合のフォールバック（デフォルト値）も .get() で徹底防御！
    lengths_list = grouped_dict.get('lengths', [])
    languages_list = grouped_dict.get('languages', [])
    
    length = lengths_list[0] if lengths_list else 0
    language = languages_list[0] if languages_list else 'UNKNOWN'
    
    # 命（名前）を吹き込んだ変数たちを美しくフォーマットして出力
    return f"【紐付け完了】単語: {word} | 長さ: {length} | 言語: {language}"

def run_cogroupbykey_pipeline():
    with beam.Pipeline() as p:        

        # 🚀 【コンベアA】単語 ➔ 文字数のストリーム
        stream_lengths = p | 'CreateLengths' >> beam.Create([
            ('CYMBAL', 6),
            ('ENGINEER', 8),
            ('DATA', 4)
        ])

        # 🚀 【コンベアB】単語 ➔ 言語のストリーム
        stream_languages = p | 'CreateLanguages' >> beam.Create([
            ('CYMBAL', 'English'),
            ('ENGINEER', 'French_Origin'),
            ('PIPELINE', 'English') # 🚨 コンベアAには存在しない単語（紐付け漏れの防衛テスト用）
        ])

        # 🌟 【完全修正】2つの別々のコンベアを正しくマッピングして CoGroupByKey で結合！
        grouped_stream = (
            {
                'lengths': stream_lengths, 
                'languages': stream_languages  # ⭕ stream_languages を正しく指定！
            }
            | 'CoGroupByKey' >> beam.CoGroupByKey()
        )

        # 3. 結合されたコンベアから、データを回収して最終出力
        (
            grouped_stream
            | 'ProcessJoined' >> beam.Map(joiined_data_processor)
            | 'FinalOutput'    >> beam.Map(print)
        )
    
if __name__ == '__main__':
    run_cogroupbykey_pipeline()