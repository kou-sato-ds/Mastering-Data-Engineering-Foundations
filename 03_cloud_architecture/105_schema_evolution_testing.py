"""
#105 スキーマ進化の検証。

🎯 【壊れる変更を人間の判断に委ねない】機械的に区別する!

実行方法:
    pytest 105_schema_evolution_testing.py -v
"""
import importlib.util
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent


def load_module_from_path(filename: str, module_name: str):
    """#71/#80-#104 と同一の動的ローダー。"""
    path = HERE / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        pytest.skip(f"cannot build spec for {filename}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _se():
    return load_module_from_path('105_schema_evolution.py', 'schema_evolution_mod')


BASE = [
    {'name': 'event_id', 'type': 'STRING', 'mode': 'REQUIRED'},
    {'name': 'user_id', 'type': 'STRING', 'mode': 'NULLABLE'},
    {'name': 'score', 'type': 'INTEGER', 'mode': 'NULLABLE'},
]


# ================================================================
# STAGE 1: 列の追加が後方互換と判定されること
# ================================================================
def test_added_column_is_compatible():
    mod = _se()

    new = BASE + [{'name': 'channel', 'type': 'STRING', 'mode': 'NULLABLE'}]
    decision = mod.decide_migration(BASE, new)

    assert decision['action'] == 'allow'
    assert any('added column channel' in c for c in decision['compatible'])


# ================================================================
# STAGE 2: 列の削除が破壊的と判定されること ← 本ファイルの核心
#   その列を参照するクエリが全て落ちる。
# ================================================================
def test_removed_column_is_breaking():
    mod = _se()

    new = [f for f in BASE if f['name'] != 'score']
    decision = mod.decide_migration(BASE, new)

    assert decision['action'] == 'review'
    assert any('removed column score' in b for b in decision['breaking'])


# ================================================================
# STAGE 3: 型の緩和が後方互換と判定されること
# ================================================================
@pytest.mark.parametrize('old_type,new_type', [
    ('INTEGER', 'FLOAT'),
    ('INTEGER', 'NUMERIC'),
    ('DATE', 'TIMESTAMP'),
    ('NUMERIC', 'BIGNUMERIC'),
])
def test_type_widening_is_compatible(old_type, new_type):
    mod = _se()

    assert mod.is_type_widening(old_type, new_type) is True


# ================================================================
# STAGE 4: 型の厳格化が破壊的と判定されること
# ================================================================
@pytest.mark.parametrize('old_type,new_type', [
    ('FLOAT', 'INTEGER'),
    ('STRING', 'INTEGER'),
    ('TIMESTAMP', 'DATE'),
])
def test_type_narrowing_is_breaking(old_type, new_type):
    mod = _se()

    assert mod.is_type_widening(old_type, new_type) is False


# ================================================================
# STAGE 5: 未知の型遷移は危険とみなすこと
#   許可リスト方式にする理由——禁止リストでは新しい型が
#   自動的に「安全」と判定されてしまう。
# ================================================================
def test_unknown_type_transition_is_treated_as_unsafe():
    mod = _se()

    assert mod.is_type_widening('GEOGRAPHY', 'STRING') is False, (
        'an allow-list must reject what it does not know; a deny-list would '
        'silently approve any newly introduced type'
    )


# ================================================================
# STAGE 6: REQUIRED -> NULLABLE は安全、逆は破壊的であること
#   既存の NULL が REQUIRED 制約に違反する。
# ================================================================
def test_mode_relaxation_is_safe_but_tightening_is_not():
    mod = _se()

    assert mod.is_mode_relaxation('REQUIRED', 'NULLABLE') is True
    assert mod.is_mode_relaxation('NULLABLE', 'REQUIRED') is False


# ================================================================
# STAGE 7: モード厳格化が review を要求すること
# ================================================================
def test_tightening_mode_requires_review():
    mod = _se()

    new = [
        {**f, 'mode': 'REQUIRED'} if f['name'] == 'user_id' else f
        for f in BASE
    ]
    decision = mod.decide_migration(BASE, new)

    assert decision['action'] == 'review'
    assert any('existing NULLs' in b for b in decision['breaking'])


# ================================================================
# STAGE 8: 追加された列がバックフィル対象として返ること
#   「追加は安全」で終わらせると、過去1年がNULLの列が生まれる。
# ================================================================
def test_added_columns_are_flagged_for_backfill():
    mod = _se()

    new = BASE + [{'name': 'channel', 'type': 'STRING', 'mode': 'NULLABLE'}]
    decision = mod.decide_migration(BASE, new)

    assert decision['backfill_required'] == ['channel'], (
        'an added column is empty for all historical rows; without a backfill '
        'the column is NULL for the entire past'
    )


# ================================================================
# STAGE 9: 変更が無ければ allow かつ空であること
# ================================================================
def test_identical_schema_produces_no_changes():
    mod = _se()

    decision = mod.decide_migration(BASE, BASE)

    assert decision['action'] == 'allow'
    assert decision['compatible'] == []
    assert decision['breaking'] == []
    assert decision['backfill_required'] == []


# ================================================================
# STAGE 10: 安全な変更と破壊的変更が混在しても review になること
#   1つでも破壊的なら止める——安全な変更に紛れて通してはいけない。
# ================================================================
def test_mixed_changes_require_review():
    mod = _se()

    new = [f for f in BASE if f['name'] != 'score']
    new.append({'name': 'channel', 'type': 'STRING', 'mode': 'NULLABLE'})
    decision = mod.decide_migration(BASE, new)

    assert decision['action'] == 'review'
    assert decision['compatible'], 'the safe change must still be reported'
    assert decision['breaking']


# ================================================================
# STAGE 11: 出力に次の行動が書かれること
# ================================================================
def test_rendered_decision_points_to_the_backfill_plan():
    mod = _se()

    new = BASE + [{'name': 'channel', 'type': 'STRING', 'mode': 'NULLABLE'}]
    text = mod.render_decision(mod.decide_migration(BASE, new))

    assert '#103' in text, (
        'stating that a backfill is needed without naming the tool leaves '
        'the operator to find it'
    )


if __name__ == '__main__':
    print("🚀 スキーマ進化の監査を開始するのね...")
    print("🟢 監査完了!破壊的変更が人間の承認を要求する基盤が完全画定したのね!")
    print("実行するには: pytest 105_schema_evolution_testing.py -v")