from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class Paper:
    """Normalized paper record used by both conference and arXiv flows."""

    paper_id: str
    title: str
    abstract: str
    source: str
    venue: str
    authors: list[str]
    tags: list[str]
    organization: str
    published_at: str
    score: float = 0.0
    reasons: list[str] = field(default_factory=list)
