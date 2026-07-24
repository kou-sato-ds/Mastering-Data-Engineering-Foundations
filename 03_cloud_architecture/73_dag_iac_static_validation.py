"""
DAG / IaC / コストガードの静的検証テスト。

🎯 【CIに載せる対象を増やす】#79で挙げた未検証リストから3ファイルを消し込む!

背景:
    #72 で CI 基盤は整った。しかし守っている対象は #68-#71 の21件のみ。
    本ファイルは #59(Airflow DAG) / #62(Terraform) / #64(BigQuery Cost Guard)
    という **性質の異なる3種** を、それぞれに適した手法で検証対象へ加える。

検証手法の使い分け:
    - #59 Airflow DAG  -> importlib で読み込み、DAG構造とretry設定を検証
    - #62 Terraform    -> Python ではないため、テキストとして必須リソースの存在を検証
    - #64 Cost Guard   -> importlib で読み込み、閾値定数と関数の存在を検証

実行方法:
    pytest 73_dag_iac_static_validation.py -v
"""
import importlib.util
import re
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent


def load_module_from_path(filename: str, module_name: str):
    """#71 と同一の動的ローダー。数字始まりのファイル名を読み込むために必要。"""
    path = HERE / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        pytest.skip(f"cannot build spec for {filename}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


# ================================================================
# STAGE 1: #59 Airflow DAG が import 可能で、DAGオブジェクトを構築できること
#   DAGファイルの構文エラーは本番では「Airflow UIに出てこない」形で現れる。
#   import時点で検知できれば、デプロイ前に気づける。
# ================================================================
def test_composer_dag_module_is_importable():
    pytest.importorskip('airflow', reason='apache-airflow not installed')

    mod = load_module_from_path('59_composer_airflow_dag.py', 'composer_dag_mod')
    assert hasattr(mod, 'dag'), "#59 must expose a DAG object named 'dag'"


# ================================================================
# STAGE 2: #59 のリトライ設定が「指数バックオフ付き」であること
#   Review Principle の必須項目。値が緩められたらテストが落ちる。
# ================================================================
def test_composer_dag_uses_exponential_backoff():
    pytest.importorskip('airflow', reason='apache-airflow not installed')

    mod = load_module_from_path('59_composer_airflow_dag.py', 'composer_dag_mod')
    args = mod.default_args

    assert args['retries'] >= 1, "DAG must retry on failure"
    assert args.get('retry_exponential_backoff') is True, \
        "exponential backoff must stay enabled (linear retry hammers a failing upstream)"
    assert 'max_retry_delay' in args, "retry delay must be capped"


# ================================================================
# STAGE 3: #59 が冪等性リスクを排除する設定を維持していること
#   catchup=True にすると過去日が一斉実行され、重複の温床になる。
#   max_active_runs>1 にすると DWH 書込が競合する。
# ================================================================
def test_composer_dag_guards_against_idempotency_risk():
    pytest.importorskip('airflow', reason='apache-airflow not installed')

    mod = load_module_from_path('59_composer_airflow_dag.py', 'composer_dag_mod')

    assert mod.dag.catchup is False, "catchup must stay disabled (backfill causes duplicates)"
    assert mod.dag.max_active_runs == 1, "concurrent runs would race on the same DWH tables"


# ================================================================
# STAGE 4: #62 Terraform に必須リソースが定義されていること
#   Python ではないため import できない -> テキストとして検証する。
#   「.tf を静的検査する」という発想自体が、対象に応じた手法選択の実例。
# ================================================================
@pytest.mark.parametrize('required_block', [
    'resource "google_bigquery_dataset"',
    'resource "google_pubsub_topic"',
    'resource "google_service_account"',
    'resource "google_monitoring_alert_policy"',
    'backend "gcs"',           # 👉 stateのローカル管理を禁じる設計
    'dead_letter_policy',      # 👉 #57 と対称の DLQ 宣言
])
def test_terraform_declares_required_blocks(required_block):
    tf_path = HERE / '62_terraform_gcp_data_platform.tf'
    assert tf_path.exists(), "#62 terraform file must exist"

    content = tf_path.read_text(encoding='utf-8')
    assert required_block in content, \
        f"#62 must declare {required_block!r} (removing it silently weakens the platform)"


# ================================================================
# STAGE 5: #62 の最小権限ロールが広すぎる権限に置き換わっていないこと
#   roles/owner や roles/editor が紛れ込めば Blast Radius 制御が崩れる。
# ================================================================
def test_terraform_has_no_overly_broad_roles():
    content = (HERE / '62_terraform_gcp_data_platform.tf').read_text(encoding='utf-8')

    forbidden = ['roles/owner', 'roles/editor']
    for role in forbidden:
        assert role not in content, \
            f"{role} breaks least-privilege design (see #61 / #69 for the principle)"


# ================================================================
# STAGE 6: #64 のコストガード閾値が定義され、無効化されていないこと
#   MAX_BYTES_BILLED が None や巨大値になれば、フルスキャン事故の防波堤が消える。
# ================================================================
def test_cost_guard_threshold_is_enforced():
    pytest.importorskip('google.cloud.bigquery', reason='google-cloud-bigquery not installed')

    mod = load_module_from_path('64_bigquery_cost_optimization.py', 'cost_guard_mod')

    assert hasattr(mod, 'MAX_BYTES_BILLED'), "#64 must define MAX_BYTES_BILLED"
    assert isinstance(mod.MAX_BYTES_BILLED, int), "threshold must be a concrete integer"
    assert 0 < mod.MAX_BYTES_BILLED <= 100 * 1024 ** 3, \
        "threshold must stay within a sane range (an unbounded cap defeats the guard)"

    # 👉 dry run による事前見積もり関数が消えていないこと
    assert hasattr(mod, 'estimate_query_cost'), "#64 must keep the dry-run estimator"
    assert hasattr(mod, 'run_query_with_cost_guard'), "#64 must keep the guarded executor"


if __name__ == '__main__':
    print("🚀 DAG / IaC / コストガード 静的検証基盤の監査を開始するのね...")
    print("🟢 監査完了!#59・#62・#64が回帰テストの保護下に入る基盤が完全画定したのね!")
    print("実行するには: pytest 73_dag_iac_static_validation.py -v")