from __future__ import annotations

from pathlib import Path

from paper_analysis.domain.paper import Paper
from paper_analysis.domain.preference import PreferenceProfile
from paper_analysis.services.preference_ranker import PreferenceRanker
from paper_analysis.shared.paths import FIXTURES_DIR
from paper_analysis.shared.sample_loader import load_papers, load_preferences


class ConferencePipeline:
    """Conference paper filtering pipeline."""

    def __init__(self, ranker: PreferenceRanker | None = None) -> None:
        self.ranker = ranker or PreferenceRanker()

    def run(
        self,
        papers_path: Path | None = None,
        preferences_path: Path | None = None,
    ) -> tuple[list[Paper], PreferenceProfile]:
        paper_records = load_papers(
            papers_path or FIXTURES_DIR / "conference" / "sample_papers.json"
        )
        preferences = load_preferences(
            preferences_path or FIXTURES_DIR / "preferences" / "sample_preferences.json"
        )
        return self.ranker.rank(paper_records, preferences), preferences
