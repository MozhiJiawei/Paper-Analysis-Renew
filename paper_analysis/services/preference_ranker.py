"""Preference ranking service shared by conference and arXiv pipelines."""

from __future__ import annotations

from typing import TYPE_CHECKING

from paper_analysis.domain.filtering import rank_papers

if TYPE_CHECKING:
    from paper_analysis.domain.paper import Paper
    from paper_analysis.domain.preference import PreferenceProfile


class PreferenceRanker:
    """Shared preference ranking service for both source pipelines."""

    def rank(self, candidates: list[Paper], preferences: PreferenceProfile) -> list[Paper]:
        """Rank candidate papers against the provided preference profile."""
        return rank_papers(candidates, preferences)
