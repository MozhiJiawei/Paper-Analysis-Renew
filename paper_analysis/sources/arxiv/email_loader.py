"""Gmail-backed arXiv subscription digest loader."""

from __future__ import annotations

import email
import imaplib
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.header import decode_header, make_header
from email.utils import parsedate_to_datetime
from os import environ, getenv
from pathlib import Path
from typing import TYPE_CHECKING

import yaml
from paper_analysis.cli.common import CliInputError
from paper_analysis.domain.paper import Paper
from paper_analysis.sources.arxiv.subscription_loader import parse_subscription_date

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from email.message import Message


DEFAULT_CONFIG_DIR_NAME = ".paper-analysis"
DEFAULT_GMAIL_CONFIG_FILE_NAME = "gmail.yaml"
DEFAULT_IMAP_HOST = "imap.gmail.com"
DEFAULT_IMAP_PORT = 993
DEFAULT_MAILBOX = "INBOX"
DEFAULT_SENDER_CONTAINS = "send mail ONLY to cs"
DEFAULT_SUBJECT_CONTAINS = "cs daily Subj-class mailing"
EMAIL_LOOKAHEAD_DAYS = 10


@dataclass(slots=True)
class GmailSubscriptionConfig:
    """IMAP settings and arXiv digest matching rules."""

    imap_host: str
    imap_port: int
    username: str
    app_password: str
    mailbox: str = DEFAULT_MAILBOX
    sender_contains: str = DEFAULT_SENDER_CONTAINS
    subject_contains: str = DEFAULT_SUBJECT_CONTAINS


@dataclass(slots=True)
class DigestHeader:
    """Small message header record used before fetching large digest bodies."""

    message_id: bytes
    date: datetime | None
    sender: str
    subject: str


def load_subscription_email_papers(
    subscription_date: str,
    categories: list[str] | None = None,
    max_results: int | None = 10,
    config: GmailSubscriptionConfig | None = None,
    imap_factory: Callable[..., imaplib.IMAP4_SSL] = imaplib.IMAP4_SSL,
) -> list[Paper]:
    """Load arXiv papers from Gmail subscription digests for one paper date."""
    if max_results is not None and max_results <= 0:
        raise CliInputError("--max-results 必须大于 0")

    target_date = parse_subscription_date(subscription_date)
    email_config = config or load_gmail_subscription_config()
    selected_categories = set(categories or [])

    try:
        with imap_factory(email_config.imap_host, email_config.imap_port) as client:
            client.login(email_config.username, email_config.app_password)
            status, _data = client.select(email_config.mailbox, readonly=True)
            if status != "OK":
                raise CliInputError(f"无法选择 Gmail 邮箱文件夹：{email_config.mailbox}")
            candidate_headers = _search_digest_headers(client, email_config, target_date)
            papers: list[Paper] = []
            for header in candidate_headers:
                raw_message = _fetch_full_message(client, header.message_id)
                text_body = extract_text_body(email.message_from_bytes(raw_message))
                digest_papers = parse_arxiv_digest_text(text_body)
                matched = [
                    paper
                    for paper in digest_papers
                    if paper.published_at == target_date.strftime("%Y-%m-%d")
                    and (not selected_categories or selected_categories.intersection(paper.tags))
                ]
                if matched:
                    papers.extend(_with_source_metadata(matched, header))
                if max_results is not None and len(papers) >= max_results:
                    break
    except imaplib.IMAP4.error as exc:
        raise CliInputError(f"Gmail IMAP 访问失败：{exc}") from exc
    except OSError as exc:
        raise CliInputError(f"Gmail IMAP 连接失败：{exc}") from exc

    if not papers:
        raise CliInputError(
            f"没有在 Gmail arXiv 订阅邮件中找到论文日期 {target_date.strftime('%Y-%m-%d')} 的记录"
        )
    return papers if max_results is None else papers[:max_results]


def load_gmail_subscription_config(
    env: Mapping[str, str] | None = None,
    config_path: Path | None = None,
) -> GmailSubscriptionConfig:
    """Load Gmail IMAP and arXiv digest matching settings."""
    source = environ if env is None else env
    payload = _load_gmail_config_file(config_path or _default_gmail_config_path())
    gmail_payload = payload.get("gmail", {})
    arxiv_payload = payload.get("arxiv_subscription_email", {})

    username = _read_setting(source, "GMAIL_USERNAME", gmail_payload, "username")
    app_password = _read_setting(source, "GMAIL_APP_PASSWORD", gmail_payload, "app_password")
    if not username or not app_password:
        raise CliInputError("缺少 Gmail IMAP 配置：GMAIL_USERNAME / GMAIL_APP_PASSWORD")

    return GmailSubscriptionConfig(
        imap_host=_read_setting(source, "GMAIL_IMAP_HOST", gmail_payload, "imap_host") or DEFAULT_IMAP_HOST,
        imap_port=int(_read_setting(source, "GMAIL_IMAP_PORT", gmail_payload, "imap_port") or DEFAULT_IMAP_PORT),
        username=username,
        app_password=app_password,
        mailbox=_read_setting(source, "GMAIL_MAILBOX", gmail_payload, "mailbox") or DEFAULT_MAILBOX,
        sender_contains=(
            _read_setting(source, "ARXIV_EMAIL_SENDER", arxiv_payload, "sender_contains")
            or DEFAULT_SENDER_CONTAINS
        ),
        subject_contains=(
            _read_setting(source, "ARXIV_EMAIL_SUBJECT_PREFIX", arxiv_payload, "subject_contains")
            or DEFAULT_SUBJECT_CONTAINS
        ),
    )


def parse_arxiv_digest_text(text_body: str) -> list[Paper]:
    """Parse one complete arXiv digest text body into normalized paper records."""
    blocks = re.split(r"(?m)^\\\\\s*\n(?=arXiv:)", text_body)
    papers: list[Paper] = []
    seen_ids: set[str] = set()
    for block in blocks:
        paper = _parse_digest_block(block)
        if paper is None or paper.paper_id in seen_ids:
            continue
        seen_ids.add(paper.paper_id)
        papers.append(paper)
    return papers


def extract_text_body(message: Message) -> str:
    """Extract full text/plain body from a MIME email, falling back to HTML text."""
    if message.is_multipart():
        text_parts: list[str] = []
        html_fallbacks: list[str] = []
        for part in message.walk():
            if part.get_content_disposition() == "attachment":
                continue
            payload = _decode_part_payload(part)
            if not payload:
                continue
            if part.get_content_type() == "text/plain":
                text_parts.append(payload)
            elif part.get_content_type() == "text/html":
                html_fallbacks.append(_strip_html(payload))
        return "\n".join(text_parts).strip() or "\n".join(html_fallbacks).strip()
    return _decode_part_payload(message)


def _parse_digest_block(block: str) -> Paper | None:
    if "arXiv:" not in block or "Title:" not in block:
        return None
    paper_id_match = re.search(r"(?m)^arXiv:([0-9.]+)(?:v\d+)?", block)
    title_match = re.search(r"(?ms)^Title:\s*(.*?)(?=^Authors?:|^Comments?:|^Subjects?:|^Categories?:|^\\\\|\Z)", block)
    authors_match = re.search(r"(?ms)^Authors?:\s*(.*?)(?=^Comments?:|^Subjects?:|^Categories?:|^\\\\|\Z)", block)
    categories_match = re.search(r"(?ms)^(?:Subjects?|Categories):\s*(.*?)(?=^Comments?:|^\\\\|\Z)", block)
    date_match = re.search(r"(?m)^Date:\s*(.*?GMT)", block)
    if paper_id_match is None or title_match is None or authors_match is None or categories_match is None:
        return None

    paper_id = paper_id_match.group(1).strip()
    categories = _clean_digest_field(categories_match.group(1)).split()
    published_at = _format_digest_date(date_match.group(1)) if date_match else ""
    return Paper(
        paper_id=paper_id,
        title=_clean_digest_field(title_match.group(1)),
        abstract=_extract_abstract(block),
        source="arxiv",
        venue="arXiv",
        authors=_split_authors(_clean_digest_field(authors_match.group(1))),
        tags=categories,
        organization="",
        published_at=published_at,
        primary_area=categories[0] if categories else "",
        keywords=categories,
        pdf_url=f"https://arxiv.org/pdf/{paper_id}",
        source_path="gmail-arxiv-digest",
        raw_payload={
            "categories": categories,
            "email_date": _clean_digest_field(date_match.group(1)) if date_match else "",
        },
    )


def _search_digest_headers(
    client: imaplib.IMAP4_SSL,
    config: GmailSubscriptionConfig,
    target_date: datetime,
) -> list[DigestHeader]:
    since_date = target_date.strftime("%d-%b-%Y")
    before_date = (target_date + timedelta(days=EMAIL_LOOKAHEAD_DAYS)).strftime("%d-%b-%Y")
    status, data = client.search(
        None,
        "SINCE",
        since_date,
        "BEFORE",
        before_date,
        "SUBJECT",
        f'"{config.subject_contains}"',
    )
    if status != "OK" or not data or not data[0]:
        return []
    message_ids = data[0].split()
    headers: list[DigestHeader] = []
    for message_id in message_ids:
        status, header_data = client.fetch(message_id, "(BODY.PEEK[HEADER.FIELDS (DATE FROM SUBJECT)])")
        if status != "OK" or not header_data:
            continue
        raw_header = next(
            (item[1] for item in header_data if isinstance(item, tuple) and isinstance(item[1], bytes)),
            b"",
        )
        message = email.message_from_bytes(raw_header)
        sender = _decode_mime_header(message.get("From", ""))
        subject = _decode_mime_header(message.get("Subject", ""))
        if config.sender_contains not in sender or config.subject_contains not in subject:
            continue
        headers.append(
            DigestHeader(
                message_id=message_id,
                date=_parse_message_date(message.get("Date", "")),
                sender=sender,
                subject=subject,
            )
        )
    return headers


def _fetch_full_message(client: imaplib.IMAP4_SSL, message_id: bytes) -> bytes:
    status, data = client.fetch(message_id.decode("ascii"), "(RFC822)")
    if status != "OK" or not data:
        raise CliInputError(f"无法获取 Gmail 完整邮件：{message_id!r}")
    raw_message = next(
        (item[1] for item in data if isinstance(item, tuple) and isinstance(item[1], bytes)),
        b"",
    )
    if not raw_message:
        raise CliInputError(f"Gmail 完整邮件为空：{message_id!r}")
    return raw_message


def _with_source_metadata(papers: list[Paper], header: DigestHeader) -> list[Paper]:
    label = _source_message_label(header)
    for paper in papers:
        paper.raw_payload["source_email"] = label
        paper.raw_payload["source_email_subject"] = header.subject
    return papers


def _source_message_label(header: DigestHeader) -> str:
    if header.date is None:
        return header.subject
    return f"{header.date.strftime('%Y-%m-%d %H:%M:%S %Z')} | {header.subject}"


def _extract_abstract(block: str) -> str:
    abstract_match = re.search(
        r"(?ms)^(?:Subjects?|Categories):\s*.*?\n\s*\\\\\s*\n\s*(.*?)(?=^\\\\\s*\(|^------------------------------------------------------------------------------|\Z)",
        block,
    )
    if not abstract_match:
        return ""
    lines = abstract_match.group(1).strip().splitlines()
    filtered_lines = [
        line
        for line in lines
        if not line.startswith("\\\\")
        and not line.startswith("http://")
        and not line.startswith("https://")
        and not line.startswith("arXiv:")
    ]
    return _clean_digest_field("\n".join(filtered_lines))


def _split_authors(value: str) -> list[str]:
    normalized = value.replace(" and ", ", ")
    return [author.strip() for author in normalized.split(",") if author.strip()]


def _format_digest_date(raw_value: str) -> str:
    try:
        return (
            datetime.strptime(_clean_digest_field(raw_value), "%a, %d %b %Y %H:%M:%S GMT")
            .replace(tzinfo=UTC)
            .strftime("%Y-%m-%d")
        )
    except ValueError:
        return ""


def _parse_message_date(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _decode_part_payload(part: Message) -> str:
    payload = part.get_payload(decode=True)
    if payload is None:
        raw_payload = part.get_payload()
        return raw_payload if isinstance(raw_payload, str) else ""
    if not isinstance(payload, bytes):
        return ""
    charset = part.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="replace")
    except LookupError:
        return payload.decode("utf-8", errors="replace")


def _decode_mime_header(value: str) -> str:
    return str(make_header(decode_header(value))) if value else ""


def _strip_html(value: str) -> str:
    without_tags = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", without_tags).strip()


def _clean_digest_field(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _load_gmail_config_file(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except OSError as exc:
        raise CliInputError(f"无法读取 Gmail 配置文件：{path}") from exc
    except yaml.YAMLError as exc:
        raise CliInputError(f"Gmail 配置文件不是合法 YAML：{path}") from exc
    return payload if isinstance(payload, dict) else {}


def _read_setting(
    env: Mapping[str, str],
    env_key: str,
    file_payload: Mapping[str, object],
    yaml_key: str,
) -> str:
    env_value = env.get(env_key)
    if env_value is not None and env_value.strip():
        return env_value.strip()
    file_value = file_payload.get(yaml_key)
    return "" if file_value is None else str(file_value).strip()


def _default_gmail_config_path() -> Path:
    config_root = getenv("PAPER_ANALYSIS_HOME")
    if config_root:
        return Path(config_root) / DEFAULT_GMAIL_CONFIG_FILE_NAME
    return Path.home() / DEFAULT_CONFIG_DIR_NAME / DEFAULT_GMAIL_CONFIG_FILE_NAME
