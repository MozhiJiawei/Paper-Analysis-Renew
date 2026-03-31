from __future__ import annotations

import json
import shutil
import unittest
from pathlib import Path

from paper_analysis.services.ci_html_writer import QualityStageResult, write_ci_html_report
from paper_analysis.services.quality_case_support import QualityCaseResult, write_case_results


ROOT_DIR = Path(__file__).resolve().parents[2]


class CIHtmlWriterTests(unittest.TestCase):
    def test_write_ci_html_report_renders_case_categories_and_e2e_sections(self) -> None:
        """验证 CI HTML 会渲染三大类用例区与 E2E 报告附件区。"""

        artifacts_dir = ROOT_DIR / "artifacts" / "test-output" / "ci-html-writer"
        if artifacts_dir.exists():
            shutil.rmtree(artifacts_dir)

        self._write_e2e_payloads(artifacts_dir)
        self._write_case_artifacts(
            artifacts_dir,
            {
                "lint": [
                    QualityCaseResult(
                        stage_name="lint",
                        case_id="quality.lint",
                        title="lint 检查",
                        status="passed",
                        description="检查仓库文本文件的编码与基础格式。",
                        failure_check="命令退出码非 0 时判定失败。",
                        process_log=["执行 lint 脚本。", "读取扫描结果。"],
                        result_log="lint output",
                        source_label="lint",
                        artifact_paths=["artifacts/quality/lint-latest.txt"],
                        script_path=str(ROOT_DIR / "scripts" / "quality" / "lint.py"),
                    )
                ],
                "integration": [
                    QualityCaseResult(
                        stage_name="integration",
                        case_id="tests.integration.test_pipelines.PipelineIntegrationTests.test_conference_filter_missing_input",
                        title="conference filter 缺失输入",
                        status="passed",
                        description="验证 conference filter 在输入文件缺失时输出结构化失败信息。",
                        failure_check="若 CLI 未返回失败码、未输出缺失文件提示，或出现 Traceback，则判定失败。",
                        process_log=["调用 conference filter 缺失输入路径。", "断言 stdout 含 [FAIL] scope=conference.filter。"],
                        result_log="[FAIL] scope=conference.filter\nsummary: 输入文件不存在：missing.json",
                        source_label="integration",
                        artifact_paths=["artifacts/quality/integration-latest.txt"],
                        script_path=str(ROOT_DIR / "tests" / "integration" / "test_pipelines.py"),
                    )
                ],
                "e2e": [
                    QualityCaseResult(
                        stage_name="e2e",
                        case_id="tests.e2e.test_golden_paths.GoldenPathE2ETests.test_conference_report_generates_stable_artifacts",
                        title="conference report 黄金路径",
                        status="passed",
                        description="验证 conference report 能生成稳定的 summary/json/csv/stdout 产物。",
                        failure_check="若 CLI 返回码非 0 或关键产物缺失则判定失败。",
                        process_log=["执行 conference report。", "检查 result.json 的 source 与 count。"],
                        result_log="测试通过。",
                        source_label="conference e2e",
                        artifact_paths=["artifacts/e2e/conference/latest/result.json"],
                        script_path=str(ROOT_DIR / "tests" / "e2e" / "test_golden_paths.py"),
                    )
                ],
            },
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
                    stage_name="integration",
                    status="passed",
                    summary="阶段通过",
                    artifact_path="artifacts/quality/integration-latest.txt",
                    output="integration output with [FAIL] scope=conference.filter",
                ),
                QualityStageResult(
                    stage_name="e2e",
                    status="passed",
                    summary="阶段通过",
                    artifact_path="artifacts/quality/e2e-latest.txt",
                    output="e2e output",
                ),
            ],
            artifacts_dir=artifacts_dir,
        )

        html = report_path.read_text(encoding="utf-8")
        self.assertIn("CI 审核报告", html)
        self.assertIn("整体结果：通过", html)
        self.assertIn("质量检查", html)
        self.assertIn("单元测试", html)
        self.assertIn("E2E 测试", html)
        self.assertIn("用例描述", html)
        self.assertIn("用例过程", html)
        self.assertIn("conference filter 缺失输入", html)
        self.assertIn("conference e2e", html)
        self.assertIn("Reasoning Agents with Tool Feedback", html)
        self.assertIn("file:///", html)
        self.assertIn("tests/e2e/test_golden_paths.py", html)

    def test_write_ci_html_report_keeps_overall_passed_when_case_log_contains_fail_text(self) -> None:
        """验证结果日志包含 FAIL 文案时，整体状态仍按真实测试结果显示通过。"""

        artifacts_dir = ROOT_DIR / "artifacts" / "test-output" / "ci-html-pass-with-fail-log"
        if artifacts_dir.exists():
            shutil.rmtree(artifacts_dir)

        self._write_case_artifacts(
            artifacts_dir,
            {
                "integration": [
                    QualityCaseResult(
                        stage_name="integration",
                        case_id="integration.case",
                        title="integration case",
                        status="passed",
                        description="验证负路径测试本身通过。",
                        failure_check="如果断言不成立则失败。",
                        process_log=["执行负路径测试。"],
                        result_log="[FAIL] scope=conference.report",
                        source_label="integration",
                        artifact_paths=["artifacts/quality/integration-latest.txt"],
                    )
                ]
            },
        )

        report_path = artifacts_dir / "quality" / "local-ci-latest.html"
        write_ci_html_report(
            report_path=report_path,
            stage_results=[
                QualityStageResult(
                    stage_name="integration",
                    status="passed",
                    summary="阶段通过",
                    artifact_path="artifacts/quality/integration-latest.txt",
                    output="[FAIL] scope=conference.report",
                )
            ],
            artifacts_dir=artifacts_dir,
        )

        html = report_path.read_text(encoding="utf-8")
        self.assertIn("整体结果：通过", html)
        self.assertIn("[FAIL] scope=conference.report", html)

    def test_write_ci_html_report_marks_missing_e2e_artifacts(self) -> None:
        """验证缺失 e2e 结构化产物时，HTML 会明确标记为缺失。"""

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
        """验证 HTML 报告会转义不可信内容，避免脚本注入。"""

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
        """验证 e2e 的 result.json 非法时，HTML 会显示失败提示。"""

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
        self.assertIn("失败", html)

    def test_write_ci_html_report_sorts_e2e_cases_by_title(self) -> None:
        """验证 E2E 用例按标题名称排序显示。"""

        artifacts_dir = ROOT_DIR / "artifacts" / "test-output" / "ci-html-sort-by-title"
        if artifacts_dir.exists():
            shutil.rmtree(artifacts_dir)

        self._write_case_artifacts(
            artifacts_dir,
            {
                "e2e": [
                    QualityCaseResult(
                        stage_name="e2e",
                        case_id="e2e.z",
                        title="【推荐】主仓推荐算法评测接口可用",
                        status="passed",
                        description="desc",
                        failure_check="check",
                        process_log=["step"],
                        result_log="ok",
                        source_label="evaluation api e2e",
                    ),
                    QualityCaseResult(
                        stage_name="e2e",
                        case_id="e2e.a",
                        title="【arxiv】arXiv API 可以正常获取论文",
                        status="passed",
                        description="desc",
                        failure_check="check",
                        process_log=["step"],
                        result_log="ok",
                        source_label="arxiv e2e",
                    ),
                    QualityCaseResult(
                        stage_name="e2e",
                        case_id="e2e.b",
                        title="【顶会】顶会论文筛选可以正常生成结果",
                        status="passed",
                        description="desc",
                        failure_check="check",
                        process_log=["step"],
                        result_log="ok",
                        source_label="conference e2e",
                    ),
                ]
            },
        )

        report_path = artifacts_dir / "quality" / "local-ci-latest.html"
        write_ci_html_report(
            report_path=report_path,
            stage_results=[
                QualityStageResult(
                    stage_name="e2e",
                    status="passed",
                    summary="阶段通过",
                    artifact_path="artifacts/quality/e2e-latest.txt",
                    output="e2e output",
                )
            ],
            artifacts_dir=artifacts_dir,
        )

        html = report_path.read_text(encoding="utf-8")
        arxiv_index = html.index("【arxiv】arXiv API 可以正常获取论文")
        recommend_index = html.index("【推荐】主仓推荐算法评测接口可用")
        conference_index = html.index("【顶会】顶会论文筛选可以正常生成结果")
        self.assertLess(arxiv_index, recommend_index)
        self.assertLess(recommend_index, conference_index)

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

    def _write_case_artifacts(
        self,
        artifacts_dir: Path,
        stage_cases: dict[str, list[QualityCaseResult]],
    ) -> None:
        for stage_name, cases in stage_cases.items():
            write_case_results(artifacts_dir / "quality" / f"{stage_name}-cases-latest.json", cases)


if __name__ == "__main__":
    unittest.main()
