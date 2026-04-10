from __future__ import annotations

import smtplib
import tempfile
import unittest
from os import environ
from pathlib import Path
from typing import Self

from paper_analysis.domain.email_delivery import (
    EmailConfig,
    EmailMessagePayload,
    load_email_config_from_env,
)
from paper_analysis.services.email_sender import build_email_message, send_email_message


class EmailConfigTests(unittest.TestCase):
    def test_load_email_config_from_env_requires_all_required_vars(self) -> None:
        """验证邮件配置缺失时会返回稳定的结构化错误语义。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            missing_config_root = str(Path(temp_dir) / "missing-config-root")
            previous_home = environ.get("PAPER_ANALYSIS_HOME")
            environ["PAPER_ANALYSIS_HOME"] = missing_config_root
            try:
                with self.assertRaisesRegex(Exception, "缺少 SMTP 配置"):
                    load_email_config_from_env({"SMTP_HOST": "smtp.qq.com"})
            finally:
                if previous_home is None:
                    environ.pop("PAPER_ANALYSIS_HOME", None)
                else:
                    environ["PAPER_ANALYSIS_HOME"] = previous_home

    def test_load_email_config_from_private_yaml(self) -> None:
        """验证邮件配置可从用户私有目录 email.yaml 读取。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            email_config_path = Path(temp_dir) / "email.yaml"
            email_config_path.write_text(
                "\n".join(
                    [
                        "smtp:",
                        "  host: smtp.qq.com",
                        "  port: 587",
                        "  username: sender@qq.com",
                        "  password: yaml-auth-code",
                        "  from_address: sender@qq.com",
                        "  from_name: Codex_MOZHI",
                        "  to_address: lijiawei14@huawei.com",
                        "  timeout_seconds: 12",
                        "  use_starttls: true",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            previous_home = environ.get("PAPER_ANALYSIS_HOME")
            environ["PAPER_ANALYSIS_HOME"] = temp_dir
            try:
                config = load_email_config_from_env({})
            finally:
                if previous_home is None:
                    environ.pop("PAPER_ANALYSIS_HOME", None)
                else:
                    environ["PAPER_ANALYSIS_HOME"] = previous_home

        self.assertEqual("smtp.qq.com", config.host)
        self.assertEqual(587, config.port)
        self.assertEqual("lijiawei14@huawei.com", config.to_address)
        self.assertEqual("Codex_MOZHI", config.from_name)

    def test_load_email_config_from_env_overrides_private_yaml(self) -> None:
        """验证环境变量会覆盖私有 YAML 中的同名配置。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            email_config_path = Path(temp_dir) / "email.yaml"
            email_config_path.write_text(
                "\n".join(
                    [
                        "smtp:",
                        "  host: smtp.qq.com",
                        "  port: 587",
                        "  username: sender@qq.com",
                        "  password: yaml-auth-code",
                        "  from_address: sender@qq.com",
                        "  from_name: YAML_NAME",
                        "  to_address: yaml@example.com",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            previous_home = environ.get("PAPER_ANALYSIS_HOME")
            environ["PAPER_ANALYSIS_HOME"] = temp_dir
            try:
                config = load_email_config_from_env(
                    {
                        "SMTP_TO": "env@example.com",
                        "SMTP_PASSWORD": "env-auth-code",
                        "SMTP_FROM_NAME": "ENV_NAME",
                    }
                )
            finally:
                if previous_home is None:
                    environ.pop("PAPER_ANALYSIS_HOME", None)
                else:
                    environ["PAPER_ANALYSIS_HOME"] = previous_home

        self.assertEqual("env@example.com", config.to_address)
        self.assertEqual("env-auth-code", config.password)
        self.assertEqual("ENV_NAME", config.from_name)

    def test_load_email_config_from_env_parses_port_and_flags(self) -> None:
        """验证邮件配置加载会解析端口、超时和 STARTTLS 开关。"""

        config = load_email_config_from_env(
            {
                "SMTP_HOST": "smtp.qq.com",
                "SMTP_PORT": "587",
                "SMTP_USERNAME": "sender@qq.com",
                "SMTP_PASSWORD": "auth-code",
                "SMTP_FROM": "sender@qq.com",
                "SMTP_TO": "receiver@example.com",
                "SMTP_FROM_NAME": "Codex_MOZHI",
                "SMTP_TIMEOUT_SECONDS": "12.5",
                "SMTP_USE_STARTTLS": "false",
            }
        )

        self.assertEqual("smtp.qq.com", config.host)
        self.assertEqual(587, config.port)
        self.assertEqual(12.5, config.timeout_seconds)
        self.assertFalse(config.use_starttls)
        self.assertEqual("Codex_MOZHI", config.from_name)


class EmailSenderTests(unittest.TestCase):
    def test_build_email_message_keeps_utf8_subject_and_body(self) -> None:
        """验证 MIME 消息会以 UTF-8 编码中文主题与正文。"""

        message = build_email_message(
            EmailConfig(
                host="smtp.qq.com",
                port=587,
                username="sender@qq.com",
                password="auth-code",  # noqa: S106 - 测试夹具密文
                from_address="sender@qq.com",
                to_address="receiver@example.com",
                from_name="Codex_MOZHI",
            ),
            EmailMessagePayload(
                subject="Paper Analysis 中文测试",
                text_body="这是一封中文测试邮件。",
                html_body="<p>这是一封中文测试邮件。</p>",
                recipient="receiver@example.com",
            ),
        )

        message_bytes = message.as_bytes()
        self.assertIn(b'charset="utf-8"', message_bytes)
        self.assertIn(b"=?utf-8?", message_bytes.lower())
        self.assertIn(b"Codex_MOZHI", message_bytes)

    def test_send_email_message_returns_success_and_writes_eml_snapshot(self) -> None:
        """验证 SMTP 成功时会返回 sent 状态并保存 .eml 快照。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            result = send_email_message(
                _sample_config(),
                _sample_payload(),
                smtp_factory=SuccessfulSMTP,
                eml_output_path=Path(temp_dir) / "message.eml",
            )

        self.assertEqual("sent", result.status)
        self.assertEqual("receiver@example.com", result.recipient)
        self.assertTrue(result.message_id)
        self.assertTrue(result.eml_path.endswith("message.eml"))

    def test_send_email_message_translates_authentication_failure(self) -> None:
        """验证 SMTP 认证失败会被翻译为稳定错误结果。"""

        result = send_email_message(
            _sample_config(),
            _sample_payload(),
            smtp_factory=AuthenticationFailingSMTP,
        )

        self.assertEqual("failed", result.status)
        self.assertEqual("authentication_failed", result.error_type)
        self.assertIn("QQ 邮箱授权码", result.error_summary)

    def test_send_email_message_translates_recipient_refusal(self) -> None:
        """验证收件人拒收会被翻译为发送失败结果。"""

        result = send_email_message(
            _sample_config(),
            _sample_payload(),
            smtp_factory=RecipientRefusedSMTP,
        )

        self.assertEqual("failed", result.status)
        self.assertEqual("send_failed", result.error_type)
        self.assertIn("receiver@example.com", result.error_summary)

    def test_send_email_message_translates_connection_error(self) -> None:
        """验证连接失败会被翻译为连接错误结果。"""

        result = send_email_message(
            _sample_config(),
            _sample_payload(),
            smtp_factory=ConnectionFailingSMTP,
        )

        self.assertEqual("failed", result.status)
        self.assertEqual("connection_failed", result.error_type)
        self.assertIn("连接失败", result.error_summary)


def _sample_config() -> EmailConfig:
    return EmailConfig(
        host="smtp.qq.com",
        port=587,
        username="sender@qq.com",
        password="auth-code",  # noqa: S106 - 测试夹具密文
        from_address="sender@qq.com",
        to_address="receiver@example.com",
        from_name="Codex_MOZHI",
    )


def _sample_payload() -> EmailMessagePayload:
    return EmailMessagePayload(
        subject="Paper Analysis 测试",
        text_body="测试正文",
        recipient="receiver@example.com",
    )


class SuccessfulSMTP:
    def __init__(self, host: str, port: int, timeout: float) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.logged_in = False

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    def ehlo(self) -> None:
        return None

    def starttls(self, context: object) -> None:
        return None

    def login(self, username: str, password: str) -> None:
        self.logged_in = bool(username and password)

    def send_message(self, message: object) -> None:
        return None


class AuthenticationFailingSMTP(SuccessfulSMTP):
    def login(self, username: str, password: str) -> None:
        raise smtplib.SMTPAuthenticationError(535, b"auth failed")


class RecipientRefusedSMTP(SuccessfulSMTP):
    def send_message(self, message: object) -> None:
        raise smtplib.SMTPRecipientsRefused({"receiver@example.com": (550, b"rejected")})


class ConnectionFailingSMTP:
    def __init__(self, host: str, port: int, timeout: float) -> None:
        raise OSError("network unreachable")

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    def ehlo(self) -> None:
        return None

    def starttls(self, context: object) -> None:
        return None

    def login(self, username: str, password: str) -> None:
        return None

    def send_message(self, message: object) -> None:
        return None


if __name__ == "__main__":
    unittest.main()
