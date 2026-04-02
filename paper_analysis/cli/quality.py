from __future__ import annotations

import os
import subprocess
import sys
from argparse import Namespace
from pathlib import Path
from typing import Any

from paper_analysis.services.ci_html_writer import QualityStageResult, write_ci_html_report
from paper_analysis.services.quality_case_support import (
    build_lint_case_result,
    build_stage_case_result,
    discover_skipped_test_cases,
    write_case_results,
)
from paper_analysis.shared.encoding import build_utf8_subprocess_env
from paper_analysis.shared.paths import ARTIFACTS_DIR, ROOT_DIR

SCRIPT_ROOT = Path(__file__).resolve().parents[2]
LINT_STAGE_NAME = "lint"


UNITTEST_STAGE_CONFIG: dict[str, dict[str, str]] = {
    "unit": {"start_dir": "tests/unit", "pattern": "test_*.py"},
    "integration": {"start_dir": "tests/integration", "pattern": "test_*.py"},
    "e2e": {"start_dir": "tests/e2e", "pattern": "test_*.py"},
}


QUALITY_STAGES: list[str] = [LINT_STAGE_NAME, "unit", "integration", "e2e"]


STAGE_COMMAND_OVERRIDES: dict[str, list[str]] = {}
RUFF_TARGETS = [
    "paper_analysis/cli/quality.py",
    "paper_analysis/services/quality_case_support.py",
    "paper_analysis/services/ci_html_writer.py",
    "paper_analysis/domain/paper.py",
    "paper_analysis/domain/preference.py",
    "paper_analysis/api/evaluation_protocol.py",
    "paper_analysis/api/evaluation_predictor.py",
    "paper_analysis/api/evaluation_server.py",
    "paper_analysis/sources/arxiv/api_client.py",
    "paper_analysis/sources/arxiv/atom_parser.py",
    "paper_analysis/sources/arxiv/subscription_loader.py",
    "paper_analysis/services/report_writer.py",
    "scripts/quality/lint.py",
    "scripts/quality/quality_report.py",
    "scripts/quality/run_unittest_stage.py",
    "tests/unit/test_lint.py",
    "tests/unit/test_ci_html_writer.py",
    "tests/integration/test_quality_html.py",
    "tests/integration/test_cli_help.py",
]


LINT_SUBCHECKS: list[tuple[str, list[str]]] = [
    ("repo_rules", [sys.executable, "scripts/quality/lint.py"]),
    ("ruff", [sys.executable, "-m", "ruff", "check", *RUFF_TARGETS]),
    ("mypy", [sys.executable, "-m", "mypy", "--config-file", "pyproject.toml"]),
    ("quality_report", [sys.executable, "scripts/quality/quality_report.py"]),
]


LINT_BLOCKING_SUBCHECKS = {"repo_rules", "ruff", "mypy"}


def register(subparsers: Any) -> None:
    parser = subparsers.add_parser("quality", help="本地质量门禁")
    quality_subparsers = parser.add_subparsers(dest="quality_action", required=True)

    local_ci_parser = quality_subparsers.add_parser(
        "local-ci",
        help="按 lint -> unit -> integration -> e2e 顺序执行",
    )
    local_ci_parser.set_defaults(handler=handle_local_ci)

    for stage_name in _quality_stage_names():
        stage_parser = quality_subparsers.add_parser(stage_name, help=f"只运行 {stage_name} 阶段")
        stage_parser.set_defaults(handler=handle_single_stage, stage_name=stage_name)


def handle_local_ci(_args: Namespace) -> int:
    stage_results: list[QualityStageResult] = []
    for stage_name in _quality_stage_names():
        exit_code, stage_result = _run_quality_stage(stage_name)
        stage_results.append(stage_result)
        if exit_code != 0:
            stage_results.extend(_build_skipped_stage_results(stage_name))
            _write_skipped_case_artifacts(stage_name)
            _write_local_ci_html(stage_results)
            return exit_code

    _write_local_ci_html(stage_results)
    print("[OK] quality local-ci 全部通过。")
    return 0


def handle_single_stage(args: Namespace) -> int:
    exit_code, _stage_result = _run_quality_stage(args.stage_name)
    return exit_code


def _run_quality_stage(stage_name: str) -> tuple[int, QualityStageResult]:
    if stage_name == LINT_STAGE_NAME:
        return _run_lint_stage()
    return _run_simple_stage(stage_name, _command_for_stage(stage_name))


def _run_lint_stage() -> tuple[int, QualityStageResult]:
    artifacts_dir = ARTIFACTS_DIR / "quality"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    combined_artifact_path = artifacts_dir / "lint-latest.txt"

    case_results = []
    combined_sections: list[str] = []
    warning_detected = False
    blocking_exit_code = 0
    blocking_failure_summary = ""

    for index, (case_key, command) in enumerate(LINT_SUBCHECKS):
        output, return_code, artifact_path = _run_subprocess_to_artifact(
            command=command,
            artifact_path=artifacts_dir / f"lint-{case_key}-latest.txt",
        )
        summary = first_non_empty_line(output) or _default_lint_summary(case_key, return_code)

        if case_key in LINT_BLOCKING_SUBCHECKS:
            status = "passed" if return_code == 0 else "failed"
        else:
            status = "warning" if _is_quality_report_warning(output) else "passed"
            warning_detected = warning_detected or status == "warning"

        case_results.append(
            build_lint_case_result(
                case_key=case_key,
                status=status,
                summary=summary,
                output=output,
                artifact_paths=[
                    str(combined_artifact_path.relative_to(ROOT_DIR)),
                    str(artifact_path.relative_to(ROOT_DIR)),
                ],
            )
        )
        combined_sections.append(f"## {case_key}\n{output.strip() or '无输出。'}")

        if status == "failed":
            blocking_exit_code = return_code or 1
            blocking_failure_summary = summary
            for skipped_key, _skipped_command in LINT_SUBCHECKS[index + 1 :]:
                case_results.append(
                    build_lint_case_result(
                        case_key=skipped_key,
                        status="skipped",
                        summary="前置子检查失败，本子检查未执行",
                        output="前置子检查失败，本子检查未执行。",
                        artifact_paths=[str(combined_artifact_path.relative_to(ROOT_DIR))],
                    )
                )
                combined_sections.append(f"## {skipped_key}\n前置子检查失败，本子检查未执行。")
            break

    combined_output = "\n\n".join(combined_sections).strip() + "\n"
    combined_artifact_path.write_text(combined_output, encoding="utf-8")
    write_case_results(_case_artifact_path(LINT_STAGE_NAME), case_results)

    if blocking_exit_code != 0:
        print("[FAIL] stage=lint")
        print(f"summary: {blocking_failure_summary or 'lint 阶段失败'}")
        print("next: run `py -m paper_analysis.cli.main quality lint`")
        print(f"artifact: {combined_artifact_path.relative_to(ROOT_DIR)}")
        return (
            blocking_exit_code,
            QualityStageResult(
                stage_name=LINT_STAGE_NAME,
                status="failed",
                summary=blocking_failure_summary or "lint 阶段失败",
                artifact_path=str(combined_artifact_path.relative_to(ROOT_DIR)),
                output=combined_output,
            ),
        )

    summary = "仓库规范、Ruff 与 Mypy 通过"
    if warning_detected:
        summary += "；存在代码质量治理告警（不阻断）"
    print("[OK] stage=lint")
    if warning_detected:
        print("note: 发现代码质量治理告警，但不影响 lint 退出码。")
    return (
        0,
        QualityStageResult(
            stage_name=LINT_STAGE_NAME,
            status="passed",
            summary=summary,
            artifact_path=str(combined_artifact_path.relative_to(ROOT_DIR)),
            output=combined_output,
        ),
    )


def _run_simple_stage(stage_name: str, command: list[str]) -> tuple[int, QualityStageResult]:
    output, return_code, artifact_path = _run_subprocess_to_artifact(
        command=command,
        artifact_path=ARTIFACTS_DIR / "quality" / f"{stage_name}-latest.txt",
    )

    if return_code == 0:
        print(f"[OK] stage={stage_name}")
        stage_result = QualityStageResult(
            stage_name=stage_name,
            status="passed",
            summary=first_non_empty_line(output) or "阶段通过",
            artifact_path=str(artifact_path.relative_to(ROOT_DIR)),
            output=output,
        )
        _write_non_unittest_case_artifact(stage_result)
        return 0, stage_result

    summary = first_non_empty_line(output) or "阶段执行失败"
    print(f"[FAIL] stage={stage_name}")
    print(f"summary: {summary}")
    print(f"next: run `py -m paper_analysis.cli.main quality {stage_name}`")
    print(f"artifact: {artifact_path.relative_to(ROOT_DIR)}")
    stage_result = QualityStageResult(
        stage_name=stage_name,
        status="failed",
        summary=summary,
        artifact_path=str(artifact_path.relative_to(ROOT_DIR)),
        output=output,
    )
    _write_non_unittest_case_artifact(stage_result)
    return return_code, stage_result


def _run_subprocess_to_artifact(*, command: list[str], artifact_path: Path) -> tuple[str, int, Path]:
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        command,
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=build_subprocess_env(),
        check=False,
    )
    output = (result.stdout or "") + (result.stderr or "")
    artifact_path.write_text(output, encoding="utf-8")
    return output, result.returncode, artifact_path


def build_subprocess_env() -> dict[str, str]:
    return build_utf8_subprocess_env(os.environ.copy())


def first_non_empty_line(content: str) -> str:
    for line in content.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def _build_skipped_stage_results(failed_stage_name: str) -> list[QualityStageResult]:
    skipped_results: list[QualityStageResult] = []
    failed_index = _quality_stage_names().index(failed_stage_name)
    for stage_name in _quality_stage_names()[failed_index + 1 :]:
        skipped_results.append(
            QualityStageResult(
                stage_name=stage_name,
                status="skipped",
                summary="前置阶段失败，本阶段未执行",
                artifact_path=f"artifacts/quality/{stage_name}-latest.txt",
                output="",
            )
        )
    return skipped_results


def _write_local_ci_html(stage_results: list[QualityStageResult]) -> None:
    report_path = ARTIFACTS_DIR / "quality" / "local-ci-latest.html"
    write_ci_html_report(report_path=report_path, stage_results=stage_results, artifacts_dir=ARTIFACTS_DIR)


def _quality_stage_names() -> list[str]:
    return QUALITY_STAGES[:]


def _command_for_stage(stage_name: str) -> list[str]:
    if stage_name in STAGE_COMMAND_OVERRIDES:
        return STAGE_COMMAND_OVERRIDES[stage_name]
    if stage_name in UNITTEST_STAGE_CONFIG:
        return _build_unittest_stage_command(stage_name)
    raise KeyError(f"未找到阶段命令：{stage_name}")


def _build_unittest_stage_command(stage_name: str) -> list[str]:
    config = UNITTEST_STAGE_CONFIG[stage_name]
    return [
        sys.executable,
        str(SCRIPT_ROOT / "scripts" / "quality" / "run_unittest_stage.py"),
        "--stage",
        stage_name,
        "--start-dir",
        config["start_dir"],
        "--pattern",
        config["pattern"],
        "--top-level-dir",
        ".",
        "--case-report-path",
        str(_case_artifact_path(stage_name)),
    ]


def _case_artifact_path(stage_name: str) -> Path:
    return ARTIFACTS_DIR / "quality" / f"{stage_name}-cases-latest.json"


def _write_non_unittest_case_artifact(stage_result: QualityStageResult) -> None:
    if stage_result.stage_name in UNITTEST_STAGE_CONFIG:
        return
    write_case_results(
        _case_artifact_path(stage_result.stage_name),
        [
            build_stage_case_result(
                stage_name=stage_result.stage_name,
                status=stage_result.status,
                description=stage_result.description,
                summary=stage_result.summary,
                output=stage_result.output,
                artifact_path=stage_result.artifact_path,
            )
        ],
    )


def _write_skipped_case_artifacts(failed_stage_name: str) -> None:
    failed_index = _quality_stage_names().index(failed_stage_name)
    for stage_name in _quality_stage_names()[failed_index + 1 :]:
        if stage_name not in UNITTEST_STAGE_CONFIG:
            skipped_stage = QualityStageResult(
                stage_name=stage_name,
                status="skipped",
                summary="前置阶段失败，本阶段未执行",
                artifact_path=f"artifacts/quality/{stage_name}-latest.txt",
                output="",
            )
            _write_non_unittest_case_artifact(skipped_stage)
            continue

        config = UNITTEST_STAGE_CONFIG[stage_name]
        skipped_cases = discover_skipped_test_cases(
            stage_name=stage_name,
            start_dir=ROOT_DIR / config["start_dir"],
            pattern=config["pattern"],
            top_level_dir=ROOT_DIR,
            reason="前置阶段失败，本用例未执行。",
        )
        write_case_results(_case_artifact_path(stage_name), skipped_cases)


def _default_lint_summary(case_key: str, return_code: int) -> str:
    if case_key == "quality_report":
        return "未发现额外治理热点" if return_code == 0 else "代码质量治理报告执行失败"
    return f"{case_key} 通过" if return_code == 0 else f"{case_key} 失败"


def _is_quality_report_warning(output: str) -> bool:
    return first_non_empty_line(output).startswith("[WARN]")
