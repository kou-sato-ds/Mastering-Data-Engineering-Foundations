# 🎯 【IaC統治の狼煙】GCPデータ基盤全体をコードで再現可能に画定!
# 使い方:
#   terraform init && terraform plan && terraform apply
#   → 本番/ステージング/検証環境を完全に同一構成で複製可能

# ================================================================
# STAGE 1: Provider設定 - GCP接続の起点
# ================================================================
terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
  # 🚨 【重要】stateファイルはGCS backendで管理(ローカル管理は事故の元)
  backend "gcs" {
    bucket = "your-gcp-project-id-tfstate"
    prefix = "data-platform/prod"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# ================================================================
# STAGE 2: 変数定義 - 環境間の差分を注入可能に
# ================================================================
variable "project_id" {
  type        = string
  description = "GCP project ID"
}

variable "region" {
  type    = string
  default = "asia-northeast1"
}

variable "environment" {
  type        = string
  description = "prod / staging / dev"
  validation {
    condition     = contains(["prod", "staging", "dev"], var.environment)
    error_message = "environment must be one of: prod, staging, dev"
  }
}

# ================================================================
# STAGE 3: BigQuery Dataset - #52-#58の器を明示宣言
# ================================================================
resource "google_bigquery_dataset" "analytics_ds" {
  dataset_id                  = "analytics_ds"
  location                    = var.region
  default_table_expiration_ms = 7776000000  # 👉 90日で自動削除(TCO制御)

  labels = {
    environment = var.environment
    owner       = "data-engineering-team"
    managed_by  = "terraform"
  }

  # 🛡️ 【最小権限】#61で作成したSAのみBQ書込可能に
  access {
    role          = "WRITER"
    user_by_email = google_service_account.pipeline_sa.email
  }
}

# ================================================================
# STAGE 4: PubSub Topic + Subscription - #54のストリーム経路を宣言
# ================================================================
resource "google_pubsub_topic" "user_events" {
  name = "user-events-${var.environment}"

  labels = {
    environment = var.environment
    managed_by  = "terraform"
  }

  # 👉 メッセージ保持期間: 7日間(再処理時の巻き戻し可能範囲)
  message_retention_duration = "604800s"
}

resource "google_pubsub_subscription" "user_events_sub" {
  name  = "user-events-sub-${var.environment}"
  topic = google_pubsub_topic.user_events.name

  ack_deadline_seconds       = 60
  message_retention_duration = "604800s"

  # 🚨 【DLQ設計】#57と対称: 5回失敗したら死信キューへ隔離
  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.dlq.id
    max_delivery_attempts = 5
  }

  # 🔁 指数バックオフ付きリトライ(Review Principles必須項目)
  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }
}

resource "google_pubsub_topic" "dlq" {
  name = "user-events-dlq-${var.environment}"
}

# ================================================================
# STAGE 5: Service Account - #61の最小権限SAをコード化
# ================================================================
resource "google_service_account" "pipeline_sa" {
  account_id   = "dataflow-pipeline-sa-${var.environment}"
  display_name = "Dataflow Pipeline Runner (least-privilege, ${var.environment})"
  description  = "Managed by Terraform. Rotation: quarterly review required."
}

# 🎯 最小権限ロールを for_each で個別バインディング(#61と完全同一設計)
resource "google_project_iam_member" "pipeline_sa_roles" {
  for_each = toset([
    "roles/dataflow.worker",
    "roles/pubsub.subscriber",
    "roles/bigquery.dataEditor",
    "roles/bigquery.jobUser",
    "roles/monitoring.metricWriter",
  ])

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.pipeline_sa.email}"
}

# ================================================================
# STAGE 6: Monitoring Alert Policy - #60をコード化
# ================================================================
resource "google_monitoring_alert_policy" "dlq_threshold_breach" {
  display_name = "Pipeline DLQ SLA breach (${var.environment})"
  combiner     = "OR"

  conditions {
    display_name = "DLQ count > 100/day"
    condition_threshold {
      filter          = "metric.type=\"custom.googleapis.com/pipeline/dlq_count\" resource.type=\"global\""
      comparison      = "COMPARISON_GT"
      threshold_value = 100
      duration        = "300s"  # 👉 5分継続で発火(スパイク誤検知回避)

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_MAX"
      }
    }
  }

  alert_strategy {
    auto_close = "86400s"  # 👉 24時間で自動クローズ
  }
}

# ================================================================
# STAGE 7: Outputs - 他モジュール/CIから参照可能に
# ================================================================
output "pipeline_sa_email" {
  value       = google_service_account.pipeline_sa.email
  description = "Service Account email for Dataflow jobs to attach"
}

output "dataset_id" {
  value = google_bigquery_dataset.analytics_ds.dataset_id
}

output "pubsub_subscription" {
  value = google_pubsub_subscription.user_events_sub.name
}

# 🟢 実行例:
#   terraform init -backend-config="bucket=your-gcp-project-id-tfstate"
#   terraform plan -var="project_id=your-gcp-project-id" -var="environment=prod"
#   terraform apply -var="project_id=your-gcp-project-id" -var="environment=prod"
#
# 監査完了!GCPデータ基盤全体のIaC化および再現可能インフラ基盤が完全画定したのね!
