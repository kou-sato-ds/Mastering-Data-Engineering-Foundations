"""
データ契約(Data Contract) — 渡す側と受ける側の約束を、コードで持つ。

背景:
    受託で一番揉めるのは技術ではなく責任の境界である。
    「データが壊れていたのは、渡した側か、受けた側か」。
    口頭やメールの約束は、問題が起きたときに解釈が割れる。

    本ファイルは約束を契約として宣言し、受け取る瞬間に判定する:
      - 必須列の欠落・型違い・鮮度切れ -> 受け取り拒否(reject)
      - 契約に無い列の追加             -> 警告だけ(#105 と同じく追加は後方互換)
      - 拒否理由には契約の owner を必ず載せる -> 誰に連絡すべきかが分かる
"""
from datetime import timedelta

TYPE_CHECKS = {
    'string': lambda v: isinstance(v, str),
    'integer': lambda v: isinstance(v, int) and not isinstance(v, bool),
    'number': lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    'boolean': lambda v: isinstance(v, bool),
}


def validate_contract(contract):
    """
    契約そのものの不備を返す。

    owner が無い契約は契約として認めない。
    違反を見つけても、誰に伝えればよいか分からなければ直らない。
    """
    errors = []
    for key in ('name', 'version', 'owner', 'fields', 'freshness_hours'):
        if not contract.get(key):
            errors.append(f'contract is missing {key}')
    unknown = sorted({f['type'] for f in contract.get('fields', {}).values()} - set(TYPE_CHECKS))
    if unknown:
        errors.append(f'unknown field types: {unknown}')
    return errors


def check_row(contract, row):
    """1行を契約と照合し、(違反, 警告) を返す。"""
    violations, warnings = [], []
    fields = contract['fields']

    for name, spec in fields.items():
        value = row.get(name)
        if value is None:
            if spec.get('required'):
                violations.append(f'{name} is required')
            continue
        if not TYPE_CHECKS[spec['type']](value):
            violations.append(f'{name} should be {spec["type"]}, got {type(value).__name__}')

    extra = sorted(set(row) - set(fields))
    if extra:
        warnings.append(f'fields not in the contract: {extra}')

    return violations, warnings


def check_delivery(contract, rows, delivered_at, now):
    """
    受け渡し1回分を判定する。

    鮮度切れは行の中身が正しくても拒否する。
    古いデータを正しく処理しても、古い結果を配るだけである。
    """
    contract_errors = validate_contract(contract)
    if contract_errors:
        return {'decision': 'reject', 'reasons': contract_errors, 'warnings': [], 'contact': None}

    reasons, warnings = [], []

    if not rows:
        reasons.append('delivery contains no rows')

    if now - delivered_at > timedelta(hours=contract['freshness_hours']):
        reasons.append(f"data is older than the promised {contract['freshness_hours']} hours")

    for i, row in enumerate(rows):
        v, w = check_row(contract, row)
        reasons += [f'row {i}: {m}' for m in v]
        warnings += [f'row {i}: {m}' for m in w]

    return {
        'decision': 'reject' if reasons else 'accept',
        'reasons': reasons,
        'warnings': sorted(set(warnings)),
        'contact': contract['owner'],
    }


def render_notice(contract, result):
    """拒否時に渡す側へ送る連絡文。誰に・何が・どの約束に反したかを1通で伝える。"""
    if result['decision'] == 'accept':
        return f"{contract['name']} v{contract['version']}: 受領しました。"
    lines = [f"{result['contact']} 様", f"{contract['name']} v{contract['version']} の受け渡しで、契約との不一致がありました。"]
    lines += [f'- {r}' for r in result['reasons'][:10]]
    return '\n'.join(lines)