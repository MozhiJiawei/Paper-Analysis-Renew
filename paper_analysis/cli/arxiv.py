"""CLI commands for the arXiv fetch and report workflow."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from paper_analysis.cli.common import CliInputError, emit_lines, print_cli_error
from paper_analysis.services.arxiv_pipeline import ArxivPipeline
from paper_analysis.services.report_writer import write_report
from paper_analysis.shared.paths import ARTIFACTS_DIR

if TYPE_CHECKING:
    import argparse

    from paper_analysis.domain.paper import Paper
    from paper_analysis.domain.preference import PreferenceProfile


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the arXiv CLI namespace and its stable subcommands."""
    parser = subparsers.add_parser("arxiv", help="arXiv 日更与订阅筛选工作流")
    arxiv_subparsers = parser.add_subparsers(dest="arxiv_action", required=True)

    filter_parser = arxiv_subparsers.add_parser(
        "daily-filter",
        help="从样例数据或订阅 API 拉取 arXiv 论文",
    )
    _add_common_arguments(filter_parser)
    filter_parser.set_defaults(handler=handle_daily_filter)

    report_parser = arxiv_subparsers.add_parser(
        "report",
        help="执行 arXiv 拉取并写出 Markdown/JSON/CSV/stdout 报告",
    )
    _add_common_arguments(report_parser)
    report_parser.set_defaults(handler=handle_report)


def _add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--input", type=Path, help="样例论文 JSON 路径")
    parser.add_argument("--preferences", type=Path, help="偏好配置 JSON 路径")
    parser.add_argument(
        "--source-mode",
        choices=["fixture", "subscription-api"],
        default="fixture",
        help="输入来源，默认 fixture",
    )
    parser.add_argument(
        "--subscription-date",
        help="订阅日期，格式 YYYY-MM/MM-DD，仅 subscription-api 模式必填",
    )
    parser.add_argument(
        "--category",
        action="append",
        default=[],
        help="限定 arXiv 分类，可重复传入；未传时使用默认分类集合",
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=10,
        help="订阅 API 最多拉取多少篇论文",
    )


def handle_daily_filter(args: argparse.Namespace) -> int:
    """Run the arXiv fetch flow and print a compact terminal summary."""
    try:
        papers, _preferences = _run_pipeline(args)
    except CliInputError as exc:
        return print_cli_error(
            scope="arxiv.daily-filter",
            message=str(exc),
            next_step="检查 --input/--preferences，或在 subscription-api 模式下补充 --subscription-date",
        )

    if not papers:
        emit_lines("[OK] 本次 arXiv 拉取没有返回论文。")
        return 0

    emit_lines(f"[OK] arXiv 拉取完成，共 {len(papers)} 篇：")
    for index, paper in enumerate(papers, start=1):
        emit_lines(f"{index}. {paper.title} | {paper.venue} | {paper.published_at}")
    return 0


def handle_report(args: argparse.Namespace) -> int:
    """Run the arXiv report flow and write report artifacts."""
    try:
        papers, _preferences = _run_pipeline(args)
    except CliInputError as exc:
        return print_cli_error(
            scope="arxiv.report",
            message=str(exc),
            next_step="检查报告输入文件，或在 subscription-api 模式下补充有效的订阅参数",
        )

    report_dir = ARTIFACTS_DIR / "e2e" / "arxiv" / "latest"
    artifacts = write_report(
        report_dir=report_dir,
        source_name="arXiv",
        papers=papers,
        command_name=_build_command_name(args),
    )
    emit_lines(f"[OK] arXiv 报告已生成：{artifacts['markdown']}")
    return 0


def _run_pipeline(args: argparse.Namespace) -> tuple[list[Paper], PreferenceProfile]:
    try:
        return ArxivPipeline().run(
            args.input,
            args.preferences,
            source_mode=args.source_mode,
            subscription_date=args.subscription_date,
            categories=args.category,
            max_results=args.max_results,
        )
    except ValueError as exc:
        raise CliInputError(str(exc)) from exc


def _build_command_name(args: argparse.Namespace) -> str:
    if args.source_mode != "subscription-api":
        return "arxiv report"

    parts = [
        "arxiv report",
        "--source-mode subscription-api",
        f"--subscription-date {args.subscription_date}",
        f"--max-results {args.max_results}",
    ]
    parts.extend(f"--category {category}" for category in args.category)
    return " ".join(parts)
