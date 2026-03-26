from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from paper_analysis.domain.benchmark import AnnotationRecord, CandidatePaper
from paper_analysis.services.codex_annotator import (
    build_codex_annotation_prompt,
    parse_codex_annotation_payload,
)
from paper_analysis.utils.doubao_client import DoubaoClient


Runner = Callable[[list[dict[str, object]]], dict[str, object]]


@dataclass(slots=True)
class DoubaoAnnotator:
    runner: Runner | None = None
    api_key: str | None = None
    base_url: str | None = None
    model: str | None = None
    config_path: Path | None = None
    labeler_id: str = "doubao"
    _client: DoubaoClient = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._client = DoubaoClient(
            runner=self.runner,
            api_key=self.api_key,
            base_url=self.base_url,
            model=self.model,
            config_path=self.config_path,
        )

    def annotate(self, candidate: CandidatePaper) -> AnnotationRecord:
        prompts = [
            build_doubao_annotation_messages(candidate),
            build_doubao_annotation_messages(candidate, force_decision=True),
        ]
        last_error: Exception | None = None
        for messages in prompts:
            try:
                payload = self._run_messages(messages)
                data = parse_codex_annotation_payload(payload)
                return AnnotationRecord(
                    paper_id=candidate.paper_id,
                    labeler_id=self.labeler_id,
                    primary_research_object=str(data["primary_research_object"]),
                    preference_labels=[str(item) for item in data["preference_labels"]],
                    negative_tier=str(data["negative_tier"]),
                    evidence_spans={
                        str(key): [str(item) for item in value]
                        for key, value in dict(data.get("evidence_spans", {})).items()
                    },
                    notes=str(data.get("notes", "")),
                    review_status="pending",
                )
            except (RuntimeError, ValueError) as exc:
                last_error = exc
        if last_error is not None:
            raise last_error
        raise RuntimeError(f"Doubao 预标失败：{candidate.paper_id}")

    def _run_messages(self, messages: list[dict[str, str]]) -> str:
        result = self._client.chat(messages, stream=False)
        if not result.get("success"):
            raise RuntimeError(f"Doubao 预标失败：{result.get('error', '未知错误')}")
        content = str(result.get("content", "")).strip()
        if not content:
            raise ValueError("Doubao 未返回内容")
        return content


def build_doubao_annotation_messages(
    candidate: CandidatePaper,
    *,
    force_decision: bool = False,
) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "你是论文预标助手。"
                "你必须严格返回一个 JSON 对象，不要解释，不要提问，不要输出 Markdown。"
            ),
        },
        {
            "role": "user",
            "content": build_codex_annotation_prompt(candidate, force_decision=force_decision),
        },
    ]
