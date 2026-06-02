import apache_beam as beam

# 1. 合流した後のデータを安全に処理する関数（自己文書化・防衛運転仕様）
def process_merged_data(kv):
    # 合流した出口でも入り口で即アンパックして命（名前）を吹き込む！
    word, length = kv  
    
    # マジックナンバーを排除したクリーンな文字数カウント出力
    return f"【合流コンベア通過】単語: {word} (長さ: {length})"

def run_flatten_pipeline():
    with beam.Pipeline() as p:        

        # 🚀 【コンベアA】ルートAから流れてくるデータ
        stream_a = p | 'CreateStreamA' >> beam.Create([
            ('CYMBAL', 6),
            ('ENGINEER', 8)
        ])

        # 🚀 【コンベアB】ルートBから流れてくるデータ（データ型が完全に一致しているのね！）
        stream_b = p | 'CreateStreamB' >> beam.Create([
            ('DATA', 4),
            ('PIPELINE', 8)
        ])

        # 🌟 【今夜の主役】2つのコンベアをタプルで包んで、beam.Flatten() でガチャンと1つに統合！
        merged_stream = (
            (stream_a, stream_b) 
            | 'MergeStreams' >> beam.Flatten()
        )

        # 3. 統合された巨大なコンベアから、データを回収して最終出力
        (
            merged_stream
            | 'ProcessMerged' >> beam.Map(process_merged_data)
            | 'FinalOutput'   >> beam.Map(print)
        )
    
if __name__ == '__main__':
    run_flatten_pipeline()