from __future__ import annotations

import unittest

from paper_analysis.api.evaluation_protocol import EvaluationPrediction
from paper_analysis.evaluation.ab_protocol import (
    ROUTE_EXECUTION_STATUSES,
    BinaryRoutePrediction,
    RouteManifestEntry,
)


class ABProtocolUnitTests(unittest.TestCase):
    def test_route_manifest_accepts_all_expected_statuses(self) -> None:
        self.assertEqual(("ready", "stub", "failed", "skipped"), ROUTE_EXECUTION_STATUSES)

    def test_route_manifest_rejects_unknown_status(self) -> None:
        with self.assertRaises(ValueError):
            RouteManifestEntry(
                route_name="bad",
                algorithm_version="v1",
                capability_type="test",
                implementation_status="stub",
                execution_status="unknown",  # type: ignore[arg-type]
            )

    def test_binary_route_prediction_serializes_public_prediction(self) -> None:
        prediction = BinaryRoutePrediction(
            paper_id="paper-1",
            prediction=EvaluationPrediction(
                primary_research_object="LLM",
                preference_labels=["解码策略优化"],
                negative_tier="positive",
                evidence_spans={"general": ["paper title"]},
            ),
        )

        payload = prediction.to_dict()

        self.assertEqual("paper-1", payload["paper_id"])
        self.assertEqual("positive", payload["prediction"]["negative_tier"])


if __name__ == "__main__":
    unittest.main()
