from __future__ import annotations

from dataclasses import dataclass

from paper_analysis.api.evaluation_protocol import EvaluationPaper
from paper_analysis.evaluation.ab_protocol import BinaryRoutePrediction
from paper_analysis.evaluation.errors import RouteNotImplementedError


@dataclass(slots=True)
class BaseBinaryRoute:
    route_name: str
    algorithm_version: str
    capability_type: str
    implementation_status: str = "stub"

    def prepare(self) -> None:
        return

    def predict_many(self, papers: list[EvaluationPaper]) -> list[BinaryRoutePrediction]:
        raise RouteNotImplementedError(f"{self.route_name} 尚未实现真实算法。")
