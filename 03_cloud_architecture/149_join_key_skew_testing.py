"""#149 結合キーの偏り検知の検証。全 1000 行・10 パーティション(平均 100 行)。"""
import importlib.util
import sys
import zlib
from pathlib import Path

import pytest

HERE = Path(__file__).parent


def _mod():
    spec = importlib.util.spec_from_file_location('skew_mod', HERE / '149_join_key_skew.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules['skew_mod'] = module
    spec.loader.exec_module(module)
    return module


def test_evenly_spread_keys_have_no_hot_key():
    mod = _mod()
    report = mod.skew_report([i % 100 for i in range(1000)], 10)
    assert report.ok
    assert report.imbalance < 3


def test_dominant_key_is_reported_with_its_share():
    """全注文の6割が1社。"""
    mod = _mod()
    report = mod.skew_report(['big'] * 600 + list(range(400)), 10)
    assert report.hot_keys == [('big', 600, 0.6)]


def test_dominant_key_makes_one_partition_heavy():
    """他の作業が終わっても、1つだけが平均の6倍以上かかる。"""
    mod = _mod()
    report = mod.skew_report(['big'] * 600 + list(range(400)), 10)
    assert report.imbalance >= 6


def test_salt_factor_spreads_the_hot_key_to_average_weight():
    """600 行を平均 100 行ずつにするには、6個に分ける。"""
    mod = _mod()
    report = mod.skew_report(['big'] * 600 + list(range(400)), 10)
    assert report.salt_factors == {'big': 6}


def test_null_keys_are_a_classic_hot_key():
    """未ログインのアクセスが全部 NULL なら、全部1か所に集まる。"""
    mod = _mod()
    report = mod.skew_report([None] * 300 + list(range(700)), 10)
    assert report.hot_keys == [(None, 300, 0.3)]


def test_partitioning_is_stable_across_runs():
    """hash() は実行ごとに変わる。crc32 なら毎回同じ。"""
    mod = _mod()
    assert mod.partition_of('abc', 8) == zlib.crc32(repr('abc').encode('utf-8')) % 8


def test_no_rows_is_fine():
    mod = _mod()
    report = mod.skew_report([], 4)
    assert report.ok and report.imbalance == 1.0 and report.partition_loads == [0, 0, 0, 0]


def test_invalid_settings_stop():
    mod = _mod()
    with pytest.raises(ValueError, match='partitions'):
        mod.skew_report([1], 0)
    with pytest.raises(ValueError, match='hot_share'):
        mod.skew_report([1], 4, hot_share=0)


def test_this_file_passes_the_type_hint_ratchet():
    spec = importlib.util.spec_from_file_location('audit_for_149', HERE / '117_type_hint_audit.py')
    audit = importlib.util.module_from_spec(spec)
    sys.modules['audit_for_149'] = audit
    spec.loader.exec_module(audit)
    assert audit.audit_file(HERE / '149_join_key_skew.py')['missing'] == []
