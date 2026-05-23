import apache_beam as beam

# 昨日のFB：ログを出力しつつ、要素を次の工程へそのまま流す（パススルー）職人の型
def log_and_passthrough(kv):
    print(f'【検疫通過】データ: {kv[0]} (長さ: {kv[1]})')
    return kv  # 🔥 超重要：Noneを流さず、受け取ったデータをそのまま次のコンベアに引き渡す！

def run_light_pipeline():
    with beam.Pipeline() as p:        

        # モックデータ：(単語, 文字数) のKVペア（タプル）
        raw_kv_pairs = p | 'CreateKVPairs' >> beam.Create([
            ('CYMBAL', 6),
            ('ECOM', 4),
            ('DATA', 4),
            ('ENGINEER', 8)
        ])

        # ログを出力した後も、ストリームを途切れさせずに下流へ繋ぐチェイン
        (
            raw_kv_pairs
            # 1. 名前付き関数を呼び出して安全にログを出力（データはそのまま下流へ流れる）
            | 'LogAndPass' >> beam.Map(log_and_passthrough)
            
            # 2. データの生存確認：Noneになっていないので、さらに下流でKey（単語）だけを抽出できる
            | 'ExtractKey' >> beam.Map(lambda kv: kv[0])
            
            # 3. 最終ゴール
            | 'FinalOutput' >> beam.Map(lambda word: print(f'最終ストリーム: {word}'))
        )
    
if __name__ == '__main__':
    run_light_pipeline()