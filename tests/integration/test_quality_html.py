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
        """验证 quality local-ci 成功时会写出包含三大类的 HTML 审核页。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            root_dir = Path(temp_dir)
            artifacts_dir = root_dir / "artifacts"
            self._write_e2e_payloads(artifacts_dir)

            with (
                patch.object(quality, "ROOT_DIR", root_dir),
                patch.object(quality, "ARTIFACTS_DIR", artifacts_dir),
                patch.object(quality, "QUALITY_STAGES", ["lint", "unit"]),
                patch.object(
                    quality,
                    "LINT_SUBCHECKS",
                    [
                        ("repo_rules", [sys.executable, "-c", "print('repo rules ok')"]),
                        ("ruff", [sys.executable, "-c", "print('ruff ok')"]),
                        ("mypy", [sys.executable, "-c", "print('mypy ok')"]),
                        ("quality_report", [sys.executable, "-c", "print('[OK] quality report')"]),
                    ],
                ),
                patch.object(
                    quality,
                    "UNITTEST_STAGE_CONFIG",
                    {},
                ),
                patch.object(
                    quality,
                    "STAGE_COMMAND_OVERRIDES",
                    {"unit": [sys.executable, "-c", "print('unit ok')"]},
                ),
            ):
                exit_code = quality.handle_local_ci(Namespace())

            self.assertEqual(0, exit_code)
            html = (artifacts_dir / "quality" / "local-ci-latest.html").read_text(encoding="utf-8")
            self.assertIn("整体结果：通过", html)
            self.assertIn("质量检查", html)
            self.assertIn("单元测试", html)
            self.assertIn("用例过程", html)
            self.assertIn("repo rules ok", html)
            self.assertIn("Ruff Python 静态检查", html)
            self.assertIn("Reasoning Agents with Tool Feedback", html)

    def test_handle_local_ci_writes_html_on_failure_and_marks_skipped_cases(self) -> None:
        """验证 quality local-ci 失败时仍写出 HTML，并把后续用例标记为未执行。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            root_dir = Path(temp_dir)
            artifacts_dir = root_dir / "artifacts"
            self._write_e2e_payloads(artifacts_dir)
            self._write_discoverable_test(root_dir / "tests" / "unit" / "test_dummy.py", "DummyUnitTests")
            self._write_discoverable_test(root_dir / "tests" / "e2e" / "test_dummy.py", "DummyE2ETests")

            with (
                patch.object(quality, "ROOT_DIR", root_dir),
                patch.object(quality, "ARTIFACTS_DIR", artifacts_dir),
                patch.object(quality, "QUALITY_STAGES", ["lint", "unit", "e2e"]),
                patch.object(
                    quality,
                    "LINT_SUBCHECKS",
                    [
                        ("repo_rules", [sys.executable, "-c", "import sys; print('repo rules failed'); sys.exit(1)"]),
                        ("ruff", [sys.executable, "-c", "print('ruff ok')"]),
                        ("mypy", [sys.executable, "-c", "print('mypy ok')"]),
                        ("quality_report", [sys.executable, "-c", "print('[OK] quality report')"]),
                    ],
                ),
                patch.object(
                    quality,
                    "UNITTEST_STAGE_CONFIG",
                    {
                        "unit": {"start_dir": "tests/unit", "pattern": "test_*.py"},
                        "e2e": {"start_dir": "tests/e2e", "pattern": "test_*.py"},
                    },
                ),
                patch.object(quality, "STAGE_COMMAND_OVERRIDES", {}),
            ):
                exit_code = quality.handle_local_ci(Namespace())

            self.assertEqual(1, exit_code)
            html = (artifacts_dir / "quality" / "local-ci-latest.html").read_text(encoding="utf-8")
            self.assertIn("整体结果：失败", html)
            self.assertIn("repo rules failed", html)
            self.assertIn("前置阶段失败，本用例未执行。", html)

    def test_handle_local_ci_still_writes_html_when_e2e_json_is_invalid(self) -> None:
        """验证 e2e 的 result.json 非法时，quality local-ci 仍会生成 HTML。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            root_dir = Path(temp_dir)
            artifacts_dir = root_dir / "artifacts"
            self._write_e2e_payloads(artifacts_dir)
            (artifacts_dir / "e2e" / "conference" / "latest" / "result.json").write_text("{", encoding="utf-8")

            commands = {
                "unit": [sys.executable, "-c", "print('unit ok')"],
            }
            with (
                patch.object(quality, "ROOT_DIR", root_dir),
                patch.object(quality, "ARTIFACTS_DIR", artifacts_dir),
                patch.object(quality, "QUALITY_STAGES", ["lint", "unit"]),
                patch.object(
                    quality,
                    "LINT_SUBCHECKS",
                    [
                        ("repo_rules", [sys.executable, "-c", "print('repo rules ok')"]),
                        ("ruff", [sys.executable, "-c", "print('ruff ok')"]),
                        ("mypy", [sys.executable, "-c", "print('mypy ok')"]),
                        ("quality_report", [sys.executable, "-c", "print('[WARN] quality report\\n1. hotspot')"]),
                    ],
                ),
                patch.object(quality, "UNITTEST_STAGE_CONFIG", {}),
                patch.object(quality, "STAGE_COMMAND_OVERRIDES", commands),
            ):
                exit_code = quality.handle_local_ci(Namespace())

            self.assertEqual(0, exit_code)
            html = (artifacts_dir / "quality" / "local-ci-latest.html").read_text(encoding="utf-8")
            self.assertIn("result.json 存在但无法解析", html)
            self.assertIn("顶会报告", html)
            self.assertIn("告警", html)

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

    def _write_discoverable_test(self, path: Path, class_name: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "\n".join(
                [
                    "import unittest",
                    "",
                    f"class {class_name}(unittest.TestCase):",
                    "    def test_placeholder(self):",
                    '        """占位测试，用于验证 skipped 用例采集。"""',
                    "        self.assertTrue(True)",
                    "",
                    "",
                    "if __name__ == '__main__':",
                    "    unittest.main()",
                ]
            ),
            encoding="utf-8",
        )


if __name__ == "__main__":
    unittest.main()
