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
                json.dumps({"source": "arXiv", "papers": []}, ensure_ascii=False),
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
                                "paper_id": "p1",
                                "title": "Pretraining Data Scaling",
                                "confidence": 0.9,
                                "reason": "核心贡献是预训练数据，不是推理优化。",
                            }
                        ],
                        "borderline_recommendations": [],
                        "missed_recommendations": [
                            {
                                "paper_id": "p2",
                                "title": "KV Cache Scheduling",
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

        self.assertIn("## 蓝军审阅", markdown)
        self.assertIn("Pretraining Data Scaling", markdown)
        self.assertIn("KV Cache Scheduling", markdown)
        self.assertEqual("completed", payload["blue_team_review"]["status"])
        self.assertEqual(1, payload["blue_team_review"]["false_positive_count"])
        self.assertIn("[OK] 蓝军审阅：误推荐 1，边界 1，漏推荐 1", stdout)


if __name__ == "__main__":
    unittest.main()
