from __future__ import annotations

import unittest
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import patch

from paper_analysis.domain.paper import Paper
from paper_analysis.services.arxiv_pipeline import ArxivPipeline
from paper_analysis.services.arxiv_recommender import ArxivRecommendationResult

if TYPE_CHECKING:
    from collections.abc import Callable


class FakeRecommender:
    algorithm_version = "fake"

    def recommend(
        self,
        candidates: list[Paper],
        *,
        limit: int | None = None,
        progress: Callable[[str], None] | None = None,
    ) -> ArxivRecommendationResult:
        if progress:
            progress(f"[test] recommender saw {len(candidates)} candidates")
        selected = candidates[: limit or len(candidates)]
        return ArxivRecommendationResult(papers=selected, algorithm_version="fake")


class ArxivPipelineProgressTests(unittest.TestCase):
    def test_pipeline_emits_progress_for_fixture_flow(self) -> None:
        progress_lines: list[str] = []

        with patch(
            "paper_analysis.services.arxiv_pipeline.load_papers",
            return_value=[
                Paper(
                    paper_id="p1",
                    title="Paper",
                    abstract="Abstract",
                    source="arxiv",
                    venue="arXiv",
                    authors=["Ada"],
                    tags=["cs.CL"],
                    organization="",
                    published_at="2026-05-24",
                )
            ],
        ):
            result = ArxivPipeline(recommender=cast(Any, FakeRecommender())).run_with_details(
                source_mode="fixture",
                progress=progress_lines.append,
            )

        self.assertEqual(1, result.fetched_count)
        self.assertIn("[arxiv] loading fixture papers...", progress_lines)
        self.assertIn("[arxiv] fetched 1 candidate papers", progress_lines)
        self.assertIn("[arxiv] loading preference profile...", progress_lines)
        self.assertIn("[test] recommender saw 1 candidates", progress_lines)


if __name__ == "__main__":
    unittest.main()
