from __future__ import annotations

from paper_analysis.evaluation.routes.base import BaseBinaryRoute


class TwoStageStubRoute(BaseBinaryRoute):
    def __init__(self) -> None:
        super().__init__(
            route_name="two_stage_stub",
            algorithm_version="ab-two-stage-stub-v1",
            capability_type="two_stage",
            implementation_status="stub",
        )
