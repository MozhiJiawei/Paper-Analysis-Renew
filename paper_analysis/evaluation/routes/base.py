"""Base interface for binary evaluation routes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from paper_analysis.evaluation.errors import RouteNotImplementedError

if TYPE_CHECKING:
    from paper_analysis.api.evaluation_protocol import EvaluationPaper
    from paper_analysis.evaluation.ab_protocol import BinaryRoutePrediction


@dataclass(slots=True)
class BaseBinaryRoute:
    """Base implementation shared by all scaffolded binary routes."""

    route_name: str
    algorithm_version: str
    capability_type: str
    implementation_status: str = "stub"

    def prepare(self) -> None:
        """Prepare route-level resources before prediction."""
        return

    def predict_many(self, _papers: list[EvaluationPaper]) -> list[BinaryRoutePrediction]:
        """Predict labels for a batch of papers."""
        raise RouteNotImplementedError(f"{self.route_name} 尚未实现真实算法。")
