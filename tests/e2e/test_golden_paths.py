from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

from paper_analysis.services.ci_html_writer import QualityStageResult, write_ci_html_report
from paper_analysis.testing.case_metadata import CaseMetadataMixin


ROOT_DIR = Path(__file__).resolve().parents[2]


class GoldenPathE2ETests(CaseMetadataMixin, unittest.TestCase):
    def test_conference_report_generates_stable_artifacts(self) -> None:
        """【顶会】顶会论文筛选可以正常生成结果。"""

        self.set_case_source_label("conference e2e")
        self.set_failure_check_description("CLI 返回码非 0，或 summary/result/csv/stdout 任一关键产物缺失时判定失败。")
        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        self.record_step("准备 conference report 命令与 UTF-8 子进程环境。")

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
        self.record_step(f"执行 conference report，返回码={result.returncode}。")
        self.assertEqual(0, result.returncode)

        report_dir = ROOT_DIR / "artifacts" / "e2e" / "conference" / "latest"
        self.add_case_artifact(str(report_dir / "summary.md"))
        self.add_case_artifact(str(report_dir / "result.json"))
        self.add_case_artifact(str(report_dir / "result.csv"))
        self.add_case_artifact(str(report_dir / "stdout.txt"))
        self.record_step("校验 summary.md、result.csv、result.json、stdout.txt 已生成。")
        self.assertTrue((report_dir / "summary.md").exists())
        self.assertTrue((report_dir / "result.csv").exists())
        payload = json.loads((report_dir / "result.json").read_text(encoding="utf-8"))
        self.record_step(f"读取 result.json，确认 source={payload['source']}，count={payload['count']}。")
        self.assertEqual("顶会", payload["source"])
        self.assertEqual(2, payload["count"])
        self.assertIn("候选不足 10 篇", (report_dir / "stdout.txt").read_text(encoding="utf-8"))
        self.record_step("检查 stdout.txt 含候选不足提示，确认文本产物内容稳定。")

    def test_arxiv_report_generates_stable_artifacts(self) -> None:
        """【arxiv】arXiv API 可以正常获取论文。"""

        self.set_case_source_label("arxiv e2e")
        self.set_failure_check_description("CLI 返回码非 0，或联网 arXiv 报告缺少关键产物时判定失败。")
        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        self.record_step("准备 arxiv report 命令与 UTF-8 子进程环境。")

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "paper_analysis.cli.main",
                "arxiv",
                "report",
                "--source-mode",
                "subscription-api",
                "--subscription-date",
                "2025-09/09-01",
                "--max-results",
                "10",
            ],
            cwd=ROOT_DIR,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            check=False,
        )
        self.record_step(f"执行 arxiv report，返回码={result.returncode}。")
        self.assertEqual(0, result.returncode)

        report_dir = ROOT_DIR / "artifacts" / "e2e" / "arxiv" / "latest"
        self.add_case_artifact(str(report_dir / "summary.md"))
        self.add_case_artifact(str(report_dir / "result.json"))
        self.add_case_artifact(str(report_dir / "result.csv"))
        self.add_case_artifact(str(report_dir / "stdout.txt"))
        self.record_step("校验 arXiv 报告目录中的关键产物存在。")
        self.assertTrue((report_dir / "summary.md").exists())
        self.assertTrue((report_dir / "result.csv").exists())
        payload = json.loads((report_dir / "result.json").read_text(encoding="utf-8"))
        self.record_step(f"读取 result.json，确认 source={payload['source']}，count={payload['count']}。")
        self.assertEqual("arXiv", payload["source"])
        self.assertGreaterEqual(payload["count"], 1)
        first_paper = payload["papers"][0]
        self.assertTrue(first_paper["paper_id"])
        self.assertTrue(first_paper["title"])
        self.assertTrue(first_paper["published_at"])
        self.record_step("确认 arXiv 联网结果至少包含一篇结构完整的论文。")

    def test_ci_html_report_renders_recommendations_from_real_e2e_artifacts(self) -> None:
        """【推荐】本地 CI 页面可以正常展示推荐相关 E2E 结果。"""

        self.set_case_source_label("ci html e2e")
        self.set_failure_check_description("若 HTML 未包含真实 e2e 推荐结果或关键区块缺失，则判定失败。")
        self.record_step("先生成 conference 与 arXiv 的真实 e2e 报告产物。")
        self._run_report(
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
            ]
        )
        self._run_report(
            [
                sys.executable,
                "-m",
                "paper_analysis.cli.main",
                "arxiv",
                "report",
                "--source-mode",
                "subscription-api",
                "--subscription-date",
                "2025-09/09-01",
                "--max-results",
                "10",
            ]
        )
        self.record_step("基于真实产物调用 CI HTML writer 生成 local-ci 审核页。")

        report_dir = ROOT_DIR / "artifacts" / "test-output" / "e2e-ci-html"
        if report_dir.exists():
            shutil.rmtree(report_dir)
        report_path = report_dir / "local-ci-latest.html"
        self.add_case_artifact(str(report_path))
        write_ci_html_report(
            report_path=report_path,
            stage_results=[
                QualityStageResult(
                    stage_name="lint",
                    status="passed",
                    summary="阶段通过",
                    artifact_path="artifacts/quality/lint-latest.txt",
                    output="lint ok",
                ),
                QualityStageResult(
                    stage_name="e2e",
                    status="passed",
                    summary="阶段通过",
                    artifact_path="artifacts/quality/e2e-latest.txt",
                    output="e2e ok",
                ),
            ],
            artifacts_dir=ROOT_DIR / "artifacts",
        )

        html = report_path.read_text(encoding="utf-8")
        self.record_step("读取 local-ci-latest.html，检查顶会标题、arXiv 区块和 E2E 报告附件是否存在。")
        self.assertIn("Agentic Retrieval Planning for Long-Horizon Tasks", html)
        self.assertIn("arXiv", html)
        self.assertIn("--source-mode subscription-api", html)
        self.assertIn("E2E 报告附件", html)

    def _run_report(self, command: list[str]) -> None:
        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"

        result = subprocess.run(
            command,
            cwd=ROOT_DIR,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            check=False,
        )
        self.assertEqual(0, result.returncode)


if __name__ == "__main__":
    unittest.main()
