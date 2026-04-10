"""Reusable unittest metadata helpers for CI HTML case rendering."""

from __future__ import annotations


class CaseMetadataMixin:
    """Collect process logs and artifacts for one unittest case result."""

    failure_check_description = "断言失败、抛出异常，或测试结果被框架标记为失败时判定失败。"
    case_source_label = ""

    def setUp(self) -> None:
        """Initialize per-case metadata while preserving parent setup hooks."""
        parent_setup = getattr(super(), "setUp", None)
        if callable(parent_setup):
            parent_setup()
        self.case_process_logs: list[str] = []
        self.case_artifacts: list[str] = []

    def record_step(self, message: str) -> None:
        """Append one human-readable execution step to the case log."""
        self.case_process_logs.append(message)

    def add_case_artifact(self, path: str) -> None:
        """Attach one artifact path to the rendered case output."""
        self.case_artifacts.append(path)

    def set_case_source_label(self, label: str) -> None:
        """Override the source label displayed in the HTML dashboard."""
        self.case_source_label = label

    def set_failure_check_description(self, description: str) -> None:
        """Override the failure semantics shown alongside the case."""
        self.failure_check_description = description
