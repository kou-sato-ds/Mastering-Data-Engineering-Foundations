"""
データ突合(Reconciliation) — 「全件ちゃんと合っていますか」に答える。

背景:
    移行や連携の最後に必ず聞かれるのが「全件合っていますか」である。
    件数だけ数えて「合っています」と答えるのは危ない:
      - 件数は同じでも、1件欠けて別の1件が二重に入っていれば件数は一致する
      - 件数もキーも同じでも、金額の列が丸められていれば合計が合わない

    本ファイルは移行元と移行先を3段で照らす:
      1. 件数
      2. キーの過不足と、移行先の重複
      3. 指定した数値列の合計
"""
from collections import Counter

# 不一致の例として出す最大件数。全件並べても人は読めない。
SAMPLE_LIMIT = 5


def _keys(rows, key):
    return [r[key] for r in rows]


def compare_keys(source, target, key):
    """移行先に無いキー、移行先にだけあるキー、移行先で重複したキーを返す。"""
    src = set(_keys(source, key))
    tgt_list = _keys(target, key)
    tgt = set(tgt_list)
    dup = sorted(k for k, c in Counter(tgt_list).items() if c > 1)
    return {
        'missing': sorted(src - tgt),
        'unexpected': sorted(tgt - src),
        'duplicated': dup,
    }


def compare_totals(source, target, measures, tolerance=0.0):
    """
    数値列の合計を比べ、差が許容範囲を超えた列を返す。

    金額は丸め誤差が出ないよう整数(円・セント)で持つのが原則である。
    小数で持つ列だけ tolerance を使う。
    """
    diffs = {}
    for m in measures:
        s = sum(r.get(m) or 0 for r in source)
        t = sum(r.get(m) or 0 for r in target)
        if abs(s - t) > tolerance:
            diffs[m] = {'source': s, 'target': t, 'diff': t - s}
    return diffs


def reconcile(source, target, key, measures, tolerance=0.0):
    """
    3段の照合をまとめて行い、'match' か 'mismatch' を返す。

    件数が一致しても、キーや合計がずれていれば mismatch とする。
    件数だけで合格にすれば、欠落と重複が打ち消し合ったケースを見逃す。
    """
    keys = compare_keys(source, target, key)
    totals = compare_totals(source, target, measures, tolerance)

    reasons = []
    if len(source) != len(target):
        reasons.append(f'row count differs: source {len(source)}, target {len(target)}')
    if keys['missing']:
        reasons.append(f"{len(keys['missing'])} keys missing in target, e.g. {keys['missing'][:SAMPLE_LIMIT]}")
    if keys['unexpected']:
        reasons.append(f"{len(keys['unexpected'])} unexpected keys in target, e.g. {keys['unexpected'][:SAMPLE_LIMIT]}")
    if keys['duplicated']:
        reasons.append(f"{len(keys['duplicated'])} keys duplicated in target, e.g. {keys['duplicated'][:SAMPLE_LIMIT]}")
    for m, d in totals.items():
        reasons.append(f"total of {m} differs by {d['diff']}")

    return {
        'status': 'mismatch' if reasons else 'match',
        'source_rows': len(source),
        'target_rows': len(target),
        'reasons': reasons,
    }


def render_summary(result, label):
    """発注者に渡せる突合結果の要約。"""
    head = f"## 突合結果: {label}\n\n- 判定: **{result['status']}**\n- 件数: 移行元 {result['source_rows']} / 移行先 {result['target_rows']}"
    return head + ''.join(f'\n- ⚠️ {r}' for r in result['reasons'])