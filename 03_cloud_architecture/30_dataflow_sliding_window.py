import apache_beam as beam
from apache_beam.transforms.window import SlidingWindows
import time

# 1. データに動的なイベント発生時刻を付与するカスタムDoFn
class AddDynamicTimestampDoFn(beam.DoFn):
    def process(self, element):
        word, delay_seconds = element
        event_time = time.time() - delay_seconds
        yield beam.window.TimestampedValue(word, event_time)

# 2. 重複するスライド窓から出力されたデータを安全に処理する関数
def process_sliding_elements(windowed_kv):
    # どんなに窓が重なり合っても、出口の境界線（関頭）で即アンパックして命を吹き込む！
    word, count = windowed_kv
    return f"【スライド窓集計完了】単語: {word} | 直近20秒間の出現回数: {count}回"

def run_sliding_window_pipeline():
    with beam.Pipeline() as p:        

        # 🚀 【STAGE 1: Ingestion】生データと発生秒数前モック
        raw_stream = p | 'CreateRawStream' >> beam.Create([
            ('CYMBAL', 2),   # 2秒前に発生（窓Aと窓Bの両方に重複してカウントされるはず！）
            ('CYMBAL', 8),   # 8秒前に発生
            ('ENGINEER', 5)  # 5秒前に発生
        ])

        # 🚀 【STAGE 2: Add Timestamp】データにイベント時間の概念を注入
        timestamped_stream = raw_stream | 'AddEventTime' >> beam.ParDo(AddDynamicTimestampDoFn())

        # 🌟 【本日の主役】「サイズ20秒、スライド10秒」の重複スライディング窓を設置！
        # 10秒ごとに時計の針が動いて、常に「過去20秒分のデータ」を拾い上げるのね！
        windowed_stream = (
            timestamped_stream
            | 'ApplySlidingWindow' >> beam.WindowInto(SlidingWindows(size=20, period=10)) # 👈 ココ！
        )

        # 🚀 【STAGE 3: Transform】重なり合った窓の枠内だけで、単語ごとに数を集計
        counted_stream = (
            windowed_stream
            | 'PairWithOne'  >> beam.Map(lambda word: (word, 1))
            | 'CountPerWord' >> beam.CombinePerKey(sum)
        )

        # 🚀 【STAGE 4: Output】回収して最終クリーン出力
        (
            counted_stream
            | 'FormatResult' >> beam.Map(process_sliding_elements)
            | 'FinalOutput'  >> beam.Map(print)
        )
    
if __name__ == '__main__':
    run_sliding_window_pipeline()