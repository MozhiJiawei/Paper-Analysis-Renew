"""Placeholder route for a future two-stage implementation."""

from __future__ import annotations

from paper_analysis.evaluation.routes.base import BaseBinaryRoute


class TwoStageStubRoute(BaseBinaryRoute):
    """Scaffold route reserved for a future two-stage implementation."""

    def __init__(self) -> None:
        """Initialize the placeholder two-stage route metadata."""
        super().__init__(
            route_name="two_stage_stub",
            algorithm_version="ab-two-stage-stub-v1",
            capability_type="two_stage",
            implementation_status="stub",
        )
