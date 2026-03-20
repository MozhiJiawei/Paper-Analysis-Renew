from __future__ import annotations

import os
import subprocess
import sys
from argparse import Namespace
from typing import Any

from paper_analysis.services.ci_html_writer import QualityStageResult, write_ci_html_report
from paper_analysis.shared.paths import ARTIFACTS_DIR, ROOT_DIR


QUALITY_STAGES: list[tuple[str, list[str]]] = [
    ("lint", [sys.executable, "scripts/quality/lint.py"]),
    ("typecheck", [sys.executable, "scripts/quality/typecheck.py"]),
    ("unit", [sys.executable, "-m", "unittest", "discover", "-s", "tests/unit", "-p", "test_*.py"]),
    (
        "integration",
        [sys.executable, "-m", "unittest", "discover", "-s", "tests/integration", "-p", "test_*.py"],
    ),
    ("e2e", [sys.executable, "-m", "unittest", "discover", "-s", "tests/e2e", "-p", "test_*.py"]),
]


def register(subparsers: Any) -> None:
    parser = subparsers.add_parser("quality", help="本地质量门禁")
    quality_subparsers = parser.add_subparsers(dest="quality_action", required=True)

    local_ci_parser = quality_subparsers.add_parser(
        "local-ci",
        help="按 lint -> typecheck -> unit -> integration -> e2e 顺序执行",
    )
    local_ci_parser.set_defaults(handler=handle_local_ci)

    for stage_name, _command in QUALITY_STAGES:
        stage_parser = quality_subparsers.add_parser(
            stage_name,
            help=f"只运行 {stage_name} 阶段",
        )
        stage_parser.set_defaults(handler=handle_single_stage, stage_name=stage_name)


def handle_local_ci(_args: Namespace) -> int:
    stage_results: list[QualityStageResult] = []
    for stage_name, command in QUALITY_STAGES:
        exit_code, stage_result = _run_stage(stage_name, command)
        stage_results.append(stage_result)
        if exit_code != 0:
            stage_results.extend(_build_skipped_stage_results(stage_name))
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
        return (
            0,
            QualityStageResult(
                stage_name=stage_name,
                status="passed",
                summary=first_non_empty_line(output) or "阶段通过",
                artifact_path=str(artifact_path.relative_to(ROOT_DIR)),
                output=output,
            ),
        )

    summary = first_non_empty_line(output) or "阶段执行失败"
    print(f"[FAIL] stage={stage_name}")
    print(f"summary: {summary}")
    print(f"next: run `py -m paper_analysis.cli.main quality {stage_name}`")
    print(f"artifact: {artifact_path.relative_to(ROOT_DIR)}")
    return (
        result.returncode,
        QualityStageResult(
            stage_name=stage_name,
            status="failed",
            summary=summary,
            artifact_path=str(artifact_path.relative_to(ROOT_DIR)),
            output=output,
        ),
    )


def build_subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def first_non_empty_line(content: str) -> str:
    for line in content.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def _build_skipped_stage_results(failed_stage_name: str) -> list[QualityStageResult]:
    skipped_results: list[QualityStageResult] = []
    failed_index = next(
        index for index, (stage_name, _command) in enumerate(QUALITY_STAGES) if stage_name == failed_stage_name
    )
    for stage_name, _command in QUALITY_STAGES[failed_index + 1 :]:
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
    return dict(QUALITY_STAGES)
