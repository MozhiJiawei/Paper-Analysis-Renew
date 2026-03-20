from __future__ import annotations

import json
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

from paper_analysis.cli import quality


class QualityHtmlIntegrationTests(unittest.TestCase):
    def test_handle_local_ci_writes_html_on_success(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root_dir = Path(temp_dir)
            artifacts_dir = root_dir / "artifacts"
            self._write_e2e_payloads(artifacts_dir)

            with (
                patch.object(quality, "ROOT_DIR", root_dir),
                patch.object(quality, "ARTIFACTS_DIR", artifacts_dir),
                patch.object(
                    quality,
                    "QUALITY_STAGES",
                    [
                        ("lint", [sys.executable, "-c", "print('lint ok')"]),
                        ("unit", [sys.executable, "-c", "print('unit ok')"]),
                    ],
                ),
            ):
                exit_code = quality.handle_local_ci(Namespace())

            self.assertEqual(0, exit_code)
            html = (artifacts_dir / "quality" / "local-ci-latest.html").read_text(encoding="utf-8")
            self.assertIn("整体结果：通过", html)
            self.assertIn("lint ok", html)
            self.assertIn("Reasoning Agents with Tool Feedback", html)

    def test_handle_local_ci_writes_html_on_failure_and_marks_skipped_stages(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root_dir = Path(temp_dir)
            artifacts_dir = root_dir / "artifacts"
            self._write_e2e_payloads(artifacts_dir)

            with (
                patch.object(quality, "ROOT_DIR", root_dir),
                patch.object(quality, "ARTIFACTS_DIR", artifacts_dir),
                patch.object(
                    quality,
                    "QUALITY_STAGES",
                    [
                        ("lint", [sys.executable, "-c", "import sys; print('lint failed'); sys.exit(1)"]),
                        ("unit", [sys.executable, "-c", "print('unit ok')"]),
                        ("e2e", [sys.executable, "-c", "print('e2e ok')"]),
                    ],
                ),
            ):
                exit_code = quality.handle_local_ci(Namespace())

            self.assertEqual(1, exit_code)
            html = (artifacts_dir / "quality" / "local-ci-latest.html").read_text(encoding="utf-8")
            self.assertIn("整体结果：失败", html)
            self.assertIn("lint failed", html)
            self.assertIn("前置阶段失败，本阶段未执行", html)

    def test_handle_local_ci_still_writes_html_when_e2e_json_is_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root_dir = Path(temp_dir)
            artifacts_dir = root_dir / "artifacts"
            self._write_e2e_payloads(artifacts_dir)
            (artifacts_dir / "e2e" / "conference" / "latest" / "result.json").write_text("{", encoding="utf-8")

            commands = {
                "lint": [sys.executable, "-c", "print('lint ok')"],
                "unit": [sys.executable, "-c", "print('unit ok')"],
            }
            with (
                patch.object(quality, "ROOT_DIR", root_dir),
                patch.object(quality, "ARTIFACTS_DIR", artifacts_dir),
                patch.object(quality, "QUALITY_STAGES", list(commands.items())),
            ):
                exit_code = quality.handle_local_ci(Namespace())

            self.assertEqual(0, exit_code)
            html = (artifacts_dir / "quality" / "local-ci-latest.html").read_text(encoding="utf-8")
            self.assertIn("result.json 存在但无法解析", html)
            self.assertIn("顶会报告", html)

    def _write_e2e_payloads(self, artifacts_dir: Path) -> None:
        conference_dir = artifacts_dir / "e2e" / "conference" / "latest"
        arxiv_dir = artifacts_dir / "e2e" / "arxiv" / "latest"
        conference_dir.mkdir(parents=True, exist_ok=True)
        arxiv_dir.mkdir(parents=True, exist_ok=True)

        (conference_dir / "summary.md").write_text("# 顶会报告", encoding="utf-8")
        (conference_dir / "stdout.txt").write_text("[OK] conference report", encoding="utf-8")
        (conference_dir / "result.json").write_text(
            json.dumps(
                {
                    "count": 1,
                    "papers": [
                        {
                            "title": "Agentic Retrieval Planning for Long-Horizon Tasks",
                            "authors": "Alice | Bob",
                            "organization": "OpenAI",
                            "venue": "ICLR 2025",
                            "reasons": ["命中 Agents 偏好"],
                        }
                    ],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        (arxiv_dir / "summary.md").write_text("# arXiv 报告", encoding="utf-8")
        (arxiv_dir / "stdout.txt").write_text("[OK] arxiv report", encoding="utf-8")
        (arxiv_dir / "result.json").write_text(
            json.dumps(
                {
                    "count": 1,
                    "papers": [
                        {
                            "title": "Reasoning Agents with Tool Feedback",
                            "authors": "Dana | Evan",
                            "organization": "Google DeepMind",
                            "venue": "arXiv",
                            "reasons": ["命中评测信号"],
                        }
                    ],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )


if __name__ == "__main__":
    unittest.main()
