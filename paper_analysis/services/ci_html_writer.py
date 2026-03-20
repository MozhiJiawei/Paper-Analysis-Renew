from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from jinja2 import Environment, FileSystemLoader


STAGE_DESCRIPTIONS: dict[str, str] = {
    "lint": "检查 UTF-8、行尾空格、制表符与结尾换行。",
    "typecheck": "检查公开函数的类型注解边界。",
    "unit": "验证共享领域模型、筛选逻辑与报告写入逻辑。",
    "integration": "验证 CLI 与 pipeline 的跨层协作。",
    "e2e": "验证顶会与 arXiv 两条黄金路径及其报告产物。",
}


STATUS_LABELS: dict[str, str] = {
    "passed": "通过",
    "failed": "失败",
    "skipped": "未执行",
    "missing": "缺失",
}


TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates"
TEMPLATE_NAME = "ci_report.html.j2"


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
    overall_status = "passed" if all(item.status == "passed" for item in stage_results) else "failed"
    e2e_sections = [_load_e2e_report(artifacts_dir, source) for source in ("conference", "arxiv")]
    env = _build_environment()
    template = env.get_template(TEMPLATE_NAME)
    html = template.render(
        title="CI 审核报告",
        overall_status=overall_status,
        overall_status_label=STATUS_LABELS[overall_status],
        stage_results=[_serialize_stage_result(item) for item in stage_results],
        e2e_sections=[_serialize_e2e_section(item) for item in e2e_sections],
        total_stages=len(stage_results),
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
