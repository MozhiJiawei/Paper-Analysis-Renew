from __future__ import annotations


class CaseMetadataMixin:
    failure_check_description = "断言失败、抛出异常，或测试结果被框架标记为失败时判定失败。"
    case_source_label = ""

    def setUp(self) -> None:
        super().setUp()
        self.case_process_logs: list[str] = []
        self.case_artifacts: list[str] = []

    def record_step(self, message: str) -> None:
        self.case_process_logs.append(message)

    def add_case_artifact(self, path: str) -> None:
        self.case_artifacts.append(path)

    def set_case_source_label(self, label: str) -> None:
        self.case_source_label = label

    def set_failure_check_description(self, description: str) -> None:
        self.failure_check_description = description
