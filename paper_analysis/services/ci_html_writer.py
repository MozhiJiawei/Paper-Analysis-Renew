from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from paper_analysis.services.quality_case_support import (
    CATEGORY_LABELS,
    QualityCaseResult,
    load_case_results,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates"
TEMPLATE_NAME = "ci_report.html.j2"


STAGE_DESCRIPTIONS: dict[str, str] = {
    "lint": "检查 UTF-8、行尾空格、制表符与结尾换行。",
    "typecheck": "检查公开函数的类型注解边界。",
    "unit": "验证共享领域模型、筛选逻辑与报告写入逻辑。",
    "integration": "验证 CLI 与 pipeline 的跨层协作。",
    "e2e": "验证顶会与 arXiv 黄金链路及其报告产物。",
}


STATUS_LABELS: dict[str, str] = {
    "passed": "通过",
    "failed": "失败",
    "skipped": "未执行",
    "missing": "缺失",
}


STATUS_PRIORITY: dict[str, int] = {
    "failed": 0,
    "missing": 1,
    "skipped": 2,
    "passed": 3,
}


@dataclass(slots=True)
class QualityStageResult:
    stage_name: str
    status: str
    summary: str
    artifact_path: str
    output: str

    @property
    def description(self) -> str:
        return STAGE_DESCRIPTIONS.get(self.stage_name, "未配置说明。")


@dataclass(slots=True)
class E2EReportSection:
    source: str
    status: str
    summary_markdown: str
    stdout: str
    count: int
    papers: list[dict[str, object]]
    report_dir: str
    note: str = ""

    @property
    def status_label(self) -> str:
        return STATUS_LABELS[self.status]


def write_ci_html_report(
    report_path: Path,
    stage_results: list[QualityStageResult],
    artifacts_dir: Path,
) -> Path:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    case_categories = _build_case_categories(stage_results, artifacts_dir)
    overall_status = "passed" if all(item.status == "passed" for item in stage_results) else "failed"
    e2e_sections = [_load_e2e_report(artifacts_dir, source) for source in ("conference", "arxiv")]
    env = _build_environment()
    template = env.get_template(TEMPLATE_NAME)
    html = template.render(
        title="CI 审核报告",
        overall_status=overall_status,
        overall_status_label=STATUS_LABELS[overall_status],
        stage_results=[_serialize_stage_result(item) for item in stage_results],
        case_categories=case_categories,
        e2e_sections=[_serialize_e2e_section(item) for item in e2e_sections],
        total_stages=len(stage_results),
        total_cases=sum(category["total_count"] for category in case_categories),
        passed_count=sum(1 for item in stage_results if item.status == "passed"),
        failed_count=sum(1 for item in stage_results if item.status == "failed"),
        skipped_count=sum(1 for item in stage_results if item.status == "skipped"),
    )
    report_path.write_text(html, encoding="utf-8")
    return report_path


def _build_environment() -> Environment:
    return Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def _serialize_stage_result(result: QualityStageResult) -> dict[str, str]:
    return {
        "stage_name": result.stage_name,
        "status": result.status,
        "status_label": STATUS_LABELS[result.status],
        "summary": result.summary,
        "artifact_path": result.artifact_path,
        "output": result.output.strip() or "无输出。",
        "description": result.description,
    }


def _serialize_e2e_section(section: E2EReportSection) -> dict[str, object]:
    return {
        "source": section.source,
        "source_name": _source_name(section.source),
        "status": section.status,
        "status_label": section.status_label,
        "summary_markdown": section.summary_markdown,
        "stdout": section.stdout,
        "count": section.count,
        "papers": section.papers,
        "report_dir": section.report_dir,
        "note": section.note,
    }


def _build_case_categories(
    stage_results: list[QualityStageResult],
    artifacts_dir: Path,
) -> list[dict[str, object]]:
    categories: dict[str, list[QualityCaseResult]] = {
        "quality_checks": [],
        "unit_tests": [],
        "e2e_tests": [],
    }
    for stage_result in stage_results:
        for case in _load_stage_cases(stage_result, artifacts_dir):
            categories.setdefault(case.category_key, []).append(case)

    serialized_categories: list[dict[str, object]] = []
    for category_key in ("quality_checks", "unit_tests", "e2e_tests"):
        cases = _sort_cases(categories.get(category_key, []))
        serialized_categories.append(
            {
                "category_key": category_key,
                "label": CATEGORY_LABELS[category_key],
                "status": _status_from_cases(cases),
                "status_label": STATUS_LABELS[_status_from_cases(cases)],
                "cases": [_serialize_case_result(case) for case in cases],
                "total_count": len(cases),
                "passed_count": sum(1 for item in cases if item.status == "passed"),
                "failed_count": sum(1 for item in cases if item.status == "failed"),
                "skipped_count": sum(1 for item in cases if item.status == "skipped"),
            }
        )
    return serialized_categories


def _sort_cases(cases: list[QualityCaseResult]) -> list[QualityCaseResult]:
    return sorted(
        cases,
        key=lambda item: (
            item.title,
            item.source_label,
            STATUS_PRIORITY.get(item.status, 99),
        ),
    )


def _load_stage_cases(stage_result: QualityStageResult, artifacts_dir: Path) -> list[QualityCaseResult]:
    case_artifact = artifacts_dir / "quality" / f"{stage_result.stage_name}-cases-latest.json"
    if case_artifact.exists():
        return load_case_results(case_artifact)
    return [
        QualityCaseResult(
            stage_name=stage_result.stage_name,
            case_id=f"{stage_result.stage_name}.stage",
            title=f"{stage_result.stage_name} 阶段",
            status=stage_result.status,
            description=stage_result.description,
            failure_check="阶段退出码非 0 时判定失败。",
            process_log=[
                f"未找到 {case_artifact.relative_to(artifacts_dir.parent)}，回退为阶段级显示。",
                f"阶段摘要：{stage_result.summary}",
            ],
            result_log=stage_result.output.strip() or "无输出。",
            source_label=stage_result.stage_name,
            artifact_paths=[stage_result.artifact_path],
        )
    ]


def _serialize_case_result(case: QualityCaseResult) -> dict[str, object]:
    return {
        "case_id": case.case_id,
        "title": case.title,
        "status": case.status,
        "status_label": STATUS_LABELS[case.status],
        "description": case.description,
        "failure_check": case.failure_check,
        "process_log": case.process_log,
        "result_log": case.result_log,
        "source_label": case.source_label or case.stage_name,
        "artifact_links": [_serialize_local_link(path) for path in case.artifact_paths],
        "script_link": _serialize_local_link(case.script_path),
    }


def _status_from_cases(cases: list[QualityCaseResult]) -> str:
    if any(item.status == "failed" for item in cases):
        return "failed"
    if cases and all(item.status == "passed" for item in cases):
        return "passed"
    return "skipped"


def _load_e2e_report(artifacts_dir: Path, source: str) -> E2EReportSection:
    report_dir = artifacts_dir / "e2e" / source / "latest"
    summary_path = report_dir / "summary.md"
    stdout_path = report_dir / "stdout.txt"
    json_path = report_dir / "result.json"

    summary_markdown = _read_text_if_exists(summary_path)
    stdout = _read_text_if_exists(stdout_path)

    if not json_path.exists():
        return E2EReportSection(
            source=source,
            status="missing",
            summary_markdown=summary_markdown,
            stdout=stdout,
            count=0,
            papers=[],
            report_dir=str(report_dir),
            note="尚未找到 result.json，可能是对应 e2e 报告尚未生成。",
        )

    try:
        payload = json.loads(json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return E2EReportSection(
            source=source,
            status="failed",
            summary_markdown=summary_markdown,
            stdout=stdout,
            count=0,
            papers=[],
            report_dir=str(report_dir),
            note="result.json 存在但无法解析，请检查对应 e2e 产物是否写入完整。",
        )

    papers = payload.get("papers", [])
    count = int(payload.get("count", len(papers)))
    return E2EReportSection(
        source=source,
        status="passed",
        summary_markdown=summary_markdown,
        stdout=stdout,
        count=count,
        papers=papers if isinstance(papers, list) else [],
        report_dir=str(report_dir),
    )


def _source_name(source: str) -> str:
    return "顶会" if source == "conference" else "arXiv"


def _read_text_if_exists(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _serialize_local_link(path: str) -> dict[str, str]:
    if not path:
        return {"label": "", "path": "", "href": ""}
    resolved_path = Path(path)
    if not resolved_path.is_absolute():
        resolved_path = REPO_ROOT / resolved_path
    try:
        label = str(resolved_path.relative_to(REPO_ROOT))
    except ValueError:
        label = str(resolved_path)
    return {
        "label": label.replace("\\", "/"),
        "path": str(resolved_path),
        "href": resolved_path.resolve().as_uri(),
    }
