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
        papers, preferences = ConferencePipeline().run()
        self.assertGreaterEqual(len(papers), 1)
        self.assertGreaterEqual(papers[0].score, preferences.min_score)

    def test_arxiv_pipeline_returns_ranked_results(self) -> None:
        papers, preferences = ArxivPipeline().run()
        self.assertGreaterEqual(len(papers), 1)
        self.assertGreaterEqual(papers[0].score, preferences.min_score)

    def test_conference_filter_returns_structured_error_for_missing_input(self) -> None:
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
        self.assertIn("summary: 输入文件不存在：missing.json", result.stdout)
        self.assertNotIn("Traceback", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
