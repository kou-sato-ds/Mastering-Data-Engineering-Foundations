import apache_beam as beam

# 1. 結合されたデータを検疫しつつ、合格品とデッドレターにパカッと引き裂く DoFn
class JoinAuditRouteDoFn(beam.DoFn):
    TAG_DEAD_LETTER = 'dead_letter'

    def process(self, grouped_element):
        # 境界線（関頭）で即座にアンパック！絶対防衛の型！
        word, grouped_dict = grouped_element
        
        lengths_list = grouped_dict.get('lengths', [])
        languages_list = grouped_dict.get('languages', [])
        
        # 🚨 FULL OUTER JOINに伴うキー欠落（マスタ未登録）を厳格にフォールバック防衛！
        if lengths_list and languages_list:
            length = lengths_list[0]
            language = languages_list[0]
            # 🟢 双方のマスタが揃っているエリートデータは正常ルートへ！
            yield (word, length, language)
        else:
            # 🔴 どちらかが欠落しているデータは「デッドレター」として即座に隔離！
            yield beam.pvalue.TaggedOutput(self.TAG_DEAD_LETTER, word)

def run_e2e_join_pipeline():
    with beam.Pipeline() as p:        

        # 🚀 【STAGE 1: Ingestion & クレンジング】
        stream_lengths = (
            p | 'CreateRawWords' >> beam.Create([' cymbal ', 'engineer', 'data'])
            | 'CleanAndLength'   >> beam.Map(lambda w: (w.strip().upper(), len(w.strip())))
        )

        # 🚀 【STAGE 2: マスタデータのインプット】
        stream_languages = p | 'CreateLanguages' >> beam.Create([
            ('CYMBAL', 'English'),
            ('ENGINEER', 'French_Origin') # 🚨 'DATA' のマスタが欠落している（防衛テスト用）
        ])

        # 🚀 【STAGE 3: CoGroupByKey によるキー結合】
        grouped_stream = (
            {'lengths': stream_lengths, 'languages': stream_languages}
            | 'CoGroupByKey' >> beam.CoGroupByKey()
        )

        # 🚀 【STAGE 4: 監査＆マルチ流路分岐】
        branched_results = (
            grouped_stream
            | 'AuditAndRoute' >> beam.ParDo(JoinAuditRouteDoFn()).with_outputs(
                JoinAuditRouteDoFn.TAG_DEAD_LETTER, main='main_route'
            )
        )

        # 🚀 【STAGE 5-A: Main Output】(正常系)
        branched_results.main_route | 'LogMain' >> beam.Map(lambda res: print(f'🟢【BQ格納】合流完了: {res[0]} (長さ: {res[1]} | 言語: {res[2]})'))

        # 🚀 【STAGE 5-B: Dead Letter Output】(隔離系：マスタ未登録の DATA がここに来るのね！)
        branched_results[JoinAuditRouteDoFn.TAG_DEAD_LETTER] | 'LogDLQ' >> beam.Map(lambda w: print(f'🔴【DLQ隔離】マスタ未登録エラー: {w}'))
    
if __name__ == '__main__':
    run_e2e_join_pipeline()