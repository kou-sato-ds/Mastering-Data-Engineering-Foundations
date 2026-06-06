import apache_beam as beam
from apache_beam.transforms.window import FixedWindows
import time

# 1. 擬似的にタイムスタンプ（発生時刻）を持ったデータを生成するカスタムDoFn
class AddTimestampDoFn(beam.DoFn):
    def process(self, element):
        word, delay_seconds = element
        # 現在時刻から指定秒数だけ引いた「過去のイベント発生時刻」を計算
        event_time = time.time() - delay_seconds
        
        # 🚨 beam.window.TimestampedValue を使い、データに明示的な「発生時間刻み」を付与して流す！
        yield beam.window.TimestampedValue(word, event_time)

# 2. 10秒の窓ごとに集められたデータを安全にアンパックして処理する関数
def process_windowed_elements(windowed_kv):
    # ウィンドウ集計（GroupByKey等）の出口でも、入り口で即アンパックして命を吹き込む！
    word, count = windowed_kv
    return f"【窓内集計完了】単語: {word} | この10秒間の出現回数: {count}回"

def run_fixed_window_pipeline():
    with beam.Pipeline() as p:        

        # 🚀 【STAGE 1: Ingestion】生データと「何秒前に発生したか」のモック
        raw_stream = p | 'CreateRawStream' >> beam.Create([
            ('CYMBAL', 2),   # 2秒前に発生（最初の10秒窓に入るはず）
            ('CYMBAL', 5),   # 5秒前に発生（最初の10秒窓に入るはず）
            ('ENGINEER', 15), # 15秒前に発生（1つ前の10秒窓に自動で振り分けられるはず！）
            ('DATA', 3)      # 3秒前に発生（最初の10秒窓に入るはず）
        ])

        # 🚀 【STAGE 2: Add Timestamp】データに時間の概念（命）を吹き込む
        timestamped_stream = raw_stream | 'AddEventTime' >> beam.ParDo(AddTimestampDoFn())

        # 🌟 【本日の主役】無限の川を「10秒固定」の窓でパカパカと切り取る！
        windowed_stream = (
            timestamped_stream
            | 'ApplyFixedWindow' >> beam.WindowInto(FixedWindows(10)) # 👈 10秒枠の窓を設置！
        )

        # 🚀 【STAGE 3: Transform】窓の枠内だけで、単語ごとに数をカウント（GroupByKeyの変形）
        # WindowIntoの後は、カウントや集計が「窓ごと」に自動で限定されるのね！
        counted_stream = (
            windowed_stream
            | 'PairWithOne'  >> beam.Map(lambda word: (word, 1))
            | 'CountPerWord' >> beam.CombinePerKey(sum) # 👈 窓ごとに単語の合計を算出！
        )

        # 🚀 【STAGE 4: Output】窓ごとの集計結果を回収して最終出力
        (
            counted_stream
            | 'FormatResult' >> beam.Map(process_windowed_elements)
            | 'FinalOutput'  >> beam.Map(print)
        )
    
if __name__ == '__main__':
    run_fixed_window_pipeline()