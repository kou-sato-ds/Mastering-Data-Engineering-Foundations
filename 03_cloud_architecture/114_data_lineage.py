"""
データリネージ — 「これを変えたら、どこまで影響するか」に答える。

背景:
    受託で変更依頼が来たとき、必ず聞かれるのが影響範囲である。
    表 A の列を変えれば、A を読む B が壊れ、B を読む C のダッシュボードも壊れる。
    直接の下流しか見ていなければ、C の持ち主は本番で壊れて初めて気づく。

    本ファイルは表どうしの依存関係から:
      - 影響範囲(下流の下流まで全て)を求める
      - 循環を検出する(循環があれば実行順が決まらない)
      - 実行順を決める(上流から順に)
      - 影響先ごとの連絡先を出す
"""
from collections import deque


def build_graph(edges):
    """(上流, 下流) の組から、上流 -> 下流の一覧を作る。"""
    graph = {}
    for src, dst in edges:
        graph.setdefault(src, set()).add(dst)
        graph.setdefault(dst, set())
    return graph


def downstream(graph, node):
    """
    node に依存する全ての表を、距離付きで返す。

    直接の下流(距離1)だけで止めない。
    ダッシュボードのような末端ほど、変更の知らせが届きにくい。
    """
    if node not in graph:
        raise KeyError(f'unknown table: {node}')

    depth = {node: 0}
    queue = deque([node])
    while queue:
        current = queue.popleft()
        for nxt in sorted(graph[current]):
            if nxt not in depth:
                depth[nxt] = depth[current] + 1
                queue.append(nxt)

    return sorted(((n, d) for n, d in depth.items() if n != node), key=lambda x: (x[1], x[0]))


def execution_order(graph):
    """
    上流から順に並べる(トポロジカルソート)。

    循環があれば ValueError。
    A が B を、B が A を待てば、どちらも永遠に始まらない。
    同順位は名前順に並べ、毎回同じ順番になるようにする。
    """
    incoming = {n: 0 for n in graph}
    for dsts in graph.values():
        for d in dsts:
            incoming[d] += 1

    ready = sorted(n for n, c in incoming.items() if c == 0)
    order = []
    while ready:
        node = ready.pop(0)
        order.append(node)
        for nxt in sorted(graph[node]):
            incoming[nxt] -= 1
            if incoming[nxt] == 0:
                ready.append(nxt)
                ready.sort()

    if len(order) != len(graph):
        stuck = sorted(n for n, c in incoming.items() if c > 0)
        raise ValueError(f'dependency cycle among: {stuck}')
    return order


def impact_report(graph, node, owners):
    """
    影響先と連絡先の一覧を返す。

    持ち主が登録されていない表は 'unknown' とし、別に数える。
    連絡先の無い影響先は、変更を知らせる手段が無いことを意味する。
    """
    affected = [
        {'table': t, 'depth': d, 'owner': owners.get(t, 'unknown')}
        for t, d in downstream(graph, node)
    ]
    return {
        'source': node,
        'affected': affected,
        'unowned': [a['table'] for a in affected if a['owner'] == 'unknown'],
        'contacts': sorted({a['owner'] for a in affected if a['owner'] != 'unknown'}),
    }