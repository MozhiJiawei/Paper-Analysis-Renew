from __future__ import annotations

from pathlib import Path

from paper_analysis.cli.common import CliInputError
from paper_analysis.domain.paper import Paper
from paper_analysis.domain.preference import PreferenceProfile
from paper_analysis.shared.paths import FIXTURES_DIR
from paper_analysis.shared.sample_loader import load_papers, load_preferences
from paper_analysis.sources.arxiv.subscription_loader import load_subscription_papers


class ArxivPipeline:
    """arXiv input pipeline for fixture and subscription-api sources."""

    def run(
        self,
        papers_path: Path | None = None,
        preferences_path: Path | None = None,
        *,
        source_mode: str = "fixture",
        subscription_date: str | None = None,
        categories: list[str] | None = None,
        max_results: int = 10,
    ) -> tuple[list[Paper], PreferenceProfile]:
        if source_mode == "subscription-api":
            if not subscription_date:
                raise CliInputError("subscription-api 模式必须提供 --subscription-date")
            paper_records = load_subscription_papers(
                subscription_date=subscription_date,
                categories=categories,
                max_results=max_results,
            )
        else:
            paper_records = load_papers(
                papers_path or FIXTURES_DIR / "arxiv" / "sample_daily.json"
            )

        preferences = load_preferences(
            preferences_path or FIXTURES_DIR / "preferences" / "sample_preferences.json"
        )
        return paper_records[: preferences.limit], preferences
