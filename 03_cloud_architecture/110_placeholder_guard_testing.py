"""
#110 未記入ガード — README に穴埋めの印を残したまま push しない。

背景:
    README の「学びの足跡」に、実測値を後で書くための印を置いてきた。
    2026-09-28 に確認すると、その印が13か所残っていた——
    **書いたが、証明を書いていない**状態であり、本ポートフォリオが
    一貫して排除してきた stated と demonstrated の乖離そのものである。

    注意で防ぐには数が多すぎた。だから仕組みで防ぐ。
    書き方の揺れ(「ここを〜で埋める」「実測値」など)をまとめて検知する。
"""
import re
from pathlib import Path

HERE = Path(__file__).parent
README = HERE.parent / 'README.md'

# 角括弧で始まり、「ここを」または「実測値」を含む印。書き方の揺れをまとめて拾う。
PLACEHOLDER = re.compile(r'\[\s*(ここを|実測値)[^\]]*\]')


def find_placeholders(text):
    """(行番号, 行の先頭60文字) のリストを返す。"""
    hits = []
    for i, line in enumerate(text.splitlines(), start=1):
        if PLACEHOLDER.search(line):
            hits.append((i, line.strip()[:60]))
    return hits


def test_readme_has_no_placeholders():
    hits = find_placeholders(README.read_text(encoding='utf-8'))
    assert not hits, (
        f'{len(hits)} placeholders remain in README: {hits}. '
        'A claim without its measured result is stated but not demonstrated.'
    )


def test_detects_every_known_spelling():
    """過去に実際に使った3種類の書き方を全て捕まえること。"""
    samples = [
        '掌握。[ ここを実測値で埋める ]。',
        '掌握。[ ここを実行結果で埋める: 実測値 ]。',
        '掌握。[実測値]。',
    ]
    for s in samples:
        assert find_placeholders(s), f'missed: {s}'


def test_ordinary_brackets_are_not_flagged():
    """Markdown のリンクや普通の角括弧まで拾えば、ガードが常に赤くなり信用を失う。"""
    text = '[serverless-scraping-data-pipeline](https://github.com/x) と [ADR-002] を参照'
    assert find_placeholders(text) == []