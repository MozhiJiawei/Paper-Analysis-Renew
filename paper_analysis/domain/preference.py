from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class PreferenceProfile:
    """User preference model shared by all filtering pipelines."""

    preferred_topics: list[str]
    preferred_subtopics: list[str] = field(default_factory=list)
    preferred_organizations: list[str] = field(default_factory=list)
    excluded_topics: list[str] = field(default_factory=list)
    min_score: float = 1.0
    limit: int = 5
