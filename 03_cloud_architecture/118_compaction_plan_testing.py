"""
#118 コンパクション計画の検証。
"""
import importlib.util
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).parent
NOW = datetime(2026, 10, 7, 21, 0, tzinfo=timezone.utc)
OLD = NOW - timedelta(hours=5)
MB = 1024 * 1024


def _mod():
    path = HERE / '118_compaction_plan.py'
    spec = importlib.util.spec_from_file_location('compaction_mod', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules['compaction_mod'] = module
    spec.loader.exec_module(module)
    return module


def _f(mod, name, partition='dt=2026-10-06', mb=1, modified=OLD):
    return mod.FileInfo(path=name, partition=partition, size_bytes=mb * MB, modified_at=modified)


def test_small_files_in_one_partition_are_merged():
    mod = _mod()
    plan = mod.plan_compaction([_f(mod, f'p{i}') for i in range(10)], NOW)
    assert len(plan) == 1
    assert len(plan[0].paths) == 10


def test_partitions_are_never_mixed():
    """混ぜれば、日付による絞り込み(#64)が効かなくなる。"""
    mod = _mod()
    files = [_f(mod, f'a{i}', 'dt=2026-10-05') for i in range(3)] + \
            [_f(mod, f'b{i}', 'dt=2026-10-06') for i in range(3)]
    plan = mod.plan_compaction(files, NOW)
    assert len(plan) == 2
    assert all(len({p[0] for p in b.paths}) == 1 for b in plan)


def test_recent_files_are_left_alone():
    """書き込み直後のファイルは、遅れて届くデータと衝突する。"""
    mod = _mod()
    files = [_f(mod, f'n{i}', modified=NOW - timedelta(minutes=10)) for i in range(5)]
    assert mod.plan_compaction(files, NOW) == []


def test_large_files_are_not_touched():
    mod = _mod()
    assert mod.plan_compaction([_f(mod, f'big{i}', mb=200) for i in range(3)], NOW) == []


def test_single_small_file_is_not_a_batch():
    """1個だけでは、まとめても数が減らない。"""
    mod = _mod()
    assert mod.plan_compaction([_f(mod, 'only')], NOW) == []


def test_batches_respect_the_target_size():
    mod = _mod()
    plan = mod.plan_compaction([_f(mod, f'm{i}', mb=30) for i in range(10)], NOW)
    assert all(b.total_bytes <= mod.TARGET_SIZE for b in plan)
    assert sum(len(b.paths) for b in plan) == 10


def test_plan_is_deterministic():
    mod = _mod()
    files = [_f(mod, f'x{i}', mb=(i % 5) + 1) for i in range(20)]
    assert mod.plan_compaction(files, NOW) == mod.plan_compaction(list(reversed(files)), NOW)


def test_summary_counts_the_reduction():
    mod = _mod()
    files = [_f(mod, f'p{i}') for i in range(10)] + [_f(mod, 'big', mb=200)]
    s = mod.summarize(files, mod.plan_compaction(files, NOW))
    assert s == {'files_before': 11, 'files_after': 2, 'reduced_by': 9}


def test_this_file_passes_the_type_hint_ratchet():
    """#117 のラチェット: 新しいファイルは公開関数100%型付き。"""
    spec = importlib.util.spec_from_file_location('audit_for_118', HERE / '117_type_hint_audit.py')
    audit = importlib.util.module_from_spec(spec)
    sys.modules['audit_for_118'] = audit
    spec.loader.exec_module(audit)
    assert audit.audit_file(HERE / '118_compaction_plan.py')['missing'] == []