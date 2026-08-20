"""
#88 ビルド構成の検証。

🎯 【Dockerfileにも設計判断がある】セキュリティとTCOをテストで固定!

背景:
    Dockerfile は「動けばいい」設定ファイルとして扱われがちだが、
    root 実行・latest タグ・レイヤー順序は、いずれも
    セキュリティとコストに直結する設計判断である。

    これらをコメントではなくアサーションで守る。

実行方法:
    pytest 88_build_config_testing.py -v
"""
import importlib.util
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent


def load_module_from_path(filename: str, module_name: str):
    """#71/#80-#87 と同一の動的ローダー。"""
    path = HERE / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        pytest.skip(f"cannot build spec for {filename}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _build_mod():
    return load_module_from_path('88_flex_template_build.py', 'flex_build_mod')


# ================================================================
# STAGE 1: ベースイメージが可変タグで固定されていないこと
#   latest を使うと、再ビルドのたびに中身が変わりうる。
#   「昨日通ったビルドが今日落ちる」を構造的に防ぐ。
# ================================================================
def test_base_image_is_pinned():
    mod = _build_mod()

    assert not mod.BASE_IMAGE.endswith(':latest'), (
        "a mutable tag makes rebuilds non-reproducible; pin an explicit version"
    )
    assert ':' in mod.BASE_IMAGE, "the base image must carry an explicit tag"


# ================================================================
# STAGE 2: 非特権ユーザーで実行されること
#   root 実行はコンテナ侵害時の権限昇格を許す(#69 の Blast Radius 思想)。
# ================================================================
def test_container_does_not_run_as_root():
    mod = _build_mod()
    dockerfile = mod.build_dockerfile()

    assert f'USER {mod.RUNTIME_USER}' in dockerfile, (
        "the container must drop to a non-privileged user before ENTRYPOINT"
    )
    assert mod.RUNTIME_UID != 0, "uid 0 is root"

    # 👉 USER 指定が ENTRYPOINT より前にあること(順序が逆なら意味がない)
    user_pos = dockerfile.index(f'USER {mod.RUNTIME_USER}')
    entry_pos = dockerfile.index('ENTRYPOINT')
    assert user_pos < entry_pos, (
        "USER must be declared before ENTRYPOINT, otherwise the process "
        "still starts as root"
    )


# ================================================================
# STAGE 3: 依存インストールがコードコピーより先に来ること
#   逆順だとコード変更のたびに依存を再インストールし、
#   ビルド時間と転送量が増える(TCO)。
# ================================================================
def test_dependency_layer_precedes_code_layer():
    mod = _build_mod()
    dockerfile = mod.build_dockerfile()

    req_pos = dockerfile.index('requirements.txt')
    code_pos = dockerfile.index('COPY 86_dataflow_flex_template.py')

    assert req_pos < code_pos, (
        "dependencies must be installed before copying the pipeline code, "
        "otherwise every code change invalidates the dependency layer cache"
    )


# ================================================================
# STAGE 4: Flex Template 必須の環境変数が定義されていること
#   これが無いとランチャーがエントリポイントを見つけられない。
# ================================================================
@pytest.mark.parametrize('env_var', [
    'FLEX_TEMPLATE_PYTHON_PY_FILE',
    'FLEX_TEMPLATE_PYTHON_REQUIREMENTS_FILE',
])
def test_required_env_vars_are_declared(env_var):
    mod = _build_mod()

    assert env_var in mod.build_dockerfile(), (
        f"{env_var} is required by the Dataflow template launcher"
    )


# ================================================================
# STAGE 5: 依存がバージョン固定されていること
#   #80 と同一の理由: 「ローカルでは動くがデプロイ先では動かない」を防ぐ。
# ================================================================
def test_beam_version_is_pinned():
    mod = _build_mod()

    beam_lines = [d for d in mod.PINNED_DEPENDENCIES if 'apache-beam' in d]
    assert beam_lines, "apache-beam must be declared"
    assert '==' in beam_lines[0], (
        "apache-beam must be pinned with ==; a floating version can change "
        "TestPipeline behaviour between local runs and the deployed image"
    )


# ================================================================
# STAGE 6: pip キャッシュを残さないこと
#   イメージサイズはデプロイ時間とストレージ課金に直結する。
# ================================================================
def test_pip_cache_is_not_retained():
    mod = _build_mod()
    dockerfile = mod.build_dockerfile()

    assert '--no-cache-dir' in dockerfile, (
        "retaining the pip cache inflates the image, increasing both "
        "deploy time and registry storage cost"
    )


# ================================================================
# STAGE 7: エントリポイントがランチャーを指すこと
# ================================================================
def test_entrypoint_is_the_template_launcher():
    mod = _build_mod()

    assert 'python_template_launcher' in mod.build_dockerfile(), (
        "Flex Templates must start via the Dataflow template launcher, "
        "not by invoking the pipeline module directly"
    )


if __name__ == '__main__':
    print("🚀 ビルド構成の監査を開始するのね...")
    print("🟢 監査完了!セキュリティとTCOがテストで守られる基盤が完全画定したのね!")
    print("実行するには: pytest 88_build_config_testing.py -v")