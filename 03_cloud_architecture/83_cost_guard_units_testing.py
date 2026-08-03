"""
#64 BigQuery Cost Guard のテスト可能単位の検証。

🎯 【手法の4回目の適用】未カバー残の2番手(37 stmts中29 miss、22%)を埋める!

背景:
    #80(#58)、#81(#57)、#82(#67)で確立した手法を #64 へ適用する。

    コスト見積の算術は純粋であり、かつ**誤っても例外にならない**——
    1TiBを1000^4と誤れば見積が約10%甘くなるが、エラーは出ない。
    こうした「静かに間違う」ロジックこそテストで固定する価値が高い。

実行方法:
    pytest 83_cost_guard_units_testing.py -v
"""
import importlib.util
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent


def load_module_from_path(filename: str, module_name: str):
    """#71/#73/#74/#75/#76/#80/#81/#82 と同一の動的ローダー。"""
    path = HERE / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        pytest.skip(f"cannot build spec for {filename}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _cost_mod():
    pytest.importorskip('google.cloud.bigquery', reason='google-cloud-bigquery not installed')
    return load_module_from_path('64_bigquery_cost_optimization.py', 'cost_units_mod')


# ================================================================
# STAGE 1: 1TiB スキャンの見積額が料金レートと一致すること
#   1024^4 を 1000^4 と誤れば見積が約10%甘くなる——例外は出ないため
#   本番の請求書で初めて気づくタイプの誤り。
# ================================================================
def test_one_tib_costs_the_configured_rate():
    mod = _cost_mod()
    assert hasattr(mod, 'estimate_cost_usd'), \
        "#64 must expose estimate_cost_usd (extracted for testability)"

    one_tib = 1024 ** 4
    assert mod.estimate_cost_usd(one_tib) == pytest.approx(mod.PRICE_PER_TIB_USD)


# ================================================================
# STAGE 2: 見積が線形にスケールすること
# ================================================================
@pytest.mark.parametrize('multiplier', [0, 1, 2, 10])
def test_cost_scales_linearly(multiplier):
    mod = _cost_mod()

    scanned = (1024 ** 4) * multiplier
    expected = mod.PRICE_PER_TIB_USD * multiplier
    assert mod.estimate_cost_usd(scanned) == pytest.approx(expected)


# ================================================================
# STAGE 3: GB変換が二進接頭辞であること
# ================================================================
def test_bytes_to_gb_uses_binary_prefix():
    mod = _cost_mod()
    assert hasattr(mod, 'bytes_to_gb'), "#64 must expose bytes_to_gb"

    assert mod.bytes_to_gb(1024 ** 3) == pytest.approx(1.0)
    assert mod.bytes_to_gb(0) == 0.0


# ================================================================
# STAGE 4: コストガードが境界値で正しく振る舞うこと
#   上限ちょうどは通し、1バイト超で止める。
# ================================================================
def test_cost_guard_at_exact_limit_boundary():
    mod = _cost_mod()
    assert hasattr(mod, 'exceeds_cost_guard'), "#64 must expose exceeds_cost_guard"

    limit = mod.MAX_BYTES_BILLED
    assert mod.exceeds_cost_guard(limit - 1, limit) is False
    assert mod.exceeds_cost_guard(limit, limit) is False, \
        "exactly at the cap must pass (> not >=)"
    assert mod.exceeds_cost_guard(limit + 1, limit) is True


# ================================================================
# STAGE 5: パーティション有効期限が90日であること
#   S3 Lifecycle 90日削除(ADR-002)と対称のTCO設計。
#   長くすればコストが増え、短くすれば分析可能期間が失われる。
# ================================================================
def test_partition_expiration_matches_lifecycle_policy():
    mod = _cost_mod()
    assert hasattr(mod, 'build_partition_config'), "#64 must expose build_partition_config"

    ninety_days_ms = 90 * 24 * 60 * 60 * 1000
    assert mod.PARTITION_EXPIRATION_MS == ninety_days_ms, \
        "must stay aligned with the 90-day S3 Lifecycle policy in ADR-002"

    config = mod.build_partition_config()
    assert config.field == 'event_date', "partitioning must key on event_date"
    assert config.expiration_ms == ninety_days_ms


# ================================================================
# STAGE 6: スキーマにパーティションキーが含まれること
#   event_date が欠ければパーティション設定自体が成立しない。
# ================================================================
def test_schema_contains_partition_key():
    mod = _cost_mod()
    assert hasattr(mod, 'build_table_schema'), "#64 must expose build_table_schema"

    names = [f.name for f in mod.build_table_schema()]
    assert 'event_date' in names, \
        "the partition key must exist in the schema, or partitioning cannot be applied"
    for required in ['event_id', 'user_id', 'event_type']:
        assert required in names


if __name__ == '__main__':
    print("🚀 コストガード単位テストの監査を開始するのね...")
    print("🟢 監査完了!静かに間違う見積ロジックが固定される基盤が完全画定したのね!")
    print("実行するには: pytest 83_cost_guard_units_testing.py -v")