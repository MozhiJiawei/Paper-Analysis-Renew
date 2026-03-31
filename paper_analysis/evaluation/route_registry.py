from __future__ import annotations

from collections.abc import Callable

from paper_analysis.evaluation.routes.base import BaseBinaryRoute
from paper_analysis.evaluation.routes.embedding_retriever_stub import (
    EmbeddingRetrieverStubRoute,
)
from paper_analysis.evaluation.routes.llm_judge_stub import LlmJudgeStubRoute
from paper_analysis.evaluation.routes.local_classifier_stub import (
    LocalClassifierStubRoute,
)
from paper_analysis.evaluation.routes.two_stage_stub import TwoStageStubRoute


RouteFactory = Callable[[], BaseBinaryRoute]


class RouteRegistry:
    def __init__(self) -> None:
        self._factories: dict[str, RouteFactory] = {}

    def register(self, factory: RouteFactory) -> None:
        route = factory()
        self._factories[route.route_name] = factory

    def route_names(self) -> list[str]:
        return sorted(self._factories)

    def create_routes(self) -> list[BaseBinaryRoute]:
        return [self._factories[name]() for name in self.route_names()]


def build_default_route_registry() -> RouteRegistry:
    registry = RouteRegistry()
    registry.register(LocalClassifierStubRoute)
    registry.register(EmbeddingRetrieverStubRoute)
    registry.register(LlmJudgeStubRoute)
    registry.register(TwoStageStubRoute)
    return registry
