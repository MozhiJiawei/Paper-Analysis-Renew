from __future__ import annotations

import shutil
import unittest
from pathlib import Path

from paper_analysis.domain.paper import Paper
from paper_analysis.services.report_writer import write_report


ROOT_DIR = Path(__file__).resolve().parents[2]


class ReportWriterTests(unittest.TestCase):
    def test_write_report_creates_four_artifacts(self) -> None:
        """验证报告写入器会同时生成 Markdown、JSON、CSV 和 stdout 四类产物。"""

        report_dir = ROOT_DIR / "artifacts" / "test-output" / "report-writer"
        if report_dir.exists():
            shutil.rmtree(report_dir)

        artifacts = write_report(
            report_dir=report_dir,
            source_name="顶会",
            papers=[
                Paper(
                    paper_id="p1",
                    title="A",
                    abstract="...",
                    source="conference",
                    venue="NeurIPS",
                    authors=["A"],
                    tags=["agents"],
                    organization="OpenAI",
                    published_at="2025-01-01",
                    year=2025,
                    acceptance_status="Spotlight",
                    keywords=["agents"],
                    pdf_url="https://example.com/p1.pdf",
                    sampled_reason="固定种子随机抽样（seed=42）",
                    score=5.0,
                    reasons=["命中偏好主题：agents"],
                    raw_payload={
                        "evaluation_prediction": {
                            "primary_research_object": "LLM",
                        },
                    },
                )
            ],
            command_name="conference report",
            analysis_count=10,
        )

        self.assertTrue(artifacts["markdown"].exists())
        self.assertTrue(artifacts["json"].exists())
        self.assertTrue(artifacts["csv"].exists())
        self.assertTrue(artifacts["stdout"].exists())

        markdown = artifacts["markdown"].read_text(encoding="utf-8")
        self.assertIn("- 分析候选：10", markdown)
        self.assertIn("- 推荐结果：1", markdown)
        self.assertIn("- 推荐率：10.0%", markdown)
        self.assertIn("## 分析统计", markdown)
        self.assertIn("### 大类推荐结果", markdown)
        self.assertIn("- 未分类：1", markdown)
        self.assertIn("### 研究对象分类结果", markdown)
        self.assertIn("- LLM：1", markdown)
        self.assertIn("### 子类推荐结果", markdown)
        self.assertIn("- 固定种子随机抽样（seed=42）：1", markdown)
        self.assertIn("## 推荐论文", markdown)
        self.assertIn("- 摘要：...", markdown)
        self.assertIn("- 研究对象：LLM", markdown)
        self.assertIn("- 推荐类别：固定种子随机抽样（seed=42）", markdown)
        self.assertIn("- 推荐依据：命中偏好主题：agents", markdown)
        self.assertIn("- 链接：PDF: https://example.com/p1.pdf", markdown)
        self.assertNotIn("OpenReview：无", markdown)
        self.assertNotIn("Project：无", markdown)
        self.assertNotIn("Code：无", markdown)
        self.assertNotIn("抽样原因", markdown)
        self.assertNotIn("原因：", markdown)
        self.assertNotIn("主题标签分布", markdown)

        payload = artifacts["json"].read_text(encoding="utf-8")
        self.assertIn('"analysis_count": 10', payload)
        self.assertIn('"recommendation_rate": "10.0%"', payload)
        self.assertIn('"research_objects"', payload)


if __name__ == "__main__":
    unittest.main()
