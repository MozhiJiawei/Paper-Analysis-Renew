from __future__ import annotations

import unittest

from paper_analysis.domain.paper import Paper
from paper_analysis.services.arxiv_recommender import ArxivRecommender


class ArxivRecommenderTests(unittest.TestCase):
    def test_recommender_keeps_llm_inference_acceleration_papers(self) -> None:
        recommender = ArxivRecommender()

        result = recommender.recommend(
            [
                Paper(
                    paper_id="p1",
                    title="Speculative Decoding for Efficient LLM Inference",
                    abstract="This LLM serving method improves latency with speculative decoding.",
                    source="arxiv",
                    venue="arXiv",
                    authors=["Ada"],
                    tags=["speculative decoding", "llm"],
                    organization="",
                    published_at="2026-04-08",
                )
            ]
        )

        self.assertEqual(1, len(result.papers))
        self.assertEqual("解码策略优化", result.papers[0].sampled_reason)

    def test_recommender_drops_clear_negative_benchmark_papers(self) -> None:
        recommender = ArxivRecommender()

        result = recommender.recommend(
            [
                Paper(
                    paper_id="p2",
                    title="A Benchmark for Visual Correspondence",
                    abstract="We introduce a new image matching benchmark and dataset.",
                    source="arxiv",
                    venue="arXiv",
                    authors=["Bob"],
                    tags=["benchmark", "dataset"],
                    organization="",
                    published_at="2026-04-08",
                ),
                Paper(
                    paper_id="p3",
                    title="Speech Emotion Recognition Survey",
                    abstract="We summarize datasets and evaluation settings for speech emotion recognition.",
                    source="arxiv",
                    venue="arXiv",
                    authors=["Carol"],
                    tags=["speech", "survey"],
                    organization="",
                    published_at="2026-04-08",
                ),
            ]
        )

        self.assertEqual(0, len(result.papers))


if __name__ == "__main__":
    unittest.main()
