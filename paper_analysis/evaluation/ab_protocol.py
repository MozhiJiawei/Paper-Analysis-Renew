from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal

from paper_analysis.api.evaluation_protocol import EvaluationPrediction


RouteExecutionStatus = Literal["ready", "stub", "failed", "skipped"]
ROUTE_EXECUTION_STATUSES: tuple[RouteExecutionStatus, ...] = (
    "ready",
    "stub",
    "failed",
    "skipped",
)


@dataclass(slots=True)
class BinaryRoutePrediction:
    paper_id: str
    prediction: EvaluationPrediction

    def to_dict(self) -> dict[str, object]:
        return {
            "paper_id": self.paper_id,
            "prediction": self.prediction.to_dict(),
        }


@dataclass(slots=True)
class RouteManifestEntry:
    route_name: str
    algorithm_version: str
    capability_type: str
    implementation_status: str
    execution_status: RouteExecutionStatus
    reason: str = ""

    def __post_init__(self) -> None:
        if self.execution_status not in ROUTE_EXECUTION_STATUSES:
            raise ValueError(f"非法执行状态：{self.execution_status}")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True)
class RouteRunResult:
    manifest: RouteManifestEntry
    predictions: list[BinaryRoutePrediction] = field(default_factory=list)
    metrics: dict[str, object] = field(default_factory=dict)
    artifacts: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "manifest": self.manifest.to_dict(),
            "prediction_count": len(self.predictions),
            "metrics": self.metrics,
            "artifacts": self.artifacts,
        }


@dataclass(slots=True)
class ABRunResult:
    run_id: str
    output_dir: str
    manifest_path: str
    summary_path: str
    leaderboard_path: str
    routes: list[RouteRunResult]
    counts: dict[str, int]

    def to_dict(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "output_dir": self.output_dir,
            "manifest_path": self.manifest_path,
            "summary_path": self.summary_path,
            "leaderboard_path": self.leaderboard_path,
            "counts": self.counts,
            "routes": [route.to_dict() for route in self.routes],
        }
