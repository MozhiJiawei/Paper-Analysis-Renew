from __future__ import annotations

import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from paper_analysis.utils.codex_cli_client import CodexCliClient


class CodexCliClientTests(unittest.TestCase):
    def test_submit_runner_short_circuits_subprocess(self) -> None:
        client = CodexCliClient(runner=lambda prompt: f"ok:{prompt}")

        with patch("paper_analysis.utils.codex_cli_client.subprocess.run") as mocked_run:
            result = client.submit("hello").result()

        self.assertEqual("ok:hello", result)
        mocked_run.assert_not_called()

    def test_invalid_concurrency_raises_value_error(self) -> None:
        for value in (0, -1, 11):
            with self.assertRaises(ValueError):
                CodexCliClient(concurrency=value)

    def test_submit_non_zero_returncode_raises_runtime_error(self) -> None:
        client = CodexCliClient()
        completed = SimpleNamespace(returncode=2, stdout="fallback", stderr="boom")

        with patch("paper_analysis.utils.codex_cli_client.subprocess.run", return_value=completed):
            with self.assertRaises(RuntimeError) as context:
                client.submit("hello").result()

        self.assertIn("returncode=2", str(context.exception))
        self.assertIn("boom", str(context.exception))

    def test_windows_uses_codex_cmd(self) -> None:
        client = CodexCliClient()
        completed = SimpleNamespace(returncode=0, stdout="ok\n", stderr="")

        with patch("paper_analysis.utils.codex_cli_client.os.name", "nt"):
            with patch("paper_analysis.utils.codex_cli_client.subprocess.run", return_value=completed) as mocked_run:
                client.submit("hello").result()

        command = mocked_run.call_args.args[0]
        self.assertEqual("codex.cmd", command[0])

    def test_non_windows_uses_codex(self) -> None:
        client = CodexCliClient()
        completed = SimpleNamespace(returncode=0, stdout="ok\n", stderr="")

        with patch("paper_analysis.utils.codex_cli_client.os.name", "posix"):
            with patch("paper_analysis.utils.codex_cli_client.subprocess.run", return_value=completed) as mocked_run:
                client.submit("hello").result()

        command = mocked_run.call_args.args[0]
        self.assertEqual("codex", command[0])

    def test_submit_passes_json_ephemeral_cwd_and_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            client = CodexCliClient(
                cwd=Path(temp_dir),
                timeout=12,
                model="gpt-5.1-codex-mini",
                json_mode=True,
                ephemeral=True,
            )
            completed = SimpleNamespace(returncode=0, stdout="ok\n", stderr="")

            with patch("paper_analysis.utils.codex_cli_client.subprocess.run", return_value=completed) as mocked_run:
                client.submit("hello").result()

        command = mocked_run.call_args.args[0]
        kwargs = mocked_run.call_args.kwargs
        self.assertEqual(
            [
                command[0],
                "exec",
                "-m",
                "gpt-5.1-codex-mini",
                "--dangerously-bypass-approvals-and-sandbox",
                "--json",
                "--ephemeral",
                "hello",
            ],
            command,
        )
        self.assertEqual(Path(temp_dir), kwargs["cwd"])
        self.assertEqual(12, kwargs["timeout"])
        self.assertTrue(kwargs["capture_output"])
        self.assertEqual("utf-8", kwargs["encoding"])

    def test_timeout_raises_runtime_error(self) -> None:
        client = CodexCliClient(timeout=3)

        with patch(
            "paper_analysis.utils.codex_cli_client.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="codex", timeout=3),
        ):
            with self.assertRaises(RuntimeError) as context:
                client.submit("hello").result()

        self.assertIn("超时", str(context.exception))
        self.assertIn("3", str(context.exception))

    def test_error_message_contains_model_when_configured(self) -> None:
        client = CodexCliClient(model="gpt-5.1-codex-mini")
        completed = SimpleNamespace(returncode=2, stdout="", stderr="boom")

        with patch("paper_analysis.utils.codex_cli_client.subprocess.run", return_value=completed):
            with self.assertRaises(RuntimeError) as context:
                client.submit("hello").result()

        self.assertIn("gpt-5.1-codex-mini", str(context.exception))

    def test_shared_client_can_be_reused_concurrently(self) -> None:
        def runner(prompt: str) -> str:
            time.sleep(0.01 if prompt.endswith("0") else 0.001)
            return f"done:{prompt}"

        client = CodexCliClient(runner=runner, concurrency=4)
        prompts = [f"prompt-{index}" for index in range(8)]
        futures = [client.submit(prompt) for prompt in prompts]

        results = [future.result() for future in futures]

        self.assertEqual([f"done:{prompt}" for prompt in prompts], results)


if __name__ == "__main__":
    unittest.main()
