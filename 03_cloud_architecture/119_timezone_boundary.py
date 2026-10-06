"""
タイムゾーンと日付境界 — 「日次売上が朝9時で区切られている」を防ぐ。

背景:
    日本の受託で最もよく見るバグの1つ。サーバーが UTC で日付を切ると、
    日本時間 0:00〜8:59 の取引が前日分として集計される。
    エラーは出ず、数字だけが静かにずれる。

    本ファイルの原則:
      - タイムゾーンの無い時刻(naive)は受け付けない
      - 営業日は日本時間で決め、保存と比較は UTC で行う
      - 1日の範囲は半開区間 [0:00, 翌0:00)。23:59:59 で切ると最後の1秒が消える

    日本時間は固定オフセット(+9:00)で扱う。日本には夏時間が無いため正確であり、
    Windows で zoneinfo を使うのに必要な tzdata 依存も増やさずに済む。
    夏時間のある地域を扱うときは zoneinfo を使うこと。

    #117 のラチェットにより、公開関数は100%型付き。
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

JST = timezone(timedelta(hours=9), name='JST')


def require_aware(dt: datetime) -> datetime:
    """
    タイムゾーン付きの時刻だけを通す。

    naive な時刻は UTC なのか JST なのか誰にも分からない。
    推測で補えば、9時間ずれが静かに混入する。
    """
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError(f'naive datetime is not allowed: {dt.isoformat()}')
    return dt


def to_utc(dt: datetime) -> datetime:
    """保存・比較用に UTC へ揃える。"""
    return require_aware(dt).astimezone(timezone.utc)


def business_date(dt: datetime, tz: timezone = JST) -> date:
    """その時刻が属する営業日(日本時間の日付)を返す。"""
    return require_aware(dt).astimezone(tz).date()


def day_bounds_utc(d: date, tz: timezone = JST) -> tuple[datetime, datetime]:
    """
    営業日 d の範囲を UTC の半開区間 [start, end) で返す。

    end を「23:59:59」にすると、23:59:59.5 の取引が漏れる。
    """
    start = datetime.combine(d, time.min, tzinfo=tz)
    end = start + timedelta(days=1)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


def in_business_day(dt: datetime, d: date, tz: timezone = JST) -> bool:
    """dt が営業日 d に含まれるか(半開区間で判定)。"""
    start, end = day_bounds_utc(d, tz)
    return start <= to_utc(dt) < end


def partition_key(dt: datetime, tz: timezone = JST) -> str:
    """営業日でパーティション名を作る。UTC の日付で切ると、朝9時区切りになる。"""
    return f'dt={business_date(dt, tz).isoformat()}'


def find_misplaced(rows: list[dict[str, object]], tz: timezone = JST) -> list[str]:
    """
    保存済みのパーティション名と、営業日から計算した名前が食い違う行を返す。

    過去に UTC で切って保存したデータを見つけるための監査。
    """
    misplaced: list[str] = []
    for row in rows:
        ts = row['event_at']
        if not isinstance(ts, datetime):
            raise TypeError('event_at must be a datetime')
        expected = partition_key(ts, tz)
        if row['partition'] != expected:
            misplaced.append(f"{row['id']}: stored {row['partition']}, expected {expected}")
    return misplaced