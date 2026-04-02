from __future__ import annotations

import unittest

from paper_analysis.api.evaluation_predictor import EvaluationPredictor
from paper_analysis.api.evaluation_protocol import (
    EvaluationPaper,
    EvaluationPrediction,
    EvaluationProtocolError,
)


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

        prediction = EvaluationPredictor().predict(paper)

        self.assertEqual("positive", prediction.negative_tier)
        self.assertEqual(["解码策略优化"], prediction.preference_labels)
        self.assertEqual("LLM", prediction.primary_research_object)

    def test_predictor_does_not_emit_removed_structure_label(self) -> None:
        paper = EvaluationPaper(
            paper_id="paper-structure-only",
            title="Selective Head Reconfiguration for Transformer Inference",
            abstract="We study selective head and runtime reconfiguration during inference.",
            authors=["Alice"],
            venue="ICLR 2026",
            year=2026,
            source="conference",
            source_path="tests.json",
            keywords=["selective head", "runtime reconfiguration"],
        )

        prediction = EvaluationPredictor().predict(paper)

        self.assertEqual("negative", prediction.negative_tier)
        self.assertEqual([], prediction.preference_labels)
        self.assertIn("五个偏好标签", prediction.notes)

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

    def test_protocol_rejects_removed_structure_label(self) -> None:
        with self.assertRaises(EvaluationProtocolError):
            EvaluationPrediction(
                primary_research_object="LLM",
                preference_labels=["模型结构侧推理优化"],
                negative_tier="positive",
                evidence_spans={"模型结构侧推理优化": ["bad"]},
            )


if __name__ == "__main__":
    unittest.main()
