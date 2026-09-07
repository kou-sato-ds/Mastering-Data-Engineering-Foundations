"""
#100 ベースライン比較の検証。

🎯 【中央値を選んだ理由をテストで固定】異常値に引きずられないこと!

実行方法:
    pytest 100_quality_baseline_testing.py -v
"""
import importlib.util
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent


def load_module_from_path(filename: str, module_name: str):
    """#71/#80-#99 と同一の動的ローダー。"""
    path = HERE / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        pytest.skip(f"cannot build spec for {filename}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _base():
    return load_module_from_path('100_quality_baseline.py', 'baseline_mod')


# ================================================================
# STAGE 1: 履歴不足では基準を作らないこと
#   データが無いときに推測で基準を作らない。
# ================================================================
def test_insufficient_history_yields_no_baseline():
    mod = _base()

    baseline = mod.build_baseline([100, 98, 102])

    assert baseline['ready'] is False
    assert baseline['median'] is None
    assert 'at least' in baseline['reason']


# ================================================================
# STAGE 2: 十分な履歴では中央値が算出されること
# ================================================================
def test_sufficient_history_yields_median():
    mod = _base()

    baseline = mod.build_baseline([100, 98, 102, 101, 99])

    assert baseline['ready'] is True
    assert baseline['median'] == 100
    assert baseline['sample_size'] == 5


# ================================================================
# STAGE 3: 中央値が異常値に引きずられないこと ← 本ファイルの核心
#   平均を使えば、障害で0件だった日が基準を大きく下げる。
# ================================================================
def test_median_resists_an_outlier():
    mod = _base()

    # 👉 1日だけ障害で 0 件だった履歴
    history = [100, 98, 0, 102, 101]
    baseline = mod.build_baseline(history)

    assert baseline['median'] == 100, (
        'the median must stay near the normal volume; using the mean here '
        'would yield 80.2 and mask a genuine future drop'
    )


# ================================================================
# STAGE 4: 大幅な下振れを検知すること
#   固定閾値では捕まらない「普段の1/10」を捕まえる。
# ================================================================
def test_significant_drop_is_detected():
    mod = _base()

    baseline = mod.build_baseline([100, 100, 100, 100, 100])
    result = mod.detect_drop(20, baseline)

    assert result['detected'] is True
    assert result['ratio'] == 0.2, (
        'a fixed floor of 5 would let 20 articles pass; only comparison '
        'with the usual volume catches this'
    )


# ================================================================
# STAGE 5: 下振れ閾値の境界で正しく振る舞うこと
# ================================================================
@pytest.mark.parametrize('current,expected', [
    (49, True),    # 👉 49/100 = 0.49 < 0.5
    (50, False),   # 👉 ちょうど半分は通す
    (100, False),
])
def test_drop_threshold_boundary(current, expected):
    mod = _base()

    baseline = mod.build_baseline([100] * 5)
    assert mod.detect_drop(current, baseline)['detected'] is expected


# ================================================================
# STAGE 6: 急増も検知すること
#   下振れだけ見る監視は、重複配信を丸ごと見逃す。
# ================================================================
def test_spike_is_detected():
    mod = _base()

    baseline = mod.build_baseline([100] * 5)
    result = mod.detect_spike(400, baseline)

    assert result['detected'] is True
    assert result['ratio'] == 4.0


# ================================================================
# STAGE 7: 基準未成熟なら判定をスキップすること
#   「判定できない」と「正常」を混同しない。
# ================================================================
def test_immature_baseline_skips_rather_than_passes():
    mod = _base()

    baseline = mod.build_baseline([100, 100])
    result = mod.detect_drop(1, baseline)

    assert result['skipped'] is True
    assert result['detected'] is False, (
        'skipping must not be reported as a detection, but the caller '
        'must be able to tell it apart from a genuine pass'
    )


# ================================================================
# STAGE 8: 基準がゼロなら比較しないこと
#   ゼロ除算を避けるだけでなく、「普段0件」は比較の意味を持たない。
# ================================================================
def test_zero_baseline_is_not_compared():
    mod = _base()

    baseline = mod.build_baseline([0] * 5)

    assert mod.detect_drop(0, baseline)['skipped'] is True
    assert mod.detect_spike(10, baseline)['skipped'] is True


# ================================================================
# STAGE 9: 基準未成熟であること自体が報告されること
#   黙っていると、監視が効いていると誤認したまま運用が続く。
# ================================================================
def test_immature_baseline_is_reported_as_an_issue():
    mod = _base()

    comparison = mod.compare_with_baseline(50, [100, 100])
    issues = mod.summarise_baseline_issues(comparison)

    assert any('baseline not ready' in i for i in issues), (
        'silence about an unusable baseline lets the operator believe '
        'monitoring is in effect'
    )


# ================================================================
# STAGE 10: 正常時は違反が空であること
# ================================================================
def test_normal_volume_reports_no_issues():
    mod = _base()

    comparison = mod.compare_with_baseline(98, [100, 99, 101, 100, 102])

    assert mod.summarise_baseline_issues(comparison) == []


# ================================================================
# STAGE 11: 急増メッセージが原因の候補を示すこと
#   深夜に読む人間が必要とするのは、次の行動である。
# ================================================================
def test_spike_message_suggests_a_cause():
    mod = _base()

    comparison = mod.compare_with_baseline(500, [100] * 5)
    issues = mod.summarise_baseline_issues(comparison)

    assert any('duplicate delivery' in i for i in issues), (
        'an alert that only states a number leaves the operator to guess '
        'what to check first'
    )


if __name__ == '__main__':
    print("🚀 ベースライン比較の監査を開始するのね...")
    print("🟢 監査完了!異常値に引きずられない基準で比較する基盤が完全画定したのね!")
    print("実行するには: pytest 100_quality_baseline_testing.py -v")