"""Report artifact writer for filtered paper results."""

from __future__ import annotations

import csv
import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from paper_analysis.domain.paper import Paper


def write_report(
    report_dir: Path,
    source_name: str,
    papers: list[Paper],
    command_name: str,
) -> dict[str, Path]:
    """Persist stdout, markdown, json and csv artifacts with stable filenames."""
    report_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = report_dir / "summary.md"
    json_path = report_dir / "result.json"
    csv_path = report_dir / "result.csv"
    stdout_path = report_dir / "stdout.txt"

    csv_columns = [
        "paper_id",
        "title",
        "venue",
        "year",
        "acceptance_status",
        "authors",
        "organization",
        "primary_area",
        "topic",
        "keywords",
        "pdf_url",
        "project_url",
        "code_url",
        "openreview_url",
        "sampled_reason",
        "tags",
        "score",
        "source",
        "published_at",
        "source_path",
    ]

    markdown_lines = [
        f"# {source_name} 筛选结果",
        "",
        f"- 命令：`{command_name}`",
        f"- 结果数量：{len(papers)}",
        "",
    ]
    stdout_lines = [f"[OK] {source_name} 筛选完成，共 {len(papers)} 篇"]
    serializable: list[dict[str, object]] = []
    csv_rows: list[dict[str, object]] = []

    for index, paper in enumerate(papers, start=1):
        markdown_lines.extend(
            [
                f"## {index}. {paper.title}",
                f"- 作者：{_join_values(paper.authors)}",
                f"- 机构：{paper.organization or '未知'}",
                f"- 会议/来源：{paper.venue}",
                f"- 接收状态：{paper.acceptance_status or '未知'}",
                f"- 主题标签：{_join_values(paper.tags)}",
                f"- 抽样原因：{paper.sampled_reason or '未抽样'}",
                f"- OpenReview：{paper.openreview_url or '无'}",
                f"- PDF：{paper.pdf_url or '无'}",
                f"- Project：{paper.project_url or '无'}",
                f"- Code：{paper.code_url or '无'}",
                f"- 原因：{'；'.join(paper.reasons) if paper.reasons else '无'}",
                "",
            ]
        )
        stdout_lines.append(
            f"{index}. {paper.title} | {paper.venue} | {paper.sampled_reason or 'selected'}"
        )
        row = _serialize_paper(paper)
        serializable.append(row)
        csv_rows.append({column: row.get(column, "") for column in csv_columns})

    markdown_path.write_text("\n".join(markdown_lines), encoding="utf-8")
    json_path.write_text(
        json.dumps(
            {
                "source": source_name,
                "count": len(papers),
                "papers": serializable,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=csv_columns)
        writer.writeheader()
        writer.writerows(csv_rows)
    stdout_path.write_text("\n".join(stdout_lines) + "\n", encoding="utf-8")
    return {
        "markdown": markdown_path,
        "json": json_path,
        "csv": csv_path,
        "stdout": stdout_path,
    }


def _serialize_paper(paper: Paper) -> dict[str, object]:
    """Convert one paper object into a JSON-serializable report row."""
    return {
        "paper_id": paper.paper_id,
        "title": paper.title,
        "abstract": paper.abstract,
        "source": paper.source,
        "venue": paper.venue,
        "authors": _join_values(paper.authors),
        "tags": _join_values(paper.tags),
        "organization": paper.organization,
        "published_at": paper.published_at,
        "score": paper.score,
        "reasons": paper.reasons,
        "year": paper.year or "",
        "acceptance_status": paper.acceptance_status,
        "primary_area": paper.primary_area,
        "topic": paper.topic,
        "keywords": _join_values(paper.keywords),
        "pdf_url": paper.pdf_url,
        "project_url": paper.project_url,
        "code_url": paper.code_url,
        "openreview_url": paper.openreview_url,
        "sampled_reason": paper.sampled_reason,
        "source_path": paper.source_path,
        "raw_payload": paper.raw_payload,
    }


def _join_values(values: list[str]) -> str:
    """Join non-empty string values with a stable report delimiter."""
    return " | ".join(value for value in values if value)
