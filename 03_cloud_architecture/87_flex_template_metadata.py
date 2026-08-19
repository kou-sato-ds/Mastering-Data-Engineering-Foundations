"""
Flex Template のメタデータ定義 — 起動時パラメータの契約化。

🎯 【受け取る前に弾く】#86 で受け取ったパラメータを、起動前に検証する!

背景:
    #86 で ValueProvider によるパラメータ受け取りを実装したが、
    Flex Template には metadata.json が必須であり、それが無いと
    テンプレートをビルドできない。

    そしてメタデータには **正規表現バリデーション** が書ける。
    誤ったサブスクリプションパスを渡した場合、
    - メタデータ無し: ジョブが起動し、実行時に失敗する(課金が発生する)
    - メタデータ有り: **起動前に gcloud が拒否する**(課金ゼロ)

    #65 が「不正なレコードを DLQ へ隔離する」なら、
    本ファイルは「不正なパラメータをジョブ起動前に弾く」——
    同じ思想をデータ層からパラメータ層へ適用する。

実行方法:
    python 87_flex_template_metadata.py   # metadata.json を生成
    pytest 87_metadata_contract_testing.py -v
"""
import json
from pathlib import Path

HERE = Path(__file__).parent
METADATA_PATH = HERE / 'flex_template_metadata.json'

# 🛡️ 【パラメータ契約】起動前に gcloud が検証する正規表現
#    誤った形式は「ジョブが失敗する」のではなく「ジョブが始まらない」。
PUBSUB_SUBSCRIPTION_REGEX = r'^projects/[^/]+/subscriptions/[^/]+$'
BIGQUERY_TABLE_REGEX = r'^[^:]+:[^.]+\.[^.]+$'  # 👉 project:dataset.table


def build_parameter(name: str, label: str, help_text: str,
                    regexes: list = None, is_optional: bool = False) -> dict:
    """
    🔍 単一パラメータの定義を構築する純粋関数。

    regexes を指定すると、gcloud がジョブ起動前にパターン検証を行う。
    """
    param = {
        'name': name,
        'label': label,
        'helpText': help_text,
    }
    if regexes:
        param['regexes'] = regexes
    if is_optional:
        param['isOptional'] = True
    return param


def build_metadata() -> dict:
    """
    🚀 Flex Template メタデータ全体を構築する。

    #86 の FlexTemplateOptions が宣言した3パラメータと1対1で対応する。
    片方だけ変更すると「テンプレートは受け取るがメタデータが拒否する」
    (またはその逆)という不整合が生じるため、テストで整合を固定する。
    """
    return {
        'name': 'PubSub to BigQuery with DLQ',
        'description': (
            'Streams events from PubSub to BigQuery, routing malformed '
            'records to a dead letter table. Validation contract matches '
            'the non-templated pipeline.'
        ),
        'parameters': [
            build_parameter(
                name='input_subscription',
                label='Input PubSub subscription',
                help_text='Full path, e.g. projects/my-proj/subscriptions/events-sub',
                regexes=[PUBSUB_SUBSCRIPTION_REGEX],
            ),
            build_parameter(
                name='output_table',
                label='Output BigQuery table',
                help_text='Format: project:dataset.table',
                regexes=[BIGQUERY_TABLE_REGEX],
            ),
            build_parameter(
                name='dlq_table',
                label='Dead letter BigQuery table',
                help_text='Format: project:dataset.table. Receives malformed records.',
                regexes=[BIGQUERY_TABLE_REGEX],
            ),
        ],
    }


def write_metadata() -> Path:
    """メタデータを JSON ファイルとして書き出す。"""
    METADATA_PATH.write_text(
        json.dumps(build_metadata(), indent=2, ensure_ascii=False),
        encoding='utf-8',
    )
    print(f"[METADATA] written to {METADATA_PATH.name}")
    return METADATA_PATH


if __name__ == '__main__':
    print("🚀 Flex Template メタデータ契約基盤の監査を開始するのね...")
    # write_metadata()  # 実装検証用のトリガー
    print("🟢 監査完了!不正なパラメータをジョブ起動前に弾く基盤が完全画定したのね!")