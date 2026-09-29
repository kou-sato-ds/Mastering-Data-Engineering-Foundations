"""
月額費用の見積もり — 使う前に、金額を約束する。

背景:
    受託の最初の打ち合わせで必ず聞かれるのは「毎月いくらかかりますか」である。
    #64 のコストガードは「使いすぎを止める」仕組みだが、
    それより前に「いくらになるか」を示せなければ、発注の判断ができない。

    設計上の判断:
      - 単価をコードに書かない。クラウドの料金は改定される。
        単価表を外から渡し、**いつ時点の単価か**を見積もりに必ず載せる。
      - 予備費は合計に混ぜず、別の行で見せる。隠れた上乗せは信頼を失う。
      - データ量が増えた場合の金額を最初から出す。増えてから驚かせない。
"""
from datetime import timedelta

# 単価表がこれより古ければ警告する。料金改定を見落としたまま見積もらないため。
STALE_AFTER_DAYS = 90

DEFAULT_BUFFER = 0.2


def validate_prices(prices, usage, today):
    """
    単価表を検証する。

    - 使用量にあって単価表に無い項目 -> エラー(0円として計算すれば、見積もりが安く出る)
    - 単価の日付が無い -> エラー
    - 単価の日付が古い -> 警告
    """
    errors, warnings = [], []

    as_of = prices.get('as_of')
    if as_of is None:
        errors.append('price sheet has no as_of date; the quote cannot say when prices were valid')
    elif today - as_of > timedelta(days=STALE_AFTER_DAYS):
        warnings.append(f'prices are from {as_of.isoformat()}; check for price changes before quoting')

    missing = sorted(set(usage) - set(prices.get('unit', {})))
    if missing:
        errors.append(f'no unit price for: {missing}')

    return errors, warnings


def estimate(usage, prices):
    """使用量 x 単価 の明細と小計を返す。"""
    items = []
    for name, qty in sorted(usage.items()):
        unit = prices['unit'][name]
        items.append({'item': name, 'qty': qty, 'unit_price': unit, 'amount': round(qty * unit, 2)})
    return {'items': items, 'subtotal': round(sum(i['amount'] for i in items), 2)}


def with_buffer(subtotal, ratio=DEFAULT_BUFFER):
    """予備費を別行で返す。合計に黙って混ぜない。"""
    buffer = round(subtotal * ratio, 2)
    return {'subtotal': subtotal, 'buffer': buffer, 'total': round(subtotal + buffer, 2)}


def scale_usage(usage, factor):
    """データ量が factor 倍になった場合の使用量。"""
    return {k: v * factor for k, v in usage.items()}


def build_quote(usage, prices, today, factors=(1, 2)):
    """
    見積もり一式を作る。単価表に不備があれば作らない。

    不備があるまま金額を出せば、その金額が一人歩きする。
    """
    errors, warnings = validate_prices(prices, usage, today)
    if errors:
        return {'valid': False, 'errors': errors, 'warnings': warnings}

    scenarios = []
    for f in factors:
        est = estimate(scale_usage(usage, f), prices)
        scenarios.append({'factor': f, **with_buffer(est['subtotal']), 'items': est['items']})

    return {
        'valid': True,
        'errors': [],
        'warnings': warnings,
        'prices_as_of': prices['as_of'].isoformat(),
        'scenarios': scenarios,
    }


def render_quote(quote, currency='USD'):
    """発注者に渡せる Markdown を返す。"""
    if not quote['valid']:
        return '見積もり不可:\n' + '\n'.join(f'- {e}' for e in quote['errors'])

    lines = [f"## 月額費用の見積もり(単価は {quote['prices_as_of']} 時点)", '']
    for s in quote['scenarios']:
        lines.append(f"- データ量 {s['factor']}倍: 小計 {s['subtotal']} + 予備費 {s['buffer']} = **{s['total']} {currency}**")
    for w in quote['warnings']:
        lines.append(f'- ⚠️ {w}')
    return '\n'.join(lines)