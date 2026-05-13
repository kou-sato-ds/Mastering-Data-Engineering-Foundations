# --- Apache Beam / Dataflow 基本パイプラインの型 (修正版) ---
import apache_beam as beam

def run_basic_pipeline():
    # 修正ポイント: pipeline -> Pipeline (大文字から始まるクラスなのね！)
    with beam.Pipeline() as p:
        (
            p
            | "CreateData" >> beam.Create([
                "Data Engineering is fun",
                "Shakyo is the best way to learn",
                "Cloud Dataflow handles everything"
            ])
            # 「>>」の左側にある文字列は、Google Cloudの管理画面で表示される「工程名」なのね。
            | "FilterFun" >> beam.Filter(lambda x: "fun" in x.lower()) # 大文字小文字を無視して検索
            | "PrintResults" >> beam.Map(print)
        )

# 💡 DE軍師の補足：
# この「 | 」（パイプ）は、Unixコマンドのパイプと同じ思想なのね。
# 「前の工程の結果を、次の工程の入力に渡す」という流れが直感的にわかる、
# DEにとって非常に美しいシンタックスなのね！