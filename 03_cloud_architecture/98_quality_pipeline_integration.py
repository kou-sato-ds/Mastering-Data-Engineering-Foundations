"""
データ品質チェックのパイプライン統合 — 検証結果を行き先へ繋ぐ。

🎯 【#105の続き】ロジックは作った。次は「どこで呼び、どこへ流すか」!

背景:
    #97 で品質チェックのロジックを実装したが、
    `run_quality_checks()` を呼ぶ経路がどこにも無い。
    これは #68-#71 の頃と同じ「読めば正しそうだが実行経路が無い」状態である。

    さらに、異常を検知した後の行き先も決まっていない。
    品質異常には3種類の行き先がある:

      - **レコード単位の異常** -> DLQ へ隔離 (#65 と同じ経路)
      - **バッチ単位の異常**   -> メトリクス送出 (#68 の閾値監視へ)
      - **全ての判定結果**     -> 構造化ログ (#74 の Logs Explorer へ)

    重要なのは「どれを止めて、どれを通すか」の判断である。
    レコード1件の異常でバッチ全体を落とせば、正常な999件も届かない。

実行方法:
    pytest 98_quality_integration_testing.py -v
"""
import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent

# 🎯 【判定の行き先】異常の種類ごとに、どこへ流すかを宣言する。
#    'dlq'     : そのレコードを隔離し、他は通す
#    'metric'  : バッチ全体の指標として送出し、閾値超過ならアラート
#    'log'     : 記録のみ。処理は継続する
ROUTING = {
    'schema_missing': 'dlq',        # 👉 必須列欠落は分析を壊す
    'unknown_event_type': 'log',    # 👉 上流の新種別かもしれない。止めない
    'null_rate_exceeded': 'metric', # 👉 バッチ全体の傾向
    'staleness_exceeded': 'metric', # 👉 パイプライン停止の兆候
}

# 🚨 バッチを止める条件。これ以外は「記録して通す」。
FATAL_ISSUES = {'staleness_exceeded'}


def _load(filename: str, module_name: str):
    path = HERE / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def load_quality():
    return _load('97_data_quality_checks.py', 'quality_for_integration')


def classify_record(row: dict) -> str:
    """
    🔍 1レコードの行き先を判定する純粋関数。

    'main' なら正常系へ、'dlq' なら隔離へ。
    レコード単位の判定はここだけで完結させる——
    バッチ全体の統計と混ぜると、1件の異常で全件を落とす設計になりやすい。
    """
    quality = load_quality()
    drift = quality.detect_schema_drift(row)

    if drift['missing']:
        return 'dlq'
    return 'main'


def build_dlq_payload(row: dict, reason: str) -> dict:
    """
    🚨 DLQ レコードを構築する。#65 と同じ4列を保つ。

    品質起因の隔離であることを error_type で区別できるようにする——
    パース失敗と品質異常は原因も対処も違う。
    """
    quality = load_quality()
    drift = quality.detect_schema_drift(row)

    return {
        'raw_payload': str(row),
        'error_type': 'DataQualityViolation',
        'error_message': f'{reason}: missing {drift["missing"]}',
        'failed_at': datetime.now(timezone.utc).isoformat(),
    }


def build_metrics(report: dict) -> list:
    """
    📊 品質レポートから送出すべきメトリクスを構築する。

    #68 の Cloud Monitoring へ送る前提の形式。
    値そのものを送ることで、閾値はモニタリング側で調整できる——
    コードに閾値を埋め込むと、変更のたびにデプロイが必要になる。
    """
    metrics = []

    for field, rate in report['null_rates'].items():
        metrics.append({
            'name': 'data_quality/null_rate',
            'value': rate,
            'labels': {'field': field},
        })

    if report['staleness_hours'] is not None:
        metrics.append({
            'name': 'data_quality/staleness_hours',
            'value': report['staleness_hours'],
            'labels': {},
        })

    metrics.append({
        'name': 'data_quality/row_count',
        'value': report['row_count'],
        'labels': {},
    })

    return metrics


def decide_batch_action(report: dict) -> dict:
    """
    🎯 バッチ全体をどう扱うか判定する。

    'continue' : 記録して処理を続ける
    'halt'     : 処理を止める(鮮度異常のみ)

    NOTE: 初回実装では violations の文字列マッチで致命判定していたが、
          'staleness_exceeded' と 'data is 12.0h stale' は文字列として
          一致しない。**判定は生の数値から行う**——
          表示用に整形された文字列を判定に使うのは脆い設計である。
    """
    quality = load_quality()
    violations = quality.summarise_violations(report)

    staleness = report.get('staleness_hours')
    is_fatal = staleness is not None and quality.is_stale(staleness)

    fatal = [v for v in violations if 'stale' in v] if is_fatal else []

    return {
        'action': 'halt' if is_fatal else 'continue',
        'violations': violations,
        'fatal': fatal,
    }


def build_quality_log(report: dict, decision: dict) -> dict:
    """
    📋 構造化ログのペイロードを構築する。#74 の形式に揃える。

    正常時も出力する——「チェックが走ったこと」自体が情報である。
    異常時だけログを出すと、無音が「正常」なのか「未実行」なのか
    区別できなくなる。
    """
    return {
        'message': 'data quality check completed',
        'row_count': report['row_count'],
        'violation_count': len(decision['violations']),
        'action': decision['action'],
        'violations': decision['violations'],
        'severity': 'ERROR' if decision['action'] == 'halt' else (
            'WARNING' if decision['violations'] else 'INFO'
        ),
    }


if __name__ == '__main__':
    print("🚀 品質チェックのパイプライン統合基盤の監査を開始するのね...")
    print("🟢 監査完了!異常の種類ごとに行き先が定まる基盤が完全画定したのね!")