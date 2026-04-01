from __future__ import annotations

from dataclasses import dataclass, field

from paper_analysis.api.evaluation_protocol import EvaluationPaper, EvaluationPrediction
from paper_analysis.evaluation.routes.base import BaseBinaryRoute
from paper_analysis.evaluation.routes.rule_filtered_llm_binary import (
    DoubaoBinaryJudge,
    RuleFilteredLlmBinaryRoute,
)


@dataclass(slots=True)
class EvaluationPredictor:
    algorithm_version: str = "rule-llm-binary-v1"
    route: BaseBinaryRoute | None = None
    _prepared_route: BaseBinaryRoute = field(init=False, repr=False)

    def __post_init__(self) -> None:
        route = self.route or RuleFilteredLlmBinaryRoute(
            judge=DoubaoBinaryJudge(),
            algorithm_version=self.algorithm_version,
        )
        route.prepare()
        self._prepared_route = route
        self.algorithm_version = route.algorithm_version

    def predict(self, paper: EvaluationPaper) -> EvaluationPrediction:
        return self._prepared_route.predict_many([paper])[0].prediction
