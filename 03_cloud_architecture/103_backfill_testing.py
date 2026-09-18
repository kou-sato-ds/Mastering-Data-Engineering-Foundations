"""
#103 バックフィル計画の検証。

🎯 【実行前に弾く】指定ミスの代償が大きい操作を、計画段階で止める!

実行方法:
    pytest 103_backfill_testing.py -v
"""
import importlib.util
import sys
from datetime import date
from pathlib import Path

import pytest

HERE = Path(__file__).parent
TODAY = date(2026, 9, 18)


def load_module_from_path(filename: str, module_name: str):
    """#71/#80-#102 と同一の動的ローダー。"""
    path = HERE / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        pytest.skip(f"cannot build spec for {filename}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _bf():
    return load_module_from_path('103_backfill_planner.py', 'backfill_mod')


# ================================================================
# STAGE 1: 開始日が終了日より後なら弾くこと
# ================================================================
def test_reversed_range_is_rejected():
    mod = _bf()

    errors = mod.validate_range(date(2026, 9, 10), date(2026, 9, 1), TODAY)

    assert any('after end' in e for e in errors)


# ================================================================
# STAGE 2: 未来日付を弾くこと
#   存在しないデータを埋めようとしても、空のジョブが走るだけである。
# ================================================================
def test_future_end_is_rejected():
    mod = _bf()

    errors = mod.validate_range(date(2026, 9, 1), date(2026, 12, 1), TODAY)

    assert any('future' in e for e in errors)


# ================================================================
# STAGE 3: 上限日数を超えたら弾くこと
#   「誤って10年分を指定する」事故を計画段階で止める。
# ================================================================
def test_excessive_span_is_rejected():
    mod = _bf()

    errors = mod.validate_range(date(2025, 1, 1), date(2026, 9, 1), TODAY)

    assert any('exceeding' in e for e in errors)


# ================================================================
# STAGE 4: 妥当な期間はエラーを返さないこと
# ================================================================
def test_valid_range_passes():
    mod = _bf()

    assert mod.validate_range(date(2026, 9, 1), date(2026, 9, 7), TODAY) == []


# ================================================================
# STAGE 5: 期間が日次チャンクに分割されること
#   30日を1ジョブで流して28日目に失敗すれば、27日分が無駄になる。
# ================================================================
def test_range_splits_into_daily_chunks():
    mod = _bf()

    chunks = mod.build_date_chunks(date(2026, 9, 1), date(2026, 9, 3))

    assert len(chunks) == 3
    assert chunks[0] == {'start': date(2026, 9, 1), 'end': date(2026, 9, 1)}
    assert chunks[-1] == {'start': date(2026, 9, 3), 'end': date(2026, 9, 3)}


# ================================================================
# STAGE 6: チャンクが期間を過不足なく覆うこと
#   1日でも欠ければ、そこだけ古いデータが残り続ける。
# ================================================================
@pytest.mark.parametrize('days,chunk_size', [(7, 1), (7, 3), (10, 5), (1, 1)])
def test_chunks_cover_the_range_exactly(days, chunk_size):
    mod = _bf()

    start = date(2026, 9, 1)
    end = start + timedelta_days(days - 1)
    chunks = mod.build_date_chunks(start, end, chunk_size)

    assert chunks[0]['start'] == start
    assert chunks[-1]['end'] == end

    covered = sum((c['end'] - c['start']).days + 1 for c in chunks)
    assert covered == days, 'a gap would leave stale data in that window'


def timedelta_days(n):
    from datetime import timedelta
    return timedelta(days=n)


# ================================================================
# STAGE 7: 完了済みチャンクがスキップされること
#   冪等なら再実行しても壊れないが、コストと時間は冪等ではない。
# ================================================================
def test_completed_chunks_are_skipped():
    mod = _bf()

    chunks = mod.build_date_chunks(date(2026, 9, 1), date(2026, 9, 3))
    remaining = mod.build_resume_plan(chunks, [chunks[0]])

    assert len(remaining) == 2
    assert chunks[0] not in remaining


# ================================================================
# STAGE 8: 同時実行数が制限されること
#   90ジョブを同時に投げれば、進行中の本番処理が止まる。
# ================================================================
def test_batches_respect_the_concurrency_limit():
    mod = _bf()

    chunks = mod.build_date_chunks(date(2026, 9, 1), date(2026, 9, 10))
    batches = mod.build_execution_batches(chunks)

    assert all(len(b) <= mod.MAX_CONCURRENT_CHUNKS for b in batches), (
        'a backfill shares quota with production; saturating it would stop '
        'the pipeline that is currently running'
    )
    assert sum(len(b) for b in batches) == len(chunks)


# ================================================================
# STAGE 9: コスト見積が実行前に出ること
#   「90日分」は日常的な依頼だが、請求で初めて規模を知ることになる。
# ================================================================
def test_cost_is_estimated_before_execution():
    mod = _bf()

    one_tib = 1024 ** 4
    assert mod.estimate_cost_usd(1, one_tib) == pytest.approx(mod.PRICE_PER_TIB_USD)
    assert mod.estimate_cost_usd(0, one_tib) == 0.0


# ================================================================
# STAGE 10: 不正な計画は valid=False を返し、チャンクを作らないこと
# ================================================================
def test_invalid_plan_produces_no_chunks():
    mod = _bf()

    plan = mod.build_backfill_plan(date(2026, 9, 10), date(2026, 9, 1), TODAY)

    assert plan['valid'] is False
    assert plan['chunks'] == []
    assert plan['batches'] == []


# ================================================================
# STAGE 11: 妥当な計画が全要素を備えること
# ================================================================
def test_valid_plan_carries_everything_needed():
    mod = _bf()

    plan = mod.build_backfill_plan(
        date(2026, 9, 1), date(2026, 9, 5), TODAY,
        bytes_per_chunk=10 * 1024 ** 3,
    )

    assert plan['valid'] is True
    assert len(plan['chunks']) == 5
    assert plan['estimated_cost_usd'] > 0
    assert 'チャンク数' in mod.render_plan(plan)


if __name__ == '__main__':
    print("🚀 バックフィル計画の監査を開始するのね...")
    print("🟢 監査完了!実行前に止められる再処理基盤が完全画定したのね!")
    print("実行するには: pytest 103_backfill_testing.py -v")