"""Placeholder route for a future local classifier implementation."""

from __future__ import annotations

from paper_analysis.evaluation.routes.base import BaseBinaryRoute


class LocalClassifierStubRoute(BaseBinaryRoute):
    """Scaffold route reserved for a future local classifier implementation."""

    def __init__(self) -> None:
        """Initialize the placeholder local-classifier route metadata."""
        super().__init__(
            route_name="local_classifier_stub",
            algorithm_version="ab-local-classifier-stub-v1",
            capability_type="local_classifier",
            implementation_status="stub",
        )
