from __future__ import annotations

import json
from concurrent.futures import Future
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
    model: str | None = None
    concurrency: int = 1
    labeler_id: str | None = None
    _client: CodexCliClient = field(init=False, repr=False)
    _labeler_id: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._client = self.client or CodexCliClient(
            **_build_client_kwargs(self.runner, self.model, self.concurrency)
        )
        self._labeler_id = self.labeler_id or _default_codex_labeler_id(self.model)
        self.labeler_id = self._labeler_id

    def submit_annotate(self, candidate: CandidatePaper) -> Future[AnnotationRecord]:
        outer_future: Future[AnnotationRecord] = Future()
        prompts = [
            build_codex_annotation_prompt(candidate),
            build_codex_annotation_prompt(candidate, force_decision=True),
        ]
        self._submit_attempt(candidate, prompts, 0, outer_future)
        return outer_future

    def _submit_attempt(
        self,
        candidate: CandidatePaper,
        prompts: list[str],
        index: int,
        outer_future: Future[AnnotationRecord],
    ) -> None:
        inner_future = self._client.submit(prompts[index])
        inner_future.add_done_callback(
            lambda done: self._handle_prompt_result(candidate, prompts, index, outer_future, done)
        )

    def _handle_prompt_result(
        self,
        candidate: CandidatePaper,
        prompts: list[str],
        index: int,
        outer_future: Future[AnnotationRecord],
        inner_future: Future[str],
    ) -> None:
        if outer_future.done():
            return
        try:
            data = parse_codex_annotation_payload(inner_future.result())
            outer_future.set_result(self._build_annotation(candidate, data))
            return
        except (RuntimeError, ValueError) as exc:
            if index + 1 < len(prompts):
                self._submit_attempt(candidate, prompts, index + 1, outer_future)
                return
            outer_future.set_exception(exc)

    def _build_annotation(
        self,
        candidate: CandidatePaper,
        data: dict[str, object],
    ) -> AnnotationRecord:
        return AnnotationRecord(
            paper_id=candidate.paper_id,
            labeler_id=self._labeler_id,
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
            "primary_research_object 判断看被优化的主要对象，而不是实现手段：如果论文是在优化 LLM/RLLM/MoE/VLM 的推理、服务或压缩，通常仍应标对应模型对象，而不是 AI 系统 / 基础设施。",
            "preference_labels 的元素只能是："
            + "/".join(PREFERENCE_LABELS)
            + "。",
            "negative_tier 只能是 positive/negative。",
            "请先判断论文是否命中任一偏好标签：命中则输出 positive，否则输出 negative。",
            "如果 negative_tier=negative，则 preference_labels 必须是空数组。",
            "如果 negative_tier=positive，则只保留有明确摘要证据支持的唯一一个偏好标签，宁缺毋滥，不要为了覆盖面补充边缘标签。",
            "默认采用最小充分标注：positive 时必须且只能选择一个最相关的偏好标签，不允许输出多个偏好标签。",
            "如果摘要里同时出现多个可疑候选标签，也要比较主贡献、篇幅重心、方法命名与标题信号，只保留最核心、最贴切、最直接被摘要支持的那一项。",
            "不要因为论文同时带来吞吐、显存、延迟收益，就自动扩展到系统、内核、结构、压缩等多个标签；收益可以有多个，但偏好标签仍只选主方法对应的一项。",
            "边缘提及、实验配置、通用效率收益、实现细节、伴随收益，不足以单独构成偏好标签。",
            "如果某个技术点只是为了支撑另一个更核心的主贡献，例如为缓存压缩配套 kernel、为压缩方法配套 CUDA、为解码方法配套 head 结构，则优先保留主贡献标签，不要把配套实现再单独扩成额外标签。",
            "如果论文主要是在评测、经验研究、特性分析、工作对比，而不是提出并验证新的优化方法，则默认更保守；只有摘要明确把某种优化方法作为作者自己的主要方法与贡献时才标 positive。",
            "但如果经验研究明确围绕若干优化方法给出结论，并把其中有效的方法作为主要发现进行总结，则可以只标这些被摘要明确支持的标签，不要把被证明无效或副作用明显的方法一起标上。",
            "如果论文主要面向特殊硬件范式、替代模型范式或非主流推理设定，且六个偏好标签都不是其摘要中的直接主贡献，则输出 negative。",
            "标签边界：解码策略优化 仅限显式改变 token 生成/验证/接受流程，如 speculative decoding、tree decoding、并行解码、early exit；单纯 attention 或缓存优化不算。若论文主线就是 speculative decoding，而结构/head 改动只是为其服务，优先只标解码策略优化。",
            "标签边界：上下文与缓存优化 仅限长上下文、KV cache、prompt compression、token eviction/selection、上下文管理；参数量化或普通模型压缩不算。token 选择/剪枝若核心目的是减少上下文或注意力开销，优先归到这个标签。",
            "标签边界：系统与调度优化 仅限 serving、batching、任务编排、负载均衡、资源调度、并行执行；仅仅发生在 decoding stage、batch decoding 或带来吞吐提升，不等于解码策略优化或系统标签，需看主方法本身。MoE batch decoding、serving rerouting、load balancing 这类默认更接近系统与调度优化，而不是解码策略优化。",
            "标签边界：算子与内核优化 仅限 kernel、CUDA、fused op、编译器/运行时算子、注意力内核等底层实现，并且该底层实现本身是主要贡献；如果 kernel 只是支撑压缩、缓存或系统方法落地，默认不单独标。遇到 KV cache pruning/compression + custom kernel 时，默认优先保留上下文与缓存优化。",
            "标签边界：模型结构侧推理优化 仅限显式修改推理时使用的模型结构、head、layer、模块连接，并且这是主要贡献；如果结构改动只是服务于 speculative decoding 或其他更明确主标签，优先保留主标签，不再额外标这个标签。",
            "标签边界：模型压缩 仅限量化、剪枝、蒸馏、低比特、稀疏化、adapter/权重压缩；上下文压缩、KV cache 压缩、prompt 压缩不算模型压缩。",
            "如果某标签的证据更像它的相邻标签，应只保留更贴切的那个标签，不要重复占位。",
            "当 解码策略优化、系统与调度优化、算子与内核优化、模型结构侧推理优化 同时看起来都沾边时，优先回答“作者真正想优化的主方法是什么”，然后只选择那个最上位的主标签。",
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


def _build_client_kwargs(
    runner: Runner | None,
    model: str | None,
    concurrency: int,
) -> dict[str, object]:
    kwargs: dict[str, object] = {}
    if runner is not None:
        kwargs["runner"] = runner
    if model is not None:
        kwargs["model"] = model
    kwargs["concurrency"] = concurrency
    return kwargs


def _default_codex_labeler_id(model: str | None) -> str:
    return "codex_cli"
