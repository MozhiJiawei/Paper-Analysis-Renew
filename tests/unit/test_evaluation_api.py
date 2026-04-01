from __future__ import annotations

import unittest

from paper_analysis.api.evaluation_predictor import EvaluationPredictor
from paper_analysis.api.evaluation_protocol import (
    EvaluationPaper,
    EvaluationPrediction,
    EvaluationProtocolError,
)
from paper_analysis.evaluation.ab_protocol import BinaryRoutePrediction
from paper_analysis.evaluation.routes.base import BaseBinaryRoute


class _FakePositiveRoute(BaseBinaryRoute):
    def __init__(self) -> None:
        super().__init__(
            route_name="fake",
            algorithm_version="fake-v1",
            capability_type="test",
            implementation_status="ready",
        )

    def predict_many(self, papers: list[EvaluationPaper]) -> list[BinaryRoutePrediction]:
        return [
            BinaryRoutePrediction(
                paper_id=paper.paper_id,
                prediction=EvaluationPrediction(
                    primary_research_object="LLM",
                    preference_labels=["解码策略优化"],
                    negative_tier="positive",
                    evidence_spans={"general": [paper.title], "解码策略优化": [paper.title]},
                    notes="fake route",
                ),
            )
            for paper in papers
        ]


class EvaluationApiUnitTests(unittest.TestCase):
    def test_predictor_returns_single_positive_label_for_speculative_decoding(self) -> None:
        paper = EvaluationPaper(
            paper_id="paper-1",
            title="Speculative Decoding for Efficient LLM Inference",
            abstract="This speculative decoding method improves draft acceptance rate.",
            authors=["Alice"],
            venue="ICLR 2026",
            year=2026,
            source="conference",
            source_path="tests.json",
            keywords=["speculative decoding"],
        )

        prediction = EvaluationPredictor(route=_FakePositiveRoute()).predict(paper)

        self.assertEqual("positive", prediction.negative_tier)
        self.assertEqual(["解码策略优化"], prediction.preference_labels)
        self.assertEqual("LLM", prediction.primary_research_object)

    def test_negative_prediction_clears_preference_labels(self) -> None:
        prediction = EvaluationPrediction(
            primary_research_object="评测 / Benchmark / 数据集",
            preference_labels=[],
            negative_tier="negative",
            evidence_spans={"negative": ["benchmark only"]},
            notes="negative",
        )

        self.assertEqual([], prediction.preference_labels)

    def test_positive_prediction_rejects_multiple_labels(self) -> None:
        with self.assertRaises(EvaluationProtocolError):
            EvaluationPrediction(
                primary_research_object="LLM",
                preference_labels=["解码策略优化", "系统与调度优化"],
                negative_tier="positive",
                evidence_spans={"general": ["bad"]},
            )


if __name__ == "__main__":
    unittest.main()
