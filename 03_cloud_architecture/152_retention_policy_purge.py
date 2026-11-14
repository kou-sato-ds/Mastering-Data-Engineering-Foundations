"""
データ保持期限の適用 — 期間を過ぎたデータを消す計画を作る。保全中・不明なものは消さない。

背景:
    個人情報やログは「決めた期間を過ぎたら消す」のが原則である(法令・社内規程・契約)。
    ただし訴訟などで保全が必要なデータ(リーガルホールド)は、期限が来ても消してはいけない。
    削除は取り消せないので、まず計画を作り、確認してから実行する。

方針:
    - データの種類(data_class)ごとに保持日数を決める
    - 作成日 + 保持日数 の日を迎えたら削除の対象(その日ちょうども対象)
    - legal_hold が付いた記録は、期限切れでも消さず kept_on_hold に入れる
    - 保持日数が決まっていない種類は消さず unknown_class に入れる(分からない ≠ 消してよい)
    - 本関数は計画を返すだけ。入力は書き換えない
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta


@dataclass(frozen=True)
class Record:
    """保持期限の対象になる記録1件。"""
    id: str
    data_class: str
    created_at: date
    legal_hold: bool = False


@dataclass
class PurgePlan:
    """削除の計画。delete だけが実際に消してよいもの。"""
    delete: list[str] = field(default_factory=list)
    kept_on_hold: list[str] = field(default_factory=list)
    unknown_class: list[str] = field(default_factory=list)


def plan_purge(records: list[Record], retention_days: dict[str, int], today: date) -> PurgePlan:
    """保持日数の表に従って、削除の計画を作る。"""
    for data_class, days in retention_days.items():
        if days < 1:
            raise ValueError(f'retention for {data_class} must be at least 1 day')
    plan = PurgePlan()
    for record in records:
        days = retention_days.get(record.data_class)
        if days is None:
            plan.unknown_class.append(record.id)
            continue
        if today < record.created_at + timedelta(days=days):
            continue
        if record.legal_hold:
            plan.kept_on_hold.append(record.id)
        else:
            plan.delete.append(record.id)
    plan.delete.sort()
    plan.kept_on_hold.sort()
    plan.unknown_class.sort()
    return plan
