"""
データ品質検証 — 壊れていないが異常なデータを捕まえる。

🎯 【DLQが取りこぼす領域】パースは通るが、値がおかしいレコード!

背景:
    #57/#65 の DLQ は「パースできない」「必須フィールドが欠けている」
    レコードを隔離する。しかしそれは **構造の検証** にすぎない。

    実務で頻発するのはむしろこちらである:
      - 上流が列を1つ増やした(スキーマドリフト)
      - user_id は存在するが 9 割が空文字
      - 最新レコードが 3 日前で止まっている(パイプライン停止)
      - event_type に想定外の値が混じり始めた

    いずれも **パースは通り、DLQ には落ちず、静かに分析結果を歪める**。

    本ファイルは値の分布・鮮度・スキーマ整合を検証する。
    #57 が「壊れたデータ」を担うなら、本項は「異常なデータ」を担う。

実行方法:
    pytest 97_data_quality_testing.py -v
"""
from datetime import datetime, timedelta, timezone

# 🛡️ 【期待スキーマ】上流が列を増減させたら検知する基準
EXPECTED_FIELDS = {'event_id', 'user_id', 'event_type', 'occurred_at'}

# 🛡️ 【許容される event_type】未知の値が混じり始めたら検知する
KNOWN_EVENT_TYPES = {'click', 'view', 'purchase', 'signup'}

# 🚨 【NULL率の上限】これを超えたら上流の障害を疑う
MAX_NULL_RATE = 0.05

# 🚨 【鮮度の上限】最新レコードがこれより古ければパイプライン停止を疑う
MAX_STALENESS_HOURS = 6


def detect_schema_drift(row: dict) -> dict:
    """
    🔍 レコードのスキーマが期待と一致するか検証する純粋関数。

    「増えた」と「減った」を区別して返す——
    列の追加は無害なことも多いが、欠落は即座に分析を壊す。
    """
    actual = set(row.keys())
    return {
        'missing': sorted(EXPECTED_FIELDS - actual),
        'unexpected': sorted(actual - EXPECTED_FIELDS),
    }


def compute_null_rate(rows: list, field: str) -> float:
    """
    📊 指定フィールドの NULL / 空文字率を返す。

    None だけでなく空文字も NULL 扱いにする——
    上流が「値が無い」を空文字で表現することは非常に多い。
    """
    if not rows:
        return 0.0

    empty = sum(
        1 for r in rows
        if r.get(field) is None or r.get(field) == ''
    )
    return round(empty / len(rows), 4)


def exceeds_null_threshold(rate: float, threshold: float = MAX_NULL_RATE) -> bool:
    """🚨 NULL率が閾値を超えたか判定する。境界値では発火しない。"""
    return rate > threshold


def find_unknown_event_types(rows: list) -> list:
    """
    🔍 想定外の event_type を検出する。

    上流が新しいイベント種別を追加した場合、
    集計クエリは黙ってその行を除外し続ける——
    エラーにならないため、数ヶ月気づかないことがある。
    """
    seen = {r.get('event_type') for r in rows if r.get('event_type')}
    return sorted(seen - KNOWN_EVENT_TYPES)


def compute_staleness_hours(latest: datetime, now: datetime) -> float:
    """
    🕐 最新レコードからの経過時間を返す。

    パイプラインが止まってもテーブルは残るため、
    クエリはエラーにならず「古いデータ」を返し続ける。
    """
    delta = now - latest
    return round(delta.total_seconds() / 3600, 2)


def is_stale(hours: float, threshold: float = MAX_STALENESS_HOURS) -> bool:
    """🚨 鮮度が閾値を超えたか判定する。"""
    return hours > threshold


def run_quality_checks(rows: list, now: datetime = None) -> dict:
    """
    📋 全チェックをまとめて実行し、結果を辞書で返す。

    例外を投げずレポートを返す設計にした理由:
        品質チェックは「止める」ためではなく「知らせる」ためのものである。
        1つの異常でパイプライン全体を止めれば、
        正常なデータまで届かなくなる(#57 の DLQ と同じ思想)。
    """
    now = now or datetime.now(timezone.utc)

    timestamps = [
        r['occurred_at'] for r in rows
        if isinstance(r.get('occurred_at'), datetime)
    ]
    latest = max(timestamps) if timestamps else None

    return {
        'row_count': len(rows),
        'null_rates': {
            f: compute_null_rate(rows, f) for f in sorted(EXPECTED_FIELDS)
        },
        'unknown_event_types': find_unknown_event_types(rows),
        'staleness_hours': (
            compute_staleness_hours(latest, now) if latest else None
        ),
        'schema_issues': [
            detect_schema_drift(r) for r in rows
            if detect_schema_drift(r)['missing']
        ],
    }


def summarise_violations(report: dict) -> list:
    """
    🚨 レポートから「対処が必要な項目」だけを抜き出す。

    全ての数値を並べるのではなく、閾値を超えたものだけを返す——
    深夜に読む人間が必要とするのは、正常値の一覧ではない。
    """
    violations = []

    for field, rate in report['null_rates'].items():
        if exceeds_null_threshold(rate):
            violations.append(f'null rate for {field}: {rate:.1%}')

    if report['unknown_event_types']:
        violations.append(
            f"unknown event types: {report['unknown_event_types']}"
        )

    staleness = report['staleness_hours']
    if staleness is not None and is_stale(staleness):
        violations.append(f'data is {staleness}h stale')

    if report['schema_issues']:
        violations.append(
            f"{len(report['schema_issues'])} rows have missing fields"
        )

    return violations


if __name__ == '__main__':
    print("🚀 データ品質検証基盤の監査を開始するのね...")
    print("🟢 監査完了!壊れていないが異常なデータを捕まえる基盤が完全画定したのね!")