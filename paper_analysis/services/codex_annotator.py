from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Callable

from paper_analysis.domain.benchmark import PREFERENCE_LABELS, RESEARCH_OBJECT_LABELS
from paper_analysis.domain.benchmark import AnnotationRecord, CandidatePaper
from paper_analysis.utils.codex_cli_client import CodexCliClient


Runner = Callable[[str], str]


@dataclass(slots=True)
class CodexCliAnnotator:
    client: CodexCliClient | None = None
    runner: Runner | None = None
    _client: CodexCliClient = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._client = self.client or CodexCliClient(runner=self.runner)

    def annotate(self, candidate: CandidatePaper) -> AnnotationRecord:
        prompts = [
            build_codex_annotation_prompt(candidate),
            build_codex_annotation_prompt(candidate, force_decision=True),
        ]
        last_error: Exception | None = None
        for prompt in prompts:
            try:
                payload = self._run_prompt(prompt)
                data = parse_codex_annotation_payload(payload)
                return AnnotationRecord(
                    paper_id=candidate.paper_id,
                    labeler_id="codex_cli",
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
        raise RuntimeError(f"Codex_CLI 预标失败：{candidate.paper_id}")

    def _run_prompt(self, prompt: str) -> str:
        try:
            return self._client.exec(prompt)
        except RuntimeError as exc:
            raise RuntimeError(f"Codex_CLI 预标失败：{exc}") from exc


def build_codex_annotation_prompt(candidate: CandidatePaper, *, force_decision: bool = False) -> str:
    decision_guard = (
        "禁止输出空对象、status、message、waiting_for_input，必须直接完成标注。"
        if force_decision
        else ""
    )
    return " ".join(
        [
            "只输出一个 JSON 对象，不要解释，不要提问。",
            "字段必须是 primary_research_object, preference_labels, negative_tier, evidence_spans, notes。",
            "不得输出空对象。",
            decision_guard,
            "primary_research_object 只能从以下枚举选择一个："
            + "/".join(RESEARCH_OBJECT_LABELS)
            + "。",
            "preference_labels 的元素只能是："
            + "/".join(PREFERENCE_LABELS)
            + "。",
            "negative_tier 只能是 positive/negative。",
            "请先判断论文是否命中任一偏好标签：命中则输出 positive，否则输出 negative。",
            "如果 negative_tier=negative，则 preference_labels 必须是空数组。",
            "如果 negative_tier=positive，则只保留有明确摘要证据支持的偏好标签，宁缺毋滥，不要为了覆盖面补充边缘标签。",
            "evidence_spans 必须是对象，key 只能使用 general、negative 或允许的偏好标签，value 必须是字符串数组。",
            f"title={candidate.title};",
            f"abstract={candidate.abstract};",
            f"keywords={', '.join(candidate.keywords)};",
            f"candidate_primary_research_object={candidate.primary_research_object};",
            "candidate_preference_labels 仅作弱参考，不要机械照抄，必须以标题/摘要证据为准："
            + ",".join(candidate.candidate_preference_labels)
            + ";",
            f"candidate_negative_tier={candidate.candidate_negative_tier}.",
        ]
    )


def parse_codex_annotation_payload(payload: str) -> dict[str, object]:
    text = payload.strip()
    if not text:
        raise ValueError("Codex_CLI 未返回内容")
    if "\n" in text:
        event_payload = _extract_json_from_event_stream(text)
        if event_payload is not None:
            text = event_payload
    if "\n" in text:
        for line in reversed(text.splitlines()):
            stripped = line.strip()
            if stripped.startswith("{") and stripped.endswith("}"):
                text = stripped
                break
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("Codex_CLI 输出必须是 JSON 对象")
    required = {
        "primary_research_object",
        "preference_labels",
        "negative_tier",
        "evidence_spans",
        "notes",
    }
    missing = sorted(required - set(data))
    data = _normalize_annotation_payload(data)
    if missing:
        raise ValueError(f"Codex_CLI 输出缺少字段：{', '.join(missing)}")
    data["evidence_spans"] = _normalize_evidence_spans(data.get("evidence_spans"))
    return data


def _extract_json_from_event_stream(payload: str) -> str | None:
    for line in reversed(payload.splitlines()):
        stripped = line.strip()
        if not stripped.startswith("{"):
            continue
        try:
            event = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        item = event.get("item")
        if isinstance(item, dict) and item.get("type") == "agent_message":
            text = item.get("text")
            if isinstance(text, str) and text.strip():
                return text.strip()
    return None


def _normalize_evidence_spans(payload: object) -> dict[str, list[str]]:
    if isinstance(payload, dict):
        normalized: dict[str, list[str]] = {}
        for key, value in payload.items():
            label = _normalize_evidence_label(str(key))
            normalized.setdefault(label, []).extend([str(item) for item in value if str(item).strip()])
        return normalized
    if isinstance(payload, list):
        normalized: dict[str, list[str]] = {}
        for item in payload:
            if not isinstance(item, dict):
                continue
            label = _normalize_evidence_label(str(item.get("label", "general")))
            text = str(item.get("text", "")).strip()
            if not label or not text:
                continue
            normalized.setdefault(label, []).append(text)
        return normalized
    return {}

def _normalize_annotation_payload(payload: dict[str, object]) -> dict[str, object]:
    normalized = dict(payload)
    normalized["primary_research_object"] = _normalize_single_choice(
        str(payload.get("primary_research_object", "")),
        RESEARCH_OBJECT_LABELS,
    )
    normalized["preference_labels"] = _normalize_choice_list(payload.get("preference_labels"), PREFERENCE_LABELS)
    normalized["negative_tier"] = _normalize_negative_tier(str(payload.get("negative_tier", "")))
    if normalized["negative_tier"] == "negative":
        normalized["preference_labels"] = []
    return normalized


def _normalize_single_choice(value: str, allowed: tuple[str, ...]) -> str:
    stripped = value.strip()
    if stripped in allowed:
        return stripped
    for item in allowed:
        if item in stripped or stripped in item:
            return item
    lowered = stripped.lower()
    token_map = {
        "llm": "LLM",
        "vlm": "多模态 / VLM",
        "multimodal": "多模态 / VLM",
        "vision-language": "多模态 / VLM",
        "diffusion": "Diffusion / 生成模型",
        "reinforcement": "强化学习 / 序列决策",
        "retrieval": "检索 / 推荐 / 搜索",
        "recommend": "检索 / 推荐 / 搜索",
        "search": "检索 / 推荐 / 搜索",
        "vision": "计算机视觉",
        "image": "计算机视觉",
        "speech": "语音 / 音频",
        "audio": "语音 / 音频",
        "system": "AI 系统 / 基础设施",
        "infrastructure": "AI 系统 / 基础设施",
        "benchmark": "评测 / Benchmark / 数据集",
        "dataset": "评测 / Benchmark / 数据集",
    }
    for token, mapped in token_map.items():
        if token in lowered:
            return mapped
    raise ValueError(f"Codex_CLI 输出非法标签：{value}")


def _normalize_choice_list(value: object, allowed: tuple[str, ...]) -> list[str]:
    if not isinstance(value, list):
        raise ValueError("Codex_CLI 输出标签列表格式非法")
    normalized: list[str] = []
    for raw in value:
        item = str(raw).strip()
        if not item:
            continue
        matched = None
        for allowed_item in allowed:
            if item == allowed_item or allowed_item in item or item in allowed_item:
                matched = allowed_item
                break
        if matched is None:
            lowered = item.lower()
            for allowed_item in allowed:
                allowed_lowered = allowed_item.lower()
                if any(
                    token in lowered
                    for token in allowed_lowered.replace(" / ", "/").split("/")
                ):
                    matched = allowed_item
                    break
        if matched is None:
            continue
        if matched not in normalized:
            normalized.append(matched)
    return normalized


def _normalize_negative_tier(value: str) -> str:
    stripped = value.strip()
    if stripped in {"positive", "negative"}:
        return stripped
    for allowed in ("positive", "negative"):
        if allowed in stripped:
            return allowed
    raise ValueError(f"Codex_CLI 输出非法 negative_tier：{value}")


def _normalize_evidence_label(value: str) -> str:
    stripped = value.strip()
    if stripped in {"general", "negative"}:
        return stripped
    for label in PREFERENCE_LABELS:
        if stripped == label or label in stripped or stripped in label:
            return label
    return "general"
