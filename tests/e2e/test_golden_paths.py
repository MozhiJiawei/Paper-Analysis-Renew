from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]


class GoldenPathE2ETests(unittest.TestCase):
    def test_conference_report_generates_stable_artifacts(self) -> None:
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
                str(ROOT_DIR / "tests" / "fixtures" / "paperlists_repo"),
                "--seed",
                "7",
            ],
            cwd=ROOT_DIR,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            check=False,
        )
        self.assertEqual(0, result.returncode)

        report_dir = ROOT_DIR / "artifacts" / "e2e" / "conference" / "latest"
        self.assertTrue((report_dir / "summary.md").exists())
        self.assertTrue((report_dir / "result.csv").exists())
        payload = json.loads((report_dir / "result.json").read_text(encoding="utf-8"))
        self.assertEqual("顶会", payload["source"])
        self.assertEqual(2, payload["count"])
        self.assertIn("候选不足 10 篇", (report_dir / "stdout.txt").read_text(encoding="utf-8"))

    def test_arxiv_report_generates_stable_artifacts(self) -> None:
        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"

        result = subprocess.run(
            [sys.executable, "-m", "paper_analysis.cli.main", "arxiv", "report"],
            cwd=ROOT_DIR,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            check=False,
        )
        self.assertEqual(0, result.returncode)

        report_dir = ROOT_DIR / "artifacts" / "e2e" / "arxiv" / "latest"
        self.assertTrue((report_dir / "summary.md").exists())
        payload = json.loads((report_dir / "result.json").read_text(encoding="utf-8"))
        self.assertEqual("arXiv", payload["source"])
        self.assertGreaterEqual(payload["count"], 1)


if __name__ == "__main__":
    unittest.main()
