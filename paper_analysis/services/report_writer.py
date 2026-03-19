from __future__ import annotations

import json
from pathlib import Path

from paper_analysis.domain.paper import Paper


def write_report(
    report_dir: Path,
    source_name: str,
    papers: list[Paper],
    command_name: str,
) -> dict[str, Path]:
    """Persist stdout, markdown and json artifacts with stable filenames."""

    report_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = report_dir / "summary.md"
    json_path = report_dir / "result.json"
    stdout_path = report_dir / "stdout.txt"

    markdown_lines = [
        f"# {source_name} 筛选结果",
        "",
        f"- 命令：`{command_name}`",
        f"- 结果数量：{len(papers)}",
        "",
    ]
    stdout_lines = [f"[OK] {source_name} 筛选完成，共 {len(papers)} 篇"]
    serializable: list[dict[str, object]] = []

    for index, paper in enumerate(papers, start=1):
        markdown_lines.extend(
            [
                f"## {index}. {paper.title}",
                f"- 机构：{paper.organization}",
                f"- 会议/来源：{paper.venue}",
                f"- 分数：{paper.score}",
                f"- 标签：{', '.join(paper.tags)}",
                f"- 原因：{'；'.join(paper.reasons) if paper.reasons else '无'}",
                "",
            ]
        )
        stdout_lines.append(
            f"{index}. {paper.title} | score={paper.score} | org={paper.organization}"
        )
        serializable.append(
            {
                "paper_id": paper.paper_id,
                "title": paper.title,
                "organization": paper.organization,
                "venue": paper.venue,
                "score": paper.score,
                "tags": paper.tags,
                "reasons": paper.reasons,
            }
        )

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
    stdout_path.write_text("\n".join(stdout_lines) + "\n", encoding="utf-8")
    return {"markdown": markdown_path, "json": json_path, "stdout": stdout_path}
