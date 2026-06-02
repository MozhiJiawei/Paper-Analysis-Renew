"""Translate an arXiv final gated report with OpenRouter DS-V4-Flash."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from paper_analysis.cli.common import CliInputError
from paper_analysis.services.arxiv_final_report_translator import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_CONCURRENCY,
    DEFAULT_TRANSLATION_MODEL,
    FinalReportTranslationRequest,
    translate_final_report,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="使用 OpenRouter DS-V4-Flash 翻译 arXiv final gated report"
    )
    parser.add_argument(
        "--subscription-date",
        help="分日内容日期，格式 YYYY-MM/MM-DD；未提供时读取 artifacts/e2e/arxiv/latest/result.json",
    )
    parser.add_argument(
        "--input-json",
        type=Path,
        help="显式指定 final-result.json / result.json 路径",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="输出双语 Markdown 路径；默认写到输入 JSON 同目录 final-summary.zh.md",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_TRANSLATION_MODEL,
        help=f"OpenRouter chat model，默认 {DEFAULT_TRANSLATION_MODEL}",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"每次翻译多少篇论文，默认 {DEFAULT_BATCH_SIZE}",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=DEFAULT_CONCURRENCY,
        help=f"OpenRouter 并发请求数，默认 {DEFAULT_CONCURRENCY}",
    )
    args = parser.parse_args()
    try:
        result = translate_final_report(
            FinalReportTranslationRequest(
                subscription_date=args.subscription_date,
                input_json_path=args.input_json,
                output_markdown_path=args.output,
                model=args.model,
                batch_size=args.batch_size,
                concurrency=args.concurrency,
                progress=print,
            )
        )
    except CliInputError as exc:
        print(f"[FAIL] arxiv final report translation failed: {exc}", file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "status": "ok",
                "subscription_date": result.subscription_date,
                "model": result.model,
                "translated_count": result.translated_count,
                "accepted_count": result.accepted_count,
                "borderline_count": result.borderline_count,
                "missed_count": result.missed_count,
                "input_json": str(result.input_json_path),
                "output_markdown": str(result.output_markdown_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
