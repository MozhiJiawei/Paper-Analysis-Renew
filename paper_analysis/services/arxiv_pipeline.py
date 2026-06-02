"""arXiv paper loading pipeline for fixture, API, and email subscription modes."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING

from paper_analysis.cli.common import CliInputError
from paper_analysis.services.arxiv_recommender import ArxivRecommender
from paper_analysis.shared.paths import FIXTURES_DIR
from paper_analysis.shared.sample_loader import load_papers, load_preferences
from paper_analysis.sources.arxiv.affiliation_enricher import (
    enrich_selected_arxiv_papers_with_affiliations,
)
from paper_analysis.sources.arxiv.email_loader import load_subscription_email_papers
from paper_analysis.sources.arxiv.subscription_loader import load_subscription_papers

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from pathlib import Path

    from paper_analysis.domain.paper import Paper
    from paper_analysis.domain.preference import PreferenceProfile


class ArxivPipeline:
    """arXiv input pipeline for fixture, API, and email subscription sources."""

    def __init__(self, recommender: ArxivRecommender | None = None) -> None:
        """Initialize the pipeline with an optional recommendation service."""
        self.recommender = recommender or ArxivRecommender()

    @dataclass(slots=True)
    class Result:
        """Structured pipeline result reused by report delivery flows."""

        papers: list[Paper]
        preferences: PreferenceProfile
        fetched_count: int
        candidate_papers: list[Paper]

    def run(
        self,
        papers_path: Path | None = None,
        preferences_path: Path | None = None,
        *,
        source_mode: str = "fixture",
        subscription_date: str | None = None,
        categories: list[str] | None = None,
        max_results: int = 10,
        fetch_all: bool = False,
        progress: Callable[[str], None] | None = None,
    ) -> tuple[list[Paper], PreferenceProfile]:
        """Load papers and preferences, then cap the result count by user limit."""
        result = self.run_with_details(
            papers_path,
            preferences_path,
            source_mode=source_mode,
            subscription_date=subscription_date,
            categories=categories,
            max_results=max_results,
            fetch_all=fetch_all,
            progress=progress,
        )
        return result.papers, result.preferences

    def run_with_details(
        self,
        papers_path: Path | None = None,
        preferences_path: Path | None = None,
        *,
        source_mode: str = "fixture",
        subscription_date: str | None = None,
        categories: list[str] | None = None,
        max_results: int = 10,
        fetch_all: bool = False,
        progress: Callable[[str], None] | None = None,
    ) -> Result:
        """Load papers and preferences, preserving pre-limit fetch counts."""
        paper_records = self._load_records(
            papers_path=papers_path,
            source_mode=source_mode,
            subscription_date=subscription_date,
            categories=categories,
            max_results=max_results,
            fetch_all=fetch_all,
            progress=progress,
        )

        _emit_progress(progress, f"[arxiv] fetched {len(paper_records)} candidate papers")
        _emit_progress(progress, "[arxiv] loading preference profile...")
        preferences = load_preferences(
            preferences_path or FIXTURES_DIR / "preferences" / "sample_preferences.json"
        )
        recommendation_limit = (
            None
            if source_mode in {"subscription-api", "subscription-email"} and fetch_all
            else preferences.limit
        )
        selected_papers = self.recommender.recommend(
            paper_records,
            limit=recommendation_limit,
            progress=progress,
        ).papers
        if source_mode in {"subscription-api", "subscription-email"}:
            _emit_progress(
                progress,
                f"[arxiv] enriching affiliations for {len(selected_papers)} selected papers...",
            )
            enrichment_results = enrich_selected_arxiv_papers_with_affiliations(selected_papers)
            _emit_progress(
                progress,
                f"[arxiv] affiliation enrichment done: "
                f"{_format_enrichment_statuses(enrichment_results)}",
            )
        return self.Result(
            papers=selected_papers,
            preferences=preferences,
            fetched_count=len(paper_records),
            candidate_papers=paper_records,
        )

    def _load_records(
        self,
        *,
        papers_path: Path | None,
        source_mode: str,
        subscription_date: str | None,
        categories: list[str] | None,
        max_results: int,
        fetch_all: bool,
        progress: Callable[[str], None] | None,
    ) -> list[Paper]:
        """Load candidate papers from the requested arXiv source."""
        if source_mode == "subscription-api":
            if not subscription_date:
                raise CliInputError("subscription-api 模式必须提供 --subscription-date")
            _emit_progress(
                progress,
                f"[arxiv] loading subscription API papers date={subscription_date}...",
            )
            return load_subscription_papers(
                subscription_date=subscription_date,
                categories=categories,
                max_results=None if fetch_all else max_results,
            )
        if source_mode == "subscription-email":
            if not subscription_date:
                raise CliInputError("subscription-email 模式必须提供 --subscription-date")
            _emit_progress(
                progress,
                f"[arxiv] loading Gmail subscription papers date={subscription_date}...",
            )
            return load_subscription_email_papers(
                subscription_date=subscription_date,
                categories=categories,
                max_results=None if fetch_all else max_results,
            )
        _emit_progress(progress, "[arxiv] loading fixture papers...")
        return load_papers(papers_path or FIXTURES_DIR / "arxiv" / "sample_daily.json")


def _emit_progress(progress: Callable[[str], None] | None, line: str) -> None:
    if progress:
        progress(line)


def _format_enrichment_statuses(results: Sequence[object]) -> str:
    statuses = Counter(str(getattr(result, "status", "unknown")) for result in results)
    return "，".join(f"{status}={count}" for status, count in sorted(statuses.items())) or "none"
