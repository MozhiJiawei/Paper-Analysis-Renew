from __future__ import annotations

import argparse
import os
import sys
import traceback
import unittest
from pathlib import Path
from typing import Any, cast

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from paper_analysis.services.quality_case_support import (
    QualityCaseResult,
    build_test_case_result,
    write_case_results,
)


class CaseCollectingTextResult(unittest.TextTestResult):
    def __init__(
        self,
        stream: Any,
        descriptions: bool,
        verbosity: int,
        *,
        stage_name: str,
    ) -> None:
        super().__init__(stream, descriptions, verbosity)
        self.stage_name = stage_name
        self.case_results: list[QualityCaseResult] = []

    def addSuccess(self, test: unittest.TestCase) -> None:
        super().addSuccess(test)
        self.case_results.append(
            build_test_case_result(
                stage_name=self.stage_name,
                test=test,
                status="passed",
                result_log="测试通过。",
            )
        )

    def addFailure(
        self,
        test: unittest.TestCase,
        err: Any,
    ) -> None:
        super().addFailure(test, err)
        self.case_results.append(
            build_test_case_result(
                stage_name=self.stage_name,
                test=test,
                status="failed",
                result_log=_format_error(err),
            )
        )

    def addError(
        self,
        test: unittest.TestCase,
        err: Any,
    ) -> None:
        super().addError(test, err)
        self.case_results.append(
            build_test_case_result(
                stage_name=self.stage_name,
                test=test,
                status="failed",
                result_log=_format_error(err),
            )
        )

    def addSkip(self, test: unittest.TestCase, reason: str) -> None:
        super().addSkip(test, reason)
        self.case_results.append(
            build_test_case_result(
                stage_name=self.stage_name,
                test=test,
                status="skipped",
                result_log=reason,
                default_process_log=[reason],
            )
        )


class CaseCollectingTextRunner(unittest.TextTestRunner):
    def __init__(self, *, stage_name: str) -> None:
        super().__init__(stream=sys.stdout, verbosity=2)
        self.stage_name = stage_name

    def _makeResult(self) -> CaseCollectingTextResult:
        return CaseCollectingTextResult(
            self.stream,
            self.descriptions,
            self.verbosity,
            stage_name=self.stage_name,
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="运行指定 unittest 阶段并写出用例级结果。")
    parser.add_argument("--stage", required=True)
    parser.add_argument("--start-dir", required=True)
    parser.add_argument("--pattern", default="test_*.py")
    parser.add_argument("--top-level-dir", default=".")
    parser.add_argument("--case-report-path", required=True)
    args = parser.parse_args()

    case_report_path = Path(args.case_report_path)
    try:
        previous_cwd = Path.cwd()
        os.chdir(args.top_level_dir)
        try:
            suite = unittest.defaultTestLoader.discover(
                start_dir=args.start_dir,
                pattern=args.pattern,
            )
        finally:
            os.chdir(previous_cwd)
        runner = CaseCollectingTextRunner(stage_name=args.stage)
        result = cast(CaseCollectingTextResult, runner.run(suite))
        write_case_results(case_report_path, result.case_results)
        return 0 if result.wasSuccessful() else 1
    except Exception:
        write_case_results(
            case_report_path,
            [
                QualityCaseResult(
                    stage_name=args.stage,
                    case_id=f"{args.stage}.runner",
                    title=f"{args.stage} runner",
                    status="failed",
                    description="测试阶段启动或发现测试用例时失败。",
                    failure_check="测试发现、导入或执行阶段抛出异常时判定失败。",
                    process_log=[
                        f"start_dir={args.start_dir}",
                        f"pattern={args.pattern}",
                        f"top_level_dir={args.top_level_dir}",
                    ],
                    result_log=traceback.format_exc(),
                    source_label=args.stage,
                    artifact_paths=[str(case_report_path)],
                )
            ],
        )
        traceback.print_exc()
        return 1


def _format_error(err: Any) -> str:
    if not isinstance(err, tuple) or len(err) != 3:
        return repr(err)
    exc_type, exc_value, exc_traceback = err
    return "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))


if __name__ == "__main__":
    raise SystemExit(main())
