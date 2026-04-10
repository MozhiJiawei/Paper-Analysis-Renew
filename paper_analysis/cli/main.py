"""Top-level CLI entrypoint for stable paper-analysis namespaces."""

from __future__ import annotations

from argparse import ArgumentParser
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from collections.abc import Callable

from paper_analysis.cli import arxiv, conference, quality, report
from paper_analysis.shared.encoding import configure_utf8_stdio


def build_parser() -> ArgumentParser:
    """Build the top-level parser and register all stable namespaces."""
    parser = ArgumentParser(
        prog="paper-analysis",
        description="Agent-first paper filtering CLI with stable conference/arxiv/quality/report entrypoints",
    )
    subparsers = parser.add_subparsers(dest="namespace", required=True)
    conference.register(subparsers)
    arxiv.register(subparsers)
    quality.register(subparsers)
    report.register(subparsers)
    return parser


def main() -> int:
    """Parse arguments and dispatch to the selected CLI handler."""
    configure_utf8_stdio()
    parser = build_parser()
    args = parser.parse_args()
    handler = cast("Callable[[object], int]", args.handler)
    return handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
