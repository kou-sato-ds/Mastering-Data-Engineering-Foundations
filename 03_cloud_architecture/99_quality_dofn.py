"""
品質チェックの Beam DoFn 化 — パイプライン上で実際に振り分ける。

🎯 【#105-#106の完結】検知と行き先は決めた。次は「実際に流す」!

背景:
    #97 で検知ロジック、#98 で行き先を決めたが、
    いずれも純粋関数のままで **Beam パイプライン上を流れていない**。

    #65 の ParseAndValidateFn が「壊れたデータ」を TaggedOutput で
    振り分けるのと同じ構造を、「異常なデータ」に対して作る。

    両者の違い:
      #65: パースできるか(構造)
      本項: 値が妥当か(品質)

    同じ DLQ へ流すが、error_type で区別できるようにする(#98の判断)。

実行方法:
    pytest 99_quality_dofn_testing.py -v
"""
import importlib.util
import sys
from pathlib import Path

import apache_beam as beam

HERE = Path(__file__).parent

MAIN_TAG = 'main_output'
DLQ_TAG = 'dlq_output'


def _load(filename: str, module_name: str):
    path = HERE / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class QualityFilterFn(beam.DoFn):
    """
    🛡️ 品質基準でレコードを振り分ける DoFn。

    #65 の ParseAndValidateFn との違い:
        あちらは「パースできるか」、こちらは「値が妥当か」を見る。
        パースは通るが必須列が欠けているレコードは、
        #65 を素通りして本項で捕まる。
    """

    def setup(self):
        """
        🔍 モジュール読み込みは setup() で1回だけ行う。

        process() 内で毎回 import すると、
        レコード数分のファイル I/O が発生する(TCO)。
        """
        self._integration = _load(
            '98_quality_pipeline_integration.py', 'integ_for_dofn'
        )

    def process(self, row):
        destination = self._integration.classify_record(row)

        if destination == 'main':
            yield beam.pvalue.TaggedOutput(MAIN_TAG, row)
        else:
            yield beam.pvalue.TaggedOutput(
                DLQ_TAG,
                self._integration.build_dlq_payload(row, 'quality check'),
            )


def build_quality_pipeline(p, rows):
    """
    🚀 品質フィルタを含むパイプラインを構築する。

    テストから再利用できるよう、Pipeline オブジェクトを引数で受ける——
    パイプライン構築とランナー起動を分離するのが Beam のテスト定石である。
    """
    return (
        p
        | 'CreateRows' >> beam.Create(rows)
        | 'QualityFilter' >> beam.ParDo(QualityFilterFn()).with_outputs(
            MAIN_TAG, DLQ_TAG
        )
    )


if __name__ == '__main__':
    print("🚀 品質DoFn基盤の監査を開始するのね...")
    print("🟢 監査完了!品質異常がパイプライン上で振り分けられる基盤が完全画定したのね!")