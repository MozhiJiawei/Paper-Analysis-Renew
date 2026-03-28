from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import unittest
from pathlib import Path
from urllib import request

from paper_analysis.testing.case_metadata import CaseMetadataMixin


ROOT_DIR = Path(__file__).resolve().parents[2]
DATASET_ROOT = ROOT_DIR / "third_party" / "paper_analysis_dataset"


def _find_free_port() -> int:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as handle:
        handle.bind(("127.0.0.1", 0))
        return int(handle.getsockname()[1])


class EvaluationApiE2ETests(CaseMetadataMixin, unittest.TestCase):
    def test_evaluation_api_annotate_endpoint_golden_path(self) -> None:
        self.set_case_source_label("evaluation api e2e")
        self.set_failure_check_description("若真实 POST /v1/evaluation/annotate 未返回合法 schema，则判定失败。")
        port = _find_free_port()
        process = self._start_server(port, algorithm_version="e2e-test-v1")
        artifact_dir = ROOT_DIR / "artifacts" / "test-output" / "evaluation-api-e2e"
        if artifact_dir.exists():
            shutil.rmtree(artifact_dir)
        artifact_dir.mkdir(parents=True, exist_ok=True)
        try:
            fixture_path = ROOT_DIR / "tests" / "fixtures" / "evaluation" / "annotate_request.json"
            payload = json.loads(fixture_path.read_text(encoding="utf-8"))
            self.record_step("向本地评测服务发送真实 annotate 请求。")
            response = self._post_json(port, payload)
            request_path = artifact_dir / "request.json"
            response_path = artifact_dir / "response.json"
            request_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            response_path.write_text(
                json.dumps(response, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            self.add_case_artifact(str(fixture_path))
            self.add_case_artifact(str(request_path))
            self.add_case_artifact(str(response_path))
            self.record_step("检查响应 schema、单标签协议以及脱敏边界。")
            self.assertEqual("req-e2e-001", response["request_id"])
            self.assertEqual("e2e-test-v1", response["model_info"]["algorithm_version"])
            self.assertEqual("positive", response["prediction"]["negative_tier"])
            self.assertEqual(1, len(response["prediction"]["preference_labels"]))
            self.assertNotIn("expected_label", json.dumps(response, ensure_ascii=False))
            self.assertNotIn("split", json.dumps(response, ensure_ascii=False))
        finally:
            self._stop_server(process)

    def test_dataset_evaluate_cli_hits_real_annotate_endpoint(self) -> None:
        self.set_case_source_label("dataset evaluation e2e")
        self.set_failure_check_description("若子仓评测 CLI 未真实命中 annotate API 或报告泄露测试集信息，则判定失败。")
        port = _find_free_port()
        process = self._start_server(port, algorithm_version="cross-repo-e2e-v1")
        output_dir = DATASET_ROOT / "artifacts" / "test-output" / "evaluation-e2e"
        if output_dir.exists():
            shutil.rmtree(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "paper_analysis_dataset.tools.evaluate_paper_filter_benchmark",
                    "--base-url",
                    f"http://127.0.0.1:{port}",
                    "--limit",
                    "3",
                    "--output-dir",
                    str(output_dir),
                ],
                cwd=DATASET_ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                check=False,
            )
            self.record_step(f"执行子仓评测 CLI，返回码={result.returncode}。")
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            report_json = output_dir / "report.json"
            summary_md = output_dir / "summary.md"
            stdout_txt = output_dir / "stdout.txt"
            cli_stdout = output_dir / "cli-stdout.txt"
            cli_stderr = output_dir / "cli-stderr.txt"
            cli_stdout.write_text(result.stdout, encoding="utf-8")
            cli_stderr.write_text(result.stderr, encoding="utf-8")
            self.add_case_artifact(str(report_json))
            self.add_case_artifact(str(summary_md))
            self.add_case_artifact(str(stdout_txt))
            self.add_case_artifact(str(cli_stdout))
            self.add_case_artifact(str(cli_stderr))
            self.assertTrue(report_json.exists())
            self.assertTrue(summary_md.exists())
            self.assertTrue(stdout_txt.exists())
            payload = json.loads(report_json.read_text(encoding="utf-8"))
            summary = summary_md.read_text(encoding="utf-8")
            serialized = json.dumps(payload, ensure_ascii=False) + "\n" + summary
            self.record_step("检查报告产物只包含聚合指标，不泄露 paper_id、标题、摘要或 source_path。")
            self.assertEqual(3, payload["counts"]["evaluated_count"])
            self.assertEqual(0, payload["counts"]["request_error_count"])
            self.assertEqual(0, payload["counts"]["protocol_error_count"])
            self.assertNotIn("paper_id", serialized)
            self.assertNotIn("title", serialized.lower())
            self.assertNotIn("abstract", serialized.lower())
            self.assertNotIn("source_path", serialized)
        finally:
            self._stop_server(process)

    def _start_server(self, port: int, *, algorithm_version: str) -> subprocess.Popen[str]:
        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "paper_analysis.api.evaluation_server",
                "--port",
                str(port),
                "--algorithm-version",
                algorithm_version,
            ],
            cwd=ROOT_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
        deadline = time.time() + 10
        while time.time() < deadline:
            try:
                with request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=1) as response:
                    if response.status == 200:
                        return process
            except Exception:
                time.sleep(0.1)
        self._stop_server(process)
        self.fail("评测服务未能在预期时间内启动。")

    def _stop_server(self, process: subprocess.Popen[str]) -> None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        if process.stdout is not None:
            process.stdout.close()
        if process.stderr is not None:
            process.stderr.close()

    def _post_json(self, port: int, payload: dict[str, object]) -> dict[str, object]:
        http_request = request.Request(
            f"http://127.0.0.1:{port}/v1/evaluation/annotate",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        with request.urlopen(http_request, timeout=5) as response:
            return json.loads(response.read().decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
