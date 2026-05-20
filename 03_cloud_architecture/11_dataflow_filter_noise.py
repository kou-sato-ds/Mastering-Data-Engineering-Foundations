import apache_beam as beam

def run_light_pipeline():
    with beam.Pipeline() as p:        

        # モックデータ：連続スペースや末尾に空白がある「汚い生データ」の罠
        raw_lines = p | 'CreateLines' >> beam.Create([
            'Cymbal   ecom ',  # 空白が3つ、お尻にも空白
            'Data  engineer'   # 空白が2つ
        ])

        # FlatMap ➔ Filter ➔ Map の3本の矢で、完璧な検疫を行う型
        (
            raw_lines
            # 1. スペースでバラバラにする（このままだと空文字 '' が大量に発生する）
            | 'FlattenWords' >> beam.FlatMap(lambda line: line.split(' '))
            
            # 2. 昨夜の型：前後の余計な空白を削り（strip）、空文字になった要素を完全に遮断！
            | 'FilterEmpty' >> beam.Filter(lambda word: word.strip() != '')
            
            # 3. 検疫を通過した綺麗な単語だけを大文字に標準化
            | 'ToUpperCase' >> beam.Map(lambda word: word.upper())
            
            # 4. 最終出力
            | 'LogOutput' >> beam.Map(lambda clean_word: print(f'検疫通過データ: {clean_word}'))
        )
    
if __name__ == '__main__':
    run_light_pipeline()