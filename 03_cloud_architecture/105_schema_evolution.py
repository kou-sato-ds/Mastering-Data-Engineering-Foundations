"""
スキーマ進化の設計 — 列が増えた/型が変わったときにどうするか。

🎯 【#105で検知した後の話】ドリフトを見つけた。次は「進化させる」!

背景:
    #97 でスキーマドリフトの **検知** は実装した。
    しかし「検知した後どうするか」が空白のままである。

    実務で頻発するのは以下の4パターンであり、それぞれ対処が異なる:

      1. 列の追加     -> 後方互換。既存クエリは壊れない
      2. 列の削除     -> 破壊的。その列を参照するクエリが全て落ちる
      3. 型の緩和     -> 後方互換 (INTEGER -> FLOAT, NULLABLE化)
      4. 型の厳格化   -> 破壊的 (NULLABLE -> REQUIRED, FLOAT -> INTEGER)

    重要なのは **「壊れる変更」と「壊れない変更」を機械的に区別する**ことである。
    人間の判断に委ねれば、金曜夕方のデプロイで本番が止まる。

    そして破壊的変更を通す場合、#103 のバックフィルが必要になる——
    新しい列を追加しても、過去データは空のままだからである。

実行方法:
    pytest 105_schema_evolution_testing.py -v
"""

# 🛡️ BigQuery の型互換性。キーが現行型、値が「安全に変更できる型」の集合。
#    ここに無い遷移は全て破壊的とみなす——迷ったら破壊的に倒す。
SAFE_TYPE_WIDENING = {
    'INTEGER': {'INTEGER', 'FLOAT', 'NUMERIC', 'BIGNUMERIC'},
    'FLOAT': {'FLOAT'},
    'NUMERIC': {'NUMERIC', 'BIGNUMERIC', 'FLOAT'},
    'DATE': {'DATE', 'DATETIME', 'TIMESTAMP'},
    'DATETIME': {'DATETIME', 'TIMESTAMP'},
    'STRING': {'STRING'},
    'BOOLEAN': {'BOOLEAN'},
    'TIMESTAMP': {'TIMESTAMP'},
}

# 🚨 モード遷移の安全性。REQUIRED -> NULLABLE は緩和なので安全、逆は破壊的。
SAFE_MODE_TRANSITIONS = {
    ('REQUIRED', 'NULLABLE'),
    ('REQUIRED', 'REQUIRED'),
    ('NULLABLE', 'NULLABLE'),
}


def _field_map(schema: list) -> dict:
    """スキーマを name -> field の辞書に変換する。"""
    return {f['name']: f for f in schema}


def is_type_widening(old_type: str, new_type: str) -> bool:
    """
    🔍 型変更が後方互換かを判定する純粋関数。

    未知の遷移は False を返す——**知らない変更は危険とみなす**。
    許可リスト方式にするのは、禁止リストでは新しい型が追加されたとき
    自動的に「安全」と判定されてしまうためである。
    """
    return new_type in SAFE_TYPE_WIDENING.get(old_type, set())


def is_mode_relaxation(old_mode: str, new_mode: str) -> bool:
    """🔍 モード変更が後方互換かを判定する。"""
    return (old_mode, new_mode) in SAFE_MODE_TRANSITIONS


def diff_schemas(old: list, new: list) -> dict:
    """
    📊 新旧スキーマの差分を分類する。

    'added' / 'removed' / 'type_changed' / 'mode_changed' に分けて返す——
    まとめて「変更あり」とすると、安全な追加と破壊的な削除が同列になる。
    """
    old_map = _field_map(old)
    new_map = _field_map(new)

    added = sorted(set(new_map) - set(old_map))
    removed = sorted(set(old_map) - set(new_map))

    type_changed = []
    mode_changed = []

    for name in sorted(set(old_map) & set(new_map)):
        o, n = old_map[name], new_map[name]
        if o.get('type') != n.get('type'):
            type_changed.append({
                'name': name, 'from': o.get('type'), 'to': n.get('type'),
            })
        if o.get('mode', 'NULLABLE') != n.get('mode', 'NULLABLE'):
            mode_changed.append({
                'name': name,
                'from': o.get('mode', 'NULLABLE'),
                'to': n.get('mode', 'NULLABLE'),
            })

    return {
        'added': added,
        'removed': removed,
        'type_changed': type_changed,
        'mode_changed': mode_changed,
    }


def classify_changes(diff: dict) -> dict:
    """
    🎯 差分を「後方互換」と「破壊的」に分類する。

    この分類が本ファイルの中核である。
    人間の判断に委ねれば、金曜夕方のデプロイで本番が止まる。
    """
    compatible = []
    breaking = []

    for name in diff['added']:
        compatible.append(f'added column {name}')

    for name in diff['removed']:
        breaking.append(
            f'removed column {name}: every query referencing it will fail'
        )

    for change in diff['type_changed']:
        message = f"{change['name']}: {change['from']} -> {change['to']}"
        if is_type_widening(change['from'], change['to']):
            compatible.append(f'widened type {message}')
        else:
            breaking.append(f'narrowed type {message}')

    for change in diff['mode_changed']:
        message = f"{change['name']}: {change['from']} -> {change['to']}"
        if is_mode_relaxation(change['from'], change['to']):
            compatible.append(f'relaxed mode {message}')
        else:
            breaking.append(
                f'tightened mode {message}: existing NULLs would violate it'
            )

    return {'compatible': compatible, 'breaking': breaking}


def needs_backfill(diff: dict) -> list:
    """
    🔁 バックフィルが必要な列を返す。

    列を追加しても過去データは空のままである——
    「追加は安全」で終わらせると、**過去1年が NULL の列**が生まれる。
    #103 のバックフィル計画へ繋ぐための出力。
    """
    return list(diff['added'])


def decide_migration(old: list, new: list) -> dict:
    """
    📋 移行可否と必要な後続作業を判定する。

    'allow'  : そのまま適用してよい
    'review' : 破壊的変更を含む。人間の承認が要る

    例外を投げないのは #97 と同じ思想——
    判断材料を返し、止めるかどうかは呼び出し側が決める。
    """
    diff = diff_schemas(old, new)
    classified = classify_changes(diff)

    return {
        'action': 'review' if classified['breaking'] else 'allow',
        'compatible': classified['compatible'],
        'breaking': classified['breaking'],
        'backfill_required': needs_backfill(diff),
    }


def render_decision(decision: dict) -> str:
    """判定結果を人間が読める形で出力する。"""
    lines = [f"判定: {decision['action']}"]

    if decision['breaking']:
        lines.append('破壊的変更:')
        lines += [f"  - {b}" for b in decision['breaking']]
    if decision['compatible']:
        lines.append('後方互換な変更:')
        lines += [f"  - {c}" for c in decision['compatible']]
    if decision['backfill_required']:
        lines.append(
            f"バックフィル対象: {decision['backfill_required']} "
            "(#103 の計画を使う)"
        )

    return '\n'.join(lines)


if __name__ == '__main__':
    print("🚀 スキーマ進化の監査を開始するのね...")
    print("🟢 監査完了!壊れる変更と壊れない変更を機械的に区別する基盤が完全画定したのね!")