"""CLI command for showing the most recent report output."""

from __future__ import annotations

from typing import TYPE_CHECKING

from paper_analysis.cli.common import emit_lines
from paper_analysis.shared.paths import ARTIFACTS_DIR

if TYPE_CHECKING:
    import argparse


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the report CLI namespace."""
    parser = subparsers.add_parser("report", help="查看最近一次报告产物")
    parser.add_argument(
        "--source",
        choices=["conference", "arxiv"],
        required=True,
        help="要查看的来源类型",
    )
    parser.set_defaults(handler=handle_show)


def handle_show(args: argparse.Namespace) -> int:
    """Print the latest stored stdout artifact for the selected source."""
    stdout_path = ARTIFACTS_DIR / "e2e" / args.source / "latest" / "stdout.txt"
    if not stdout_path.exists():
        emit_lines(
            f"[FAIL] report={args.source}",
            "summary: 尚未生成对应报告",
            f"next: 先运行 `py -m paper_analysis.cli.main {args.source} report`",
        )
        return 1

    emit_lines(stdout_path.read_text(encoding="utf-8"))
    return 0
