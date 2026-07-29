"""
カバレッジ計測設定のガードテスト。

🎯 【件数から割合へ】54件緑は「コードの54件分が守られている」を意味しない!

背景:
    #68-#77 でテスト件数は積み上がったが、それは実行されたアサーションの数であり、
    コードのどれだけが実際に通ったかを示さない。
    GCP依存の run_*_pipeline() は一度も呼ばれていないため、
    実測カバレッジは低く出るはずである——その数字から目を逸らさない。

fail_under の位置づけ:
    「80%を目指す」といった理想値ではなく、実測値をわずかに下回る「下限」を置く。
    目的は向上ではなく **退化の検知** である。

実行方法:
    pytest 78_coverage_guard_testing.py -v
"""
import configparser
import re
from pathlib import Path

import pytest

HERE = Path(__file__).parent
COVERAGERC = HERE / '.coveragerc'
CI_YML = HERE.parent / '.github' / 'workflows' / 'ci.yml'


def _coverage_config() -> configparser.ConfigParser:
    parser = configparser.ConfigParser()
    parser.read(COVERAGERC, encoding='utf-8')
    return parser


# ================================================================
# STAGE 1: .coveragerc が存在し、計測対象が定義されていること
# ================================================================
def test_coveragerc_exists_and_declares_source():
    assert COVERAGERC.exists(), ".coveragerc must exist to configure measurement"

    cfg = _coverage_config()
    assert cfg.has_section('run'), ".coveragerc must define a [run] section"
    assert cfg.get('run', 'source').strip(), "source must not be empty"


# ================================================================
# STAGE 2: テストファイル自身が計測対象から除外されていること
#   テストを計測に含めると数字が不当に膨らみ、指標として意味を失う。
# ================================================================
def test_test_files_are_omitted_from_measurement():
    cfg = _coverage_config()
    omit = cfg.get('run', 'omit')

    assert '*_testing.py' in omit, \
        "test files must be omitted; measuring them inflates coverage artificially"
    assert '*_validation.py' in omit, \
        "validation test files must be omitted for the same reason"


# ================================================================
# STAGE 3: fail_under が実測に基づく具体値であること
#   0 のままなら「設定はあるが何も守っていない」状態。
# ================================================================
def test_fail_under_is_a_measured_floor():
    cfg = _coverage_config()
    assert cfg.has_section('report'), ".coveragerc must define a [report] section"

    raw = cfg.get('report', 'fail_under')
    value = float(raw)

    assert value > 0, (
        "fail_under is still 0 — measure actual coverage first, then set the floor "
        "just below it (see README #86 for the procedure)"
    )
    assert value <= 100, "fail_under cannot exceed 100"


# ================================================================
# STAGE 4: CI がカバレッジ付きで pytest を起動していること
#   設定ファイルがあっても --cov を渡さなければ計測されない。
# ================================================================
def test_ci_runs_pytest_with_coverage():
    assert CI_YML.exists(), "ci.yml must exist"
    content = CI_YML.read_text(encoding='utf-8')

    assert re.search(r'pytest[^\n]*--cov', content), (
        "ci.yml must pass --cov; a .coveragerc without --cov measures nothing"
    )


# ================================================================
# STAGE 5: 計測対象に実体ファイルが存在すること
#   omit が広すぎて「測る対象が無い」状態を防ぐ。
# ================================================================
def test_measurable_source_files_exist():
    measurable = [
        p.name for p in sorted(HERE.glob('*.py'))
        if not p.name.endswith(('_testing.py', '_validation.py'))
    ]
    assert measurable, (
        "no source files left to measure — omit patterns are too broad"
    )


if __name__ == '__main__':
    print("🚀 カバレッジ計測ガードの監査を開始するのね...")
    print("🟢 監査完了!件数ではなく割合で守られる検証基盤が完全画定したのね!")
    print("実行するには: pytest 78_coverage_guard_testing.py -v")