from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from paper_analysis.cli.arxiv import _append_blue_team_review_to_report


class ArxivBlueTeamReportTests(unittest.TestCase):
    def test_append_blue_team_review_updates_daily_report_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            markdown_path = root / "summary.md"
            json_path = root / "result.json"
            stdout_path = root / "stdout.txt"
            review_json_path = root / "review-result.json"
            markdown_path.write_text("# arXiv 筛选结果\n", encoding="utf-8")
            json_path.write_text(
                json.dumps(
                    {
                        "source": "arXiv",
                        "papers": [
                            {
                                "paper_id": "p1",
                                "title": "Speculative Decoding",
                                "sampled_reason": "解码策略优化",
                                "reasons": ["推理加速子类：解码策略优化"],
                            },
                            {
                                "paper_id": "p2",
                                "title": "KV Cache Scheduling",
                                "sampled_reason": "上下文与缓存优化",
                                "reasons": ["推理加速子类：上下文与缓存优化"],
                            },
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (root / "red-team-result.json").write_text(
                json_path.read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            stdout_path.write_text("[OK] arXiv 筛选完成，共 1 篇\n", encoding="utf-8")
            review_json_path.write_text(
                json.dumps(
                    {
                        "model": "deepseek/deepseek-v4-pro",
                        "content_date": "2026-05/05-24",
                        "false_positive_count": 1,
                        "borderline_count": 1,
                        "missed_count": 1,
                        "false_positives": [
                            {
                                "paper_id": "p0",
                                "title": "Pretraining Data Scaling",
                                "confidence": 0.9,
                                "reason": "核心贡献是预训练数据，不是推理优化。",
                            }
                        ],
                        "borderline_recommendations": [
                            {
                                "paper_id": "p2",
                                "title": "KV Cache Scheduling",
                                "confidence": 0.6,
                                "reason": "证据足够接近，但效率目标不够直接。",
                            }
                        ],
                        "missed_recommendations": [
                            {
                                "paper_id": "p3",
                                "title": "Paged KV Serving",
                                "category": "上下文与缓存优化",
                                "confidence": 0.8,
                                "reason": "明确优化 KV cache 调度。",
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            _append_blue_team_review_to_report(
                report_artifacts={
                    "markdown": markdown_path,
                    "json": json_path,
                    "stdout": stdout_path,
                },
                review_json_path=review_json_path,
            )

            markdown = markdown_path.read_text(encoding="utf-8")
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            stdout = stdout_path.read_text(encoding="utf-8")

        self.assertIn("## 1. 蓝军推荐 + 红军推荐", markdown)
        self.assertIn("Speculative Decoding", markdown)
        self.assertIn("## 2. 红军推荐 + 蓝军存疑", markdown)
        self.assertIn("KV Cache Scheduling", markdown)
        self.assertIn("## 3. 蓝军漏推荐", markdown)
        self.assertIn("Paged KV Serving", markdown)
        self.assertIn("红军主报告：`red-team-summary.md`", markdown)
        self.assertIn("蓝军审阅报告：`review-summary.md`", markdown)
        self.assertEqual("completed", payload["blue_team_review"]["status"])
        self.assertEqual(1, payload["blue_team_review"]["false_positive_count"])
        self.assertEqual(
            1,
            len(payload["merged_recommendation_sections"]["blue_and_red_recommendations"]),
        )
        self.assertEqual(
            1,
            len(payload["merged_recommendation_sections"]["red_recommendations_blue_borderline"]),
        )
        self.assertEqual(
            1,
            len(payload["merged_recommendation_sections"]["blue_missed_recommendations"]),
        )
        self.assertIn("[OK] 融合推荐报告：双方推荐 1，红军推荐蓝军存疑 1，蓝军漏推荐 1", stdout)


if __name__ == "__main__":
    unittest.main()
