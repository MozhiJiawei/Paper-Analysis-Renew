"""Heuristic predictor for the evaluation API baseline."""

from __future__ import annotations

import json
import math
import re
import threading
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

from paper_analysis.api.evaluation_protocol import EvaluationPaper, EvaluationPrediction
from paper_analysis.utils.ai_client import FallbackAiClient
from paper_analysis.utils.doubao_client import DoubaoClient
from paper_analysis.utils.openrouter_client import OpenRouterClient

if TYPE_CHECKING:
    from concurrent.futures import Future

MAX_EVIDENCE_SPANS = 2
LLM_RECOMMENDER_MODEL = "deepseek/deepseek-v4-flash"
ROOT_DIR = Path(__file__).resolve().parents[2]
PAPERLIST_PROTOTYPE_FILES: tuple[Path, ...] = (
    ROOT_DIR / "third_party" / "paperlists" / "acl" / "acl2025.json",
    ROOT_DIR / "third_party" / "paperlists" / "iclr" / "iclr2025.json",
    ROOT_DIR / "third_party" / "paperlists" / "icml" / "icml2025.json",
    ROOT_DIR / "third_party" / "paperlists" / "cvpr" / "cvpr2025.json",
    ROOT_DIR / "third_party" / "paperlists" / "iccv" / "iccv2025.json",
    ROOT_DIR / "third_party" / "paperlists" / "aaai" / "aaai2025.json",
    ROOT_DIR / "third_party" / "paperlists" / "naacl" / "naacl2025.json",
)
PROTOTYPE_MAX_DOCS_PER_BUCKET = 80
PROTOTYPE_SCORE_WEIGHT = 6.0
PROTOTYPE_OTHER_MIN_SIMILARITY = 0.16
SECONDARY_RESEARCH_OBJECT_MIN_SCORE = 3
TOKEN_PATTERN = re.compile(r"[a-z][a-z0-9-]{2,}")
TOKEN_STOPWORDS = {
    "about",
    "across",
    "after",
    "among",
    "approach",
    "approaches",
    "based",
    "between",
    "from",
    "into",
    "model",
    "models",
    "method",
    "methods",
    "paper",
    "study",
    "task",
    "tasks",
    "their",
    "these",
    "this",
    "using",
    "with",
}
PRIMARY_RESEARCH_OBJECT_RULES: tuple[tuple[str, int, tuple[str, ...]], ...] = (
    ("多模态 / VLM", 3, ("multimodal", "multi-modal", "视觉语言", "多模态", "图文")),
    (
        "多模态 / VLM",
        4,
        (
            "vision-language",
            "vision language",
            "vision language model",
            "visual language model",
            "video-language",
            "image-text",
            "image text",
            "vlm",
            "lvlm",
            "lvlms",
            "lmm",
            "mllm",
            "mllms",
            "llava",
        ),
    ),
    (
        "多模态 / VLM",
        3,
        (
            "large multimodal model",
            "large multimodal models",
            "multimodal language model",
            "multimodal language models",
            "multimodal large language model",
            "multimodal large language models",
            "vision-language transformer",
            "visual token",
            "vision token",
            "image token",
            "video token",
            "visual encoder",
            "visual reasoning",
            "image reasoning",
        ),
    ),
    (
        "Diffusion / 生成模型",
        4,
        (
            "diffusion",
            "stable diffusion",
            "latent diffusion",
            "diffusion model",
            "diffusion models",
            "diffusion transformer",
            "denoising diffusion",
            "ddpm",
            "ddim",
            "dit",
            "u-net",
            "unet",
            "扩散模型",
        ),
    ),
    (
        "Diffusion / 生成模型",
        3,
        (
            "diffusion policy",
            "score-based",
            "denoising score matching",
            "noise schedule",
        ),
    ),
    (
        "Diffusion / 生成模型",
        2,
        (
            "text-to-image",
            "image generation",
            "video generation",
            "生成模型",
        ),
    ),
    ("LLM", 5, ("llm", "llms", "大语言模型")),
    (
        "LLM",
        4,
        (
            "large language model",
            "large language models",
            "language model",
            "language models",
            "causal language model",
            "causal language models",
            "autoregressive language model",
            "autoregressive language models",
            "decoder-only language model",
            "decoder-only language models",
            "diffusion language model",
            "diffusion language models",
            "large reasoning model",
            "large reasoning models",
            "lrm",
            "lrms",
            "语言模型",
        ),
    ),
    (
        "LLM",
        2,
        (
            "kv cache",
            "speculative decoding",
            "draft model",
            "draft decoding",
            "constrained decoding",
            "prompt compression",
            "context compression",
            "token search space",
            "long-context llm",
            "long-context llms",
        ),
    ),
)
SECONDARY_RESEARCH_OBJECT_RULES: tuple[tuple[str, int, tuple[str, ...]], ...] = (
    (
        "强化学习 / 序列决策",
        3,
        (
            "reinforcement learning",
            "sequential decision",
            "sequence decision",
            "policy optimization",
            "markov decision process",
            "mdp",
            "序列决策",
            "强化学习",
        ),
    ),
    (
        "检索 / 推荐 / 搜索",
        3,
        (
            "retrieval",
            "recommendation",
            "recommender",
            "ranking",
            "search engine",
            "search",
            "检索",
            "推荐",
            "搜索",
        ),
    ),
    (
        "计算机视觉",
        3,
        (
            "computer vision",
            "object detection",
            "image classification",
            "image segmentation",
            "novel view",
            "3d vision",
            "video frame interpolation",
            "计算机视觉",
        ),
    ),
    (
        "语音 / 音频",
        3,
        (
            "speech",
            "audio",
            "asr",
            "tts",
            "speaker",
            "voice",
            "语音",
            "音频",
        ),
    ),
    (
        "AI 系统 / 基础设施",
        3,
        (
            "system infrastructure",
            "runtime system",
            "resource manager",
            "serving platform",
            "distributed system",
            "systems infrastructure",
            "基础设施",
        ),
    ),
    (
        "评测 / Benchmark / 数据集",
        3,
        (
            "benchmark",
            "benchmarks",
            "dataset",
            "datasets",
            "survey",
            "evaluation protocol",
            "leaderboard",
            "benchmarking",
            "数据集",
            "评测",
        ),
    ),
)
LLM_CONTEXT_KEYWORDS: tuple[str, ...] = (
    "kv cache",
    "speculative decoding",
    "draft model",
    "draft decoding",
    "constrained decoding",
    "tree attention",
    "tree-attention",
    "long-context",
    "long context",
    "prompt compression",
    "context compression",
    "token generation",
    "token search space",
    "autoregressive",
    "inference",
    "serving",
)
VLM_CONTEXT_KEYWORDS: tuple[str, ...] = (
    "vision",
    "visual",
    "image",
    "video",
    "pixel",
)
DIFFUSION_CONTEXT_KEYWORDS: tuple[str, ...] = (
    "sampler",
    "sampling",
    "noise",
    "denoise",
    "trajectory",
)
MIN_RESEARCH_OBJECT_SCORE = 4
POSITIVE_CONTEXT_KEYWORDS: tuple[str, ...] = (
    "acceleration",
    "accelerate",
    "cache",
    "compression",
    "compressed",
    "cost",
    "decode",
    "decoding",
    "efficiency",
    "efficient",
    "footprint",
    "inference",
    "latency",
    "memory",
    "offload",
    "optimize",
    "optimization",
    "prefetch",
    "runtime",
    "scheduler",
    "scheduling",
    "serving",
    "speedup",
    "steps",
    "throughput",
    "token",
    "tokens",
)
OPTIMIZATION_VERB_KEYWORDS: tuple[str, ...] = ("accelerate", "improve", "optimize", "optimization", "reduce", "speedup")
NEGATIVE_ONLY_TOPIC_KEYWORDS: tuple[str, ...] = (
    "analysis",
    "benchmark",
    "benchmarking",
    "dataset",
    "datasets",
    "empirical study",
    "evaluation",
    "leaderboard",
    "survey",
    "评测",
    "数据集",
)
SECONDARY_OBJECT_LABELS = {
    "通用机器学习",
    "强化学习 / 序列决策",
    "检索 / 推荐 / 搜索",
    "计算机视觉",
    "语音 / 音频",
    "AI 系统 / 基础设施",
    "评测 / Benchmark / 数据集",
}
PRIMARY_MODEL_CONTEXT_KEYWORDS: tuple[str, ...] = (
    "llm",
    "llms",
    "large language model",
    "large language models",
    "large reasoning model",
    "large reasoning models",
    "language model",
    "language models",
    "vision-language",
    "vision language model",
    "visual language model",
    "multimodal language model",
    "multimodal large language model",
    "vlm",
    "lvlm",
    "lvlms",
    "mllm",
    "mllms",
    "large vision-language model",
    "large vision-language models",
    "large vision language model",
    "large vision language models",
    "diffusion",
    "diffusion model",
    "diffusion models",
    "diffusion language model",
    "diffusion language models",
    "video diffusion",
    "video generation",
    "vla",
    "vision-language-action",
    "dit",
    "ddpm",
    "ddim",
    "text-to-image",
)
PRIMARY_BUCKET_MIN_SIMILARITY = 0.115
PREFERENCE_LABEL_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "解码策略优化",
        (
            "speculative decoding",
            "self-speculative",
            "tree decoding",
            "parallel decoding",
            "constrained decoding",
            "grammar-constrained decoding",
            "early exit",
            "draft model",
            "acceptance rate",
            "token search space",
            "self-drafting",
            "multi-branch self-drafting",
            "self drafting",
            "multi branch self drafting",
            "never autoregressively decodes",
            "asymmetric verification",
            "global forking tokens",
            "inference-time scaling",
            "inference time scaling",
            "chain-of-thought budget",
            "shorter chain-of-thought",
            "chain-of-thought",
            "best-of-n",
            "best of n",
            "reranker-guided search",
            "reasoning with sampling",
            "sampling",
            "denoising step",
            "denoising steps",
            "nfe",
            "nfes",
        ),
    ),
    (
        "上下文与缓存优化",
        (
            "kv cache",
            "key-value cache",
            "long context",
            "prompt compression",
            "token eviction",
            "context compression",
            "cache compression",
            "token selection",
            "token compression",
            "visual token compression",
            "visual-token compression",
            "token budget",
            "token budgets",
            "elastic visual-token",
            "attention sink",
            "rag compression",
            "online soft compression",
            "context denoising",
            "one vision token",
            "dynamic visual-token exit",
            "dynamic visual token exit",
            "visual-token exit",
            "visual token exit",
            "token merging",
            "token merge",
        ),
    ),
    (
        "系统与调度优化",
        (
            "serving",
            "scheduler",
            "scheduling",
            "load balancing",
            "batching",
            "multi-tenant",
            "routing",
            "offload",
            "prefetch",
            "disaggregated serving",
            "prefill-decode",
            "prefill decode",
            "request scheduling",
            "cache-aware scheduling",
            "expert parallelism",
            "cpu-gpu orchestration",
            "gpu orchestration",
            "orchestration",
            "moe serving",
            "model serving",
            "resource-constrained gpu",
            "resource-constrained gpus",
            "outdated gpu",
            "outdated gpus",
            "multi-agent scheduling",
            "multi-agent collaboration",
            "budget-controllable",
            "nucleus-electron",
            "adaptive preference arithmetic",
            "token/cost/latency",
            "segment any instance",
        ),
    ),
    (
        "算子与内核优化",
        (
            "cuda kernel",
            "gpu kernel",
            "fused operator",
            "fused op",
            "gemm",
            "compiler",
            "attention kernel",
            "kernel-level",
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
            "model compression",
            "binarization",
            "mixed precision",
            "mixed-precision",
            "weight-only quantization",
            "weight-only",
            "gptq",
            "awq",
            "post-training quantization",
            "ptq",
            "w4a4",
            "hifloat4",
            "tensor-structured compression",
            "tensor structured compression",
            "lora merging",
            "adapter merging",
            "expert pruning",
            "expert merging",
            "expert remapping",
            "low-rank adapter",
        ),
    ),
)


@dataclass(frozen=True, slots=True)
class LlmRecommendationReview:
    """Two-threshold review result from one DS-V4-Flash call."""

    broad_positive: bool
    strict_positive: bool
    label: str | None
    reason: str


@dataclass(frozen=True, slots=True)
class PrototypeIndex:
    """Sparse TF-IDF prototype vectors grouped by four research-object buckets."""

    idf: dict[str, float]
    centroids: dict[str, dict[str, float]]


def _contains_keyword(text: str, keyword: str) -> bool:
    if re.search(r"[\u4e00-\u9fff]", keyword):
        return keyword in text
    pattern = r"(?<![a-z0-9])" + re.escape(keyword) + r"(?![a-z0-9])"
    return re.search(pattern, text) is not None


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(_contains_keyword(text, keyword) for keyword in keywords)


def _tokenize_text(text: str) -> list[str]:
    tokens = TOKEN_PATTERN.findall(text.lower())
    return [token for token in tokens if token not in TOKEN_STOPWORDS]


def _vectorize_tokens(tokens: list[str], idf: dict[str, float]) -> dict[str, float]:
    counts = Counter(tokens)
    if not counts:
        return {}
    vector = {token: count * idf.get(token, 0.0) for token, count in counts.items() if token in idf}
    norm = math.sqrt(sum(value * value for value in vector.values()))
    if norm == 0.0:
        return {}
    return {token: value / norm for token, value in vector.items()}


def _cosine_similarity_sparse(left: dict[str, float], right: dict[str, float]) -> float:
    if not left or not right:
        return 0.0
    if len(left) > len(right):
        left, right = right, left
    return sum(value * right.get(token, 0.0) for token, value in left.items())


def _public_label_to_bucket(label: str) -> str:
    if label == "LLM":
        return "LLM"
    if label == "多模态 / VLM":
        return "VLM"
    if label == "Diffusion / 生成模型":
        return "Diffusion"
    return "其他"


def _strong_seed_match(text: str, label: str) -> bool:
    if label == "LLM":
        return _contains_any(
            text,
            (
                "large language model",
                "large language models",
                "llm",
                "llms",
                "autoregressive language model",
                "decoder-only language model",
            ),
        )
    if label == "VLM":
        return _contains_any(
            text,
            (
                "vision-language",
                "vision language model",
                "visual language model",
                "multimodal language model",
                "multimodal large language model",
                "mllm",
                "vlm",
                "lvlm",
                "llava",
            ),
        )
    if label == "Diffusion":
        return _contains_any(
            text,
            (
                "diffusion model",
                "diffusion models",
                "stable diffusion",
                "latent diffusion",
                "denoising diffusion",
                "ddpm",
                "ddim",
                "diffusion transformer",
                "dit",
            ),
        )
    return any(_contains_any(text, keywords) for _label, _weight, keywords in SECONDARY_RESEARCH_OBJECT_RULES)


def _paperlist_record_text(record: dict[str, object]) -> str:
    keyword_value = record.get("keywords", "")
    if isinstance(keyword_value, str):
        keyword_text = keyword_value.replace(";", " ")
    elif isinstance(keyword_value, list):
        keyword_text = " ".join(str(item) for item in keyword_value if str(item).strip())
    else:
        keyword_text = ""
    parts = [
        str(record.get("title", "")).strip(),
        str(record.get("primary_area", "")).strip(),
        keyword_text.strip(),
        str(record.get("abstract", "")).strip(),
    ]
    return "\n".join(part for part in parts if part)


@lru_cache(maxsize=1)
def _load_prototype_index() -> PrototypeIndex:
    bucket_texts = _load_prototype_bucket_texts()
    documents = [text for texts in bucket_texts.values() for text in texts]
    if not documents:
        return PrototypeIndex(idf={}, centroids={})
    idf = _build_idf(documents)
    return PrototypeIndex(
        idf=idf,
        centroids=_build_prototype_centroids(bucket_texts=bucket_texts, idf=idf),
    )


def _load_prototype_bucket_texts() -> dict[str, list[str]]:
    bucket_texts: dict[str, list[str]] = defaultdict(list)
    for path in PAPERLIST_PROTOTYPE_FILES:
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            continue
        for record in payload:
            if not isinstance(record, dict):
                continue
            text = _paperlist_record_text(record).lower()
            if not text:
                continue
            for bucket in ("LLM", "VLM", "Diffusion", "其他"):
                if len(bucket_texts[bucket]) >= PROTOTYPE_MAX_DOCS_PER_BUCKET:
                    continue
                if _strong_seed_match(text, bucket):
                    bucket_texts[bucket].append(text)
                    break
    return bucket_texts


def _build_idf(documents: list[str]) -> dict[str, float]:
    document_frequency: Counter[str] = Counter()
    tokenized_documents = [_tokenize_text(text) for text in documents]
    for tokens in tokenized_documents:
        document_frequency.update(set(tokens))
    return {
        token: math.log((1 + len(documents)) / (1 + frequency)) + 1.0
        for token, frequency in document_frequency.items()
    }


def _build_prototype_centroids(
    *,
    bucket_texts: dict[str, list[str]],
    idf: dict[str, float],
) -> dict[str, dict[str, float]]:
    centroids: dict[str, dict[str, float]] = {}
    for bucket, texts in bucket_texts.items():
        vectors = [_vectorize_tokens(_tokenize_text(text), idf) for text in texts]
        aggregate: defaultdict[str, float] = defaultdict(float)
        non_empty_vectors = [vector for vector in vectors if vector]
        if not non_empty_vectors:
            continue
        for vector in non_empty_vectors:
            for token, value in vector.items():
                aggregate[token] += value
        centroid = {token: value / len(non_empty_vectors) for token, value in aggregate.items()}
        norm = math.sqrt(sum(value * value for value in centroid.values()))
        if norm == 0.0:
            continue
        centroids[bucket] = {token: value / norm for token, value in centroid.items()}
    return centroids


def _prototype_bucket_similarities(text: str) -> dict[str, float]:
    index = _load_prototype_index()
    if not index.idf or not index.centroids:
        return {"LLM": 0.0, "VLM": 0.0, "Diffusion": 0.0, "其他": 0.0}
    vector = _vectorize_tokens(_tokenize_text(text), index.idf)
    return {
        bucket: _cosine_similarity_sparse(vector, centroid)
        for bucket, centroid in index.centroids.items()
    }


def _score_research_object(text: str, label: str) -> int:
    score = 0
    for rule_label, weight, keywords in PRIMARY_RESEARCH_OBJECT_RULES:
        if rule_label != label:
            continue
        if _contains_any(text, keywords):
            score += weight
    if label == "LLM":
        if _contains_any(text, ("transformer", "transformers")) and _contains_any(
            text, LLM_CONTEXT_KEYWORDS
        ):
            score += 2
        if _contains_any(text, ("moe", "mixture-of-experts")) and _contains_any(
            text, ("llm", "language model", "language models", "大语言模型")
        ):
            score += 2
    elif label == "多模态 / VLM":
        if _contains_any(text, VLM_CONTEXT_KEYWORDS) and _contains_any(
            text,
            ("language model", "language models", "llm", "llms", "文本", "language"),
        ):
            score += 3
    elif label == "Diffusion / 生成模型":
        if _contains_any(text, ("diffusion", "dit", "ddpm", "ddim")) and _contains_any(
            text, DIFFUSION_CONTEXT_KEYWORDS
        ):
            score += 2
    return score


def _predict_scored_primary_research_object(text: str) -> str:
    primary_scores = {
        "多模态 / VLM": _score_research_object(text, "多模态 / VLM"),
        "Diffusion / 生成模型": _score_research_object(text, "Diffusion / 生成模型"),
        "LLM": _score_research_object(text, "LLM"),
    }
    primary_scores["多模态 / VLM"] += 1 if primary_scores["多模态 / VLM"] > 0 else 0
    secondary_scores = {
        label: 0 for label, _weight, _keywords in SECONDARY_RESEARCH_OBJECT_RULES
    }
    for label, weight, keywords in SECONDARY_RESEARCH_OBJECT_RULES:
        if _contains_any(text, keywords):
            secondary_scores[label] += weight
    strongest_primary_label = max(primary_scores, key=lambda label: primary_scores[label])
    strongest_primary_score = primary_scores[strongest_primary_label]
    strongest_secondary_label = max(secondary_scores, key=lambda label: secondary_scores[label])
    strongest_secondary_score = secondary_scores[strongest_secondary_label]
    prototype_similarities = _prototype_bucket_similarities(text)
    combined_scores = {
        "LLM": primary_scores["LLM"] + prototype_similarities.get("LLM", 0.0) * PROTOTYPE_SCORE_WEIGHT,
        "多模态 / VLM": primary_scores["多模态 / VLM"] + prototype_similarities.get("VLM", 0.0) * PROTOTYPE_SCORE_WEIGHT,
        "Diffusion / 生成模型": primary_scores["Diffusion / 生成模型"] + prototype_similarities.get("Diffusion", 0.0) * PROTOTYPE_SCORE_WEIGHT,
        "其他": strongest_secondary_score + prototype_similarities.get("其他", 0.0) * PROTOTYPE_SCORE_WEIGHT,
    }
    strongest_combined_label = max(combined_scores, key=lambda label: combined_scores[label])
    strongest_combined_score = combined_scores[strongest_combined_label]
    if strongest_combined_label == "其他" and (
        strongest_secondary_score >= SECONDARY_RESEARCH_OBJECT_MIN_SCORE
        or prototype_similarities.get("其他", 0.0) >= PROTOTYPE_OTHER_MIN_SIMILARITY
    ):
        if strongest_secondary_score >= SECONDARY_RESEARCH_OBJECT_MIN_SCORE:
            return strongest_secondary_label
        return "通用机器学习"
    if strongest_combined_label != "其他" and strongest_combined_score >= MIN_RESEARCH_OBJECT_SCORE:
        return strongest_combined_label
    if strongest_primary_score >= MIN_RESEARCH_OBJECT_SCORE:
        return strongest_primary_label
    if strongest_secondary_score >= SECONDARY_RESEARCH_OBJECT_MIN_SCORE:
        return strongest_secondary_label
    return "通用机器学习"


def _extract_evidence(source_texts: list[str], keywords: tuple[str, ...]) -> list[str]:
    evidence: list[str] = []
    for keyword in keywords:
        keyword_lower = keyword.lower()
        for text in source_texts:
            lowered = text.lower()
            if keyword_lower not in lowered:
                continue
            sentence = _extract_sentence(text, keyword_lower)
            if sentence and sentence not in evidence:
                evidence.append(sentence)
            if len(evidence) >= MAX_EVIDENCE_SPANS:
                return evidence
    return evidence


def _extract_sentence(text: str, keyword_lower: str) -> str:
    sentences = re.split(r"(?<=[.!?。；;])\s+", text.strip())
    for sentence in sentences:
        if keyword_lower in sentence.lower():
            return sentence.strip()[:240]
    return text.strip()[:240]


class EvaluationAiClient(Protocol):
    """Minimal AI client surface required by the evaluation predictor."""

    @property
    def resolved_api_key(self) -> str | None:
        """Return the resolved provider API key when configured."""
        ...

    def submit(
        self,
        messages: list[dict[str, Any]],
        *,
        stream: bool = False,
    ) -> Future[dict[str, Any]]:
        """Submit one chat-completion request."""
        ...


@dataclass(slots=True)
class EvaluationPredictor:
    """Predicts a single-label preference result from paper metadata."""

    algorithm_version: str = "heuristic-v1"
    llm_hard_case_review: bool = False
    ai_provider: str = "openrouter"
    _ai_client: EvaluationAiClient | None = field(default=None, init=False, repr=False)
    _llm_cache: dict[str, LlmRecommendationReview] = field(
        default_factory=dict,
        init=False,
        repr=False,
    )
    _llm_cache_lock: threading.Lock = field(
        default_factory=threading.Lock,
        init=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        """Publish the effective algorithm version for evaluation reports."""
        if self.llm_hard_case_review and self.algorithm_version == "heuristic-v1":
            self.algorithm_version = f"heuristic-v1+{LLM_RECOMMENDER_MODEL}-dual-layer"

    def predict(self, paper: EvaluationPaper) -> EvaluationPrediction:
        """Build a heuristic prediction from a paper title, abstract, and keywords."""
        texts = [paper.title, paper.abstract, paper.abstract_zh, " ".join(paper.keywords or [])]
        normalized = " \n".join(texts).lower()
        source_texts = [item for item in texts if item.strip()]
        primary_object = self._predict_primary_research_object(normalized)
        label, label_keywords = self._predict_preference_label(normalized)

        if label is None:
            evidence = _extract_evidence(
                source_texts,
                (
                    "benchmark",
                    "evaluation",
                    "dataset",
                    "survey",
                    "analysis",
                    "empirical study",
                ),
            )
            if not evidence:
                evidence = [paper.title]
            return EvaluationPrediction(
                primary_research_object=primary_object,
                preference_labels=[],
                negative_tier="negative",
                evidence_spans={"negative": evidence},
                notes="未检测到五个偏好标签中的明确主优化杠杆。",
            )

        broad_negative_tier = "positive"
        broad_preference_labels = [label]
        recommendation_tier = "strict_positive"
        llm_review_note = ""
        if self._should_llm_review_positive():
            llm_review = self._review_positive_with_llm(
                paper=paper,
                primary_object=primary_object,
                label=label,
            )
            final_label = llm_review.label or label
            if final_label not in _preference_label_set():
                final_label = label
            if final_label != label:
                label_keywords = _preference_label_keywords(final_label)
            broad_negative_tier = "positive" if llm_review.broad_positive else "negative"
            broad_preference_labels = [final_label] if llm_review.broad_positive else []
            recommendation_tier = (
                "strict_positive"
                if llm_review.strict_positive
                else "broad_positive"
                if llm_review.broad_positive
                else "negative"
            )
            llm_review_note = f" DS-V4-Flash 复核：{llm_review.reason}"
            if not llm_review.strict_positive:
                return EvaluationPrediction(
                    primary_research_object=primary_object,
                    preference_labels=[],
                    negative_tier="negative",
                    evidence_spans={"negative": [paper.title]},
                    notes=(
                        f"启发式宽召回标签为：{label}；"
                        f"strict 判定为 negative。{llm_review_note}"
                    ),
                    broad_negative_tier=broad_negative_tier,
                    broad_preference_labels=broad_preference_labels,
                    recommendation_tier=recommendation_tier,
                )
            label = final_label

        evidence = _extract_evidence(source_texts, label_keywords)
        if not evidence:
            evidence = [paper.title]
        return EvaluationPrediction(
            primary_research_object=primary_object,
            preference_labels=[label],
            negative_tier="positive",
            evidence_spans={"general": [paper.title], label: evidence},
            notes=f"基于标题、摘要与关键词宽召回主标签为：{label}。{llm_review_note}".strip(),
            broad_negative_tier=broad_negative_tier,
            broad_preference_labels=broad_preference_labels,
            recommendation_tier=recommendation_tier,
        )

    def _predict_primary_research_object(self, text: str) -> str:
        return _predict_scored_primary_research_object(text)

    def _predict_preference_label(
        self,
        text: str,
    ) -> tuple[str | None, tuple[str, ...]]:
        for label, keywords in PREFERENCE_LABEL_RULES:
            if label == "模型压缩" and _contains_any(
                text,
                ("kv cache quantization", "kv-cache quantization", "kv cache compression"),
            ):
                continue
            if not _contains_any(text, keywords):
                continue
            if self._is_obvious_negative_recall_filter(text):
                continue
            return label, keywords
        return None, ()

    def _is_obvious_negative_recall_filter(self, text: str) -> bool:
        has_negative_topic = _contains_any(text, NEGATIVE_ONLY_TOPIC_KEYWORDS)
        has_positive_context = _contains_any(text, POSITIVE_CONTEXT_KEYWORDS)
        has_primary_model_context = _contains_any(text, PRIMARY_MODEL_CONTEXT_KEYWORDS)
        return has_negative_topic and not has_positive_context and not has_primary_model_context

    def _should_llm_review_positive(self) -> bool:
        return self.llm_hard_case_review

    def _review_positive_with_llm(
        self,
        *,
        paper: EvaluationPaper,
        primary_object: str,
        label: str,
    ) -> LlmRecommendationReview:
        cache_key = json.dumps(
            {
                "title": paper.title,
                "abstract": paper.abstract,
                "abstract_zh": paper.abstract_zh,
                "keywords": paper.keywords or [],
                "primary_object": primary_object,
                "label": label,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        with self._llm_cache_lock:
            if cache_key in self._llm_cache:
                return self._llm_cache[cache_key]

        client = self._get_ai_client()
        if client is None or not client.resolved_api_key:
            return LlmRecommendationReview(
                broad_positive=True,
                strict_positive=True,
                label=label,
                reason="AI client 未配置，保留启发式正样本。",
            )

        messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": (
                    "你是 DS-V4-Flash 推荐裁判，用于论文推理效率推荐的主算法复核。"
                    "启发式已经做了宽召回。你必须在一次调用中同时给出两层语义："
                    "broad_positive 用于高召回候选池，目标是少误杀，适合人工抽检；"
                    "strict_positive 用于日报最终推荐，目标是高准确。"
                    "broad_positive 标准：论文可能和推理效率、推理时搜索、推理时 token/cost/budget、"
                    "serving 调度、压缩、缓存、解码、采样或生成步数优化相关，就应收进候选池；"
                    "证据不完整、术语新、类别边界不稳时也应给 broad_positive=true。"
                    "broad_positive 的宽松性不得影响 strict_positive。"
                    "strict_positive 是最终推荐裁判口径，只能在论文明确应该进入日报推荐时为 true。"
                    "strict 正例必须满足：研究对象是 LLM/VLM/视频生成或视频扩散/VLA/LLM-Agent serving；"
                    "方法直接发生在推理、部署、serving、解码、KV/cache、token budget、模型压缩、算子或调度路径；"
                    "并且明确优化 latency、throughput、memory、FLOPs、token 数、step/NFE、cost 或实时性。"
                    "非 LLM 的 video diffusion / VLA 推理加速算正例。"
                    "MoE expert pruning/merging/remapping、低比特量化、KV/attention/token 压缩、"
                    "面向部署显存/内存 footprint 的模型压缩可算正例。"
                    "多模型/多 Agent 推理中的模型路由、动态拓扑、token/cost/latency 调度可算正例。"
                    "纯训练效率、质量提升、benchmark/dataset/survey、垂直应用流程、表示学习、检索质量、审计/安全分析、"
                    "以及仅把 efficient 当形容词但没有推理效率证据的论文，strict_positive 必须为 false；"
                    "如果它们只是边界相关，可以 broad_positive=true。"
                    "只有明显属于这些负例时，broad_positive 才判 false。"
                    "label 必须是五类之一或空字符串：解码策略优化、上下文与缓存优化、系统与调度优化、算子与内核优化、模型压缩。"
                    '只输出 JSON：{"broad_positive": true/false, "strict_positive": true/false, "label": "...", "reason": "..."}'
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "candidate_label": label,
                        "predicted_primary_research_object": primary_object,
                        "paper": {
                            "title": paper.title,
                            "abstract": paper.abstract,
                            "abstract_zh": paper.abstract_zh,
                            "keywords": paper.keywords or [],
                        },
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            },
        ]
        try:
            response = client.submit(messages).result(timeout=90)
        except (RuntimeError, TimeoutError, ValueError):
            return LlmRecommendationReview(
                broad_positive=True,
                strict_positive=True,
                label=label,
                reason="LLM 调用失败，保留启发式正样本。",
            )
        content = str(response.get("content", "") or "")
        parsed = self._parse_llm_review_response(content)
        decision = parsed or LlmRecommendationReview(
            broad_positive=True,
            strict_positive=False,
            label=label,
            reason="LLM 响应无法解析，仅保留为 broad 候选。",
        )
        with self._llm_cache_lock:
            self._llm_cache[cache_key] = decision
        return decision

    def _get_ai_client(self) -> EvaluationAiClient | None:
        if self._ai_client is None:
            if self.ai_provider == "openrouter":
                self._ai_client = FallbackAiClient(
                    primary=OpenRouterClient(
                        chat_model=LLM_RECOMMENDER_MODEL,
                        concurrency=4,
                    ),
                    concurrency=4,
                )
            elif self.ai_provider == "doubao":
                self._ai_client = DoubaoClient(concurrency=4)
            else:
                raise ValueError(f"不支持的 AI provider：{self.ai_provider}")
        return self._ai_client

    def _parse_llm_review_response(
        self,
        content: str,
    ) -> LlmRecommendationReview | None:
        if not content.strip():
            return None
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", content, flags=re.DOTALL)
            if match is None:
                return None
            try:
                payload = json.loads(match.group(0))
            except json.JSONDecodeError:
                return None
        broad_positive = payload.get("broad_positive")
        strict_positive = payload.get("strict_positive")
        if isinstance(broad_positive, bool) and isinstance(strict_positive, bool):
            broad_positive = broad_positive or strict_positive
            return LlmRecommendationReview(
                broad_positive=broad_positive,
                strict_positive=strict_positive,
                label=_normalize_llm_label(payload.get("label")),
                reason=str(payload.get("reason", "")).strip()[:500],
            )
        accept_positive = payload.get("accept_positive")
        if isinstance(accept_positive, bool):
            return LlmRecommendationReview(
                broad_positive=accept_positive,
                strict_positive=accept_positive,
                label=_normalize_llm_label(payload.get("label")),
                reason=str(payload.get("reason", "")).strip()[:500],
            )
        return None


def _preference_label_set() -> set[str]:
    return {label for label, _keywords in PREFERENCE_LABEL_RULES}


def _preference_label_keywords(label: str) -> tuple[str, ...]:
    for candidate_label, keywords in PREFERENCE_LABEL_RULES:
        if candidate_label == label:
            return keywords
    return ()


def _normalize_llm_label(value: object) -> str | None:
    label = str(value or "").strip()
    if label in _preference_label_set():
        return label
    return None

