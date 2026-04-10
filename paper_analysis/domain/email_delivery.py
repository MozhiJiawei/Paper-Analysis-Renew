"""Domain models for standalone email delivery capability."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from os import environ, getenv
from pathlib import Path
from typing import TYPE_CHECKING

import yaml  # type: ignore[import-untyped]

if TYPE_CHECKING:
    from collections.abc import Mapping

REQUIRED_SMTP_ENV_VARS = (
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_USERNAME",
    "SMTP_PASSWORD",
    "SMTP_FROM",
    "SMTP_TO",
)
DEFAULT_EMAIL_CONFIG_DIR_NAME = ".paper-analysis"
DEFAULT_EMAIL_CONFIG_FILE_NAME = "email.yaml"
OPTIONAL_SMTP_ENV_VARS = ("SMTP_FROM_NAME", "SMTP_TIMEOUT_SECONDS", "SMTP_USE_STARTTLS")


class EmailDeliveryError(Exception):
    """Base error for all email delivery failures."""

    error_type = "send_failed"

    def __init__(self, summary: str) -> None:
        """Store a stable, user-facing error summary."""
        super().__init__(summary)
        self.summary = summary


class EmailConfigError(EmailDeliveryError):
    """Raised when SMTP configuration is missing or invalid."""

    error_type = "config_missing"


class EmailConnectionError(EmailDeliveryError):
    """Raised when the SMTP server cannot be reached."""

    error_type = "connection_failed"


class EmailAuthenticationError(EmailDeliveryError):
    """Raised when SMTP authentication fails."""

    error_type = "authentication_failed"


class EmailSendError(EmailDeliveryError):
    """Raised when the server rejects the outbound message."""

    error_type = "send_failed"


@dataclass(slots=True)
class EmailConfig:
    """SMTP connection settings loaded from the environment."""

    host: str
    port: int
    username: str
    password: str
    from_address: str
    to_address: str
    from_name: str = ""
    timeout_seconds: float = 20.0
    use_starttls: bool = True


@dataclass(slots=True)
class EmailMessagePayload:
    """Structured email payload independent from paper domain objects."""

    subject: str
    text_body: str
    recipient: str
    html_body: str = ""
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class EmailSendResult:
    """Structured send result returned to CLI or upper layers."""

    status: str
    recipient: str
    sent_at: str
    error_type: str = ""
    error_summary: str = ""
    message_id: str = ""
    eml_path: str = ""

    @classmethod
    def success(
        cls,
        *,
        recipient: str,
        message_id: str,
        eml_path: str = "",
    ) -> EmailSendResult:
        """Build a success result with a stable UTC timestamp."""
        return cls(
            status="sent",
            recipient=recipient,
            sent_at=_utc_now_isoformat(),
            message_id=message_id,
            eml_path=eml_path,
        )

    @classmethod
    def failure(
        cls,
        *,
        recipient: str,
        error: EmailDeliveryError,
        eml_path: str = "",
    ) -> EmailSendResult:
        """Build a failure result that preserves stable error semantics."""
        return cls(
            status="failed",
            recipient=recipient,
            sent_at=_utc_now_isoformat(),
            error_type=error.error_type,
            error_summary=error.summary,
            eml_path=eml_path,
        )


def load_email_config_from_env(env: Mapping[str, str] | None = None) -> EmailConfig:
    """Load SMTP config from private YAML first, then override with environment values."""
    source = environ if env is None else env
    file_payload = _load_email_config_file(_default_email_config_path())
    merged_payload = _merge_email_config(file_payload, source)
    missing_vars = [key for key in REQUIRED_SMTP_ENV_VARS if not merged_payload.get(key, "").strip()]
    if missing_vars:
        missing_summary = "、".join(missing_vars)
        raise EmailConfigError(f"缺少 SMTP 配置：{missing_summary}")

    port_text = merged_payload["SMTP_PORT"].strip()
    try:
        port = int(port_text)
    except ValueError as exc:
        raise EmailConfigError(f"SMTP_PORT 不是合法整数：{port_text}") from exc

    timeout_text = merged_payload.get("SMTP_TIMEOUT_SECONDS", "20").strip() or "20"
    try:
        timeout_seconds = float(timeout_text)
    except ValueError as exc:
        raise EmailConfigError(f"SMTP_TIMEOUT_SECONDS 不是合法数字：{timeout_text}") from exc

    starttls_text = merged_payload.get("SMTP_USE_STARTTLS", "true").strip().lower()
    return EmailConfig(
        host=merged_payload["SMTP_HOST"].strip(),
        port=port,
        username=merged_payload["SMTP_USERNAME"].strip(),
        password=merged_payload["SMTP_PASSWORD"],
        from_address=merged_payload["SMTP_FROM"].strip(),
        to_address=merged_payload["SMTP_TO"].strip(),
        from_name=merged_payload.get("SMTP_FROM_NAME", "").strip(),
        timeout_seconds=timeout_seconds,
        use_starttls=starttls_text not in {"0", "false", "no"},
    )


def _utc_now_isoformat() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat()


def _default_email_config_path() -> Path:
    config_root = getenv("PAPER_ANALYSIS_HOME")
    if config_root:
        return Path(config_root) / DEFAULT_EMAIL_CONFIG_FILE_NAME
    return Path.home() / DEFAULT_EMAIL_CONFIG_DIR_NAME / DEFAULT_EMAIL_CONFIG_FILE_NAME


def _load_email_config_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except OSError as exc:
        raise EmailConfigError(f"无法读取邮件配置文件：{path}") from exc
    except yaml.YAMLError as exc:
        raise EmailConfigError(f"邮件配置文件不是合法 YAML：{path}") from exc

    smtp_payload = payload.get("smtp")
    if not isinstance(smtp_payload, dict):
        return {}
    normalized: dict[str, str] = {}
    field_mapping = {
        "host": "SMTP_HOST",
        "port": "SMTP_PORT",
        "username": "SMTP_USERNAME",
        "password": "SMTP_PASSWORD",
        "from_address": "SMTP_FROM",
        "to_address": "SMTP_TO",
        "from_name": "SMTP_FROM_NAME",
        "timeout_seconds": "SMTP_TIMEOUT_SECONDS",
        "use_starttls": "SMTP_USE_STARTTLS",
    }
    for yaml_key, env_key in field_mapping.items():
        value = smtp_payload.get(yaml_key)
        if value is None:
            continue
        normalized[env_key] = str(value)
    return normalized


def _merge_email_config(
    file_payload: Mapping[str, str],
    env: Mapping[str, str],
) -> dict[str, str]:
    merged = dict(file_payload)
    for key in (*REQUIRED_SMTP_ENV_VARS, *OPTIONAL_SMTP_ENV_VARS):
        env_value = env.get(key)
        if env_value is not None and env_value.strip():
            merged[key] = env_value
    return merged
