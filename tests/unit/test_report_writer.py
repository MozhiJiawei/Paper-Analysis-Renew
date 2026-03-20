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
                )
            ],
            command_name="conference report",
        )

        self.assertTrue(artifacts["markdown"].exists())
        self.assertTrue(artifacts["json"].exists())
        self.assertTrue(artifacts["csv"].exists())
        self.assertTrue(artifacts["stdout"].exists())


if __name__ == "__main__":
    unittest.main()
