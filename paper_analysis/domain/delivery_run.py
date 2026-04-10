"""Domain models for arXiv subscription delivery runs."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from paper_analysis.domain.paper import Paper


@dataclass(slots=True)
class DeliveryStepState:
    """One delivery step state persisted in the run snapshot."""

    status: str
    summary: str
    updated_at: str
    details: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class DeliveryPaperRecord:
    """Stable paper payload shared by email, site, and run snapshots."""

    paper_id: str
    title: str
    abstract: str
    source: str
    venue: str
    authors: str
    organization: str
    published_at: str
    tags: str
    sampled_reason: str
    reasons: list[str]
    pdf_url: str
    project_url: str
    code_url: str
    openreview_url: str


@dataclass(slots=True)
class DeliveryRunSnapshot:
    """Structured arXiv subscription run snapshot."""

    run_id: str
    source: str
    subscription_date: str
    generated_at: str
    command_name: str
    fetched_count: int
    recommended_count: int
    recipient: str
    archive_dir: str
    latest_report_dir: str
    site_dir: str
    papers: list[DeliveryPaperRecord]
    steps: dict[str, DeliveryStepState]

    def to_dict(self) -> dict[str, object]:
        """Serialize the snapshot into JSON-safe nested dictionaries."""
        payload = asdict(self)
        payload["history_entry"] = self.history_entry()
        return payload

    def history_entry(self) -> dict[str, object]:
        """Build the site history entry for the current run."""
        return {
            "run_id": self.run_id,
            "subscription_date": self.subscription_date,
            "generated_at": self.generated_at,
            "fetched_count": self.fetched_count,
            "recommended_count": self.recommended_count,
            "recipient": self.recipient,
            "email_status": self.steps["email"].status,
            "site_status": self.steps["site"].status,
            "archive_dir": self.archive_dir,
        }


@dataclass(slots=True)
class DeliveryExecutionResult:
    """Final status returned to the CLI after one subscription delivery run."""

    status: str
    snapshot_path: str
    run_id: str
    email_status: str
    site_status: str
    summary: str = ""
    next_step: str = ""
    latest_page_path: str = ""
    index_page_path: str = ""


@dataclass(slots=True)
class SubscriptionDeliveryRequest:
    """Input bundle for one arXiv subscription delivery run."""

    papers: list[Paper]
    fetched_count: int
    subscription_date: str
    command_name: str
    latest_report_dir: Path
    report_artifacts: dict[str, Path]
    runs_root_dir: Path
    site_dir: Path


def utc_now_isoformat() -> str:
    """Return a stable UTC timestamp for persisted metadata."""
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat()
