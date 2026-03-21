from __future__ import annotations

from argparse import ArgumentParser

from paper_analysis.cli import arxiv, conference, quality, report
from paper_analysis.shared.encoding import configure_utf8_stdio


def build_parser() -> ArgumentParser:
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
    configure_utf8_stdio()
    parser = build_parser()
    args = parser.parse_args()
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
