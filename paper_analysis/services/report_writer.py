"""Report artifact writer for filtered paper results."""

from __future__ import annotations

import csv
import json
from collections import Counter
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

    from paper_analysis.domain.paper import Paper


def write_report(
    report_dir: Path,
    source_name: str,
    papers: list[Paper],
    command_name: str,
    analysis_count: int | None = None,
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

    analysis = _build_analysis_summary(papers, analysis_count=analysis_count)
    markdown_lines = [
        f"# {source_name} 筛选结果",
        "",
        f"- 命令：`{command_name}`",
        f"- 分析候选：{analysis['analysis_count']}",
        f"- 推荐结果：{analysis['recommended_count']}",
        f"- 推荐率：{analysis['recommendation_rate']}",
        f"- 有摘要：{analysis['abstract_count']}",
        f"- 有机构信息：{analysis['organization_count']}",
        "",
        "## 分析统计",
        "",
        "### 大类推荐结果",
        "",
        *_format_distribution_lines(analysis["major_categories"]),
        "",
        "### 研究对象分类结果",
        "",
        *_format_distribution_lines(analysis["research_objects"]),
        "",
        "### 子类推荐结果",
        "",
        *_format_distribution_lines(analysis["subcategories"]),
        "",
        "## 推荐论文",
        "",
    ]
    stdout_lines = [f"[OK] {source_name} 筛选完成，共 {len(papers)} 篇"]
    serializable = serialize_papers(papers)
    csv_rows: list[dict[str, object]] = []

    for index, paper in enumerate(papers, start=1):
        markdown_lines.extend(_format_paper_markdown(index, paper))
        stdout_lines.append(
            f"{index}. {paper.title} | {paper.venue} | {paper.sampled_reason or 'selected'}"
        )
        row = serializable[index - 1]
        csv_rows.append({column: row.get(column, "") for column in csv_columns})

    markdown_path.write_text("\n".join(markdown_lines), encoding="utf-8")
    json_path.write_text(
        json.dumps(
            {
                "source": source_name,
                "count": len(papers),
                "analysis": analysis,
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


def serialize_papers(papers: list[Paper]) -> list[dict[str, object]]:
    """Convert paper objects into JSON-safe rows reused by other services."""
    return [_serialize_paper(paper) for paper in papers]


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


def _build_analysis_summary(
    papers: list[Paper],
    *,
    analysis_count: int | None,
) -> dict[str, object]:
    candidate_count = analysis_count if analysis_count is not None else len(papers)
    recommended_count = len(papers)
    rate = recommended_count / candidate_count if candidate_count else 0.0
    return {
        "analysis_count": candidate_count,
        "recommended_count": recommended_count,
        "recommendation_rate": f"{rate:.1%}",
        "abstract_count": sum(1 for paper in papers if paper.abstract.strip()),
        "organization_count": sum(1 for paper in papers if paper.organization.strip()),
        "major_categories": _count_major_categories(papers),
        "research_objects": _count_values(
            _paper_research_object(paper) or "未分类" for paper in papers
        ),
        "subcategories": _count_values(
            paper.sampled_reason or "未分类" for paper in papers
        ),
    }


def _count_major_categories(papers: list[Paper]) -> dict[str, int]:
    values = [_extract_major_category(paper) or "未分类" for paper in papers]
    return _count_values(values)


def _extract_major_category(paper: Paper) -> str:
    for reason in paper.reasons:
        if "子类：" in reason:
            return reason.split("子类：", 1)[0].strip()
    if paper.primary_area:
        return paper.primary_area
    if paper.topic:
        return paper.topic
    return ""


def _paper_research_object(paper: Paper) -> str:
    prediction = paper.raw_payload.get("evaluation_prediction")
    if isinstance(prediction, dict):
        return str(prediction.get("primary_research_object", "")).strip()
    return ""


def _count_values(values: Iterable[str]) -> dict[str, int]:
    counter = Counter(value for value in values if str(value).strip())
    return {
        key: counter[key]
        for key in sorted(counter, key=lambda item: (-counter[item], str(item)))
    }


def _format_distribution_lines(distribution: object) -> list[str]:
    if not isinstance(distribution, dict) or not distribution:
        return ["- 无"]
    return [f"- {key}：{value}" for key, value in distribution.items()]


def _format_paper_markdown(index: int, paper: Paper) -> list[str]:
    """Build a reader-facing markdown block for one selected paper."""
    lines = [
        f"## {index}. {paper.title}",
        f"- 作者：{_join_values(paper.authors) or '未知'}",
        f"- 机构：{paper.organization or '未知'}",
        f"- 来源：{paper.venue}",
    ]
    if paper.acceptance_status and paper.acceptance_status != "未知":
        lines.append(f"- 接收状态：{paper.acceptance_status}")
    if paper.tags:
        lines.append(f"- 主题标签：{_join_values(paper.tags)}")
    research_object = _paper_research_object(paper)
    if research_object:
        lines.append(f"- 研究对象：{research_object}")
    if paper.sampled_reason:
        lines.append(f"- 推荐类别：{paper.sampled_reason}")
    lines.append(f"- 摘要：{paper.abstract or '无'}")

    reason = _format_recommendation_reason(paper.reasons)
    if reason:
        lines.append(f"- 推荐依据：{reason}")

    links = _format_links(paper)
    if links:
        lines.append(f"- 链接：{links}")

    lines.append("")
    return lines


def _format_recommendation_reason(reasons: list[str]) -> str:
    """Keep recommendation evidence compact enough for daily reading."""
    readable_reasons = [
        reason.strip()
        for reason in reasons
        if reason.strip() and not reason.startswith("基于标题、摘要与关键词的启发式规则判定")
    ]
    if not readable_reasons:
        return ""
    return "；".join(readable_reasons[:2])


def _format_links(paper: Paper) -> str:
    links = [
        ("PDF", paper.pdf_url),
        ("Project", paper.project_url),
        ("Code", paper.code_url),
        ("OpenReview", paper.openreview_url),
    ]
    return " | ".join(f"{label}: {url}" for label, url in links if url)


def _join_values(values: list[str]) -> str:
    """Join non-empty string values with a stable report delimiter."""
    return " | ".join(value for value in values if value)
