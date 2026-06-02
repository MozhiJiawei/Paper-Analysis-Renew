from __future__ import annotations

import json
import tempfile
import unittest
from concurrent.futures import Future
from pathlib import Path
from typing import Any

from paper_analysis.cli.common import CliInputError
from paper_analysis.services.arxiv_final_report_translator import (
    FinalReportTranslationRequest,
    translate_final_report,
)


class FakeTranslationClient:
    resolved_chat_model = "deepseek/deepseek-v4-flash"

    def __init__(self) -> None:
        self.calls: list[list[dict[str, Any]]] = []

    def submit(
        self,
        messages: list[dict[str, Any]],
        *,
        stream: bool = False,
    ) -> Future[dict[str, Any]]:
        self.calls.append(messages)
        payload = json.loads(str(messages[-1]["content"]))
        translations = []
        for paper in payload["papers"]:
            paper_id = paper["paper_id"]
            translations.append(
                {
                    "paper_id": paper_id,
                    "title_zh": f"{paper['title']} 中文标题",
                    "abstract_zh": "这是一段完整的中文摘要翻译，保留 LLM、KV Cache 和 latency 等术语，并忠实覆盖原文中的方法、动机、实验结果与效率收益。" * 3,
                }
            )
        future: Future[dict[str, Any]] = Future()
        future.set_result(
            {
                "success": True,
                "content": json.dumps({"translations": translations}, ensure_ascii=False),
            }
        )
        return future


class ShortAbstractTranslationClient(FakeTranslationClient):
    def submit(
        self,
        messages: list[dict[str, Any]],
        *,
        stream: bool = False,
    ) -> Future[dict[str, Any]]:
        payload = json.loads(str(messages[-1]["content"]))
        translations = [
            {
                "paper_id": paper["paper_id"],
                "title_zh": "短标题",
                "abstract_zh": "一句话。",
            }
            for paper in payload["papers"]
        ]
        future: Future[dict[str, Any]] = Future()
        future.set_result(
            {
                "success": True,
                "content": json.dumps({"translations": translations}, ensure_ascii=False),
            }
        )
        return future


class BatchThenSingleRetryClient(FakeTranslationClient):
    def submit(
        self,
        messages: list[dict[str, Any]],
        *,
        stream: bool = False,
    ) -> Future[dict[str, Any]]:
        self.calls.append(messages)
        payload = json.loads(str(messages[-1]["content"]))
        translations = []
        for paper in payload["papers"]:
            item = {
                "paper_id": paper["paper_id"],
                "title_zh": f"{paper['title']} 中文标题",
            }
            if len(payload["papers"]) == 1:
                item["abstract_zh"] = "逐篇重试后返回的完整中文摘要翻译，包含足够的信息量，避免被误判为过度压缩。" * 4
            translations.append(item)
        future: Future[dict[str, Any]] = Future()
        future.set_result(
            {
                "success": True,
                "content": json.dumps({"translations": translations}, ensure_ascii=False),
            }
        )
        return future


class ArxivFinalReportTranslatorTests(unittest.TestCase):
    def test_translates_final_gated_sections_to_bilingual_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / "final-result.json"
            output_path = Path(temp_dir) / "final-summary.zh.md"
            input_path.write_text(json.dumps(_sample_payload(), ensure_ascii=False), encoding="utf-8")

            client = FakeTranslationClient()
            result = translate_final_report(
                FinalReportTranslationRequest(
                    input_json_path=input_path,
                    output_markdown_path=output_path,
                    client=client,
                    batch_size=2,
                    concurrency=2,
                )
            )

            markdown = output_path.read_text(encoding="utf-8")
            self.assertEqual(output_path, result.output_markdown_path)
            self.assertEqual(4, result.translated_count)
            self.assertEqual(2, len(client.calls))
            self.assertIn("# arXiv 最终融合推荐报告（标题/摘要双语）", markdown)
            self.assertIn("## 1. 蓝军推荐 + 红军推荐", markdown)
            self.assertIn("## 2. 红军推荐 + 蓝军存疑/误推荐", markdown)
            self.assertIn("Abstract (EN)：", markdown)
            self.assertIn("摘要（中文）：", markdown)
            self.assertIn("- 组织：Org A", markdown)
            self.assertIn("- 组织：Org FP", markdown)
            self.assertIn("- 组织：Org Missed", markdown)
            self.assertIn("红军推荐依据：red reason accepted", markdown)
            self.assertIn("红军推荐依据：red reason false positive", markdown)
            self.assertIn("蓝军意见：blue false positive reason", markdown)
            self.assertIn("蓝军漏推荐依据：blue reason missed", markdown)
            self.assertNotIn("论文 ID", markdown)
            self.assertNotIn("主题标签", markdown)
            self.assertNotIn("Red-team reason (EN)", markdown)
            self.assertNotIn("Blue-team opinion (EN)", markdown)

    def test_rejects_suspiciously_short_abstract_translation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / "final-result.json"
            input_path.write_text(json.dumps(_sample_payload(), ensure_ascii=False), encoding="utf-8")

            with self.assertRaisesRegex(CliInputError, "摘要翻译过短"):
                translate_final_report(
                    FinalReportTranslationRequest(
                        input_json_path=input_path,
                        client=ShortAbstractTranslationClient(),
                    )
                )

    def test_retries_batch_parse_failure_per_paper(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / "final-result.json"
            output_path = Path(temp_dir) / "final-summary.zh.md"
            input_path.write_text(json.dumps(_sample_payload(), ensure_ascii=False), encoding="utf-8")

            client = BatchThenSingleRetryClient()
            result = translate_final_report(
                FinalReportTranslationRequest(
                    input_json_path=input_path,
                    output_markdown_path=output_path,
                    client=client,
                    batch_size=2,
                    concurrency=1,
                )
            )

            markdown = output_path.read_text(encoding="utf-8")
            self.assertEqual(4, result.translated_count)
            self.assertGreater(len(client.calls), 2)
            self.assertIn("逐篇重试后返回的完整中文摘要翻译", markdown)


def _sample_payload() -> dict[str, Any]:
    long_abstract = (
        "Large language models need efficient inference. "
        "This paper changes the decoding path, reduces memory, improves latency, "
        "and reports speedups across several long-context benchmarks. "
    ) * 5
    return {
        "count": 2,
        "recommendation_layers": {
            "analyzed_count": 42,
            "strict_positive_count": 2,
        },
        "blue_team_review": {
            "content_date": "2026-05/05-29",
            "false_positive_count": 1,
            "borderline_count": 1,
            "missed_count": 1,
            "false_positives": [
                {
                    "paper_id": "2605.00004",
                    "title": "False Positive Paper",
                    "reason": "blue false positive reason",
                    "confidence": 0.91,
                }
            ],
        },
        "candidate_papers": [
            {
                "paper_id": "2605.00003",
                "organization": "Org Missed",
            }
        ],
        "papers": [
            {
                "paper_id": "2605.00001",
                "title": "Accepted Paper",
                "abstract": long_abstract,
                "authors": "A | B",
                "organization": "Org A",
                "tags": "cs.CL",
                "sampled_reason": "解码策略优化",
                "reasons": ["red reason accepted"],
                "pdf_url": "https://arxiv.org/pdf/2605.00001",
            },
            {
                "paper_id": "2605.00002",
                "title": "Borderline Paper",
                "abstract": long_abstract,
                "authors": "C",
                "organization": "Org Borderline",
                "tags": "cs.AI",
                "sampled_reason": "系统与调度优化",
                "reasons": ["red reason borderline"],
                "pdf_url": "https://arxiv.org/pdf/2605.00002",
            },
            {
                "paper_id": "2605.00004",
                "title": "False Positive Paper",
                "abstract": long_abstract,
                "authors": "E",
                "organization": "Org FP",
                "tags": "cs.CL",
                "sampled_reason": "解码策略优化",
                "reasons": ["red reason false positive"],
                "pdf_url": "https://arxiv.org/pdf/2605.00004",
            },
        ],
        "merged_recommendation_sections": {
            "blue_and_red_recommendations": [
                {
                    "paper_id": "2605.00001",
                    "title": "Accepted Paper",
                    "abstract": long_abstract,
                    "authors": "A | B",
                    "tags": "cs.CL",
                    "category": "解码策略优化",
                    "red_reason": "red reason accepted",
                    "blue_reason": "blue reason accepted",
                    "confidence": 0.9,
                    "pdf_url": "https://arxiv.org/pdf/2605.00001",
                },
            ],
            "red_recommendations_blue_borderline": [
                {
                    "paper_id": "2605.00002",
                    "title": "Borderline Paper",
                    "abstract": long_abstract,
                    "authors": "C",
                    "tags": "cs.AI",
                    "category": "系统与调度优化",
                    "red_reason": "red reason borderline",
                    "blue_reason": "blue reason borderline",
                    "confidence": 0.6,
                    "pdf_url": "https://arxiv.org/pdf/2605.00002",
                }
            ],
            "blue_missed_recommendations": [
                {
                    "paper_id": "2605.00003",
                    "title": "Missed Paper",
                    "abstract": long_abstract,
                    "authors": "D",
                    "tags": "cs.CV",
                    "category": "上下文与缓存优化",
                    "blue_reason": "blue reason missed",
                    "confidence": 0.95,
                    "pdf_url": "https://arxiv.org/pdf/2605.00003",
                }
            ],
        },
    }


if __name__ == "__main__":
    unittest.main()
