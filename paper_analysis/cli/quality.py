from __future__ import annotations

import os
import subprocess
import sys
from argparse import Namespace
from pathlib import Path
from typing import Any

from paper_analysis.shared.encoding import build_utf8_subprocess_env
from paper_analysis.services.ci_html_writer import QualityStageResult, write_ci_html_report
from paper_analysis.services.quality_case_support import (
    build_stage_case_result,
    discover_skipped_test_cases,
    write_case_results,
)
from paper_analysis.shared.paths import ARTIFACTS_DIR, ROOT_DIR


SCRIPT_ROOT = Path(__file__).resolve().parents[2]


UNITTEST_STAGE_CONFIG: dict[str, dict[str, str]] = {
    "unit": {"start_dir": "tests/unit", "pattern": "test_*.py"},
    "integration": {"start_dir": "tests/integration", "pattern": "test_*.py"},
    "e2e": {"start_dir": "tests/e2e", "pattern": "test_*.py"},
}


QUALITY_STAGES: list[tuple[str, list[str]]] = [
    ("lint", [sys.executable, "scripts/quality/lint.py"]),
    ("typecheck", [sys.executable, "scripts/quality/typecheck.py"]),
    ("unit", []),
    ("integration", []),
    ("e2e", []),
]

for index, (stage_name, _command) in enumerate(QUALITY_STAGES):
    if stage_name in UNITTEST_STAGE_CONFIG:
        QUALITY_STAGES[index] = (stage_name, [])


def register(subparsers: Any) -> None:
    parser = subparsers.add_parser("quality", help="本地质量门禁")
    quality_subparsers = parser.add_subparsers(dest="quality_action", required=True)

    local_ci_parser = quality_subparsers.add_parser(
        "local-ci",
        help="按 lint -> typecheck -> unit -> integration -> e2e 顺序执行",
    )
    local_ci_parser.set_defaults(handler=handle_local_ci)

    for stage_name, _command in _quality_stage_entries():
        stage_parser = quality_subparsers.add_parser(stage_name, help=f"只运行 {stage_name} 阶段")
        stage_parser.set_defaults(handler=handle_single_stage, stage_name=stage_name)


def handle_local_ci(_args: Namespace) -> int:
    stage_results: list[QualityStageResult] = []
    for stage_name, command in _quality_stage_entries():
        exit_code, stage_result = _run_stage(stage_name, command)
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
    command = _quality_stage_commands()[args.stage_name]
    exit_code, _stage_result = _run_stage(args.stage_name, command)
    return exit_code


def _run_stage(stage_name: str, command: list[str]) -> tuple[int, QualityStageResult]:
    artifacts_dir = ARTIFACTS_DIR / "quality"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifacts_dir / f"{stage_name}-latest.txt"
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

    if result.returncode == 0:
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
    return result.returncode, stage_result


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
    failed_index = next(
        index for index, (stage_name, _command) in enumerate(_quality_stage_entries()) if stage_name == failed_stage_name
    )
    for stage_name, _command in _quality_stage_entries()[failed_index + 1 :]:
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


def _quality_stage_commands() -> dict[str, list[str]]:
    return dict(_quality_stage_entries())


def _quality_stage_entries() -> list[tuple[str, list[str]]]:
    entries: list[tuple[str, list[str]]] = []
    for stage_name, command in QUALITY_STAGES:
        if stage_name in UNITTEST_STAGE_CONFIG:
            entries.append((stage_name, _build_unittest_stage_command(stage_name)))
            continue
        entries.append((stage_name, command))
    return entries


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
    failed_index = next(
        index for index, (stage_name, _command) in enumerate(_quality_stage_entries()) if stage_name == failed_stage_name
    )
    for stage_name, _command in _quality_stage_entries()[failed_index + 1 :]:
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
