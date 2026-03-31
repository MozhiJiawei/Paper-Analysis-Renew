from __future__ import annotations

import json
from pathlib import Path

from paper_analysis.evaluation.ab_protocol import ABRunResult, RouteRunResult


def write_run_summary(output_dir: Path, result: ABRunResult) -> tuple[Path, Path]:
    summary_path = output_dir / "summary.md"
    leaderboard_path = output_dir / "leaderboard.json"
    summary_path.write_text(_build_summary_markdown(result), encoding="utf-8")
    leaderboard_path.write_text(
        json.dumps(_build_leaderboard_payload(result.routes), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary_path, leaderboard_path


def _build_summary_markdown(result: ABRunResult) -> str:
    lines = [
        "# A/B 脚手架运行摘要",
        "",
        f"- run_id: {result.run_id}",
        f"- ready: {result.counts.get('ready', 0)}",
        f"- stub: {result.counts.get('stub', 0)}",
        f"- failed: {result.counts.get('failed', 0)}",
        f"- skipped: {result.counts.get('skipped', 0)}",
        "",
        "## 路线状态",
        "",
    ]
    for route in result.routes:
        manifest = route.manifest
        reason = f"，reason={manifest.reason}" if manifest.reason else ""
        lines.append(
            f"- {manifest.route_name}: status={manifest.execution_status}, algorithm_version={manifest.algorithm_version}{reason}"
        )
        if route.metrics:
            lines.append(f"  metrics={json.dumps(route.metrics, ensure_ascii=False)}")
    return "\n".join(lines) + "\n"


def _build_leaderboard_payload(routes: list[RouteRunResult]) -> dict[str, object]:
    leaderboard = []
    for route in routes:
        manifest = route.manifest
        score = 1.0 if manifest.execution_status == "ready" else 0.0
        leaderboard.append(
            {
                "route_name": manifest.route_name,
                "execution_status": manifest.execution_status,
                "algorithm_version": manifest.algorithm_version,
                "implementation_status": manifest.implementation_status,
                "score": score,
                "metrics": route.metrics,
            }
        )
    leaderboard.sort(key=lambda item: (-float(item["score"]), str(item["route_name"])))
    return {"routes": leaderboard}
