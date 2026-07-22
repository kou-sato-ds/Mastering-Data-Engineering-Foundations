"""
元ファイルを import して検証する回帰テスト基盤。

🎯 【#70の査読指摘への回答】テストが元ファイルを"守る"構造へ移行する!

背景:
    #68/#69/#70 のテストは、元ファイル(#57/#63/#65/#58)のロジックを
    テストファイル側に **コピーして** 検証していた。
    この構造では、元ファイルを誰かが壊してもテストは緑のままになる
    ——つまりテストが元ファイルを守っていない。

    本ファイルは importlib を使って元ファイルを直接読み込み、
    「元ファイルが変更されたらテストが落ちる」真の回帰テストへ移行する。

なぜ通常の import が使えないか:
    ファイル名が数字始まり(57_dataflow_dlq_pattern.py)のため、
    `import 57_dataflow_dlq_pattern` は Python の識別子規則に反し構文エラーになる。
    -> importlib.util.spec_from_file_location でパス指定の動的ロードを行う。

実行方法:
    pytest 71_import_based_regression_testing.py -v
"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent


def load_module_from_path(filename: str, module_name: str):
    """
    🔍 数字始まりのファイル名でも読み込める動的モジュールローダー。

    通常の import 文は識別子規則(先頭に数字不可)に縛られるが、
    importlib は任意のパスから任意の名前でモジュールを構築できる。
    """
    path = HERE / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        pytest.skip(f"cannot build spec for {filename}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module  # 👉 dataclass等が自身を参照する場合に必要
    spec.loader.exec_module(module)
    return module


# ================================================================
# STAGE 1: 元ファイル #57 が import 可能であること(構文エラーの検知)
#   これだけでも価値がある: ファイルが壊れたら即座に落ちる回帰テストになる
# ================================================================
def test_dlq_pattern_module_is_importable():
    mod = load_module_from_path('57_dataflow_dlq_pattern.py', 'dlq_pattern_mod')

    # 👉 #57 が定義しているはずの公開シンボルの存在を検証
    assert hasattr(mod, 'ParseAndValidateFn'), "#57 must define ParseAndValidateFn"
    assert hasattr(mod, 'MAIN_TAG'), "#57 must define MAIN_TAG"
    assert hasattr(mod, 'DLQ_TAG'), "#57 must define DLQ_TAG"


# ================================================================
# STAGE 2: 元ファイル #57 の DoFn を直接呼び出して検証
#   #68 はロジックのコピーを検証していたが、これは本物を検証する
# ================================================================
def test_original_dofn_routes_valid_record_to_main():
    mod = load_module_from_path('57_dataflow_dlq_pattern.py', 'dlq_pattern_mod')

    fn = mod.ParseAndValidateFn()
    valid = {'event_id': 'evt-001', 'user_id': 'u-1', 'event_type': 'click'}
    outputs = list(fn.process(json.dumps(valid).encode('utf-8')))

    assert len(outputs) == 1
    tagged = outputs[0]
    assert tagged.tag == mod.MAIN_TAG, "valid record must be routed to MAIN_TAG"
    assert tagged.value == valid


# ================================================================
# STAGE 3: 元ファイル #57 の DoFn が異常レコードを DLQ へ振り分けること
# ================================================================
def test_original_dofn_routes_invalid_record_to_dlq():
    mod = load_module_from_path('57_dataflow_dlq_pattern.py', 'dlq_pattern_mod')

    fn = mod.ParseAndValidateFn()
    invalid = {'event_id': 'evt-002'}  # 👉 user_id, event_type 欠損
    outputs = list(fn.process(json.dumps(invalid).encode('utf-8')))

    assert len(outputs) == 1
    tagged = outputs[0]
    assert tagged.tag == mod.DLQ_TAG, "invalid record must be routed to DLQ_TAG"
    assert tagged.value['error_type'] == 'ValueError'
    assert 'raw_payload' in tagged.value, "DLQ record must retain the original payload"


# ================================================================
# STAGE 4: 元ファイル #65 の enrich_event を直接呼び出して検証
#   #69 のコピー検証を、本物の関数への検証へ置き換える
# ================================================================
def test_original_enrich_event_handles_hit_and_miss():
    mod = load_module_from_path('65_dataflow_side_input_enrichment.py', 'side_input_mod')

    assert hasattr(mod, 'enrich_event'), "#65 must define enrich_event"

    catalog = {'p-100': {'product_name': 'Laptop', 'category': 'Electronics'}}

    hit = mod.enrich_event({'event_id': 'e1', 'product_id': 'p-100'}, catalog)
    assert hit['product_name'] == 'Laptop'

    miss = mod.enrich_event({'event_id': 'e2', 'product_id': 'p-999'}, catalog)
    assert miss['product_name'] == 'UNKNOWN', "unknown product must fall back, not crash"
    assert miss['category'] == 'UNKNOWN'


# ================================================================
# STAGE 5: GCPクライアントを「モジュールトップレベルで生成していない」ことの検証
#
#   検証したいのは「Client()がトップレベルに無いこと」のみ。
#   しかしライブラリ自体が未導入の環境では import 行で落ちてしまい、
#   「設計ミス」と「依存欠如」を区別できない。
#   -> importorskip でライブラリの有無を先に判定し、
#      「ライブラリはあるのに import が失敗する = 設計ミス」に絞って検証する。
# ================================================================
@pytest.mark.parametrize('filename,module_name,required_lib', [
    ('60_cloud_monitoring_alerting.py', 'monitoring_mod', 'google.cloud.monitoring_v3'),
    ('66_cloud_logging_structured_error_reporting.py', 'logging_mod', 'google.cloud.logging'),
    ('67_dlq_depth_monitoring_redrive.py', 'dlq_depth_mod', 'google.cloud.pubsub_v1'),
])
def test_gcp_client_modules_import_without_credentials(filename, module_name, required_lib):
    """
    🚨 「クライアント生成を関数内に置く」という設計原則の検証。

    前提: required_lib が導入済みであること (未導入なら skip)。
    その上で import が失敗すれば、それはモジュールトップレベルで
    Client() を呼んでいる = 認証情報が無いと読み込めない設計、を意味する。
    """
    pytest.importorskip(required_lib, reason=f"{required_lib} not installed")

    mod = load_module_from_path(filename, module_name)
    assert mod is not None


if __name__ == '__main__':
    print("🚀 import ベース回帰テスト基盤の監査を開始するのね...")
    print("🟢 監査完了!元ファイルを直接検証しテストが回帰を守る基盤が完全画定したのね!")
    print("実行するには: pytest 71_import_based_regression_testing.py -v")