from __future__ import annotations

import json
import shutil
import unittest
from pathlib import Path

from paper_analysis.services.ci_html_writer import QualityStageResult, write_ci_html_report


ROOT_DIR = Path(__file__).resolve().parents[2]


class CIHtmlWriterTests(unittest.TestCase):
    def test_write_ci_html_report_renders_stage_and_e2e_sections(self) -> None:
        artifacts_dir = ROOT_DIR / "artifacts" / "test-output" / "ci-html-writer"
        if artifacts_dir.exists():
            shutil.rmtree(artifacts_dir)

        conference_dir = artifacts_dir / "e2e" / "conference" / "latest"
        arxiv_dir = artifacts_dir / "e2e" / "arxiv" / "latest"
        conference_dir.mkdir(parents=True, exist_ok=True)
        arxiv_dir.mkdir(parents=True, exist_ok=True)

        (conference_dir / "summary.md").write_text("# 顶会报告", encoding="utf-8")
        (conference_dir / "stdout.txt").write_text("[OK] conference report", encoding="utf-8")
        (conference_dir / "result.json").write_text(
            json.dumps(
                {
                    "source": "顶会",
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
                    "source": "arXiv",
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

        report_path = artifacts_dir / "quality" / "local-ci-latest.html"
        write_ci_html_report(
            report_path=report_path,
            stage_results=[
                QualityStageResult(
                    stage_name="lint",
                    status="passed",
                    summary="阶段通过",
                    artifact_path="artifacts/quality/lint-latest.txt",
                    output="lint output",
                ),
                QualityStageResult(
                    stage_name="e2e",
                    status="failed",
                    summary="e2e 失败",
                    artifact_path="artifacts/quality/e2e-latest.txt",
                    output="e2e output",
                ),
            ],
            artifacts_dir=artifacts_dir,
        )

        html = report_path.read_text(encoding="utf-8")
        self.assertIn("CI 审核报告", html)
        self.assertIn("整体结果：失败", html)
        self.assertIn("检查 UTF-8、行尾空格、制表符与结尾换行。", html)
        self.assertIn("Agentic Retrieval Planning for Long-Horizon Tasks", html)
        self.assertIn("Reasoning Agents with Tool Feedback", html)
        self.assertIn("查看执行过程", html)

    def test_write_ci_html_report_marks_missing_e2e_artifacts(self) -> None:
        artifacts_dir = ROOT_DIR / "artifacts" / "test-output" / "ci-html-missing"
        if artifacts_dir.exists():
            shutil.rmtree(artifacts_dir)

        report_path = artifacts_dir / "quality" / "local-ci-latest.html"
        write_ci_html_report(
            report_path=report_path,
            stage_results=[
                QualityStageResult(
                    stage_name="lint",
                    status="passed",
                    summary="阶段通过",
                    artifact_path="artifacts/quality/lint-latest.txt",
                    output="lint output",
                )
            ],
            artifacts_dir=artifacts_dir,
        )

        html = report_path.read_text(encoding="utf-8")
        self.assertIn("尚未找到 result.json", html)
        self.assertIn("缺失", html)

    def test_write_ci_html_report_escapes_untrusted_html(self) -> None:
        artifacts_dir = ROOT_DIR / "artifacts" / "test-output" / "ci-html-escape"
        if artifacts_dir.exists():
            shutil.rmtree(artifacts_dir)

        report_path = artifacts_dir / "quality" / "local-ci-latest.html"
        write_ci_html_report(
            report_path=report_path,
            stage_results=[
                QualityStageResult(
                    stage_name="lint",
                    status="failed",
                    summary="<script>alert('summary')</script>",
                    artifact_path="artifacts/quality/lint-latest.txt",
                    output="<b>unsafe output</b>",
                )
            ],
            artifacts_dir=artifacts_dir,
        )

        html = report_path.read_text(encoding="utf-8")
        self.assertIn("&lt;script&gt;alert", html)
        self.assertIn("&lt;b&gt;unsafe output&lt;/b&gt;", html)
        self.assertNotIn("<script>alert('summary')</script>", html)

    def test_write_ci_html_report_marks_invalid_e2e_json_as_failed(self) -> None:
        artifacts_dir = ROOT_DIR / "artifacts" / "test-output" / "ci-html-invalid-json"
        if artifacts_dir.exists():
            shutil.rmtree(artifacts_dir)

        conference_dir = artifacts_dir / "e2e" / "conference" / "latest"
        conference_dir.mkdir(parents=True, exist_ok=True)
        (conference_dir / "result.json").write_text("{", encoding="utf-8")

        report_path = artifacts_dir / "quality" / "local-ci-latest.html"
        write_ci_html_report(
            report_path=report_path,
            stage_results=[
                QualityStageResult(
                    stage_name="e2e",
                    status="failed",
                    summary="e2e 失败",
                    artifact_path="artifacts/quality/e2e-latest.txt",
                    output="e2e output",
                )
            ],
            artifacts_dir=artifacts_dir,
        )

        html = report_path.read_text(encoding="utf-8")
        self.assertIn("result.json 存在但无法解析", html)
        self.assertIn(">失败</div>", html)


if __name__ == "__main__":
    unittest.main()
