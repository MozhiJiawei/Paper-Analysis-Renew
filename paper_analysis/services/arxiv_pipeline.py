"""arXiv paper loading pipeline for fixture and subscription-api modes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from paper_analysis.cli.common import CliInputError
from paper_analysis.services.arxiv_recommender import ArxivRecommender
from paper_analysis.shared.paths import FIXTURES_DIR
from paper_analysis.shared.sample_loader import load_papers, load_preferences
from paper_analysis.sources.arxiv.subscription_loader import load_subscription_papers

if TYPE_CHECKING:
    from pathlib import Path

    from paper_analysis.domain.paper import Paper
    from paper_analysis.domain.preference import PreferenceProfile


class ArxivPipeline:
    """arXiv input pipeline for fixture and subscription-api sources."""

    def __init__(self, recommender: ArxivRecommender | None = None) -> None:
        """Initialize the pipeline with an optional recommendation service."""
        self.recommender = recommender or ArxivRecommender()

    @dataclass(slots=True)
    class Result:
        """Structured pipeline result reused by report delivery flows."""

        papers: list[Paper]
        preferences: PreferenceProfile
        fetched_count: int

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
    ) -> Result:
        """Load papers and preferences, preserving pre-limit fetch counts."""
        if source_mode == "subscription-api":
            if not subscription_date:
                raise CliInputError("subscription-api 模式必须提供 --subscription-date")
            paper_records = load_subscription_papers(
                subscription_date=subscription_date,
                categories=categories,
                max_results=None if fetch_all else max_results,
            )
        else:
            paper_records = load_papers(
                papers_path or FIXTURES_DIR / "arxiv" / "sample_daily.json"
            )

        preferences = load_preferences(
            preferences_path or FIXTURES_DIR / "preferences" / "sample_preferences.json"
        )
        recommendation_limit = None if source_mode == "subscription-api" and fetch_all else preferences.limit
        selected_papers = self.recommender.recommend(
            paper_records,
            limit=recommendation_limit,
        ).papers
        return self.Result(
            papers=selected_papers,
            preferences=preferences,
            fetched_count=len(paper_records),
        )
