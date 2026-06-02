import apache_beam as beam

# 1. 1つの入力から、正常と異常（Dead Letter）の2系統へ分岐出力するカスタムDoFn
class SplitRouteDoFn(beam.DoFn):
    
    # 🚨 動的に分岐ルートを識別するための「タグ名」をクラス定数として定義しておくのね！
    # タイポを完全に排除し、安全なLETTERのスペルで統一するのね！
    TAG_DEAD_LETTER = 'dead_letter'

    def process(self, kv):
        # 入り口で即アンパック（マジックナンバーの生存を一切許さない絶対防衛の型！）
        word, length = kv  
        
        # 分岐条件の評価
        if length > 4:
            # 🟢 条件クリア：メインのコンベア（正常ルート）へそのまま yield で流す！
            yield (word, length)
        else:
            # 🔴 条件落ち（ノイズ）：beam.pvalue.TaggedOutput を使い、定数タグ指定でサブルートへ流す！
            yield beam.pvalue.TaggedOutput(self.TAG_DEAD_LETTER, (word, length))

def run_multiple_outputs_pipeline():
    with beam.Pipeline() as p:        

        # モックデータ：正常データと、弾くべき4文字以下のノイズデータ
        raw_kv_pairs = p | 'CreateRawData' >> beam.Create([
            ('CYMBAL', 6),
            ('ECOM', 4),       # 🚨 4文字以下（デッドレタールートへ行くはず！）
            ('DATA', 4),       # 🚨 4文字以下（デッドレタールートへ行くはず！）
            ('ENGINEER', 8)
        ])

        # 【今夜の主役】ParDo の戻り値として、複数のコンベアが詰まったオブジェクトを受け取る！
        # with_outputs() の中に、クラス定数タグをバシッと指定するのがBeamの美しい決まり事なのね！
        results = (
            raw_kv_pairs
            | 'SplitRoute' >> beam.ParDo(SplitRouteDoFn()).with_outputs(
                SplitRouteDoFn.TAG_DEAD_LETTER, # 👈 登録した定数タグ付きのサブコンベアを生成
                main='main_route'               # 👈 メインコンベアの名前
            )
        )

        # 🚀 分岐ルートA：メインコンベア（5文字以上のエリートデータ）の回収
        (
            results.main_route 
            | 'LogMainRoute' >> beam.Map(lambda res: print(f'🟢【メインルート通過】BigQuery行き: {res[0]} ({res[1]}文字)'))
        )

        # 🚀 分岐ルートB：デッドレタールート（タイポなき定数タグ指定でサブコンベアを個別に引っ張り出す！）
        (
            results[SplitRouteDoFn.TAG_DEAD_LETTER]
            | 'LogDeadLetter' >> beam.Map(lambda res: print(f'🔴【デッドレター検知】別ストレージへ隔離: {res[0]} ({res[1]}文字)'))
        )
    
if __name__ == '__main__':
    run_multiple_outputs_pipeline()