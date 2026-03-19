from __future__ import annotations

from argparse import Namespace
from typing import Any

from paper_analysis.shared.paths import ARTIFACTS_DIR


def register(subparsers: Any) -> None:
    parser = subparsers.add_parser("report", help="查看最近一次报告产物")
    parser.add_argument(
        "--source",
        choices=["conference", "arxiv"],
        required=True,
        help="要查看的来源类型",
    )
    parser.set_defaults(handler=handle_show)


def handle_show(args: Namespace) -> int:
    stdout_path = ARTIFACTS_DIR / "e2e" / args.source / "latest" / "stdout.txt"
    if not stdout_path.exists():
        print(f"[FAIL] report={args.source}")
        print("summary: 尚未生成对应报告")
        print(f"next: 先运行 `py -m paper_analysis.cli.main {args.source} report`")
        return 1

    print(stdout_path.read_text(encoding="utf-8"))
    return 0
