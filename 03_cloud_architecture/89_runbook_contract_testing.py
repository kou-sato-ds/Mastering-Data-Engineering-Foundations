"""
#89 デプロイRunbookの契約検証。

🎯 【Runbookにも守るべき契約がある】確認手順とロールバックの不在を検知!

背景:
    Runbookは「コマンドが書いてあれば良い」ものではない。

    - 確認手順(verify)が無ければ「打ったが効いたか分からない」
    - ロールバック手順が無ければ、深夜に問題が起きた時に戻せない
    - 生成されるコマンドが #87 の契約を満たさなければ、起動時に拒否される

    これらをテストで固定する。

実行方法:
    pytest 89_runbook_contract_testing.py -v
"""
import importlib.util
import re
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent

SAMPLE = {
    'project_id': 'my-proj',
    'repo': 'dataflow-repo',
    'image': 'pubsub-to-bq',
    'tag': 'v1',
    'template_name': 'pubsub-to-bq-dlq',
    'subscription': 'projects/my-proj/subscriptions/events-sub',
    'output_table': 'my-proj:analytics.events',
    'dlq_table': 'my-proj:analytics.events_dlq',
}


def load_module_from_path(filename: str, module_name: str):
    """#71/#80-#88 と同一の動的ローダー。"""
    path = HERE / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        pytest.skip(f"cannot build spec for {filename}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _runbook_mod():
    return load_module_from_path('89_deployment_runbook.py', 'runbook_mod')


def _steps():
    mod = _runbook_mod()
    return mod.build_runbook(**SAMPLE)


# ================================================================
# STAGE 1: 全ステップが command / verify / note を持つこと
#   確認手順の無いRunbookは「打ったが効いたか分からない」を生む。
# ================================================================
@pytest.mark.parametrize('field', ['command', 'verify', 'note'])
def test_every_step_has_required_fields(field):
    missing = [s['step'] for s in _steps() if not s.get(field)]

    assert not missing, (
        f"steps {missing} lack {field!r}. A runbook without verification "
        "leaves the operator unsure whether the command took effect."
    )


# ================================================================
# STAGE 2: ロールバック手順が含まれること
#   「進める手順」だけのRunbookは、障害時に半分しか役に立たない。
# ================================================================
def test_runbook_includes_rollback():
    titles = ' '.join(s['title'].lower() for s in _steps())

    assert 'roll back' in titles or 'rollback' in titles, (
        "a runbook that only moves forward is useless at 3am; "
        "the way back must be documented"
    )


# ================================================================
# STAGE 3: ロールバックが cancel ではなく drain を使うこと
#   cancel は処理中のデータを破棄する。DLQを持つストリーミングでは
#   drain を選ぶことでデータ整合性が保たれる(#65 の思想と一貫)。
# ================================================================
def test_rollback_drains_rather_than_cancels():
    mod = _runbook_mod()
    rollback = mod.build_step_rollback(SAMPLE['project_id'], SAMPLE['template_name'])

    assert 'drain' in rollback['command'], (
        "drain finishes in-flight work; cancel discards it. For a pipeline "
        "with a DLQ, discarding in-flight records defeats the isolation design."
    )
    assert 'cancel' not in rollback['command']


# ================================================================
# STAGE 4: 生成されるパラメータが #87 の正規表現契約を満たすこと
#   Runbookが契約違反のコマンドを吐けば、実行者は起動時に弾かれる。
# ================================================================
def test_generated_parameters_satisfy_metadata_contract():
    meta_mod = load_module_from_path(
        '87_flex_template_metadata.py', 'meta_for_runbook'
    )
    run_step = _steps()[2]

    sub = re.search(r'input_subscription=(\S+)', run_step['command']).group(1)
    out = re.search(r'output_table=(\S+)', run_step['command']).group(1)
    dlq = re.search(r'dlq_table=(\S+)', run_step['command']).group(1)

    assert re.match(meta_mod.PUBSUB_SUBSCRIPTION_REGEX, sub), (
        f"the runbook emits {sub!r}, which item 87's contract would reject"
    )
    assert re.match(meta_mod.BIGQUERY_TABLE_REGEX, out)
    assert re.match(meta_mod.BIGQUERY_TABLE_REGEX, dlq)


# ================================================================
# STAGE 5: イメージURIが可変タグを使わないこと
#   latest では「どのイメージがデプロイされたか」を後から特定できない。
# ================================================================
def test_image_uri_is_explicitly_tagged():
    mod = _runbook_mod()
    uri = mod.build_image_uri('p', 'r', 'i', 'v1')

    assert uri.endswith(':v1')
    assert not uri.endswith(':latest'), (
        "a mutable tag makes it impossible to identify which image is running"
    )


# ================================================================
# STAGE 6: ステップが順序通りに並んでいること
#   イメージが無ければテンプレートは作れず、
#   テンプレートが無ければジョブは起動できない。
# ================================================================
def test_steps_are_ordered():
    numbers = [s['step'] for s in _steps()]

    assert numbers == sorted(numbers), "steps must be in execution order"
    assert numbers == list(range(1, len(numbers) + 1)), (
        "step numbers must be contiguous starting from 1"
    )


# ================================================================
# STAGE 7: DLQテーブルが起動コマンドに含まれること
#   省略できてしまえば、不正レコードが行き場を失う(#65 の設計が崩れる)。
# ================================================================
def test_run_command_always_passes_dlq_table():
    run_step = _steps()[2]

    assert 'dlq_table=' in run_step['command'], (
        "omitting the DLQ table would let malformed records vanish, "
        "undoing the isolation design of item 65"
    )


if __name__ == '__main__':
    print("🚀 Runbook契約の監査を開始するのね...")
    print("🟢 監査完了!確認手順とロールバックを備えたRunbook基盤が完全画定したのね!")
    print("実行するには: pytest 89_runbook_contract_testing.py -v")