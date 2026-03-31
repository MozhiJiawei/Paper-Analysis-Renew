from __future__ import annotations

from paper_analysis.evaluation.routes.base import BaseBinaryRoute


class LlmJudgeStubRoute(BaseBinaryRoute):
    def __init__(self) -> None:
        super().__init__(
            route_name="llm_judge_stub",
            algorithm_version="ab-llm-judge-stub-v1",
            capability_type="llm_judge",
            implementation_status="stub",
        )
