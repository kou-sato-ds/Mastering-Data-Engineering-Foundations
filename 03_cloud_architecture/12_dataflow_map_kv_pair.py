import apache_beam as beam

def run_light_pipeline():
    with beam.Pipeline() as p:        

        # モックデータ：検疫済みの綺麗な単語たち
        raw_words = p | 'CreateWords' >> beam.Create([
            'CYMBAL',
            'ECOM',
            'DATA',
            'ENGINEER'
        ])

        # 各単語を (単語, 文字数) のタプルにマッピングする型
        (
            raw_words
            # 1. 昨日の思想：引数名は流れてくるデータそのものである 'word'
            # 2. 処理内容：単語と、その文字数（len）をペアにして下流へ流す
            | 'MapToLengthKV' >> beam.Map(lambda word: (word, len(word)))
            
            # 3. 最終出力：タプルデータ（kv_pair）として受け取ってログに出力
            | 'LogKVOutput' >> beam.Map(lambda kv_pair: print(f'変換ペア: {kv_pair}'))
        )
    
if __name__ == '__main__':
    run_light_pipeline()