from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import unittest
from pathlib import Path
from urllib import error, request


ROOT_DIR = Path(__file__).resolve().parents[2]


def _find_free_port() -> int:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as handle:
        handle.bind(("127.0.0.1", 0))
        return int(handle.getsockname()[1])


class EvaluationApiIntegrationTests(unittest.TestCase):
    def test_server_returns_structured_400_for_invalid_payload(self) -> None:
        port = _find_free_port()
        process = self._start_server(port)
        try:
            response = self._post_json(
                port,
                {"request_id": "bad-1", "paper": {"paper_id": "only-id"}},
                expect_error=True,
            )
            self.assertEqual("invalid_request", response["error"]["code"])
            self.assertIn("paper.title", response["error"]["message"])
        finally:
            self._stop_server(process)

    def _start_server(self, port: int) -> subprocess.Popen[str]:
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
                "integration-test-v1",
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

    def _post_json(
        self,
        port: int,
        payload: dict[str, object],
        *,
        expect_error: bool = False,
    ) -> dict[str, object]:
        http_request = request.Request(
            f"http://127.0.0.1:{port}/v1/evaluation/annotate",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        try:
            with request.urlopen(http_request, timeout=5) as response:
                return json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            if not expect_error:
                raise
            body = exc.read().decode("utf-8")
            exc.close()
            return json.loads(body)


if __name__ == "__main__":
    unittest.main()
