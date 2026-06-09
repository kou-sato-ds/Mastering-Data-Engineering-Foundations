import apache_beam as beam
from apache_beam.transforms.window import FixedWindows
from apache_beam.transforms.trigger import AfterWatermark, AccumulationMode
import time

# 1. 意図的に「未来の現在時刻」と「遥か過去（遅延）」のデータをエミュレートするDoFn
class AddLateTimestampDoFn(beam.DoFn):
    def process(self, element):
        word, delay_seconds = element
        # データの発生時刻を決定
        event_time = time.time() - delay_seconds
        yield beam.window.TimestampedValue(word, event_time)

# 2. トリガーによって「確定時」「遅延救済時」に何度も発火する出力を安全に処理する関数
def process_triggered_elements(windowed_kv):
    # トリガーの再計算出口でも、境界線（関頭）で即アンパックして命（名前）を吹き込む！
    word, count = windowed_kv
    return f"【トリガー発火・窓内最新集計】単語: {word} | 最新の合計カウント: {count}回"

def run_trigger_pipeline():
    with beam.Pipeline() as p:        

        # 🚀 【STAGE 1: Ingestion】通常データと、あえて「30秒前」という大遅延データを混ぜて投入！
        raw_stream = p | 'CreateLateStream' >> beam.Create([
            ('CYMBAL', 2),   # 正常データ（最初の10秒窓に滑り込み）
            ('CYMBAL', 5),   # 正常データ（最初の10秒窓に滑り込み）
            ('CYMBAL', 35)  # 🚨 大遅延データ！「35秒前」の電波障害から復帰したログを想定！
        ])

        # 🚀 【STAGE 2: Add Timestamp】データにイベント時間の概念を注入
        timestamped_stream = raw_stream | 'AddEventTime' >> beam.ParDo(AddLateTimestampDoFn())

        # 🌟 【今夜の主役】トリガーと許容遅延を組み合わせた、本番運用最強の「防衛窓」の設置！
        windowed_stream = (
            timestamped_stream
            | 'ApplyWindowWithTrigger' >> beam.WindowInto(
                FixedWindows(10), # ① ベースは10秒の固定窓
                
                # ② トリガー設定：基本は時間通り（AfterWatermark）に出し、
                # もし窓が閉じた後に「遅延データ」が来たら、1件来るごとに（withEarlyFirings）即座に再計算して上書き出力する！
                trigger=AfterWatermark(late=beam.transforms.trigger.AfterCount(1)),
                
                # ③ 蓄積モード：遅延データが来たとき、過去の値に「プラス」して合計を出す（Accumulating）
                accumulation_mode=AccumulationMode.ACCUMULATING,
                
                # 🚨 【絶対防衛】Allowed Lateness：窓が閉じた後も「60秒間」だけは遅延データの突入を許す！
                allowed_lateness=60 
            )
        )

        # 🚀 【STAGE 3: Transform】トリガー枠内で、単語ごとに数を集計
        counted_stream = (
            windowed_stream
            | 'PairWithOne'  >> beam.Map(lambda word: (word, 1))
            | 'CountPerWord' >> beam.CombinePerKey(sum) # 👈 トリガーが引かれるたびに再集計が走る！
        )

        # 🚀 【STAGE 4: Output】回収して最終クリーン出力
        (
            counted_stream
            | 'FormatResult' >> beam.Map(process_triggered_elements)
            | 'FinalOutput'  >> beam.Map(print)
        )
    
if __name__ == '__main__':
    run_trigger_pipeline()