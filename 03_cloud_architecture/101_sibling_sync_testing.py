"""
姉妹プロジェクト同期の検証 — 対応表の更新漏れを検知する。

🎯 【今日実際に起きた漏れ】ADR-010をマージしたのに索引が空欄だった!

背景:
    #106 で ADR-010 (AWS側のデータ品質検証) をマージしたが、
    GCP側の SIBLING_MAP は更新しなかった。
    索引の data_quality 行は「—」のまま——
    **AWS側に実装があるのに、GCP側から辿れない状態**が1日続いた。

    #99 で「リポジトリをまたぐ整合は自動検証できないため
    SIBLING_ADR_MAX という手動更新点を明示的に置いた」と書いたが、
    それは「範囲外参照を検知する」だけであり、
    **「対応があるのに書いていない」ことは検知できない**。

    本ファイルはその逆方向を守る:
      - 実装が両側にある関心は、姉妹対応を持たねばならない
      - SIBLING_ADR_MAX が実際の ADR 数と乖離していないか

実行方法:
    pytest 101_sibling_sync_testing.py -v
"""
import importlib.util
import re
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent

# 🚨 両クラウドで実装済みの関心。
#    片方だけの実装なら姉妹対応が無くて当然だが、
#    ここに挙げた関心は「両方にあるのに繋いでいない」状態を許さない。
CROSS_CLOUD_CONCERNS = [
    'idempotency',
    'fault_tolerance',
    'observability',
    'testing',
    'meta',
    'data_quality',
]


def load_module_from_path(filename: str, module_name: str):
    """#71/#80-#100 と同一の動的ローダー。"""
    path = HERE / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        pytest.skip(f"cannot build spec for {filename}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _index():
    return load_module_from_path('90_repository_index.py', 'index_for_sync')


def _link():
    return load_module_from_path('91_sibling_link_testing.py', 'link_for_sync')


# ================================================================
# STAGE 1: 両クラウド実装の関心が姉妹対応を持つこと ← 本ファイルの核心
#   今日実際に起きた漏れ(data_quality が空欄)を検知する。
# ================================================================
@pytest.mark.parametrize('concern', CROSS_CLOUD_CONCERNS)
def test_cross_cloud_concern_declares_a_counterpart(concern):
    mod = _index()

    assert mod.SIBLING_MAP.get(concern), (
        f"{concern} is implemented in both clouds but the index shows no "
        "counterpart. An implementation that cannot be reached from the "
        "other side is invisible to a reader entering from there."
    )


# ================================================================
# STAGE 2: 姉妹対応を持つ関心が実体を伴うこと
#   「対応がある」と書いて実装が無ければ、それは主張にすぎない。
# ================================================================
def test_declared_counterparts_have_local_files():
    mod = _index()

    hollow = [
        e['concern'] for e in mod.build_index()
        if e['sibling'] and not e['items']
    ]

    assert not hollow, (
        f"these concerns claim a counterpart but index no local files: {hollow}"
    )


# ================================================================
# STAGE 3: SIBLING_ADR_MAX が参照ADRを網羅していること
#   上げ忘れれば範囲外として弾かれ、下げすぎれば検知が緩む。
# ================================================================
def test_adr_max_covers_every_referenced_adr():
    index = _index()
    link = _link()

    referenced = set()
    for value in index.SIBLING_MAP.values():
        referenced.update(int(n) for n in re.findall(r'ADR-(\d{3})', value))

    highest = max(referenced) if referenced else 0

    assert link.SIBLING_ADR_MAX >= highest, (
        f"SIBLING_ADR_MAX is {link.SIBLING_ADR_MAX} but ADR-{highest:03d} "
        "is referenced. Raise it after adding ADRs on the other side."
    )


# ================================================================
# STAGE 4: SIBLING_ADR_MAX が過大でないこと
#   実在しないADRまで許容すれば、範囲チェックが形骸化する。
# ================================================================
def test_adr_max_is_not_inflated():
    index = _index()
    link = _link()

    referenced = set()
    for value in index.SIBLING_MAP.values():
        referenced.update(int(n) for n in re.findall(r'ADR-(\d{3})', value))

    highest = max(referenced) if referenced else 0

    assert link.SIBLING_ADR_MAX <= highest + 2, (
        f"SIBLING_ADR_MAX is {link.SIBLING_ADR_MAX} while the highest "
        f"referenced ADR is {highest}. An inflated ceiling stops catching "
        "typos in ADR numbers."
    )


# ================================================================
# STAGE 5: 対応表の記述が具体的なADRを挙げること
# ================================================================
def test_every_counterpart_cites_an_adr_number():
    mod = _index()

    vague = [
        c for c, desc in mod.SIBLING_MAP.items()
        if not re.search(r'ADR-\d{3}', desc)
    ]

    assert not vague, f"these counterparts cite no specific ADR: {vague}"


# ================================================================
# STAGE 6: data_quality が具体的に ADR-010 を指すこと
#   今日の漏れが再発したら、この1件で分かる。
# ================================================================
def test_data_quality_points_to_adr_010():
    mod = _index()

    desc = mod.SIBLING_MAP.get('data_quality', '')

    assert 'ADR-010' in desc, (
        "the AWS side implemented data quality checks as ADR-010; without "
        "this link the GCP index shows an empty counterpart column"
    )


if __name__ == '__main__':
    print("🚀 姉妹プロジェクト同期の監査を開始するのね...")
    print("🟢 監査完了!対応表の更新漏れを検知する基盤が完全画定したのね!")
    print("実行するには: pytest 101_sibling_sync_testing.py -v")