"""CLI commands for the conference filtering and report workflow."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from paper_analysis.cli.common import CliInputError, emit_lines, print_cli_error
from paper_analysis.services.conference_pipeline import ConferencePipeline
from paper_analysis.services.report_writer import write_report
from paper_analysis.shared.paths import ARTIFACTS_DIR

if TYPE_CHECKING:
    import argparse


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the conference CLI namespace and its stable subcommands."""
    parser = subparsers.add_parser("conference", help="顶会论文筛选工作流")
    conference_subparsers = parser.add_subparsers(dest="conference_action", required=True)

    filter_parser = conference_subparsers.add_parser(
        "filter",
        help="从样例数据或 paperlists 真实会议数据中筛选顶会论文",
    )
    _add_common_arguments(filter_parser)
    filter_parser.set_defaults(handler=handle_filter)

    report_parser = conference_subparsers.add_parser(
        "report",
        help="执行顶会筛选并输出 Markdown/JSON/CSV/stdout 报告",
    )
    _add_common_arguments(report_parser)
    report_parser.set_defaults(handler=handle_report)


def _add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--input", type=Path, help="样例论文 JSON 路径")
    parser.add_argument("--preferences", type=Path, help="偏好配置 JSON 路径")
    parser.add_argument("--venue", help="paperlists 会议名称，例如 iclr、neurips、cvpr")
    parser.add_argument("--year", type=int, help="paperlists 会议年份，例如 2025")
    parser.add_argument(
        "--paperlists-root",
        type=Path,
        help="paperlists 子仓根目录，默认 third_party/paperlists",
    )
    parser.add_argument("--seed", type=int, default=42, help="paperlists 抽样随机种子")


def handle_filter(args: argparse.Namespace) -> int:
    """Run conference filtering and print a compact terminal summary."""
    try:
        result = ConferencePipeline().run(
            args.input,
            args.preferences,
            venue=args.venue,
            year=args.year,
            paperlists_root=args.paperlists_root,
            seed=args.seed,
        )
    except CliInputError as exc:
        return print_cli_error(
            scope="conference.filter",
            message=str(exc),
            next_step="检查 --input/--preferences，或补充 --venue --year 并初始化 paperlists 子模块",
        )

    if not result.papers:
        emit_lines("[OK] 未找到符合条件的顶会论文。")
        return 0

    if result.source_mode == "paperlists":
        emit_lines(
            f"[OK] 顶会筛选完成，会议={result.venue} {result.year}，"
            f"已录用候选 {result.candidate_count} 篇，输出 {result.selected_count} 篇，seed={result.seed}"
        )
        for index, paper in enumerate(result.papers, start=1):
            emit_lines(f"{index}. {paper.title} | {paper.venue} | {paper.sampled_reason}")
        return 0

    emit_lines(f"[OK] 顶会筛选完成，共 {len(result.papers)} 篇：")
    for index, paper in enumerate(result.papers, start=1):
        emit_lines(f"{index}. {paper.title} | score={paper.score} | org={paper.organization}")
    return 0


def handle_report(args: argparse.Namespace) -> int:
    """Run conference filtering and write report artifacts."""
    try:
        result = ConferencePipeline().run(
            args.input,
            args.preferences,
            venue=args.venue,
            year=args.year,
            paperlists_root=args.paperlists_root,
            seed=args.seed,
        )
    except CliInputError as exc:
        return print_cli_error(
            scope="conference.report",
            message=str(exc),
            next_step="检查报告输入文件，或补充 --venue --year 并初始化 paperlists 子模块",
        )

    report_dir = ARTIFACTS_DIR / "e2e" / "conference" / "latest"
    command_name = "conference report"
    if result.source_mode == "paperlists":
        command_name = (
            f"conference report --venue {args.venue} --year {args.year} --seed {args.seed}"
        )
    artifacts = write_report(
        report_dir=report_dir,
        source_name="顶会",
        papers=result.papers,
        command_name=command_name,
    )
    emit_lines(f"[OK] 顶会报告已生成：{artifacts['markdown']}")
    return 0
