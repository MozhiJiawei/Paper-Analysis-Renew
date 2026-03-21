from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]


class CliHelpTests(unittest.TestCase):
    def test_main_help_lists_business_namespaces(self) -> None:
        """验证主命令帮助页只暴露 conference 与 arxiv 两个业务命名空间。"""

        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"

        result = subprocess.run(
            [sys.executable, "-m", "paper_analysis.cli.main", "--help"],
            cwd=ROOT_DIR,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            check=False,
        )

        self.assertEqual(0, result.returncode)
        self.assertIn("conference", result.stdout)
        self.assertIn("arxiv", result.stdout)
        self.assertNotIn("recommend", result.stdout)

    def test_arxiv_help_lists_subscription_options(self) -> None:
        """验证 arxiv 帮助页暴露订阅 API 参数。"""

        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"

        result = subprocess.run(
            [sys.executable, "-m", "paper_analysis.cli.main", "arxiv", "report", "--help"],
            cwd=ROOT_DIR,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            check=False,
        )

        self.assertEqual(0, result.returncode)
        self.assertIn("--source-mode", result.stdout)
        self.assertIn("--subscription-date", result.stdout)
        self.assertIn("--max-results", result.stdout)


if __name__ == "__main__":
    unittest.main()
