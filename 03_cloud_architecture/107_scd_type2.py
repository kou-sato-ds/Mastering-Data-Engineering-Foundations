"""
SCD Type 2 — ディメンションの変化を履歴として残す。

背景:
    顧客の地域が「関東」から「関西」に変わったとき、単純に上書き(Type 1)すると、
    **過去の売上まで関西の売上として集計される**。
    分析結果は静かに書き換わり、誰もエラーに気づかない。

    SCD Type 2 は、変化のたびに古い行を閉じ(valid_to を設定)、新しい行を開く。
    「その時点で何が正しかったか」を後から引けるようにする。

    ただし全ての列を履歴化すると行数が膨らむ(TCO)。
    履歴化する列(tracked)と、上書きでよい列(誤字修正など)を分ける。

    姉妹プロジェクト stat-learning-data-pipeline の Star Schema と同じ文脈の論点である。
"""


def _new_version(row, as_of):
    """新しい現行行を作る。valid_to=None は「まだ有効」を意味する。"""
    version = dict(row)
    version['valid_from'] = as_of
    version['valid_to'] = None
    version['is_current'] = True
    return version


def has_changed(old, new, tracked):
    """履歴化対象の列が1つでも変わったか。"""
    return any(old.get(c) != new.get(c) for c in tracked)


def apply_scd2(dimension, incoming, key, tracked, as_of):
    """
    取り込みデータをディメンションへ SCD Type 2 で反映する。

    - 新しいキー            -> 現行行として追加
    - tracked 列が変化      -> 古い行を閉じ、新しい行を追加
    - tracked 以外だけ変化  -> 現行行を上書き (Type 1)
    - 変化なし              -> 何もしない (同じ取り込みを何度流しても結果が変わらない)

    入力の dimension は変更しない。呼び出し側の状態を黙って書き換えれば、
    失敗時にどこまで反映されたか分からなくなる。
    """
    result = [dict(r) for r in dimension]
    current = {r[key]: r for r in result if r['is_current']}

    for row in incoming:
        existing = current.get(row[key])

        if existing is None:
            version = _new_version(row, as_of)
            result.append(version)
            current[row[key]] = version
            continue

        if has_changed(existing, row, tracked):
            existing['valid_to'] = as_of
            existing['is_current'] = False
            version = _new_version(row, as_of)
            result.append(version)
            current[row[key]] = version
            continue

        for column, value in row.items():
            if column not in tracked:
                existing[column] = value

    return result


def lookup_as_of(dimension, key, value, ts):
    """
    ある時点で有効だった行を返す。

    valid_from <= ts < valid_to の半開区間で判定する。
    両端を閉区間にすると、切り替わりの瞬間に2行が同時に該当する。
    """
    for row in dimension:
        if row[key] != value:
            continue
        if row['valid_from'] <= ts and (row['valid_to'] is None or ts < row['valid_to']):
            return row
    return None