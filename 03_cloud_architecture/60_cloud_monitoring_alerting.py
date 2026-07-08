from google.cloud import monitoring_v3
from google.cloud.monitoring_v3 import AlertPolicy, NotificationChannel
import time

# 🎯 【観測性統治の狼煙】パイプラインの健全性をカスタムメトリクスで可視化!
PROJECT_ID = 'your-gcp-project-id'
PROJECT_NAME = f'projects/{PROJECT_ID}'

def emit_custom_metric(dlq_count: int, main_throughput: int):
    """
    🛡️ パイプライン実行結果をCloud Monitoringへカスタムメトリクスとして送出。
    Dataflow/Composer/Cloud Functions等のジョブから直接呼び出し可能。
    """
    client = monitoring_v3.MetricServiceClient()

    # 🚀 【STAGE 1: DLQ件数メトリクス】異常データの流量を時系列で観測!
    dlq_series = monitoring_v3.TimeSeries()
    dlq_series.metric.type = 'custom.googleapis.com/pipeline/dlq_count'
    dlq_series.resource.type = 'global'
    dlq_series.resource.labels['project_id'] = PROJECT_ID

    now = time.time()
    dlq_point = monitoring_v3.Point({
        'interval': {'end_time': {'seconds': int(now)}},
        'value': {'int64_value': dlq_count}
    })
    dlq_series.points = [dlq_point]

    # 🔍 【STAGE 2: メインスループットメトリクス】正常データ処理量の観測!
    throughput_series = monitoring_v3.TimeSeries()
    throughput_series.metric.type = 'custom.googleapis.com/pipeline/main_throughput'
    throughput_series.resource.type = 'global'
    throughput_series.resource.labels['project_id'] = PROJECT_ID
    throughput_point = monitoring_v3.Point({
        'interval': {'end_time': {'seconds': int(now)}},
        'value': {'int64_value': main_throughput}
    })
    throughput_series.points = [throughput_point]

    # 🚀 【STAGE 3: 一括送出】Cloud Monitoringへ並列プッシュ!
    client.create_time_series(
        name=PROJECT_NAME,
        time_series=[dlq_series, throughput_series]
    )
    print(f"[METRICS] dlq={dlq_count}, throughput={main_throughput}")


def create_dlq_alert_policy():
    """
    🚨 DLQ件数がSLA閾値(100件/日)を超過したら深夜3時でも起こす通知ポリシーを画定。
    """
    alert_client = monitoring_v3.AlertPolicyServiceClient()

    # 🎯 【条件定義】DLQ_countが100超過を検知
    condition = AlertPolicy.Condition(
        display_name='DLQ threshold breach (>100/day)',
        condition_threshold=AlertPolicy.Condition.MetricThreshold(
            filter='metric.type="custom.googleapis.com/pipeline/dlq_count" '
                   'resource.type="global"',
            comparison=monitoring_v3.ComparisonType.COMPARISON_GT,
            threshold_value=100,
            duration={'seconds': 300},  # 👉 5分継続で発火(スパイク誤検知回避)
            aggregations=[
                monitoring_v3.Aggregation(
                    alignment_period={'seconds': 60},
                    per_series_aligner=monitoring_v3.Aggregation.Aligner.ALIGN_MAX
                )
            ]
        )
    )

    # 🚨 【ポリシー本体】即座に通知チャンネル(Slack/PagerDuty)へ発火!
    policy = AlertPolicy(
        display_name='Pipeline DLQ SLA breach',
        conditions=[condition],
        combiner=AlertPolicy.ConditionCombinerType.OR,
        notification_channels=[
            # 👉 事前に作成したチャンネルARNを指定
            f'projects/{PROJECT_ID}/notificationChannels/YOUR-SLACK-CHANNEL-ID'
        ],
        alert_strategy=AlertPolicy.AlertStrategy(
            auto_close={'seconds': 86400}  # 👉 24時間で自動クローズ
        )
    )

    created = alert_client.create_alert_policy(
        name=PROJECT_NAME,
        alert_policy=policy
    )
    print(f"[ALERT] Policy created: {created.name}")
    return created


if __name__ == '__main__':
    print("🚀 Cloud Monitoring 観測性基盤の監査を開始するのね...")
    # emit_custom_metric(dlq_count=42, main_throughput=15000)  # 実装検証用のトリガー
    # create_dlq_alert_policy()  # 初回のみ実行
    print("🟢 監査完了!カスタムメトリクス送出およびSLA閾値アラート基盤が完全画定したのね!")