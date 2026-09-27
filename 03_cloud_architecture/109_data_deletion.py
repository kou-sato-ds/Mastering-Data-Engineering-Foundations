"""
個人データの削除依頼と保持期限 — 預かったデータを、消せる形で持つ。

背景:
    #108 で個人情報を仮名化した。しかし「この人のデータを消してほしい」と
    依頼されたとき、仮名化されたデータから該当行を探せなければ対応できない。

    #108 のトークンは決定的(同じ値 -> 同じトークン)なので、
    同じ秘密鍵で依頼者のメールアドレスを再計算すれば、該当行を特定できる。

    本ファイルは3つを扱う:
      - 削除依頼: 依頼者の行を全て除き、除いたことを記録する
      - 監査記録: 「いつ・何件消したか」は残すが、**生の個人情報は書かない**
      - 保持期限: 期限を過ぎた行を自動で除く(#64 の90日パーティション期限と同じ思想)
"""
import importlib.util
import sys
from datetime import timedelta
from pathlib import Path

HERE = Path(__file__).parent

# 保持期間の既定値。#64 の BigQuery パーティション期限、姉妹プロジェクトの S3 Lifecycle と揃える。
DEFAULT_RETENTION_DAYS = 90


def _pii():
    """#108 の仮名化を再利用する。同じ関数を使わなければ、トークンが一致しない。"""
    name = 'pii_for_deletion'
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, HERE / '108_pii_masking.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def subject_token(email, secret):
    """削除依頼者のトークンを、#108 と同じ方法で計算する。"""
    return _pii().pseudonymize(email, secret)


def delete_subject(rows, token_column, email, secret, requested_at):
    """
    依頼者の行を全て除く。

    戻り値の監査記録にはトークンと件数だけを書く。
    削除依頼の記録に元のメールアドレスを残せば、消したはずの個人情報が
    監査ログという別の場所に残り続ける。

    同じ依頼を2回処理しても結果は変わらない(2回目は deleted=0)。
    """
    token = subject_token(email, secret)
    kept = [r for r in rows if r.get(token_column) != token]
    audit = {
        'subject_token': token,
        'deleted': len(rows) - len(kept),
        'requested_at': requested_at.isoformat(),
    }
    return kept, audit


def verify_deleted(rows, token_column, email, secret):
    """削除後に、依頼者の行が1件も残っていないことを確かめる。"""
    token = subject_token(email, secret)
    return not any(r.get(token_column) == token for r in rows)


def apply_retention(rows, ts_column, now, days=DEFAULT_RETENTION_DAYS):
    """
    保持期限を過ぎた行を除く。

    境界は「now - days ちょうど」の行を **残す**。
    1日早く消す誤りは取り返しがつかないが、1日遅く消す誤りは次回で直る。

    時刻が無い行は残す。判定できないものを消せば、必要なデータまで失う。
    その件数は戻り値で報告する——黙って残し続ければ、期限の無いデータが溜まる。
    """
    cutoff = now - timedelta(days=days)
    kept, expired, undated = [], 0, 0

    for r in rows:
        ts = r.get(ts_column)
        if ts is None:
            kept.append(r)
            undated += 1
        elif ts >= cutoff:
            kept.append(r)
        else:
            expired += 1

    return kept, {'expired': expired, 'undated': undated, 'cutoff': cutoff.isoformat()}