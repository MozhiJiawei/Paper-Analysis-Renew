from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

from paper_analysis.services.arxiv_pipeline import ArxivPipeline
from paper_analysis.services.conference_pipeline import ConferencePipeline


ROOT_DIR = Path(__file__).resolve().parents[2]


class PipelineIntegrationTests(unittest.TestCase):
    def test_conference_pipeline_returns_ranked_results(self) -> None:
        """验证 conference pipeline 默认运行时会返回满足最低分阈值的排序结果。"""

        result = ConferencePipeline().run()
        self.assertGreaterEqual(len(result.papers), 1)
        self.assertGreaterEqual(result.papers[0].score, result.preferences.min_score)

    def test_arxiv_pipeline_returns_ranked_results(self) -> None:
        """验证 arXiv pipeline 默认运行时会返回满足最低分阈值的排序结果。"""

        papers, preferences = ArxivPipeline().run()
        self.assertGreaterEqual(len(papers), 1)
        self.assertGreaterEqual(papers[0].score, preferences.min_score)

    def test_conference_pipeline_reads_paperlists_fixture(self) -> None:
        """验证 conference pipeline 能从 paperlists fixture 读取真实会议数据。"""

        result = ConferencePipeline().run(
            venue="iclr",
            year=2025,
            paperlists_root=ROOT_DIR / "tests" / "fixtures" / "paperlists_repo",
            seed=7,
        )

        self.assertEqual("paperlists", result.source_mode)
        self.assertEqual(2, result.candidate_count)
        self.assertEqual(2, result.selected_count)
        self.assertEqual("ICLR", result.venue)
        self.assertEqual(2025, result.year)
        self.assertTrue(all(paper.acceptance_status for paper in result.papers))

    def test_conference_filter_returns_structured_error_for_missing_input(self) -> None:
        """验证 conference filter 在输入文件缺失时返回结构化失败输出而非 Traceback。"""

        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "paper_analysis.cli.main",
                "conference",
                "filter",
                "--input",
                "missing.json",
            ],
            cwd=ROOT_DIR,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            check=False,
        )

        self.assertEqual(1, result.returncode)
        self.assertIn("[FAIL] scope=conference.filter", result.stdout)
        self.assertIn("missing.json", result.stdout)
        self.assertNotIn("Traceback", result.stdout + result.stderr)

    def test_conference_report_returns_structured_error_for_missing_paperlists_root(self) -> None:
        """验证 conference report 在 paperlists 数据源缺失时返回结构化失败输出。"""

        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "paper_analysis.cli.main",
                "conference",
                "report",
                "--venue",
                "iclr",
                "--year",
                "2025",
                "--paperlists-root",
                "missing-paperlists",
            ],
            cwd=ROOT_DIR,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            check=False,
        )

        self.assertEqual(1, result.returncode)
        self.assertIn("[FAIL] scope=conference.report", result.stdout)
        self.assertIn("paperlists 数据源不存在", result.stdout)
        self.assertNotIn("Traceback", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
