from __future__ import annotations

from paper_analysis.evaluation.routes.base import BaseBinaryRoute


class LocalClassifierStubRoute(BaseBinaryRoute):
    def __init__(self) -> None:
        super().__init__(
            route_name="local_classifier_stub",
            algorithm_version="ab-local-classifier-stub-v1",
            capability_type="local_classifier",
            implementation_status="stub",
        )
