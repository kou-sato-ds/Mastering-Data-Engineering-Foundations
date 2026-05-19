import apache_beam as beam

def run_light_pipeline():
    with beam.Pipeline() as p:        

        # モックデータ：実務を意識した小文字混じりのテキスト
        raw_lines = p | 'CreateLines' >> beam.Create([
            'Cymbal ecom',
            'Data engineer'
        ])

        # FlatMap で平坦化した後、Map で標準化処理を繋ぐ「連鎖（チェイン）」の型
        (
            raw_lines
            # 1. まずスペースでバラバラに（FlatMapの後は単語単体 'word' が流れる）
            | 'FlattenWords' >> beam.FlatMap(lambda line: line.split(' '))
            
            # 2. 昨夜のFB：引数名を 'word' にしてデータの意味を明示（可読性MAX）
            | 'ToUpperCase' >> beam.Map(lambda word: word.upper())
            
            # 3. 最終出力：標準化された単語をログに出力
            | 'LogOutput' >> beam.Map(lambda clean_word: print(f'標準化データ: {clean_word}'))
        )
    
if __name__ == '__main__':
    run_light_pipeline()