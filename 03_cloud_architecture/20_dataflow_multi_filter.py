import apache_beam as beam

# 1. 複数条件を評価する多層検疫関数（自己文書化・防衛運転仕様）
def filter_valid_and_long_words(kv):
    # 入り口で即アンパック（マジックナンバーの生存を許さない！）
    word, length = kv  
    
    # 条件A（ブラックリスト方式）：空文字、またはスペースだけのゴミデータは異常（True）とする
    is_empty_or_invalid = (word == "" or word.isspace())
    
    # 条件B（ホワイトリスト方式）：文字数が4文字より大きい（5文字以上）
    is_long_enough = (length > 4)
    
    # 【多層防御のリターン】「異常データではなく（not）」かつ「十分な長さを持っている」ものだけを通過！
    return (not is_empty_or_invalid) and is_long_enough

def run_multi_filter_pipeline():
    with beam.Pipeline() as p:        

        # モックデータ：空文字やスペース、短い単語が混ざった未クレンジングデータ
        raw_kv_pairs = p | 'CreateRawData' >> beam.Create([
            ('CYMBAL', 6),
            ('', 0),          # 🚨 空文字（弾くべきノイズ）
            ('ECOM', 4),       # 🚨 4文字以下（短いので弾く）
            (' ', 1),           # 🚨 スペースのみ（弾くべきノイズ）
            ('ENGINEER', 8)
        ])

        # 幾重もの関門をノーバグで突破させるクリーンなDAGチェイン
        (
            raw_kv_pairs
            # 本筋の進化：beam.Filter に多層評価関数をマッピング
            | 'MultiLayerFilter' >> beam.Filter(filter_valid_and_long_words)
            
            # 最終ゴールの顔つき確認（ノイズが完全に消滅し、CYMBAL と ENGINEER だけが残るのね！）
            | 'FinalOutput'      >> beam.Map(lambda res: print(f'【検疫完全通過】防衛線を突破したクリーンデータ: {res[0]}'))
        )
    
if __name__ == '__main__':
    run_multi_filter_pipeline()