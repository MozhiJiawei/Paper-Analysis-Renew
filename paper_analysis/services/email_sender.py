"""SMTP-backed standalone email delivery service."""

from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid
from typing import TYPE_CHECKING, Protocol, Self, cast

from paper_analysis.domain.email_delivery import (
    EmailAuthenticationError,
    EmailConfig,
    EmailConnectionError,
    EmailDeliveryError,
    EmailMessagePayload,
    EmailSendError,
    EmailSendResult,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

_DEFAULT_SMTP_FACTORY = cast("Callable[..., SMTPClientProtocol]", smtplib.SMTP)


class SMTPClientProtocol(Protocol):  # noqa: D101
    def __enter__(self) -> Self: ...  # noqa: D105

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None: ...  # noqa: D105

    def ehlo(self) -> object: ...  # noqa: D102

    def starttls(self, *, context: ssl.SSLContext) -> object: ...  # noqa: D102

    def login(self, username: str, password: str) -> object: ...  # noqa: D102

    def send_message(self, message: EmailMessage) -> object: ...  # noqa: D102


def build_email_message(config: EmailConfig, payload: EmailMessagePayload) -> EmailMessage:
    """Build a UTF-8 MIME email message from structured payload data."""
    message = EmailMessage()
    message["Subject"] = payload.subject
    message["From"] = formataddr((config.from_name, config.from_address))
    message["To"] = payload.recipient
    message["Date"] = formatdate(localtime=False)
    message["Message-ID"] = make_msgid()

    for key, value in payload.metadata.items():
        message[f"X-Paper-Analysis-{key}"] = value

    message.set_content(payload.text_body, subtype="plain", charset="utf-8")
    if payload.html_body:
        message.add_alternative(payload.html_body, subtype="html", charset="utf-8")
    return message


def send_email_message(
    config: EmailConfig,
    payload: EmailMessagePayload,
    *,
    smtp_factory: Callable[..., SMTPClientProtocol] = _DEFAULT_SMTP_FACTORY,
    eml_output_path: Path | None = None,
) -> EmailSendResult:
    """Send one message through SMTP and return a structured result."""
    message = build_email_message(config, payload)
    eml_path = _write_eml_snapshot(message, eml_output_path)

    try:
        with smtp_factory(config.host, config.port, timeout=config.timeout_seconds) as client:
            client.ehlo()
            if config.use_starttls:
                client.starttls(context=ssl.create_default_context())
                client.ehlo()
            client.login(config.username, config.password)
            client.send_message(message)
    except smtplib.SMTPAuthenticationError:
        error: EmailDeliveryError = EmailAuthenticationError(
            "SMTP 认证失败，请检查 QQ 邮箱授权码或用户名。"
        )
        return EmailSendResult.failure(recipient=payload.recipient, error=error, eml_path=eml_path)
    except smtplib.SMTPRecipientsRefused as exc:
        refused_recipients = "、".join(exc.recipients.keys()) or payload.recipient
        error = EmailSendError(f"SMTP 拒绝收件人：{refused_recipients}")
        return EmailSendResult.failure(recipient=payload.recipient, error=error, eml_path=eml_path)
    except (
        TimeoutError,
        OSError,
        smtplib.SMTPConnectError,
        smtplib.SMTPServerDisconnected,
    ) as exc:
        error = EmailConnectionError(f"SMTP 连接失败：{exc}")
        return EmailSendResult.failure(recipient=payload.recipient, error=error, eml_path=eml_path)
    except smtplib.SMTPException as exc:
        error = EmailSendError(f"SMTP 发送失败：{exc}")
        return EmailSendResult.failure(recipient=payload.recipient, error=error, eml_path=eml_path)

    message_id = str(message["Message-ID"] or "")
    return EmailSendResult.success(
        recipient=payload.recipient,
        message_id=message_id,
        eml_path=eml_path,
    )


def _write_eml_snapshot(message: EmailMessage, output_path: Path | None) -> str:
    if output_path is None:
        return ""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(message.as_bytes())
    return str(output_path)
