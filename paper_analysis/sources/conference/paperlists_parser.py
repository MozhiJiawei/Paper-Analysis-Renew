"""Normalize raw paperlists JSON rows into shared paper domain objects."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from paper_analysis.cli.common import CliInputError, read_json_file
from paper_analysis.domain.paper import Paper

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(slots=True)
class PaperlistsRawRecord:
    """Raw conference record plus source metadata needed for normalization."""

    payload: dict[str, object]
    venue: str
    year: int
    source_path: Path


def load_raw_records(source_path: Path, venue: str, year: int) -> list[PaperlistsRawRecord]:
    """Load raw paperlists entries and attach venue/year source metadata."""
    raw = read_json_file(source_path)
    if not isinstance(raw, list):
        raise CliInputError(f"paperlists 输入必须是 JSON 数组：{source_path}")

    records: list[PaperlistsRawRecord] = []
    for item in raw:
        if not isinstance(item, dict):
            raise CliInputError(f"paperlists 记录必须是 JSON 对象：{source_path}")
        records.append(
            PaperlistsRawRecord(
                payload=item,
                venue=venue,
                year=year,
                source_path=source_path,
            )
        )
    return records


def filter_accepted_records(records: list[PaperlistsRawRecord]) -> list[PaperlistsRawRecord]:
    """Keep only accepted paperlists records based on the status field."""
    return [record for record in records if is_accepted_record(record.payload)]


def normalize_records(records: list[PaperlistsRawRecord]) -> list[Paper]:
    """Normalize a batch of raw paperlists rows into shared paper objects."""
    return [normalize_record(record) for record in records]


def normalize_record(record: PaperlistsRawRecord) -> Paper:
    """Normalize one paperlists row into the shared paper schema."""
    payload = record.payload
    title = _read_string(payload, "title")
    paper_id = _read_string(payload, "id") or _slugify(title)
    abstract = _read_string(payload, "abstract") or _read_string(payload, "tldr")
    authors = _read_people(payload)
    organizations = _dedupe_keep_order(_split_multi_value(payload.get("aff")))
    keywords = _split_multi_value(payload.get("keywords"))
    topic = _read_string(payload, "topic")
    primary_area = _read_string(payload, "primary_area")
    tags = _dedupe_keep_order(
        keywords + _split_multi_value(topic) + _split_multi_value(primary_area)
    )

    return Paper(
        paper_id=paper_id,
        title=title or f"{record.venue} {record.year} 未命名论文",
        abstract=abstract,
        source="conference",
        venue=f"{record.venue} {record.year}",
        authors=authors,
        tags=tags,
        organization=" | ".join(organizations),
        published_at=str(record.year),
        year=record.year,
        acceptance_status=_read_string(payload, "status") or "accepted",
        primary_area=primary_area,
        topic=topic,
        keywords=keywords,
        pdf_url=_first_non_empty(payload, "pdf", "proceeding"),
        project_url=_first_non_empty(payload, "project", "site", "oa"),
        code_url=_first_non_empty(payload, "github", "code"),
        openreview_url=_first_non_empty(payload, "openreview"),
        source_path=str(record.source_path),
        raw_payload={str(key): value for key, value in payload.items()},
    )


def is_accepted_record(payload: dict[str, object]) -> bool:
    """Heuristically classify whether a paperlists row represents acceptance."""
    status = _read_string(payload, "status")
    if not status:
        return True

    normalized = status.strip().lower()
    reject_tokens = ("reject", "withdraw", "desk", "submitted", "under review")
    if any(token in normalized for token in reject_tokens):
        return False

    accept_tokens = ("accept", "accepted", "oral", "spotlight", "poster", "main", "technical")
    return any(token in normalized for token in accept_tokens)


def _read_people(payload: dict[str, object]) -> list[str]:
    author_value = payload.get("author")
    if isinstance(author_value, str) and author_value.strip():
        return _split_multi_value(author_value)

    author_site_value = payload.get("author_site")
    if isinstance(author_site_value, str) and author_site_value.strip():
        return [part.strip() for part in author_site_value.split(",") if part.strip()]

    return []


def _read_string(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if isinstance(value, str):
        return value.strip()
    return ""


def _first_non_empty(payload: dict[str, object], *keys: str) -> str:
    for key in keys:
        value = _read_string(payload, key)
        if value:
            return value
    return ""


def _split_multi_value(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if not isinstance(value, str):
        return []

    normalized = value.replace("；", ";").replace("|", ";")
    separator = ";" if ";" in normalized else ","
    return [part.strip() for part in normalized.split(separator) if part.strip()]


def _dedupe_keep_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        normalized = item.strip()
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(normalized)
    return result


def _slugify(text: str) -> str:
    normalized = "".join(char.lower() if char.isalnum() else "-" for char in text.strip())
    normalized = normalized.strip("-")
    while "--" in normalized:
        normalized = normalized.replace("--", "-")
    return normalized or "paperlists-record"
