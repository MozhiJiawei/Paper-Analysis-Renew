from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]


class CliHelpTests(unittest.TestCase):
    def test_arxiv_help_keeps_chinese_readable_without_env_overrides(self) -> None:
        """验证 CLI 入口会主动固定 stdout/stderr 编码，避免被子进程抓取时出现乱码。"""

        result = subprocess.run(
            [sys.executable, "-m", "paper_analysis.cli.main", "arxiv", "--help"],
            cwd=ROOT_DIR,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )

        self.assertEqual(0, result.returncode)
        self.assertIn("从样例数据或订阅 API 拉取 arXiv 论文", result.stdout)
        self.assertNotIn("\ufffd", result.stdout)

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

    def test_quality_help_lists_stable_quality_commands(self) -> None:
        """验证 quality 命令面保留稳定入口，并移除旧 typecheck 子命令。"""

        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"

        result = subprocess.run(
            [sys.executable, "-m", "paper_analysis.cli.main", "quality", "--help"],
            cwd=ROOT_DIR,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            check=False,
        )

        self.assertEqual(0, result.returncode)
        self.assertIn("local-ci", result.stdout)
        self.assertIn("lint", result.stdout)
        self.assertNotIn("typecheck", result.stdout)
        self.assertNotIn("\ufffd", result.stdout)


if __name__ == "__main__":
    unittest.main()
