import apache_beam as beam
# 1. 修正：apache_beam のスペルを正確に
from apache_beam.options.pipeline_options import PipelineOptions

def run_pipeline():
    # パイプラインの実行オプションを設定
    options = PipelineOptions(
        flags=None,
        runner='DirectRunner',
        project='your-gcp-project-id',
        temp_location='gs://your-bucket-temp'
    )

    # 2. 修正：1つの Context Manager 内にすべての工程（DAG）を包み込む
    with beam.Pipeline(options=options) as p:
        
        # 3. データの読み込み
        raw_data = (
            p 
            | 'ReadFromSource' >> beam.Create([
                'Cymbal-Ecom,UserA,20',
                'Cymbal-Ecom,UserB,35',
                'Cymbal-Ecom,UserC,50'
            ])
        )
     
        # 4. データの加工・クレンジング（インデントを揃えて同じ p の中に配置）
        # 修正：Pase -> Parse、lone -> line
        parsed_data = (
            raw_data
            | 'ParseCSV' >> beam.Map(lambda line: line.split(','))
            | 'FilterAge' >> beam.Filter(lambda x: int(x[2]) >= 30)
        )
    
        # 5. 出力
        parsed_data | 'LogOutput' >> beam.Map(print)

if __name__ == '__main__':
    run_pipeline()