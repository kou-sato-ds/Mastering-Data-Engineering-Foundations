"""
品質履歴との比較検知 — 「普段と比べてどうか」を測る。

🎯 【#105の残課題】固定閾値では「普段の1/10」を検知できない!

背景:
    #105 で品質チェックを実装し、記事数の下限を固定値で置いた。
    しかしADR-010(姉妹プロジェクト)にこう書いた:

      「過去との比較(記事数が『普段の』1/10か)は未実装。
        現状は固定の下限値のみ」

    固定閾値の限界は明白である。下限を5に置けば、
    **普段100件のフィードが20件に激減しても通過する**。
    逆に下限を80に上げれば、元々少ないフィードで誤検知が頻発する。

    必要なのは絶対値ではなく **普段との差** である。

    ただし移動平均や標準偏差を持ち込むと、
    「何件の履歴が必要か」「初回はどうするか」という問題が生じる。
    本ファイルは中央値ベースの単純な手法を選ぶ——
    説明できない複雑さより、説明できる単純さを優先する。

実行方法:
    pytest 100_quality_baseline_testing.py -v
"""
from statistics import median

# 🚨 ベースライン算出に必要な最小履歴数。
#    これ未満では「普段」が定義できないため、比較検知を行わない。
MIN_HISTORY_SIZE = 5

# 🚨 中央値からの下振れ許容率。0.5 なら「普段の半分未満で異常」。
#    平均ではなく中央値を使う理由は build_baseline() の docstring 参照。
DROP_RATIO_THRESHOLD = 0.5

# 🚨 上振れも検知する。急増は重複配信やクローラー暴走の兆候でありうる。
SPIKE_RATIO_THRESHOLD = 3.0


def build_baseline(history: list) -> dict:
    """
    🔍 履歴から基準値を構築する純粋関数。

    平均ではなく中央値を使う理由:
        1件の異常値(障害で0件だった日)が平均を大きく引き下げる。
        中央値なら、履歴の半数以上が正常であれば基準は安定する。
        「異常を検知するための基準が、異常に引きずられる」ことを避ける。

    履歴が不足していれば ready=False を返す——
    データが無いときに推測で基準を作らない。
    """
    if len(history) < MIN_HISTORY_SIZE:
        return {
            'ready': False,
            'median': None,
            'sample_size': len(history),
            'reason': f'need at least {MIN_HISTORY_SIZE} observations',
        }

    return {
        'ready': True,
        'median': median(history),
        'sample_size': len(history),
        'reason': None,
    }


def detect_drop(current: int, baseline: dict,
                threshold: float = DROP_RATIO_THRESHOLD) -> dict:
    """
    🚨 現在値が基準を大きく下回っていないか判定する。

    baseline が未成熟なら判定しない。
    「判定できない」と「正常」を混同すると、
    履歴の少ない初期に異常を見逃す。
    """
    if not baseline['ready']:
        return {'detected': False, 'skipped': True, 'ratio': None}

    base = baseline['median']
    if base == 0:
        return {'detected': False, 'skipped': True, 'ratio': None}

    ratio = round(current / base, 4)
    return {
        'detected': ratio < threshold,
        'skipped': False,
        'ratio': ratio,
    }


def detect_spike(current: int, baseline: dict,
                 threshold: float = SPIKE_RATIO_THRESHOLD) -> dict:
    """
    🚨 急増を検知する。

    急増は「良いこと」に見えるが、実際には
    重複配信・クローラーの暴走・上流の再送などの兆候であることが多い。
    下振れだけを見る監視は、この種の異常を丸ごと見逃す。
    """
    if not baseline['ready']:
        return {'detected': False, 'skipped': True, 'ratio': None}

    base = baseline['median']
    if base == 0:
        return {'detected': False, 'skipped': True, 'ratio': None}

    ratio = round(current / base, 4)
    return {
        'detected': ratio > threshold,
        'skipped': False,
        'ratio': ratio,
    }


def compare_with_baseline(current: int, history: list) -> dict:
    """
    📋 履歴との比較結果をまとめて返す。

    例外を投げずレポートを返す設計は #105 と同一。
    比較検知は「止める」ためではなく「知らせる」ためのものである。
    """
    baseline = build_baseline(history)
    drop = detect_drop(current, baseline)
    spike = detect_spike(current, baseline)

    return {
        'current': current,
        'baseline': baseline,
        'drop': drop,
        'spike': spike,
    }


def summarise_baseline_issues(comparison: dict) -> list:
    """
    🚨 対処が必要な項目だけを抜き出す。

    baseline が未成熟な場合、その事実自体を報告する——
    「まだ判定できない」ことを黙っていると、
    監視が効いていると誤認したまま運用が続く。
    """
    issues = []
    baseline = comparison['baseline']

    if not baseline['ready']:
        issues.append(
            f"baseline not ready: {baseline['reason']} "
            f"(have {baseline['sample_size']})"
        )
        return issues

    if comparison['drop']['detected']:
        issues.append(
            f"volume dropped to {comparison['drop']['ratio']:.0%} "
            f"of the median ({baseline['median']})"
        )

    if comparison['spike']['detected']:
        issues.append(
            f"volume spiked to {comparison['spike']['ratio']:.0%} "
            f"of the median ({baseline['median']}); "
            "check for duplicate delivery"
        )

    return issues


if __name__ == '__main__':
    print("🚀 品質ベースライン比較基盤の監査を開始するのね...")
    print("🟢 監査完了!「普段との差」で異常を捕まえる基盤が完全画定したのね!")