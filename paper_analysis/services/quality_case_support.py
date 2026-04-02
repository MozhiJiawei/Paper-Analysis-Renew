from __future__ import annotations

import json
import os
import unittest
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]


CATEGORY_LABELS: dict[str, str] = {
    "quality_checks": "质量检查",
    "unit_tests": "单元测试",
    "e2e_tests": "E2E 测试",
}


STAGE_TO_CATEGORY: dict[str, str] = {
    "lint": "quality_checks",
    "unit": "unit_tests",
    "integration": "unit_tests",
    "e2e": "e2e_tests",
}


STAGE_SOURCE_LABELS: dict[str, str] = {
    "lint": "lint",
    "unit": "unit",
    "integration": "integration",
    "e2e": "e2e",
}


LINT_CASE_METADATA: dict[str, dict[str, str]] = {
    "repo_rules": {
        "title": "仓库规范检查",
        "description": "检查 UTF-8、疑似乱码片段，以及非 Python 文本文件的基础卫生规则。",
        "failure_check": "命令退出码非 0 时判定失败。",
        "source_label": "repo rules",
        "script_path": str(REPO_ROOT / "scripts" / "quality" / "lint.py"),
    },
    "ruff": {
        "title": "Ruff Python 静态检查",
        "description": "检查 Python 文件的通用静态问题，例如未使用导入、重复定义与 import 风格。",
        "failure_check": "命令退出码非 0 时判定失败。",
        "source_label": "ruff",
        "script_path": "py -m ruff check .",
    },
    "mypy": {
        "title": "Mypy 类型检查",
        "description": "在首批核心结构化模块上执行真实类型检查，避免只检查注解存在性的假安全感。",
        "failure_check": "命令退出码非 0 时判定失败。",
        "source_label": "mypy",
        "script_path": "py -m mypy --config-file pyproject.toml",
    },
    "quality_report": {
        "title": "代码质量治理报告",
        "description": "输出复杂度、长函数、大文件与模块依赖热点，默认只告警不阻断。",
        "failure_check": "该子检查只提供治理提示，不影响 quality lint 的退出码。",
        "source_label": "quality report",
        "script_path": str(REPO_ROOT / "scripts" / "quality" / "quality_report.py"),
    },
}


@dataclass(slots=True)
class QualityCaseResult:
    stage_name: str
    case_id: str
    title: str
    status: str
    description: str
    failure_check: str
    process_log: list[str] = field(default_factory=list)
    result_log: str = ""
    source_label: str = ""
    artifact_paths: list[str] = field(default_factory=list)
    script_path: str = ""

    @property
    def category_key(self) -> str:
        return STAGE_TO_CATEGORY.get(self.stage_name, "unit_tests")


def write_case_results(path: Path, cases: list[QualityCaseResult]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"cases": [asdict(case) for case in cases]}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_case_results(path: Path) -> list[QualityCaseResult]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_cases = payload.get("cases", [])
    cases: list[QualityCaseResult] = []
    for item in raw_cases:
        if not isinstance(item, dict):
            continue
        cases.append(
            QualityCaseResult(
                stage_name=str(item.get("stage_name", "")),
                case_id=str(item.get("case_id", "")),
                title=str(item.get("title", "")),
                status=str(item.get("status", "")),
                description=str(item.get("description", "")),
                failure_check=str(item.get("failure_check", "")),
                process_log=_coerce_string_list(item.get("process_log")),
                result_log=str(item.get("result_log", "")),
                source_label=str(item.get("source_label", "")),
                artifact_paths=_coerce_string_list(item.get("artifact_paths")),
                script_path=str(item.get("script_path", "")),
            )
        )
    return cases


def build_stage_case_result(
    stage_name: str,
    status: str,
    description: str,
    summary: str,
    output: str,
    artifact_path: str,
) -> QualityCaseResult:
    process_log = [
        f"执行阶段：{stage_name}",
        f"摘要：{summary}",
        f"原始产物：{artifact_path}",
    ]
    return QualityCaseResult(
        stage_name=stage_name,
        case_id=f"quality.{stage_name}",
        title=f"{stage_name} 阶段",
        status=status,
        description=description,
        failure_check="命令退出码非 0 时判定失败。",
        process_log=process_log,
        result_log=output.strip() or "无输出。",
        source_label=STAGE_SOURCE_LABELS.get(stage_name, stage_name),
        artifact_paths=[artifact_path],
        script_path=_infer_quality_script_path(stage_name),
    )


def build_lint_case_result(
    *,
    case_key: str,
    status: str,
    summary: str,
    output: str,
    artifact_paths: list[str] | None = None,
    extra_process_logs: list[str] | None = None,
) -> QualityCaseResult:
    metadata = LINT_CASE_METADATA[case_key]
    process_log = [
        "执行阶段：lint",
        f"执行子检查：{case_key}",
        f"摘要：{summary}",
    ]
    if extra_process_logs:
        process_log.extend(extra_process_logs)
    return QualityCaseResult(
        stage_name="lint",
        case_id=f"quality.lint.{case_key}",
        title=metadata["title"],
        status=status,
        description=metadata["description"],
        failure_check=metadata["failure_check"],
        process_log=process_log,
        result_log=output.strip() or "无输出。",
        source_label=metadata["source_label"],
        artifact_paths=artifact_paths or [],
        script_path=metadata["script_path"],
    )


def discover_skipped_test_cases(
    *,
    stage_name: str,
    start_dir: Path,
    pattern: str,
    top_level_dir: Path,
    reason: str,
) -> list[QualityCaseResult]:
    discover_start_dir = str(start_dir)
    if start_dir.is_absolute() and top_level_dir.is_absolute():
        discover_start_dir = str(start_dir.relative_to(top_level_dir))
    previous_cwd = Path.cwd()
    os.chdir(top_level_dir)
    try:
        suite = unittest.defaultTestLoader.discover(
            start_dir=discover_start_dir,
            pattern=pattern,
        )
    except ImportError:
        return [
            QualityCaseResult(
                stage_name=stage_name,
                case_id=f"{stage_name}.skipped",
                title=f"{stage_name} 阶段",
                status="skipped",
                description=f"{stage_name} 阶段未执行，无法枚举更细的测试用例。",
                failure_check="前置阶段失败时，本用例按未执行处理。",
                process_log=[reason, "未能发现测试列表，回退为阶段级未执行记录。"],
                result_log=reason,
                source_label=STAGE_SOURCE_LABELS.get(stage_name, stage_name),
                script_path=_infer_test_directory_path(stage_name),
            )
        ]
    finally:
        os.chdir(previous_cwd)
    cases: list[QualityCaseResult] = []
    for test in iter_test_cases(suite):
        cases.append(
            build_test_case_result(
                stage_name=stage_name,
                test=test,
                status="skipped",
                result_log=reason,
                default_process_log=[reason],
            )
        )
    return cases


def build_test_case_result(
    *,
    stage_name: str,
    test: unittest.TestCase,
    status: str,
    result_log: str,
    default_process_log: list[str] | None = None,
) -> QualityCaseResult:
    case_id = test.id()
    short_description = test.shortDescription()
    description = short_description or f"执行 {case_id}，验证该测试场景符合预期。"
    title = _case_title(test, short_description=short_description)
    failure_check = str(
        getattr(
            test,
            "failure_check_description",
            "断言失败、抛出异常，或测试结果被框架标记为失败时判定失败。",
        )
    )
    process_log = _coerce_string_list(getattr(test, "case_process_logs", []))
    if not process_log:
        process_log = default_process_log or ["测试框架执行了该用例，未记录更细的过程日志。"]
    artifact_paths = _coerce_string_list(getattr(test, "case_artifacts", []))
    source_label = str(getattr(test, "case_source_label", STAGE_SOURCE_LABELS.get(stage_name, stage_name)))
    script_path = str(getattr(test, "case_script_path", "")) or _infer_case_script_path(stage_name, test)
    return QualityCaseResult(
        stage_name=stage_name,
        case_id=case_id,
        title=title,
        status=status,
        description=description,
        failure_check=failure_check,
        process_log=process_log,
        result_log=result_log.strip() or f"测试结果：{status}",
        source_label=source_label,
        artifact_paths=artifact_paths,
        script_path=script_path,
    )


def iter_test_cases(suite: unittest.TestSuite) -> list[unittest.TestCase]:
    cases: list[unittest.TestCase] = []
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            cases.extend(iter_test_cases(item))
            continue
        if isinstance(item, unittest.TestCase):
            cases.append(item)
    return cases


def _case_title(test: unittest.TestCase, *, short_description: str | None = None) -> str:
    explicit_title = getattr(test, "case_title", "")
    if explicit_title:
        return str(explicit_title)
    if short_description:
        return str(short_description).strip().rstrip("。")
    method_name = getattr(test, "_testMethodName", "case")
    humanized = method_name.replace("test_", "").replace("_", " ")
    return f"验证 {humanized} 场景"


def _coerce_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _infer_quality_script_path(stage_name: str) -> str:
    if stage_name == "lint":
        return str(REPO_ROOT / "scripts" / "quality" / "lint.py")
    return ""


def _infer_test_directory_path(stage_name: str) -> str:
    stage_dir = {"unit": "tests/unit", "integration": "tests/integration", "e2e": "tests/e2e"}.get(stage_name, "")
    if not stage_dir:
        return ""
    return str(REPO_ROOT / Path(stage_dir))


def _infer_case_script_path(stage_name: str, test: unittest.TestCase) -> str:
    module_name = test.__class__.__module__
    if not module_name:
        return _infer_test_directory_path(stage_name)
    filename = f"{module_name.split('.')[-1]}.py"
    base_dir = {
        "unit": REPO_ROOT / "tests" / "unit",
        "integration": REPO_ROOT / "tests" / "integration",
        "e2e": REPO_ROOT / "tests" / "e2e",
    }.get(stage_name)
    if base_dir is None:
        return ""
    return str(base_dir / filename)
