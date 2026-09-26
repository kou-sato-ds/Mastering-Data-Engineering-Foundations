"""
個人情報(PII)の仮名化とマスキング — 分析には使えるが、生では持たない。

背景:
    分析基盤に顧客のメールアドレスや電話番号がそのまま入ると、
    アクセスできる全員が個人情報を見られる状態になる。
    かといって列ごと削除すれば、「同じ顧客の購買を束ねる」分析ができなくなる。

    本ファイルは列ごとに処理を宣言する:
      - pseudonymize : 秘密鍵付き HMAC で置き換える。同じ人は同じトークンになり JOIN できる
      - mask         : 一部を伏せて表示用に残す
      - drop         : 列ごと捨てる
      - keep         : そのまま通す (個人情報でないと判断した列)

    単純な SHA-256 ハッシュを使わない理由:
        メールアドレスは推測可能な値の集合であり、候補を片端からハッシュすれば
        元の値を特定できる(辞書攻撃)。秘密鍵が無ければ再計算できない HMAC にする。
"""
import hashlib
import hmac
import re

ACTIONS = {'pseudonymize', 'mask', 'drop', 'keep'}

EMAIL_PATTERN = re.compile(r'[\w.+-]+@[\w-]+\.[\w.-]+')
PHONE_PATTERN = re.compile(r'0\d{1,4}-?\d{1,4}-?\d{3,4}')


def pseudonymize(value, secret):
    """
    秘密鍵付き HMAC で決定的なトークンに置き換える。

    同じ値は常に同じトークンになるため、仮名化後も JOIN や重複排除ができる。
    秘密鍵が空なら拒否する——鍵なしの HMAC は単純ハッシュと変わらない。
    """
    if not secret:
        raise ValueError('a non-empty secret is required; without it the token can be reversed by guessing')
    if value is None:
        return None
    digest = hmac.new(secret.encode(), str(value).strip().lower().encode(), hashlib.sha256)
    return 'pii_' + digest.hexdigest()[:24]


def mask_email(value):
    """先頭1文字とドメインだけ残す。問い合わせ対応などで「誰のことか」の手がかりに使う。"""
    if not value or '@' not in value:
        return value
    local, domain = value.split('@', 1)
    return f'{local[:1]}***@{domain}'


def mask_phone(value):
    """末尾4桁だけ残す。"""
    if not value:
        return value
    digits = re.sub(r'\D', '', value)
    return '*' * max(len(digits) - 4, 0) + digits[-4:]


def mask_value(column, value):
    """列の種類に応じたマスキング。未知の列は全て伏せる。"""
    if 'email' in column:
        return mask_email(value)
    if 'phone' in column or 'tel' in column:
        return mask_phone(value)
    return '***' if value else value


def find_pii_in_text(text):
    """
    自由記述の中に紛れた個人情報を検出する。

    問い合わせ本文やメモ欄は「個人情報の列」として宣言されないまま、
    メールアドレスや電話番号を含むことが多い。
    """
    if not text:
        return []
    return EMAIL_PATTERN.findall(text) + PHONE_PATTERN.findall(text)


def validate_policy(columns, policy):
    """
    全ての列に処理が宣言されているか検証する。

    ポリシーに無い列を黙って通せば、上流が列を追加した瞬間に
    個人情報がそのまま分析基盤へ流れ込む。**知らない列は通さない。**
    """
    errors = []
    missing = sorted(set(columns) - set(policy))
    if missing:
        errors.append(f'columns without a declared action: {missing}')
    unknown = sorted({a for a in policy.values() if a not in ACTIONS})
    if unknown:
        errors.append(f'unknown actions: {unknown}')
    return errors


def apply_policy(row, policy, secret):
    """1行にポリシーを適用する。ポリシーに不備があれば処理しない(fail closed)。"""
    errors = validate_policy(row.keys(), policy)
    if errors:
        raise ValueError('; '.join(errors))

    result = {}
    for column, value in row.items():
        action = policy[column]
        if action == 'drop':
            continue
        if action == 'pseudonymize':
            result[column] = pseudonymize(value, secret)
        elif action == 'mask':
            result[column] = mask_value(column, value)
        else:
            result[column] = value
    return result


def audit_kept_text(rows, policy):
    """keep 指定の列に、個人情報らしき文字列が残っていないか報告する。"""
    findings = []
    for i, row in enumerate(rows):
        for column, value in row.items():
            if policy.get(column) == 'keep' and isinstance(value, str):
                hits = find_pii_in_text(value)
                if hits:
                    findings.append({'row': i, 'column': column, 'count': len(hits)})
    return findings