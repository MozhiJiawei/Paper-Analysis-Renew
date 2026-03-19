from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]


class CliHelpTests(unittest.TestCase):
    def test_main_help_lists_business_namespaces(self) -> None:
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


if __name__ == "__main__":
    unittest.main()
