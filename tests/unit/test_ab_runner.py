from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from paper_analysis.api.evaluation_protocol import EvaluationPaper, EvaluationPrediction
from paper_analysis.evaluation.ab_runner import ABRunner
from paper_analysis.evaluation.ab_protocol import BinaryRoutePrediction
from paper_analysis.evaluation.route_registry import RouteRegistry
from paper_analysis.evaluation.routes.base import BaseBinaryRoute


def _sample_paper() -> EvaluationPaper:
    return EvaluationPaper(
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


class ReadyRoute(BaseBinaryRoute):
    def __init__(self) -> None:
        super().__init__(
            route_name="ready_route",
            algorithm_version="ready-v1",
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


class FailedRoute(BaseBinaryRoute):
    def __init__(self) -> None:
        super().__init__(
            route_name="failed_route",
            algorithm_version="failed-v1",
            capability_type="test",
            implementation_status="ready",
        )

    def predict_many(self, papers: list[EvaluationPaper]) -> list[BinaryRoutePrediction]:
        raise RuntimeError("boom")


class WrongContractRoute(BaseBinaryRoute):
    def __init__(self) -> None:
        super().__init__(
            route_name="wrong_contract_route",
            algorithm_version="broken-v1",
            capability_type="test",
            implementation_status="ready",
        )

    def predict_many(self, papers: list[EvaluationPaper]) -> list[BinaryRoutePrediction]:
        return []


class ABRunnerUnitTests(unittest.TestCase):
    def test_runner_normalizes_ready_failed_and_skipped(self) -> None:
        registry = RouteRegistry()
        registry.register(ReadyRoute)
        registry.register(FailedRoute)

        with tempfile.TemporaryDirectory() as temp_dir:
            result = ABRunner(
                registry=registry,
                output_root=Path(temp_dir),
            ).run(
                papers=[_sample_paper()],
                run_id="run-1",
                enabled_route_names=["ready_route", "failed_route"],
            )

            self.assertEqual({"ready": 1, "stub": 0, "failed": 1, "skipped": 0}, result.counts)
            manifest = json.loads(Path(result.manifest_path).read_text(encoding="utf-8"))
            self.assertEqual(2, len(manifest["routes"]))

    def test_runner_marks_route_as_stub_on_not_implemented(self) -> None:
        registry = RouteRegistry()

        class StubRoute(BaseBinaryRoute):
            def __init__(self) -> None:
                super().__init__(
                    route_name="stub_route",
                    algorithm_version="stub-v1",
                    capability_type="test",
                    implementation_status="stub",
                )

        registry.register(StubRoute)
        with tempfile.TemporaryDirectory() as temp_dir:
            result = ABRunner(
                registry=registry,
                output_root=Path(temp_dir),
            ).run(papers=[_sample_paper()], run_id="run-2")

            self.assertEqual("stub", result.routes[0].manifest.execution_status)
            self.assertEqual({}, result.routes[0].metrics)

    def test_runner_marks_unselected_routes_as_skipped(self) -> None:
        registry = RouteRegistry()
        registry.register(ReadyRoute)
        registry.register(WrongContractRoute)

        with tempfile.TemporaryDirectory() as temp_dir:
            result = ABRunner(
                registry=registry,
                output_root=Path(temp_dir),
            ).run(
                papers=[_sample_paper()],
                run_id="run-3",
                enabled_route_names=["ready_route"],
            )

            statuses = {route.manifest.route_name: route.manifest.execution_status for route in result.routes}
            self.assertEqual("ready", statuses["ready_route"])
            self.assertEqual("skipped", statuses["wrong_contract_route"])

    def test_runner_treats_contract_violation_as_failed(self) -> None:
        registry = RouteRegistry()
        registry.register(WrongContractRoute)

        with tempfile.TemporaryDirectory() as temp_dir:
            result = ABRunner(
                registry=registry,
                output_root=Path(temp_dir),
            ).run(papers=[_sample_paper()], run_id="run-4")

            self.assertEqual("failed", result.routes[0].manifest.execution_status)
            status_payload = json.loads(
                Path(result.routes[0].artifacts["status"]).read_text(encoding="utf-8")
            )
            self.assertIn("不一致", status_payload["reason"])


if __name__ == "__main__":
    unittest.main()
