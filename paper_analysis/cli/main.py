from __future__ import annotations

from argparse import ArgumentParser

from paper_analysis.cli import arxiv, conference, quality, report


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(
        prog="paper-analysis",
        description="Agent-first paper filtering CLI",
    )
    subparsers = parser.add_subparsers(dest="namespace", required=True)
    conference.register(subparsers)
    arxiv.register(subparsers)
    quality.register(subparsers)
    report.register(subparsers)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
