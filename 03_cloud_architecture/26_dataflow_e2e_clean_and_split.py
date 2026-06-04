import apache_beam as beam

# 1. データの形を整える（Map用）のクリーンな関数
def attach_length_attribute(word):
    # 関頭で即時アンパック（今回は単一要素なのでそのまま名前を吹き込む！）
    clean_word = word.strip().upper()
    return (clean_word, len(clean_word))

# 2. 正常系と異常系（Dead Letter）に流路をパカッと分岐する DoFn
class AuditAndRouteDoFn(beam.DoFn):
    TAG_DEAD_LETTER = 'dead_letter'

    def process(self, kv):
        # 入り口で即アンパック！絶対防衛の型！
        word, length = kv  
        
        # 実戦的な検疫ルール：5文字以上のクリーンデータのみ正常ルートへ
        if length >= 5:
            yield (word, length, 'PASSED')
        else:
            # 🚨 4文字以下のノイズは「デッドレター」として隔離サブルートへ強制排他！
            yield beam.pvalue.TaggedOutput(self.TAG_DEAD_LETTER, (word, length, 'REJECTED'))

def run_e2e_pipeline():
    with beam.Pipeline() as p:        

        # 🚀 【STAGE 1: Ingestion】生データのインプット（表記の揺れやノイズが混在）
        raw_inputs = p | 'ReadRawSource' >> beam.Create([
            ' cymbal ',     # 空白あり（クリーンアップ対象）
            'go',           # 短すぎる（ノイズ対象）
            'engineer',     # 正常データ
            'data'          # 短すぎる（ノイズ対象）
        ])

        # 🚀 【STAGE 2: Extract & Transform】データのクレンジングと属性付与
        cleaned_kv_pairs = (
            raw_inputs
            # ① 不要な空白を除去して大文字化し、(word, length) のKV型に変換！
            | 'CleanAndTransform' >> beam.Map(attach_length_attribute)
            # ② 明らかな超短インプット（2文字以下）をこの段階で水際フィルター検疫！
            | 'FilterOutTrash'    >> beam.Filter(lambda kv: kv[1] > 2)
        )

        # 🚀 【STAGE 3: Audit & Branching】実戦的なマルチ流路への分岐制御
        # 1回のスキャンで正常ストリームとデッドレターストリームに引き裂く！
        branched_results = (
            cleaned_kv_pairs
            | 'AuditAndRoute' >> beam.ParDo(AuditAndRouteDoFn()).with_outputs(
                AuditAndRouteDoFn.TAG_DEAD_LETTER,
                main='main_route'
            )
        )

        # 🚀 【STAGE 4-A: Main Output】審査を通過したエリートデータの最終出力（実務ではBigQuery等へ）
        (
            branched_results.main_route 
            | 'LogToMainStorage' >> beam.Map(lambda res: print(f'🟢【BQ格納完了】正常データ: {res[0]} (長さ: {res[1]} | ステータス: {res[2]})'))
        )

        # 🚀 【STAGE 4-B: Dead Letter Output】弾かれたノイズデータの最終出力（実務ではGCS等へ）
        (
            branched_results[AuditAndRouteDoFn.TAG_DEAD_LETTER]
            | 'LogToDeadLetter'  >> beam.Map(lambda res: print(f'🔴【DLQ隔離完了】ノイズ検知: {res[0]} (長さ: {res[1]} | ステータス: {res[2]})'))
        )
    
if __name__ == '__main__':
    run_e2e_pipeline()