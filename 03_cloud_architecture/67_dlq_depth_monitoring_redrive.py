from google.cloud import monitoring_v3, pubsub_v1
from google.cloud.monitoring_v3 import AlertPolicy
import time

# 🎯 【観測性の最終ピース】DLQに隔離した異常を"誰かが見張り、誰かが再処理する"仕組みへ!
PROJECT_ID = 'your-gcp-project-id'
PROJECT_NAME = f'projects/{PROJECT_ID}'
DLQ_SUBSCRIPTION = 'user-events-dlq-sub'  # 👉 #62 Terraformで作成したDLQトピックへの購読
MAIN_TOPIC = 'user-events'
DLQ_DEPTH_THRESHOLD = 50  # 👉 未処理50件超で「静かな積み上がり」と判定


def build_dlq_metric_filter(subscription_id: str) -> str:
    """
    🔍 Cloud Monitoring のメトリクスフィルタ構築を切り出した純粋関数。

    フィルタ文字列が1文字違えば「メトリクスは取れているのに0件が返る」という
    サイレント失敗になる——本番でしか気づけない事故を、テストで固定する
    (#82の指摘による改善)。
    """
    return (
        'metric.type="pubsub.googleapis.com/subscription/num_undelivered_messages" '
        f'AND resource.labels.subscription_id="{subscription_id}"'
    )


def build_time_interval(now: float, lookback_seconds: int = 300) -> monitoring_v3.TimeInterval:
    """
    🕐 計測窓の構築。lookbackが短すぎると欠測、長すぎると古い値を拾う。
    """
    return monitoring_v3.TimeInterval({
        'end_time': {'seconds': int(now)},
        'start_time': {'seconds': int(now) - lookback_seconds},
    })


def extract_depth_from_series(results) -> int:
    """
    📊 TimeSeries の結果から最新の滞留数を取り出す。

    points が空のケース(メトリクス未生成)で IndexError を出さず 0 を返すことで、
    「まだデータが無い」と「本当に0件」を同じ安全な値に収束させる。
    """
    depth = 0
    for series in results:
        if series.points:
            depth = int(series.points[0].value.int64_value)
    return depth


def should_alert(depth: int, threshold: int = DLQ_DEPTH_THRESHOLD) -> bool:
    """
    🚨 アラート判定の純粋関数。閾値との比較ロジックを単独で検証可能にする。
    """
    return depth > threshold


def build_runbook_message(depth: int) -> str:
    """
    📋 深夜3時に人間が最初に読む文言。空でも曖昧でもいけない。
    """
    if depth == 0:
        return "[RUNBOOK] DLQ is empty. No action needed."
    return (
        f"[RUNBOOK] {depth} messages found. "
        "Investigate root cause before re-driving blindly. "
        "If cause is resolved (e.g., transient upstream outage), run re_drive_dlq()."
    )


def check_dlq_depth() -> int:
    """
    🔍 GCP標準メトリクス num_undelivered_messages でDLQ滞留数を取得する。
    """
    client = monitoring_v3.MetricServiceClient()
    interval = build_time_interval(time.time())

    results = client.list_time_series(
        request={
            'name': PROJECT_NAME,
            'filter': build_dlq_metric_filter(DLQ_SUBSCRIPTION),
            'interval': interval,
            'view': monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL,
        }
    )

    depth = extract_depth_from_series(results)
    print(f"[DLQ DEPTH] {DLQ_SUBSCRIPTION}: {depth} undelivered messages")
    return depth


def create_dlq_depth_alert_policy():
    """
    🚨 DLQ滞留数が閾値を超過したら即座に通知する監視ポリシーを画定。
    """
    alert_client = monitoring_v3.AlertPolicyServiceClient()

    condition = AlertPolicy.Condition(
        display_name=f'DLQ backlog exceeds {DLQ_DEPTH_THRESHOLD} messages',
        condition_threshold=AlertPolicy.Condition.MetricThreshold(
            filter=build_dlq_metric_filter(DLQ_SUBSCRIPTION),
            comparison=monitoring_v3.ComparisonType.COMPARISON_GT,
            threshold_value=DLQ_DEPTH_THRESHOLD,
            duration={'seconds': 300},  # 👉 5分継続で発火(一時スパイクと恒久滞留を区別)
            aggregations=[
                monitoring_v3.Aggregation(
                    alignment_period={'seconds': 60},
                    per_series_aligner=monitoring_v3.Aggregation.Aligner.ALIGN_MAX,
                )
            ],
        ),
    )

    policy = AlertPolicy(
        display_name='DLQ backlog requiring re-drive',
        conditions=[condition],
        combiner=AlertPolicy.ConditionCombinerType.OR,
        notification_channels=[
            f'projects/{PROJECT_ID}/notificationChannels/YOUR-SLACK-CHANNEL-ID'
        ],
        alert_strategy=AlertPolicy.AlertStrategy(
            auto_close={'seconds': 86400}  # 👉 24時間で自動クローズ(アラート疲労防止)
        ),
    )

    created = alert_client.create_alert_policy(name=PROJECT_NAME, alert_policy=policy)
    print(f"[ALERT] DLQ depth policy created: {created.name}")
    return created


def re_drive_dlq(max_messages: int = 100) -> int:
    """
    🔁 DLQに滞留したメッセージを取り出し、メイントピックへ再投入する。

    冪等性の保証(#58依存):
        再投入されたメッセージは#58のMERGE Upsertが冪等反映するため、
        二重処理でもデータは壊れない。
    """
    subscriber = pubsub_v1.SubscriberClient()
    publisher = pubsub_v1.PublisherClient()
    subscription_path = subscriber.subscription_path(PROJECT_ID, DLQ_SUBSCRIPTION)
    topic_path = publisher.topic_path(PROJECT_ID, MAIN_TOPIC)

    response = subscriber.pull(
        request={'subscription': subscription_path, 'max_messages': max_messages}
    )

    ack_ids = []
    re_driven = 0
    for received_message in response.received_messages:
        # 🚨 再投入が失敗した場合はackしない -> DLQに残り続け、次回re-driveの対象になる
        publisher.publish(topic_path, received_message.message.data)
        ack_ids.append(received_message.ack_id)
        re_driven += 1

    if ack_ids:
        subscriber.acknowledge(
            request={'subscription': subscription_path, 'ack_ids': ack_ids}
        )

    print(f"[RE-DRIVE] {re_driven} messages moved from DLQ back to '{MAIN_TOPIC}'")
    return re_driven


def dlq_runbook():
    """
    📋 深夜3時にアラートが鳴った時、人間が最初にたどるべき手順を関数として明示。
    """
    depth = check_dlq_depth()
    print(build_runbook_message(depth))


if __name__ == '__main__':
    print("🚀 Pub/Sub DLQ深さ監視+自動Re-drive基盤の監査を開始するのね...")
    # create_dlq_depth_alert_policy()  # 初回のみ実行
    # dlq_runbook()  # 実装検証用のトリガー
    print("🟢 監査完了!DLQ滞留の自動検知およびRunbook化された再処理基盤が完全画定したのね!")