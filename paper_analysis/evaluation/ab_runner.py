"""Executor for running multiple evaluation routes within one scaffold run."""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Callable
from typing import TYPE_CHECKING

from paper_analysis.api.evaluation_protocol import EvaluationPaper
from paper_analysis.evaluation.ab_protocol import (
    ABRunResult,
    BinaryRoutePrediction,
    RouteManifestEntry,
    RouteRunResult,
)
from paper_analysis.evaluation.ab_reporter import write_run_summary
from paper_analysis.evaluation.errors import RouteContractError, RouteNotImplementedError

if TYPE_CHECKING:
    from pathlib import Path

    from paper_analysis.evaluation.route_registry import RouteRegistry
    from paper_analysis.evaluation.routes.base import BaseBinaryRoute


MetricsBuilder = Callable[[str, list[EvaluationPaper], list[BinaryRoutePrediction]], dict[str, object]]
ROUTE_EXECUTION_ERRORS = (RouteContractError, RuntimeError, TypeError, ValueError)


class ABRunner:
    """Run a selected set of routes and persist per-route artifacts."""

    def __init__(
        self,
        *,
        registry: RouteRegistry,
        output_root: Path,
        metrics_builder: MetricsBuilder | None = None,
    ) -> None:
        """Initialize one scaffold runner with output and metric dependencies."""
        self._registry = registry
        self._output_root = output_root
        self._metrics_builder = metrics_builder

    def run(
        self,
        *,
        papers: list[EvaluationPaper],
        run_id: str,
        enabled_route_names: list[str] | None = None,
    ) -> ABRunResult:
        """Execute all enabled routes and write scaffold-level artifacts."""
        output_dir = self._output_root / run_id
        routes_dir = output_dir / "routes"
        routes_dir.mkdir(parents=True, exist_ok=True)

        enabled = set(enabled_route_names) if enabled_route_names else None
        route_results: list[RouteRunResult] = []
        for route in self._registry.create_routes():
            route_dir = routes_dir / route.route_name
            route_dir.mkdir(parents=True, exist_ok=True)
            if enabled is not None and route.route_name not in enabled:
                route_results.append(
                    self._write_route_artifacts(
                        route_dir=route_dir,
                        result=RouteRunResult(
                            manifest=RouteManifestEntry(
                                route_name=route.route_name,
                                algorithm_version=route.algorithm_version,
                                capability_type=route.capability_type,
                                implementation_status=route.implementation_status,
                                execution_status="skipped",
                                reason="本次运行未选择该路线。",
                            ),
                        ),
                    )
                )
                continue

            route_results.append(
                self._execute_route(route=route, route_dir=route_dir, papers=papers)
            )

        counts = self._count_statuses(route_results)
        manifest_payload = {
            "run_id": run_id,
            "counts": counts,
            "routes": [item.manifest.to_dict() for item in route_results],
        }
        manifest_path = output_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        result = ABRunResult(
            run_id=run_id,
            output_dir=str(output_dir),
            manifest_path=str(manifest_path),
            summary_path=str(output_dir / "summary.md"),
            leaderboard_path=str(output_dir / "leaderboard.json"),
            routes=route_results,
            counts=counts,
        )
        summary_path, leaderboard_path = write_run_summary(output_dir, result)
        result.summary_path = str(summary_path)
        result.leaderboard_path = str(leaderboard_path)
        return result

    def _execute_route(
        self,
        *,
        route: BaseBinaryRoute,
        route_dir: Path,
        papers: list[EvaluationPaper],
    ) -> RouteRunResult:
        """Execute one route and normalize its outcome into a route result."""
        try:
            route.prepare()
            predictions = route.predict_many(papers)
            self._validate_predictions(
                route_name=route.route_name,
                papers=papers,
                predictions=predictions,
            )
            metrics = self._build_metrics(route.route_name, papers, predictions)
            result = RouteRunResult(
                manifest=RouteManifestEntry(
                    route_name=route.route_name,
                    algorithm_version=route.algorithm_version,
                    capability_type=route.capability_type,
                    implementation_status=route.implementation_status,
                    execution_status="ready",
                ),
                predictions=predictions,
                metrics=metrics,
            )
        except RouteNotImplementedError as exc:
            result = RouteRunResult(
                manifest=RouteManifestEntry(
                    route_name=route.route_name,
                    algorithm_version=route.algorithm_version,
                    capability_type=route.capability_type,
                    implementation_status=route.implementation_status,
                    execution_status="stub",
                    reason=str(exc),
                ),
            )
        except ROUTE_EXECUTION_ERRORS as exc:
            result = RouteRunResult(
                manifest=RouteManifestEntry(
                    route_name=route.route_name,
                    algorithm_version=route.algorithm_version,
                    capability_type=route.capability_type,
                    implementation_status=route.implementation_status,
                    execution_status="failed",
                    reason=str(exc),
                ),
            )
        return self._write_route_artifacts(route_dir=route_dir, result=result)

    def _validate_predictions(
        self,
        *,
        route_name: str,
        papers: list[EvaluationPaper],
        predictions: list[BinaryRoutePrediction],
    ) -> None:
        """Validate that route outputs preserve count and ordering contracts."""
        if len(predictions) != len(papers):
            raise RouteContractError(
                f"{route_name} 返回的预测条数与输入论文数不一致。"
            )
        expected_ids = [paper.paper_id for paper in papers]
        actual_ids = [item.paper_id for item in predictions]
        if actual_ids != expected_ids:
            raise RouteContractError(f"{route_name} 返回的 paper_id 顺序不匹配。")

    def _build_metrics(
        self,
        route_name: str,
        papers: list[EvaluationPaper],
        predictions: list[BinaryRoutePrediction],
    ) -> dict[str, object]:
        """Build optional metrics for a route execution."""
        if self._metrics_builder is None:
            return {"prediction_count": len(predictions)}
        return self._metrics_builder(route_name, papers, predictions)

    def _write_route_artifacts(
        self,
        *,
        route_dir: Path,
        result: RouteRunResult,
    ) -> RouteRunResult:
        """Persist per-route status, prediction, and metric artifacts."""
        status_path = route_dir / "status.json"
        predictions_path = route_dir / "predictions.jsonl"
        metrics_path = route_dir / "metrics.json"
        status_path.write_text(
            json.dumps(result.manifest.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        predictions_lines = [
            json.dumps(item.to_dict(), ensure_ascii=False) for item in result.predictions
        ]
        predictions_path.write_text(
            ("\n".join(predictions_lines) + ("\n" if predictions_lines else "")),
            encoding="utf-8",
        )
        metrics_path.write_text(
            json.dumps(result.metrics, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        result.artifacts = {
            "status": str(status_path),
            "predictions": str(predictions_path),
            "metrics": str(metrics_path),
        }
        return result

    def _count_statuses(self, routes: list[RouteRunResult]) -> dict[str, int]:
        """Count route outcomes by execution status."""
        counter = Counter(route.manifest.execution_status for route in routes)
        return {
            "ready": counter.get("ready", 0),
            "stub": counter.get("stub", 0),
            "failed": counter.get("failed", 0),
            "skipped": counter.get("skipped", 0),
        }
