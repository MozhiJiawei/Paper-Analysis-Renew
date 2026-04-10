from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from paper_analysis.cli.main import build_parser
from paper_analysis.domain.email_delivery import EmailConfig, EmailSendResult

ROOT_DIR = Path(__file__).resolve().parents[2]


class EmailDeliveryCliTests(unittest.TestCase):
    def test_quality_help_lists_send_test_email_command(self) -> None:
        """验证 quality 帮助页暴露独立邮件调试入口。"""

        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"

        result = subprocess.run(
            [sys.executable, "-m", "paper_analysis.cli.main", "quality", "--help"],
            cwd=ROOT_DIR,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            check=False,
        )

        self.assertEqual(0, result.returncode)
        self.assertIn("send-test-email", result.stdout)
        self.assertIn("测试邮件", result.stdout)

    def test_send_test_email_returns_structured_error_when_config_missing(self) -> None:
        """验证测试邮件命令在配置缺失时返回结构化失败。"""

        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        env["PAPER_ANALYSIS_HOME"] = str(ROOT_DIR / "artifacts" / "test-output" / "missing-email-config")
        for key in (
            "SMTP_HOST",
            "SMTP_PORT",
            "SMTP_USERNAME",
            "SMTP_PASSWORD",
            "SMTP_FROM",
            "SMTP_TO",
        ):
            env.pop(key, None)

        result = subprocess.run(
            [sys.executable, "-m", "paper_analysis.cli.main", "quality", "send-test-email"],
            cwd=ROOT_DIR,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            check=False,
        )

        self.assertEqual(1, result.returncode)
        self.assertIn("[FAIL] scope=quality.send-test-email", result.stdout)
        self.assertIn("SMTP_HOST", result.stdout)
        self.assertNotIn("Traceback", result.stdout + result.stderr)

    def test_send_test_email_handler_uses_email_service_and_returns_success(self) -> None:
        """验证测试邮件入口会加载配置并调用统一邮件发送 service。"""

        parser = build_parser()
        args = parser.parse_args(["quality", "send-test-email"])

        with (
            patch(
                "paper_analysis.cli.quality.load_email_config_from_env",
                return_value=EmailConfig(
                    host="smtp.qq.com",
                    port=587,
                    username="sender@qq.com",
                    password="auth-code",  # noqa: S106 - 测试夹具密文
                    from_address="sender@qq.com",
                    to_address="receiver@example.com",
                ),
            ),
            patch(
                "paper_analysis.cli.quality.send_email_message",
                return_value=EmailSendResult.success(
                    recipient="receiver@example.com",
                    message_id="<message-id>",
                ),
            ) as mocked_send,
        ):
            exit_code = args.handler(args)

        self.assertEqual(0, exit_code)
        mocked_send.assert_called_once()


if __name__ == "__main__":
    unittest.main()
