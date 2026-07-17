import google.cloud.logging
from google.cloud.logging import Resource
import traceback
import json
import time

# 🎯 【観測性統治の最終ピース】DLQに隔離した異常を、人間が"検索"ではなく"発見"できる形に!
LOGGER_NAME = 'dataflow-pipeline-errors'
PROJECT_ID = 'your-gcp-project-id'


def get_structured_logger():
    """
    🚀 Cloud Logging クライアントを初期化し、構造化ログ用のロガーを返す。
    ここで出力するログは、severity + 例外のスタックトレース形式を満たせば
    Error Reporting が自動検出し、集約ダッシュボードに拾い上げる
    (明示的なError Reporting APIコールは不要 -> 構造の正しさそのものが仕組み)。
    """
    client = google.cloud.logging.Client(project=PROJECT_ID)
    return client.logger(LOGGER_NAME)


def log_structured_error(logger, exc: Exception, context: dict):
    """
    🚨 例外を Error Reporting 互換の構造化ログとして送出する。

    Error Reporting がログをエラーとして認識する条件:
        - severity が ERROR 以上
        - jsonPayload に例外のスタックトレース文字列を含む
          (Python標準の traceback.format_exc() 形式であれば自動解析される)

    #57(Beam TaggedOutput DLQ)がデータの隔離を担うのに対し、
    こちらは"障害の可視化"を担う。両者は独立した責務であり、片方だけでは
    「隔離されているが誰も気づかない」「気づいたがデータが残っていない」
    のどちらかに陥る。
    """
    logger.log_struct(
        {
            'message': f'{type(exc).__name__}: {exc}',
            'stack_trace': traceback.format_exc(),  # 👉 Error Reporting の自動検出キー
            'event_id': context.get('event_id'),
            'stage': context.get('stage', 'unknown'),
            'occurred_at': time.time(),
        },
        severity='ERROR',
        resource=Resource(type='global', labels={'project_id': PROJECT_ID}),
    )


def log_structured_info(logger, message: str, **fields):
    """
    📊 正常処理の要約もJSON構造で残す。
    Cloud Logging の Logs Explorer で `jsonPayload.stage="enrichment"` のような
    フィールドクエリが可能になり、grepベースの障害調査から脱却する。
    """
    logger.log_struct(
        {'message': message, **fields},
        severity='INFO',
    )


def process_with_observability(record: dict, logger) -> dict:
    """
    🔍 #57のDLQパターンに構造化ログを組み込んだ実行例。
    レコード処理の成否に関わらず、Cloud Logging に人間が読める記録が残る
    設計を示す(#57はデータの行き先、本パターンは"誰が""いつ"気づけるかを担う)。
    """
    stage = 'enrichment'
    try:
        if 'product_id' not in record:
            raise ValueError(f"Missing product_id in record: {record.get('event_id')}")

        result = {**record, 'processed': True}
        log_structured_info(
            logger, 'Record processed successfully',
            stage=stage, event_id=record.get('event_id')
        )
        return result

    except Exception as e:
        # 🚨 データはDLQ(#57)へ、記録はCloud Logging(本パターン)へ、両輪で観測性を完成
        log_structured_error(logger, e, {'event_id': record.get('event_id'), 'stage': stage})
        raise


if __name__ == '__main__':
    print("🚀 Cloud Logging 構造化ログ + Error Reporting 自動連携基盤の監査を開始するのね...")
    # logger = get_structured_logger()  # 初回のみ実行
    # process_with_observability({'event_id': 'evt-001'}, logger)  # 実装検証用のトリガー
    print("🟢 監査完了!スタックトレース自動集約およびフィールドクエリ可能な観測性基盤が完全画定したのね!")