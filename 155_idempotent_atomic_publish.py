"""
出力の原子的な公開 — 書きかけ・検査前の出力を、読む側に見せない。

背景:
    集計結果を書いている途中で読まれると、半分だけ新しいデータで集計される。
    途中で落ちれば、壊れたファイルが「最新」として残る。

方針(オブジェクトストレージでの定番):
    1. 隠れた場所 {target}/_staging/{run_id}/ に書く
    2. 中身を検査する。失敗したら staging を消して止める(今の版は無傷)
    3. 版ごとの場所 {target}/v={run_id}/ へ移す
    4. 目印 {target}/_CURRENT を1回の書き込みで run_id に切り替える(ここだけが公開)
    - 読む側は _CURRENT が指す版だけを読むので、古い版か新しい版のどちらかしか見ない
    - 同じ run_id・同じ中身の再実行は何もしない(冪等)。中身が違えば止める
    - 戻すときは _CURRENT を前の版に向けるだけ(rollback)
"""
from __future__ import annotations

from collections.abc import Callable

Store = dict[str, bytes]
Files = dict[str, bytes]


def _pointer(target: str) -> str:
    return f'{target}/_CURRENT'


def _version_prefix(target: str, run_id: str) -> str:
    return f'{target}/v={run_id}/'


def _files_at(store: Store, prefix: str) -> Files:
    return {key[len(prefix):]: data for key, data in store.items() if key.startswith(prefix)}


def publish(store: Store, target: str, files: Files, run_id: str,
            validate: Callable[[Files], None]) -> bool:
    """新しく公開したら True、同じ実行が公開済みなら何もせず False。"""
    if not files:
        raise ValueError('nothing to publish')
    prefix = _version_prefix(target, run_id)
    existing = _files_at(store, prefix)
    if existing:
        if existing != files:
            raise ValueError(f'run {run_id} was already published with different content')
        return False
    staging = f'{target}/_staging/{run_id}/'
    for name, data in files.items():
        store[staging + name] = data
    try:
        validate(_files_at(store, staging))
    except Exception:
        for name in files:
            del store[staging + name]
        raise
    for name in files:
        store[prefix + name] = store.pop(staging + name)
    store[_pointer(target)] = run_id.encode('utf-8')
    return True


def read_current(store: Store, target: str) -> Files:
    """今公開されている版を読む。まだ何も公開されていなければ空。"""
    pointer = store.get(_pointer(target))
    if pointer is None:
        return {}
    return _files_at(store, _version_prefix(target, pointer.decode('utf-8')))


def rollback(store: Store, target: str, run_id: str) -> None:
    """目印を、既にある版に向け直す。"""
    if not _files_at(store, _version_prefix(target, run_id)):
        raise ValueError(f'version {run_id} does not exist')
    store[_pointer(target)] = run_id.encode('utf-8')
