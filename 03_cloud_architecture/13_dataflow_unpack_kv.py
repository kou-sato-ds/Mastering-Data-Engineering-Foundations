import apache_beam as beam

def run_light_pipeline():
    with beam.Pipeline() as p:        

        # モックデータ：昨日作った、(単語, 文字数) のKVペア（タプル）のストリーム
        raw_kv_pairs = p | 'CreateKVPairs' >> beam.Create([
            ('CYMBAL', 6),
            ('ECOM', 4),
            ('DATA', 4),
            ('ENGINEER', 8)
        ])

        # タプルのインデックス（[0], [1]）を駆使して、要素をバラバラに分解・出力する型
        (
            raw_kv_pairs
            # 昨日のFB：引数名を 'kv' とし、内部でインデックスを明示してアンパック
            # kv[0] = Key（単語）, kv[1] = Value（文字数）
            | 'UnpackAndLog' >> beam.Map(lambda kv: print(f'単語名: {kv[0]} | 文字数: {kv[1]}文字'))
        )
    
if __name__ == '__main__':
    run_light_pipeline()