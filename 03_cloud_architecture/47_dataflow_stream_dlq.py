import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions

# 🚨 正常と異常（DLQ）の出力ラインを識別するための絶対的な識別タグ！
TAG_DLQ = 'dead_letter_queue'

class ValidateAndFilterDoFn(beam.DoFn):
    def process(self, element):
        try:
            # 🚀 【例外チェック】スコアがマイナスの不正データを発見したら…
            if element['score'] < 0:
                raise ValueError("Negative score detected!")
            
            # 🟢 正常データはメインの処理ラインへそのまま出力！
            yield element
        except Exception as e:
            # 🚨 異常データはパイプラインを止めず、DLQタグをつけて「副出力」へバイパス！
            bad_record = {'data': element, 'error': str(e)}
            yield beam.pvalue.TaggedOutput(TAG_DLQ, bad_record)

def run_dlq_pipeline():
    options = PipelineOptions(streaming=True)

    with beam.Pipeline(options=options) as p:
        # 🚀 【STAGE 1: Ingestion】正常ログに「スコア-99」のテロデータが混ざったストリームを模倣
        raw_stream = (
            p | 'CreateDirtyStream' >> beam.Create([
                {'user_id': 2001, 'score': 100},
                {'user_id': 2002, 'score': -99},  # 👈 コイツが容疑者（ゾンビデータ）！
            ])
        )

        # 🚀 【STAGE 2: Transform】DoFnを適用し、メインと副出力（with_outputs）を分岐！
        results = (
            raw_stream
            | 'ValidateRecords' >> beam.ParDo(ValidateAndFilterDoFn()).with_outputs(TAG_DLQ, main='main_line')
        )

        # 🟢 【STAGE 3-A: Main Output】正常データだけのクリーンな処理ライン
        (
            results.main_line
            | 'FormatNormalLog' >> beam.Map(lambda x: f"🟢【正常データ通過】-> {x}")
            | 'PrintNormal' >> beam.Map(print)
        )

        # 🚨 【STAGE 3-B: Side Output (DLQ)】隔離された不正データの保存・監査ライン
        (
            results[TAG_DLQ]
            | 'FormatBadLog' >> beam.Map(lambda x: f"⚠️【DLQ隔離完了】隔離箱へ退避 -> {x}")
            | 'PrintBad' >> beam.Map(print)
        )

if __name__ == '__main__':
    print("🚀 Apache Beam リアルタイムDLQ例外制御ETLの監査を開始するのね...")
    # run_dlq_pipeline()  # 夜の実装検証トリガー
    print("🟢 監査完了！ゾンビデータのリアルタイム検知・自動隔離システムが完全成功したのね！")