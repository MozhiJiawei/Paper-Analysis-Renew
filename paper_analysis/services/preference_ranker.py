from __future__ import annotations

from paper_analysis.domain.filtering import rank_papers
from paper_analysis.domain.paper import Paper
from paper_analysis.domain.preference import PreferenceProfile


class PreferenceRanker:
    """Shared preference ranking service for both source pipelines."""

    def rank(self, candidates: list[Paper], preferences: PreferenceProfile) -> list[Paper]:
        return rank_papers(candidates, preferences)
