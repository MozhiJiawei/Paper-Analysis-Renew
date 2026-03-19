from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from paper_analysis.domain.paper import Paper
from paper_analysis.domain.preference import PreferenceProfile
from paper_analysis.services.conference_sampler import sample_papers
from paper_analysis.services.preference_ranker import PreferenceRanker
from paper_analysis.sources.conference.paperlists_loader import (
    PAPERLISTS_ROOT,
    resolve_paperlists_target,
)
from paper_analysis.sources.conference.paperlists_parser import (
    filter_accepted_records,
    load_raw_records,
    normalize_records,
)
from paper_analysis.shared.paths import FIXTURES_DIR
from paper_analysis.shared.sample_loader import load_papers, load_preferences


@dataclass(slots=True)
class ConferencePipelineResult:
    papers: list[Paper]
    preferences: PreferenceProfile
    source_mode: str
    source_path: Path
    candidate_count: int
    selected_count: int
    venue: str = ""
    year: int | None = None
    seed: int | None = None


class ConferencePipeline:
    """Conference paper filtering pipeline."""

    def __init__(self, ranker: PreferenceRanker | None = None) -> None:
        self.ranker = ranker or PreferenceRanker()

    def run(
        self,
        papers_path: Path | None = None,
        preferences_path: Path | None = None,
        *,
        venue: str | None = None,
        year: int | None = None,
        paperlists_root: Path | None = None,
        seed: int = 42,
    ) -> ConferencePipelineResult:
        preferences = load_preferences(
            preferences_path or FIXTURES_DIR / "preferences" / "sample_preferences.json"
        )

        if venue and year:
            target = resolve_paperlists_target(
                venue,
                year,
                paperlists_root or PAPERLISTS_ROOT,
            )
            raw_records = load_raw_records(target.json_path, target.venue_name, target.year)
            accepted_records = filter_accepted_records(raw_records)
            normalized = normalize_records(accepted_records)
            sampled = sample_papers(normalized, seed=seed)
            return ConferencePipelineResult(
                papers=sampled,
                preferences=preferences,
                source_mode="paperlists",
                source_path=target.json_path,
                candidate_count=len(normalized),
                selected_count=len(sampled),
                venue=target.venue_name,
                year=target.year,
                seed=seed,
            )

        paper_records = load_papers(
            papers_path or FIXTURES_DIR / "conference" / "sample_papers.json"
        )
        ranked = self.ranker.rank(paper_records, preferences)
        return ConferencePipelineResult(
            papers=ranked,
            preferences=preferences,
            source_mode="sample",
            source_path=papers_path or FIXTURES_DIR / "conference" / "sample_papers.json",
            candidate_count=len(ranked),
            selected_count=len(ranked),
        )
