"""Recommendation service for arXiv subscription papers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from paper_analysis.api.evaluation_predictor import EvaluationPredictor
from paper_analysis.api.evaluation_protocol import EvaluationPaper

if TYPE_CHECKING:
    from paper_analysis.domain.paper import Paper

YEAR_PREFIX_LENGTH = 4


@dataclass(slots=True)
class ArxivRecommendationResult:
    """Structured recommendation result for one subscription batch."""

    papers: list[Paper]
    algorithm_version: str


class ArxivRecommender:
    """Filter arXiv papers down to inference-acceleration recommendations."""

    def __init__(self, predictor: EvaluationPredictor | None = None) -> None:
        """Store the reusable inference-acceleration predictor."""
        self.predictor = predictor or EvaluationPredictor()

    def recommend(self, candidates: list[Paper], *, limit: int | None = None) -> ArxivRecommendationResult:
        """Keep only positive inference-acceleration papers and annotate their sublabels."""
        selected: list[Paper] = []
        for paper in candidates:
            evaluation_paper = _to_evaluation_paper(paper)
            prediction = self.predictor.predict(evaluation_paper)
            if prediction.negative_tier != "positive":
                continue
            sublabel = prediction.preference_labels[0]
            paper.sampled_reason = sublabel
            paper.reasons = [
                f"推理加速子类：{sublabel}",
                prediction.notes,
                *_flatten_evidence_spans(prediction.evidence_spans),
            ]
            paper.score = 1.0
            selected.append(paper)

        selected.sort(key=lambda item: (item.sampled_reason, item.title))
        if limit is not None:
            selected = selected[:limit]
        return ArxivRecommendationResult(
            papers=selected,
            algorithm_version=self.predictor.algorithm_version,
        )


def _to_evaluation_paper(paper: Paper) -> EvaluationPaper:
    return EvaluationPaper(
        paper_id=paper.paper_id,
        title=paper.title,
        abstract=paper.abstract or paper.title,
        authors=paper.authors,
        venue=paper.venue or "arXiv",
        year=_extract_year(paper.published_at),
        source=paper.source or "arxiv",
        source_path=paper.source_path or paper.pdf_url or paper.paper_id,
        keywords=paper.tags,
    )


def _extract_year(published_at: str) -> int:
    if len(published_at) >= YEAR_PREFIX_LENGTH and published_at[:YEAR_PREFIX_LENGTH].isdigit():
        return int(published_at[:YEAR_PREFIX_LENGTH])
    return 1970


def _flatten_evidence_spans(evidence_spans: dict[str, list[str]]) -> list[str]:
    flattened: list[str] = []
    for label, spans in evidence_spans.items():
        if label == "general":
            continue
        flattened.extend(f"{label} 证据：{span}" for span in spans)
    return flattened

