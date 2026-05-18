import apache_beam as beam

def run_light_pipeline():
    # 修正：p を大文字の Pipeline() に
    with beam.Pipeline() as p:        

        # モックデータ：スペース区切りのテキスト
        raw_lines = p | 'CreateLines' >> beam.Create([
            'Cymbal Ecom',
            'Data Engineer'
        ])

        # 1. beam.Map：1つの要素を「そのまま1つのリスト」として出力する型
        (
            raw_lines
            | 'UsingMap' >> beam.Map(lambda line: line.split(' '))
            | 'LogMap' >> beam.Map(lambda x: print(f'Mapの出力: {x}'))
        )

        # 2. beam.FlatMap：要素をバラバラに「平坦化（フラット）」して出力する型
        (
            raw_lines
            | 'UsingFlatMap' >> beam.FlatMap(lambda line: line.split(' '))
            | 'LogFlatMap' >> beam.Map(lambda x: print(f'FlatMapの出力: {x}'))
        )
    
if __name__ == '__main__':
    run_light_pipeline()