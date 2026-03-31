from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from paper_analysis.api.evaluation_protocol import EvaluationPaper, EvaluationPrediction
from paper_analysis.evaluation.ab_runner import ABRunner
from paper_analysis.evaluation.ab_protocol import BinaryRoutePrediction
from paper_analysis.evaluation.route_registry import build_default_route_registry, RouteRegistry
from paper_analysis.evaluation.routes.base import BaseBinaryRoute


def _sample_papers() -> list[EvaluationPaper]:
    return [
        EvaluationPaper(
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
    ]


class FixtureReadyRoute(BaseBinaryRoute):
    def __init__(self) -> None:
        super().__init__(
            route_name="fixture_ready_route",
            algorithm_version="fixture-ready-v1",
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
                    evidence_spans={"general": [paper.title]},
                ),
            )
            for paper in papers
        ]


class ABScaffoldIntegrationTests(unittest.TestCase):
    def test_default_stub_registry_writes_complete_utf8_artifact_tree(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = ABRunner(
                registry=build_default_route_registry(),
                output_root=Path(temp_dir),
            ).run(papers=_sample_papers(), run_id="stub-run")

            output_dir = Path(result.output_dir)
            self.assertTrue((output_dir / "manifest.json").exists())
            self.assertTrue((output_dir / "summary.md").exists())
            self.assertTrue((output_dir / "leaderboard.json").exists())
            for route_name in build_default_route_registry().route_names():
                route_dir = output_dir / "routes" / route_name
                self.assertTrue((route_dir / "status.json").exists())
                self.assertTrue((route_dir / "predictions.jsonl").exists())
                self.assertTrue((route_dir / "metrics.json").exists())

            summary = (output_dir / "summary.md").read_text(encoding="utf-8")
            self.assertIn("A/B 脚手架运行摘要", summary)
            self.assertIn("stub", summary)

    def test_ready_and_stub_routes_can_coexist_in_one_run(self) -> None:
        registry = RouteRegistry()
        registry.register(FixtureReadyRoute)
        for factory in build_default_route_registry().create_routes():
            registry.register(factory.__class__)

        with tempfile.TemporaryDirectory() as temp_dir:
            result = ABRunner(
                registry=registry,
                output_root=Path(temp_dir),
                metrics_builder=lambda route_name, papers, predictions: {
                    "macro_precision": 1.0 if route_name == "fixture_ready_route" else 0.0,
                    "micro_f1": 1.0 if route_name == "fixture_ready_route" else 0.0,
                },
            ).run(papers=_sample_papers(), run_id="mixed-run")

            self.assertEqual(1, result.counts["ready"])
            self.assertEqual(4, result.counts["stub"])
            leaderboard = json.loads(Path(result.leaderboard_path).read_text(encoding="utf-8"))
            self.assertEqual("fixture_ready_route", leaderboard["routes"][0]["route_name"])


if __name__ == "__main__":
    unittest.main()
