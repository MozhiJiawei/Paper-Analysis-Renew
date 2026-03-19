from __future__ import annotations

from argparse import ArgumentParser, Namespace
from pathlib import Path
from typing import Any

from paper_analysis.cli.common import CliInputError, print_cli_error
from paper_analysis.services.conference_pipeline import ConferencePipeline
from paper_analysis.services.report_writer import write_report
from paper_analysis.shared.paths import ARTIFACTS_DIR


def register(subparsers: Any) -> None:
    parser = subparsers.add_parser("conference", help="顶会论文筛选工作流")
    conference_subparsers = parser.add_subparsers(dest="conference_action", required=True)

    filter_parser = conference_subparsers.add_parser(
        "filter",
        help="从固定或指定顶会论文集合中筛选符合偏好的论文",
    )
    _add_common_arguments(filter_parser)
    filter_parser.set_defaults(handler=handle_filter)

    report_parser = conference_subparsers.add_parser(
        "report",
        help="执行顶会筛选并写出 Markdown/JSON/stdout 报告",
    )
    _add_common_arguments(report_parser)
    report_parser.set_defaults(handler=handle_report)


def _add_common_arguments(parser: ArgumentParser) -> None:
    parser.add_argument("--input", type=Path, help="论文样例 JSON 路径")
    parser.add_argument("--preferences", type=Path, help="偏好配置 JSON 路径")


def handle_filter(args: Namespace) -> int:
    try:
        papers, _preferences = ConferencePipeline().run(args.input, args.preferences)
    except CliInputError as exc:
        return print_cli_error(
            scope="conference.filter",
            message=str(exc),
            next_step="检查 --input/--preferences 是否存在且为 UTF-8 JSON",
        )

    if not papers:
        print("[OK] 未找到符合条件的顶会论文。")
        return 0

    print(f"[OK] 顶会筛选完成，共 {len(papers)} 篇：")
    for index, paper in enumerate(papers, start=1):
        print(f"{index}. {paper.title} | score={paper.score} | org={paper.organization}")
    return 0


def handle_report(args: Namespace) -> int:
    try:
        papers, _preferences = ConferencePipeline().run(args.input, args.preferences)
    except CliInputError as exc:
        return print_cli_error(
            scope="conference.report",
            message=str(exc),
            next_step="检查报告输入文件和偏好文件是否存在且格式正确",
        )

    report_dir = ARTIFACTS_DIR / "e2e" / "conference" / "latest"
    artifacts = write_report(
        report_dir=report_dir,
        source_name="顶会",
        papers=papers,
        command_name="conference report",
    )
    print(f"[OK] 顶会报告已生成：{artifacts['markdown']}")
    return 0
