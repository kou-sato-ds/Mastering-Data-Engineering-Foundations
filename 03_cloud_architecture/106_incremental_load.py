"""
増分ロード(ハイウォーターマーク方式) — 毎回全件を読まない。

背景:
    全件ロードはデータ量に比例してコストが増え続ける。
    前回どこまで読んだか(ウォーターマーク)を記録し、それ以降だけを読むのが増分ロードである。

    ただし単純に「updated_at > 前回値」とすると3つの事故が起きる:
      1. 遅延到着 -> 前回値より少し古い時刻で後から届いた行を取りこぼす
      2. 同時刻の行 -> > で切ると、前回と同じ時刻の未処理行を取りこぼす
      3. 失敗時の前進 -> ロード失敗後もウォーターマークを進めると、その区間が永久に欠ける

    本ファイルは lookback(巻き戻し幅)・>=・キー重複排除・成功後の前進で3つを潰す。
    lookback で重複して読んだ行は、#58 の MERGE と同じくキーで冪等に吸収する。
"""
from datetime import timedelta

# 遅延到着を拾うための巻き戻し幅。広げるほど安全だが読む量が増える(TCO)。
LOOKBACK = timedelta(minutes=15)


def compute_read_from(watermark, lookback=LOOKBACK):
    """読み始め時刻を返す。初回(watermark=None)は全件読み。"""
    if watermark is None:
        return None
    return watermark - lookback


def select_new_rows(rows, watermark, lookback=LOOKBACK):
    """
    ウォーターマーク - lookback 以降の行を返す。

    > ではなく >= を使う: 前回と同一時刻の未処理行を取りこぼさないため。
    重複は dedupe_by_key で吸収するので、多めに読むことは害にならない。
    """
    start = compute_read_from(watermark, lookback)
    if start is None:
        return list(rows)
    return [r for r in rows if r['updated_at'] >= start]


def dedupe_by_key(rows, key='id'):
    """同一キーは updated_at が最新の1件に集約する(#58 の MERGE と同じ考え方)。"""
    latest = {}
    for r in rows:
        current = latest.get(r[key])
        if current is None or r['updated_at'] > current['updated_at']:
            latest[r[key]] = r
    return [latest[k] for k in sorted(latest)]


def next_watermark(rows, current):
    """
    次のウォーターマークを返す。決して後退させない。

    lookback で古い行を読み直しても、ウォーターマークが巻き戻れば
    次回以降の読み取り範囲が膨らみ続ける。
    """
    if not rows:
        return current
    newest = max(r['updated_at'] for r in rows)
    return newest if current is None else max(newest, current)


def run_increment(state, rows, load_fn):
    """
    1回分の増分ロードを実行する。

    ウォーターマークはロード成功後にのみ更新する。
    load_fn が例外を投げれば state は変わらず、次回同じ区間を読み直す——
    失敗区間を永久に欠落させないための順序である。
    """
    batch = dedupe_by_key(select_new_rows(rows, state.get('watermark')))
    load_fn(batch)
    state['watermark'] = next_watermark(batch, state.get('watermark'))
    return {'loaded': len(batch), 'watermark': state['watermark']}