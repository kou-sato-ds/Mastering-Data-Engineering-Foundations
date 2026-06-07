import apache_beam as beam
from apache_beam.transforms.window import Sessions
import time

# 1. データに動的なイベント発生時刻を付与するカスタムDoFn
class AddDynamicTimestampDoFn(beam.DoFn):
    def process(self, element):
        word, delay_seconds = element
        # 現在時刻から指定秒数だけ引いた「イベント発生時刻」を算出
        event_time = time.time() - delay_seconds
        
        # データに時間の命（タイムスタンプ）を吹き込んでストリームに流す！
        yield beam.window.TimestampedValue(word, event_time)

# 2. セッションごとに束ねられたデータを安全に処理する関数
def process_session_elements(windowed_kv):
    # 動的ウィンドウの出口でも、境界線（関頭）で即アンパックして命（名前）を吹き込む！
    word, count = windowed_kv
    return f"【セッション集計完了】単語: {word} | この一連の行動内での出現回数: {count}回"

def run_session_window_pipeline():
    with beam.Pipeline() as p:        

        # 🚀 【STAGE 1: Ingestion】生データと「何秒前に発生したか」のシミュレート
        # CYMBALは2秒おき（セッション継続）、ENGINEERは単発で発生しているのね！
        raw_stream = p | 'CreateRawStream' >> beam.Create([
            ('CYMBAL', 1),   # 1秒前に発生 ➔ (A)
            ('CYMBAL', 3),   # 3秒前に発生 ➔ (A)と同じセッションにマージされる（ギャップ10秒以内）
            ('CYMBAL', 5),   # 5秒前に発生 ➔ (A)と同じセッションにマージされる（ギャップ10秒以内）
            ('ENGINEER', 25) # 25秒前に発生 ➔ 遥か昔なので、CYMBALとは完全に「別のセッション窓」に自動排他！
        ])

        # 🚀 【STAGE 2: Add Timestamp】データにイベント時間の概念を注入
        timestamped_stream = raw_stream | 'AddEventTime' >> beam.ParDo(AddDynamicTimestampDoFn())

        # 🌟 【本日の主役】ギャップ時間「10秒」の動的セッション・ウィンドウを設置！
        # これにより、同じキー（単語）で10秒以内に発生したデータは自動で1つの窓に統合されるのね！
        windowed_stream = (
            timestamped_stream
            | 'ApplySessionWindow' >> beam.WindowInto(Sessions(10)) # 👈 ギャップ10秒の動的窓！
        )

        # 🚀 【STAGE 3: Transform】セッションの枠内だけで、単語ごとに数を集計
        counted_stream = (
            windowed_stream
            | 'PairWithOne'  >> beam.Map(lambda word: (word, 1))
            | 'CountPerWord' >> beam.CombinePerKey(sum) # 👈 セッションごとに合計を算出！
        )

        # 🚀 【STAGE 4: Output】回収して最終クリーン出力
        (
            counted_stream
            | 'FormatResult' >> beam.Map(process_session_elements)
            | 'FinalOutput'  >> beam.Map(print)
        )
    
if __name__ == '__main__':
    run_session_window_pipeline()