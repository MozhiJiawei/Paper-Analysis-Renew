"""Registry for constructing evaluation scaffold routes."""

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
    """Store route factories and instantiate them in a stable order."""

    def __init__(self) -> None:
        """Initialize an empty registry keyed by route name."""
        self._factories: dict[str, RouteFactory] = {}

    def register(self, factory: RouteFactory) -> None:
        """Register a route factory under its declared route name."""
        route = factory()
        self._factories[route.route_name] = factory

    def route_names(self) -> list[str]:
        """Return registered route names in a stable sorted order."""
        return sorted(self._factories)

    def create_routes(self) -> list[BaseBinaryRoute]:
        """Instantiate one route object for each registered factory."""
        return [self._factories[name]() for name in self.route_names()]


def build_default_route_registry() -> RouteRegistry:
    """Build the default route registry used by the scaffold."""
    registry = RouteRegistry()
    registry.register(LocalClassifierStubRoute)
    registry.register(EmbeddingRetrieverStubRoute)
    registry.register(LlmJudgeStubRoute)
    registry.register(TwoStageStubRoute)
    return registry
