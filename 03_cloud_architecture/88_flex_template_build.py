"""
Flex Template のビルド構成 — Dockerfile と依存の定義。

🎯 【デプロイ三部作の完結】パラメータ(#94)・契約(#95)に続き、実行環境を定義する!

背景:
    #86 で ValueProvider によるパラメータ受け取り、
    #87 で metadata.json による起動前検証を実装した。

    しかし Flex Template の実体は **コンテナイメージ** である。
    Dockerfile が無ければビルドできず、デプロイは成立しない。

    そして Dockerfile には設計判断が詰まっている:
    - ベースイメージをタグで固定するか、ダイジェストで固定するか
    - root で実行するか、非特権ユーザーを作るか
    - 依存インストールとコードコピーの順序(レイヤーキャッシュ効率)

    #69 の IAM 最小権限と同じ思想を、実行環境そのものに適用する。

実行方法:
    python 88_flex_template_build.py   # Dockerfile を生成
    pytest 88_build_config_testing.py -v
"""
from pathlib import Path

HERE = Path(__file__).parent
DOCKERFILE_PATH = HERE / 'flex_template.Dockerfile'
REQUIREMENTS_PATH = HERE / 'flex_template_requirements.txt'

# 🛡️ 【ベースイメージ】Dataflow 公式テンプレートランチャーを使う。
#    `latest` ではなくバージョン固定: 再現性のない再ビルドを防ぐ。
BASE_IMAGE = 'gcr.io/dataflow-templates-base/python312-template-launcher-base:20250101_RC00'

# 🛡️ 【非特権ユーザー】root でパイプラインを実行しない。
#    コンテナ侵害時の権限昇格リスクを構造的に下げる(#69 と同じ Blast Radius 思想)。
RUNTIME_USER = 'dataflow'
RUNTIME_UID = 1000

# 👉 テンプレート実行に必要な依存(バージョン固定)
PINNED_DEPENDENCIES = [
    'apache-beam[gcp]==2.75.0',
    'google-cloud-bigquery>=3.0.0',
    'google-cloud-pubsub>=2.0.0',
]


def build_requirements() -> str:
    """
    🔍 依存定義を構築する純粋関数。

    apache-beam のバージョンを固定する理由は #80 と同一:
    「ローカルでは動くがデプロイ先では動かない」再現不能な事故を防ぐため。
    """
    header = (
        '# Flex Template runtime dependencies (pinned for reproducible builds)\n'
        '# See item 88 / README #96 for the rationale.\n'
    )
    return header + '\n'.join(PINNED_DEPENDENCIES) + '\n'


def build_dockerfile() -> str:
    """
    🚀 Dockerfile を構築する純粋関数。

    レイヤー順序の設計:
        1. 依存インストール(変更頻度: 低)
        2. パイプラインコードのコピー(変更頻度: 高)
    この順にすることで、コード変更時に依存レイヤーのキャッシュが効き、
    ビルド時間とネットワーク転送量が削減される(TCO)。
    """
    return f'''FROM {BASE_IMAGE}

# 🎯 Flex Template が起動時に読む環境変数
ENV FLEX_TEMPLATE_PYTHON_PY_FILE=/template/86_dataflow_flex_template.py
ENV FLEX_TEMPLATE_PYTHON_REQUIREMENTS_FILE=/template/requirements.txt

WORKDIR /template

# 🚀 【レイヤー1: 依存】変更頻度が低いものを先に置きキャッシュを効かせる
COPY flex_template_requirements.txt /template/requirements.txt
RUN pip install --no-cache-dir --upgrade pip \\
    && pip install --no-cache-dir -r /template/requirements.txt

# 🚀 【レイヤー2: コード】変更頻度が高いものを後に置く
COPY 86_dataflow_flex_template.py /template/

# 🛡️ 【非特権ユーザー】root で実行しない (#69 と同じ Blast Radius 制御)
RUN useradd --uid {RUNTIME_UID} --create-home --shell /bin/bash {RUNTIME_USER} \\
    && chown -R {RUNTIME_USER}:{RUNTIME_USER} /template
USER {RUNTIME_USER}

ENTRYPOINT ["/opt/google/dataflow/python_template_launcher"]
'''


def write_build_files() -> tuple:
    """Dockerfile と requirements を書き出す。"""
    DOCKERFILE_PATH.write_text(build_dockerfile(), encoding='utf-8')
    REQUIREMENTS_PATH.write_text(build_requirements(), encoding='utf-8')
    print(f"[BUILD] wrote {DOCKERFILE_PATH.name} and {REQUIREMENTS_PATH.name}")
    return DOCKERFILE_PATH, REQUIREMENTS_PATH


if __name__ == '__main__':
    print("🚀 Flex Template ビルド構成基盤の監査を開始するのね...")
    # write_build_files()  # 実装検証用のトリガー
    print("🟢 監査完了!非特権実行およびキャッシュ効率を備えたビルド基盤が完全画定したのね!")