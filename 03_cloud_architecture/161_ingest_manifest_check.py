"""
取り込みファイルの到着検査 — 一覧表(マニフェスト)と、実際に届いたファイルを突き合わせる。

背景:
    取引先が毎朝ファイルを置く受け渡しでは、転送の途中で止まる・切れる・古いファイルが残る。
    中身を読み始めてから気づくと、途中まで取り込んだ分の後始末が要る。

方針:
    - 一覧の各行は (名前, バイト数, sha256)。同じ名前が2行あれば止める
    - missing / unexpected / empty / size_mismatch / checksum_mismatch の5種類を報告する
    - 大きさが違えば中身の比較はしない(切れていることは既に分かっている)
    - ok が False なら取り込みを始めない
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Entry:
    """一覧表の1行。"""
    name: str
    size: int
    sha256: str


@dataclass
class ArrivalReport:
    """到着検査の結果。"""
    missing: list[str] = field(default_factory=list)
    unexpected: list[str] = field(default_factory=list)
    empty: list[str] = field(default_factory=list)
    size_mismatch: list[str] = field(default_factory=list)
    checksum_mismatch: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """一覧どおりに全部届いているか。"""
        return not (self.missing or self.unexpected or self.empty
                    or self.size_mismatch or self.checksum_mismatch)


def sha256_of(data: bytes) -> str:
    """中身のハッシュ。"""
    return hashlib.sha256(data).hexdigest()


def check_arrival(manifest: list[Entry], received: dict[str, bytes]) -> ArrivalReport:
    """一覧 manifest と、届いたファイル received(名前 → 中身)を突き合わせる。"""
    names = [e.name for e in manifest]
    if len(set(names)) != len(names):
        raise ValueError('manifest has duplicate file names')
    report = ArrivalReport()
    for entry in manifest:
        data = received.get(entry.name)
        if data is None:
            report.missing.append(entry.name)
        elif len(data) == 0:
            report.empty.append(entry.name)
        elif len(data) != entry.size:
            report.size_mismatch.append(entry.name)
        elif sha256_of(data) != entry.sha256:
            report.checksum_mismatch.append(entry.name)
    report.unexpected = sorted(set(received) - set(names))
    return report
