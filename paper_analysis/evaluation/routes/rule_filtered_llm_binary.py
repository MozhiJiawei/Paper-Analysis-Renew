from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Protocol

from paper_analysis.api.evaluation_protocol import (
    EvaluationPaper,
    EvaluationPrediction,
    PREFERENCE_LABELS,
    RESEARCH_OBJECT_LABELS,
)
from paper_analysis.evaluation.ab_protocol import BinaryRoutePrediction
from paper_analysis.evaluation.errors import RouteContractError, RouteNotImplementedError
from paper_analysis.evaluation.routes.base import BaseBinaryRoute
from paper_analysis.utils.doubao_client import DoubaoClient


_GENERAL_CANDIDATE_KEYWORDS = (
    "llm",
    "large language model",
    "language model",
    "transformer",
    "inference",
    "serving",
    "prefill",
    "decode",
    "reasoning",
    "token",
    "attention",
    "latency",
    "throughput",
    "gpu",
    "kernel",
    "quantization",
    "pruning",
    "compression",
    "mixture-of-experts",
    "moe",
)

_FOUNDATION_MODEL_KEYWORDS = (
    "llm",
    "large language model",
    "language model",
    "foundation model",
    "transformer",
    "mixture-of-experts",
    "moe",
    "diffusion",
    "diffusion model",
    "diffusion models",
    "multimodal large language model",
    "vision-language model",
    "vlm",
    "mllm",
)

_EFFICIENCY_SIGNAL_KEYWORDS = (
    "efficient inference",
    "inference efficiency",
    "inference acceleration",
    "acceleration",
    "speedup",
    "faster",
    "efficient",
    "optimized",
    "optimization",
    "scalable",
    "latency",
    "throughput",
    "memory",
    "memory-efficient",
    "serving",
    "runtime",
    "inference-time",
    "test-time",
    "decode",
    "decoding",
    "prefill",
    "compression",
    "compress",
    "cache",
    "quantization",
    "pruning",
    "sparsity",
    "offload",
    "weight-only",
    "weight only",
    "low-rank",
    "layer skipping",
    "early exit",
    "early-exit",
)

_SYSTEM_CONTEXT_KEYWORDS = (
    "inference",
    "serving",
    "runtime",
    "scheduler",
    "scheduling",
    "serving system",
    "inference engine",
    "continuous batching",
    "pipeline parallelism",
    "parallel",
    "resource manager",
    "resource allocation",
    "distributed",
    "gpu",
    "memory",
    "generation",
    "prefill",
    "decode",
    "disaggregation",
    "disaggregated",
    "queue",
    "admission control",
    "load balancing",
)

_NEGATIVE_GUARD_KEYWORDS = (
    "alignment",
    "safety",
    "fairness",
    "hallucination",
    "benchmark",
    "dataset",
    "evaluation",
    "question answering",
    "creator intent",
    "misleading",
    "recommendation",
    "news",
    "segmentation",
)

_HARD_NEGATIVE_GUARD_KEYWORDS = (
    "alignment",
    "safety",
    "fairness",
    "hallucination",
    "question answering",
    "creator intent",
    "misleading",
    "recommendation",
    "news",
    "segmentation",
)

_LABEL_KEYWORDS: dict[str, tuple[str, ...]] = {
    "解码策略优化": (
        "speculative decoding",
        "self-speculative",
        "parallel decoding",
        "tree decoding",
        "draft model",
        "acceptance rate",
        "early exit",
        "multi-token prediction",
        "draft-and-verify",
        "forking tokens",
        "reason in parallel",
    ),
    "上下文与缓存优化": (
        "kv cache",
        "key-value cache",
        "long context",
        "context compression",
        "prompt compression",
        "token eviction",
        "attention sink",
        "cache compression",
        "activation beacon",
        "token selection",
    ),
    "系统与调度优化": (
        "serving",
        "serving system",
        "scheduler",
        "scheduling",
        "batching",
        "continuous batching",
        "routing",
        "offload",
        "prefetch",
        "prefill",
        "decode",
        "disaggregation",
        "disaggregated serving",
        "prefill-decode disaggregation",
        "admission control",
        "queue",
        "resource allocation",
        "load balancing",
        "pipeline parallelism",
        "multi-tenant",
        "memory-optimized",
        "memory optimized",
    ),
    "算子与内核优化": (
        "cuda kernel",
        "gpu kernel",
        "fused operator",
        "operator fusion",
        "kernel fusion",
        "fused kernel",
        "attention kernel",
        "compiler",
        "compilation",
        "gemm",
        "tensor core",
        "memory bandwidth",
        "flashattention",
        "flash attention",
        "flashdecoding",
        "flash decoding",
        "triton",
        "flashinfer",
        "cutlass",
    ),
    "模型结构侧推理优化": (
        "layer reconfiguration",
        "runtime reconfiguration",
        "selective head",
        "retrieval head",
        "streaming head",
        "mixture-of-experts",
        "expert routing",
        "expert selection",
        "layer skipping",
        "layer skip",
        "skip layers",
        "dynamic depth",
        "adaptive depth",
        "adaptive computation",
        "hybrid architecture",
        "adaptive block size",
        "block size",
        "early tokens",
        "early exit",
        "early-exit",
    ),
    "模型压缩": (
        "quantization",
        "low-bit",
        "pruning",
        "distillation",
        "sparsity",
        "compressed weights",
        "binarization",
        "4-bit",
        "8-bit",
        "weight-only",
        "weight only",
        "layer pruning",
        "post-training quantization",
        "post training quantization",
    ),
}

class BinaryPaperJudge(Protocol):
    def is_available(self) -> bool: ...

    def judge(
        self,
        paper: EvaluationPaper,
        *,
        candidate_labels: list[str],
        matched_keywords: list[str],
    ) -> EvaluationPrediction: ...


@dataclass(slots=True)
class RuleFilterDecision:
    action: str
    matched_keywords: list[str]
    candidate_labels: list[str]
    reason: str
    preference_label: str | None = None
    positive_bias: bool = False


@dataclass(slots=True)
class DoubaoBinaryJudge:
    client: DoubaoClient | None = None

    def __post_init__(self) -> None:
        if self.client is None:
            self.client = DoubaoClient(concurrency=8)

    def is_available(self) -> bool:
        return bool(self.client and self.client.resolved_api_key)

    def judge(
        self,
        paper: EvaluationPaper,
        *,
        candidate_labels: list[str],
        matched_keywords: list[str],
    ) -> EvaluationPrediction:
        if not self.is_available():
            raise RouteNotImplementedError("未检测到可用的 Doubao 配置，无法执行大模型裁决。")
        messages = _build_judge_messages(
            paper,
            candidate_labels=candidate_labels,
            matched_keywords=matched_keywords,
        )
        payload = self.client.submit(messages).result()
        if not payload.get("success"):
            raise RouteContractError(str(payload.get("error") or "Doubao 返回失败结果。"))
        content = str(payload.get("content") or "").strip()
        if not content:
            raise RouteContractError("Doubao 未返回有效内容。")
        return _parse_prediction_payload(
            content,
            paper=paper,
            candidate_labels=candidate_labels,
        )


class RuleFilteredLlmBinaryRoute(BaseBinaryRoute):
    def __init__(
        self,
        *,
        judge: BinaryPaperJudge | None = None,
        algorithm_version: str = "rule-llm-binary-v1",
    ) -> None:
        super().__init__(
            route_name="rule_filtered_llm_binary",
            algorithm_version=algorithm_version,
            capability_type="two_stage",
            implementation_status="stub",
        )
        self._judge = judge

    def prepare(self) -> None:
        if self._judge is None:
            raise RouteNotImplementedError("未绑定大模型裁决器；请在 worktree 路线中显式注入 judge。")
        if not self._judge.is_available():
            raise RouteNotImplementedError("大模型裁决器当前不可用；请检查 Doubao 配置或测试注入。")
        self.implementation_status = "ready"

    def predict_many(self, papers: list[EvaluationPaper]) -> list[BinaryRoutePrediction]:
        predictions: list[BinaryRoutePrediction] = []
        for paper in papers:
            decision = _rule_filter(paper)
            if decision.action == "negative":
                predictions.append(
                    BinaryRoutePrediction(
                        paper_id=paper.paper_id,
                        prediction=_build_negative_prediction(
                            paper,
                            reason=decision.reason,
                        ),
                    )
                )
                continue
            if decision.action == "positive":
                predictions.append(
                    BinaryRoutePrediction(
                        paper_id=paper.paper_id,
                        prediction=_build_positive_prediction(
                            paper,
                            preference_label=decision.preference_label
                            or (decision.candidate_labels[0] if decision.candidate_labels else "系统与调度优化"),
                            evidence=decision.matched_keywords[:3] or [paper.title],
                            reason=decision.reason,
                        ),
                    )
                )
                continue
            try:
                prediction = self._judge.judge(
                    paper,
                    candidate_labels=decision.candidate_labels,
                    matched_keywords=decision.matched_keywords,
                )
            except Exception as exc:
                if decision.positive_bias:
                    prediction = _build_positive_prediction(
                        paper,
                        preference_label=decision.preference_label
                        or (decision.candidate_labels[0] if decision.candidate_labels else "系统与调度优化"),
                        evidence=decision.matched_keywords[:3] or [paper.title],
                        reason=f"LLM 裁决失败，按高召回正例偏置回退：{exc}",
                    )
                else:
                    prediction = _build_negative_prediction(
                        paper,
                        reason=f"LLM 裁决失败，回退为规则 negative：{exc}",
                    )
            else:
                if (
                    decision.positive_bias
                    and prediction.negative_tier == "negative"
                    and (decision.preference_label or decision.candidate_labels)
                ):
                    prediction = _build_positive_prediction(
                        paper,
                        preference_label=decision.preference_label
                        or decision.candidate_labels[0],
                        evidence=decision.matched_keywords[:3] or [paper.title],
                        reason="LLM 判负，但规则命中高召回正例偏置，提升为 positive。",
                    )
            predictions.append(
                BinaryRoutePrediction(
                    paper_id=paper.paper_id,
                    prediction=prediction,
                )
            )
        return predictions


def _rule_filter(paper: EvaluationPaper) -> RuleFilterDecision:
    text_parts = [paper.title, paper.abstract, paper.abstract_zh, " ".join(paper.keywords or [])]
    normalized = " ".join(part for part in text_parts if part).lower()
    title_lower = paper.title.lower()
    matched_keywords: list[str] = []
    candidate_labels: list[str] = []
    label_hit_counts: dict[str, int] = {}
    for label, keywords in _LABEL_KEYWORDS.items():
        label_hits = [keyword for keyword in keywords if keyword in normalized]
        if not label_hits:
            continue
        candidate_labels.append(label)
        label_hit_counts[label] = len(label_hits)
        for keyword in label_hits:
            if keyword not in matched_keywords:
                matched_keywords.append(keyword)
    general_hits = [keyword for keyword in _GENERAL_CANDIDATE_KEYWORDS if keyword in normalized]
    for keyword in general_hits:
        if keyword not in matched_keywords:
            matched_keywords.append(keyword)
    foundation_hits = [keyword for keyword in _FOUNDATION_MODEL_KEYWORDS if keyword in normalized]
    efficiency_hits = [keyword for keyword in _EFFICIENCY_SIGNAL_KEYWORDS if keyword in normalized]
    system_context_hits = [keyword for keyword in _SYSTEM_CONTEXT_KEYWORDS if keyword in normalized]
    negative_guard_hits = [keyword for keyword in _NEGATIVE_GUARD_KEYWORDS if keyword in normalized]
    hard_negative_guard_hits = [
        keyword for keyword in _HARD_NEGATIVE_GUARD_KEYWORDS if keyword in normalized
    ]
    title_label_hits = [
        keyword
        for keywords in _LABEL_KEYWORDS.values()
        for keyword in keywords
        if keyword in title_lower
    ]
    primary_label = _pick_primary_label(label_hit_counts)
    fallback_label = primary_label or _infer_positive_label_from_signals(normalized)
    if fallback_label is None and foundation_hits and efficiency_hits and system_context_hits:
        fallback_label = "系统与调度优化"
    if hard_negative_guard_hits and not foundation_hits and not system_context_hits:
        return RuleFilterDecision(
            action="negative",
            matched_keywords=[],
            candidate_labels=[],
            reason=f"规则预过滤命中负向主题，跳过候选裁决：{', '.join(hard_negative_guard_hits[:4])}",
        )
    primary_label_hits = label_hit_counts.get(primary_label or "", 0)
    positive_bias = bool(fallback_label) and not hard_negative_guard_hits and (
        primary_label_hits >= 1
        or (bool(foundation_hits) and bool(system_context_hits) and bool(efficiency_hits))
    )
    strong_positive = (
        bool(title_label_hits)
        or len(candidate_labels) >= 2
        or (
            bool(fallback_label)
            and primary_label_hits >= 1
            and not hard_negative_guard_hits
            and (bool(foundation_hits) or bool(system_context_hits) or bool(efficiency_hits))
        )
        or (
            primary_label == "模型压缩"
            and primary_label_hits >= 1
            and not hard_negative_guard_hits
        )
        or (
            primary_label in {"算子与内核优化", "模型结构侧推理优化"}
            and primary_label_hits >= 1
            and not hard_negative_guard_hits
        )
        or (
            primary_label in {"系统与调度优化", "算子与内核优化", "模型结构侧推理优化", "模型压缩"}
            and primary_label_hits >= 2
            and (bool(foundation_hits) or bool(system_context_hits) or bool(efficiency_hits))
        )
        or (
            bool(fallback_label)
            and bool(foundation_hits)
            and bool(efficiency_hits)
            and not hard_negative_guard_hits
        )
    )
    if strong_positive:
        return RuleFilterDecision(
            action="positive",
            matched_keywords=matched_keywords,
            candidate_labels=candidate_labels,
            reason=f"规则直判命中高置信推理优化特征：{', '.join(matched_keywords[:6])}",
            preference_label=fallback_label,
            positive_bias=positive_bias,
        )
    if matched_keywords:
        return RuleFilterDecision(
            action="judge",
            matched_keywords=matched_keywords,
            candidate_labels=candidate_labels,
            reason=f"规则预过滤命中候选特征：{', '.join(matched_keywords[:6])}",
            preference_label=fallback_label,
            positive_bias=positive_bias,
        )
    if (
        fallback_label
        and foundation_hits
        and efficiency_hits
        and system_context_hits
        and not hard_negative_guard_hits
    ):
        return RuleFilterDecision(
            action="positive",
            matched_keywords=foundation_hits[:2] + efficiency_hits[:4],
            candidate_labels=candidate_labels,
            reason="规则兜底命中 foundation model 推理效率正例特征。",
            preference_label=fallback_label,
            positive_bias=True,
        )
    return RuleFilterDecision(
        action="negative",
        matched_keywords=[],
        candidate_labels=[],
        reason="规则预过滤未命中 LLM 推理优化候选特征。",
    )


def _build_positive_prediction(
    paper: EvaluationPaper,
    *,
    preference_label: str,
    evidence: list[str],
    reason: str,
) -> EvaluationPrediction:
    return EvaluationPrediction(
        primary_research_object=_infer_primary_research_object(paper),
        preference_labels=[preference_label],
        negative_tier="positive",
        evidence_spans={
            "general": [paper.title],
            preference_label: evidence[:3] or [paper.title],
        },
        notes=reason,
    )


def _build_negative_prediction(paper: EvaluationPaper, *, reason: str) -> EvaluationPrediction:
    return EvaluationPrediction(
        primary_research_object=_infer_primary_research_object(paper),
        preference_labels=[],
        negative_tier="negative",
        evidence_spans={"negative": [paper.title]},
        notes=reason,
    )


def _build_judge_messages(
    paper: EvaluationPaper,
    *,
    candidate_labels: list[str],
    matched_keywords: list[str],
) -> list[dict[str, str]]:
    label_hint = "、".join(candidate_labels) if candidate_labels else "无明确标签提示"
    keyword_hint = "、".join(matched_keywords[:8]) if matched_keywords else "无"
    return [
        {
            "role": "system",
            "content": (
                "你是论文二分类评测裁决器。"
                "请只输出一个 JSON 对象，不要输出 markdown、解释、状态消息或追问。"
                "任务是判断论文是否属于 LLM 推理优化相关 positive 样本。"
            ),
        },
        {
            "role": "user",
            "content": (
                "请阅读论文信息后返回 JSON，字段必须为："
                "`negative_tier`、`primary_research_object`、`preference_label`、`evidence`、`notes`。\n"
                f"- `negative_tier` 只能是 `positive` 或 `negative`\n"
                f"- `primary_research_object` 只能从以下枚举中选择一个：{'、'.join(RESEARCH_OBJECT_LABELS)}\n"
                f"- 若为 `positive`，`preference_label` 必须且只能是以下之一：{'、'.join(PREFERENCE_LABELS)}\n"
                "- 若为 `negative`，`preference_label` 必须返回空字符串\n"
                "- `evidence` 必须是 1 到 3 条中文或英文证据短句数组\n"
                "- 不要声称缺少标题、摘要或关键词；输入已经完整提供\n"
                "- 先判主研究对象，再判作者是否真的提出并验证了六个偏好标签之一作为主要方法，最后若命中只选一个最核心主标签\n"
                "- `candidate_labels` 与 `matched_keywords` 只是弱提示，不能覆盖标题、摘要与关键词中的直接证据\n"
                "- 如果主方法是 token selection、KV cache、context compression、prompt compression、KV compression，优先考虑“上下文与缓存优化”\n"
                "- 如果主方法是 serving framework、routing、batch scheduling、load balancing、prefetch、offload、pipeline parallelism，优先考虑“系统与调度优化”\n"
                "- 如果主方法是 quantization、low-bit、pruning、distillation、sparsity 且压缩对象是模型参数或层，优先考虑“模型压缩”\n"
                "- 如果主方法是 speculative decoding、tree decoding、parallel decoding、draft model、early exit，优先考虑“解码策略优化”\n"
                "- 只有 kernel、CUDA、fused op、GEMM、编译器、attention kernel 本身是主要贡献时，才标“算子与内核优化”\n"
                "- 评测、benchmark、dataset、survey、应用流程、下游任务论文，若六个标签都不是作者最直接的方法贡献，则输出 `negative`\n\n"
                f"标题：{paper.title}\n"
                f"摘要：{paper.abstract}\n"
                f"中文摘要：{paper.abstract_zh}\n"
                f"关键词：{', '.join(paper.keywords or [])}\n"
                f"规则提示标签：{label_hint}\n"
                f"规则命中关键词：{keyword_hint}"
            ),
        },
    ]


def _parse_prediction_payload(
    raw_content: str,
    *,
    paper: EvaluationPaper,
    candidate_labels: list[str],
) -> EvaluationPrediction:
    payload = json.loads(_extract_json_object_text(raw_content))
    if not isinstance(payload, dict):
        raise RouteContractError("LLM 返回内容不是对象。")
    negative_tier = _normalize_negative_tier(payload.get("negative_tier"))
    if negative_tier not in {"positive", "negative"}:
        raise RouteContractError(f"LLM 返回了非法 negative_tier：{negative_tier}")
    primary_object = _normalize_primary_research_object(payload.get("primary_research_object"))
    if primary_object is None:
        primary_object = _infer_primary_research_object(paper)
    raw_label = _normalize_preference_label(
        payload.get("preference_label"),
        candidate_labels=candidate_labels,
    )
    if raw_label is None and isinstance(payload.get("preference_labels"), list):
        raw_label = _normalize_preference_label(
            payload.get("preference_labels"),
            candidate_labels=candidate_labels,
        )
    preference_labels: list[str]
    if negative_tier == "positive":
        if raw_label in PREFERENCE_LABELS:
            preference_labels = [raw_label]
        else:
            raise RouteContractError("positive 结果缺少合法的 preference_label。")
    else:
        preference_labels = []
    evidence_items = payload.get("evidence")
    evidence = _normalize_evidence(evidence_items, paper.title)
    evidence_spans = {"general": [paper.title]}
    if negative_tier == "positive" and preference_labels:
        evidence_spans[preference_labels[0]] = evidence
    else:
        evidence_spans = {"negative": evidence}
    return EvaluationPrediction(
        primary_research_object=primary_object,
        preference_labels=preference_labels,
        negative_tier=negative_tier,
        evidence_spans=evidence_spans,
        notes=str(payload.get("notes", "")).strip(),
    )


def _normalize_evidence(raw_value: object, fallback: str) -> list[str]:
    if not isinstance(raw_value, list):
        return [fallback]
    normalized = [str(item).strip() for item in raw_value if str(item).strip()]
    return normalized[:3] or [fallback]


def _strip_json_fence(content: str) -> str:
    stripped = content.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 3:
            return "\n".join(lines[1:-1]).strip()
    return stripped


def _extract_json_object_text(content: str) -> str:
    stripped = _strip_json_fence(content)
    if "\n" in stripped:
        event_payload = _extract_json_from_event_stream(stripped)
        if event_payload is not None:
            return event_payload
        for line in reversed(stripped.splitlines()):
            candidate = line.strip()
            if candidate.startswith("{") and candidate.endswith("}"):
                return candidate
    return stripped


def _extract_json_from_event_stream(content: str) -> str | None:
    for line in reversed(content.splitlines()):
        stripped = line.strip()
        if not stripped.startswith("{"):
            continue
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        item = payload.get("item")
        if isinstance(item, dict) and item.get("type") == "agent_message":
            text = item.get("text")
            if isinstance(text, str) and text.strip():
                return text.strip()
    return None


def _normalize_negative_tier(raw_value: object) -> str:
    text = str(raw_value or "").strip().lower()
    if text in {"positive", "negative"}:
        return text
    for value in ("positive", "negative"):
        if value in text:
            return value
    return text


def _normalize_primary_research_object(raw_value: object) -> str | None:
    text = str(raw_value or "").strip()
    if not text:
        return None
    if text in RESEARCH_OBJECT_LABELS:
        return text
    for label in RESEARCH_OBJECT_LABELS:
        if text in label or label in text:
            return label
    lowered = text.lower()
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
    return None


def _normalize_preference_label(
    raw_value: object,
    *,
    candidate_labels: list[str],
) -> str | None:
    values: list[str]
    if isinstance(raw_value, list):
        values = [str(item).strip() for item in raw_value if str(item).strip()]
    else:
        value = str(raw_value or "").strip()
        values = [value] if value else []
    for value in values:
        if value in PREFERENCE_LABELS:
            return value
        for label in PREFERENCE_LABELS:
            if value in label or label in value:
                return label
        lowered = value.lower()
        token_map = {
            "decode": "解码策略优化",
            "decoding": "解码策略优化",
            "cache": "上下文与缓存优化",
            "context": "上下文与缓存优化",
            "kv": "上下文与缓存优化",
            "serving": "系统与调度优化",
            "schedule": "系统与调度优化",
            "routing": "系统与调度优化",
            "kernel": "算子与内核优化",
            "cuda": "算子与内核优化",
            "compiler": "算子与内核优化",
            "structure": "模型结构侧推理优化",
            "head": "模型结构侧推理优化",
            "layer": "模型结构侧推理优化",
            "quant": "模型压缩",
            "prun": "模型压缩",
            "distill": "模型压缩",
            "spars": "模型压缩",
        }
        for token, mapped in token_map.items():
            if token in lowered:
                return mapped
    if candidate_labels:
        return candidate_labels[0]
    return None


def _pick_primary_label(label_hit_counts: dict[str, int]) -> str | None:
    if not label_hit_counts:
        return None
    priority_order = (
        "解码策略优化",
        "上下文与缓存优化",
        "模型压缩",
        "系统与调度优化",
        "算子与内核优化",
        "模型结构侧推理优化",
    )
    priority = {label: index for index, label in enumerate(priority_order)}
    return min(
        label_hit_counts,
        key=lambda label: (-label_hit_counts[label], priority[label]),
    )


def _infer_positive_label_from_signals(text: str) -> str | None:
    signal_rules: list[tuple[str, tuple[str, ...]]] = [
        (
            "解码策略优化",
            (
                "speculative decoding",
                "parallel decoding",
                "tree decoding",
                "draft model",
                "early exit",
                "decode",
                "decoding",
            ),
        ),
        (
            "上下文与缓存优化",
            (
                "kv cache",
                "key-value cache",
                "long context",
                "context compression",
                "prompt compression",
                "cache",
            ),
        ),
        (
            "系统与调度优化",
            (
                "serving",
                "scheduler",
                "scheduling",
                "routing",
                "batching",
                "offload",
                "prefetch",
                "prefill",
                "runtime",
                "multi-tenant",
            ),
        ),
        (
            "算子与内核优化",
            (
                "kernel",
                "cuda",
                "triton",
                "gemm",
                "compiler",
                "flash attention",
                "flashattention",
                "flash decoding",
                "tensor core",
            ),
        ),
        (
            "模型结构侧推理优化",
            (
                "mixture-of-experts",
                "moe",
                "expert routing",
                "expert selection",
                "layer skipping",
                "sublayer skipping",
                "dynamic depth",
                "adaptive depth",
                "hybrid architecture",
                "layer reconfiguration",
            ),
        ),
        (
            "模型压缩",
            (
                "quantization",
                "low-bit",
                "pruning",
                "distillation",
                "sparsity",
                "compressed weights",
                "post-training quantization",
                "weight-only",
            ),
        ),
    ]
    for label, keywords in signal_rules:
        if any(keyword in text for keyword in keywords):
            return label
    return None


def _infer_primary_research_object(paper: EvaluationPaper) -> str:
    text = " ".join(
        [
            paper.title,
            paper.abstract,
            paper.abstract_zh,
            " ".join(paper.keywords or []),
        ]
    ).lower()
    if any(keyword in text for keyword in ("multimodal", "vision-language", "vlm", "mllm")):
        return "多模态 / VLM"
    if any(keyword in text for keyword in ("retrieval", "search", "ranking", "recommendation")):
        return "检索 / 推荐 / 搜索"
    if any(keyword in text for keyword in ("benchmark", "dataset", "survey", "empirical study")):
        return "评测 / Benchmark / 数据集"
    if any(keyword in text for keyword in ("serving", "scheduler", "runtime system", "system infrastructure")):
        return "AI 系统 / 基础设施"
    if any(keyword in text for keyword in ("llm", "large language model", "language model", "transformer")):
        return "LLM"
    return "通用机器学习"
