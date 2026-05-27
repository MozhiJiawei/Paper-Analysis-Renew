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

if TYPE_CHECKING:
    from concurrent.futures import Future

MAX_EVIDENCE_SPANS = 2
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
SYSTEM_SECONDARY_EMBEDDING_MIN_MARGIN = 0.01
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
            "lmm",
            "mllm",
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
            "prompt compression",
            "context compression",
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
    "tree attention",
    "tree-attention",
    "long-context",
    "long context",
    "prompt compression",
    "context compression",
    "token generation",
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
    "decode",
    "decoding",
    "efficiency",
    "efficient",
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
    "throughput",
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
    "language model",
    "language models",
    "vision-language",
    "vision language model",
    "visual language model",
    "multimodal language model",
    "multimodal large language model",
    "vlm",
    "mllm",
    "diffusion",
    "diffusion model",
    "dit",
    "ddpm",
    "ddim",
    "text-to-image",
)
PRIMARY_BUCKET_MIN_SIMILARITY = 0.115
LLM_REVIEW_LABELS = {"上下文与缓存优化", "系统与调度优化", "算子与内核优化", "模型压缩"}
EMBEDDING_POSITIVE_ANCHORS: dict[str, tuple[str, ...]] = {
    "解码策略优化": (
        "Large language model inference optimization with speculative decoding, parallel decoding, draft model acceptance rate and early exit.",
        "Autoregressive LLM generation acceleration through better decoding algorithms and draft model verification.",
    ),
    "上下文与缓存优化": (
        "Inference optimization for long context, KV cache, cache compression, token eviction and prompt compression in LLM serving.",
        "Long-context language model serving with KV cache optimization, prompt compression and memory-efficient context management.",
    ),
    "系统与调度优化": (
        "Serving system optimization for scheduler, batching, routing, prefetch, offload and multi-tenant LLM infrastructure.",
        "Runtime scheduling and resource management for efficient model serving throughput and latency.",
    ),
    "算子与内核优化": (
        "GPU kernel and fused operator optimization for transformer inference, attention kernels and compiler-level acceleration.",
        "Kernel-level transformer inference acceleration using fused attention operators and optimized GPU primitives.",
    ),
    "模型压缩": (
        "Model compression for inference such as quantization, pruning, distillation, low-bit weights and sparsity.",
        "Low-bit quantization and pruning to reduce inference latency, memory and serving cost for large language models.",
    ),
}
EMBEDDING_NEGATIVE_ANCHORS: tuple[str, ...] = (
    "Benchmark, dataset, survey or evaluation paper without a concrete LLM inference optimization method.",
    "Computer vision or multimodal benchmark paper focused on recognition accuracy instead of model inference efficiency.",
    "General machine learning analysis, empirical study or resource without a direct optimization algorithm for inference.",
    "Retrieval, ranking or recommendation task paper without a concrete model inference systems optimization method.",
)
EMBEDDING_HARD_VETO_MARGIN = 0.08
EMBEDDING_CLEAR_POSITIVE_MARGIN = 0.04
PREFERENCE_LABEL_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "解码策略优化",
        (
            "speculative decoding",
            "self-speculative",
            "tree decoding",
            "parallel decoding",
            "early exit",
            "draft model",
            "acceptance rate",
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
            "attention sink",
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
        ),
    ),
)


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

    @property
    def resolved_embedding_model(self) -> str | None:
        """Return the resolved embedding model when configured."""
        ...

    def submit(
        self,
        messages: list[dict[str, Any]],
        *,
        stream: bool = False,
    ) -> Future[dict[str, Any]]:
        """Submit one chat-completion request."""
        ...

    def embed_texts(
        self,
        texts: list[str],
        *,
        model: str | None = None,
    ) -> EvaluationEmbeddingResponse:
        """Embed a batch of texts."""
        ...


class EvaluationEmbeddingResponse(Protocol):
    """Minimal embedding response surface required by the evaluation predictor."""

    success: bool
    vectors: list[list[float]]



@dataclass(slots=True)
class EvaluationPredictor:
    """Predicts a single-label preference result from paper metadata."""

    algorithm_version: str = "heuristic-v1"
    llm_hard_case_review: bool = False
    ai_provider: str = "openrouter"
    _ai_client: EvaluationAiClient | None = field(default=None, init=False, repr=False)
    _llm_cache: dict[str, bool] = field(default_factory=dict, init=False, repr=False)
    _embedding_cache: dict[str, list[float] | None] = field(default_factory=dict, init=False, repr=False)
    _embedding_anchor_cache: dict[str, Any] = field(default_factory=dict, init=False, repr=False)
    _llm_cache_lock: threading.Lock = field(
        default_factory=threading.Lock,
        init=False,
        repr=False,
    )
    _embedding_cache_lock: threading.Lock = field(
        default_factory=threading.Lock,
        init=False,
        repr=False,
    )

    def predict(self, paper: EvaluationPaper) -> EvaluationPrediction:
        """Build a heuristic prediction from a paper title, abstract, and keywords."""
        texts = [paper.title, paper.abstract, paper.abstract_zh, " ".join(paper.keywords or [])]
        normalized = " \n".join(texts).lower()
        source_texts = [item for item in texts if item.strip()]
        primary_object = self._predict_primary_research_object(normalized)
        label, label_keywords = self._predict_preference_label(normalized, primary_object)

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

        embedding_review = self._embedding_review_positive(
            paper=paper,
            text=normalized,
            primary_object=primary_object,
            label=label,
        )
        if embedding_review is False:
            return EvaluationPrediction(
                primary_research_object=primary_object,
                preference_labels=[],
                negative_tier="negative",
                evidence_spans={"negative": [paper.title]},
                notes=f"高风险正样本经 {self.ai_provider} embedding 复核后回退为 negative。",
            )

        if embedding_review is None and self._should_llm_review_positive():
            llm_positive = self._review_positive_with_llm(
                paper=paper,
                primary_object=primary_object,
                label=label,
            )
            if not llm_positive:
                return EvaluationPrediction(
                    primary_research_object=primary_object,
                    preference_labels=[],
                    negative_tier="negative",
                    evidence_spans={"negative": [paper.title]},
                    notes=f"高风险正样本经 {self.ai_provider} 复核后回退为 negative。",
                )

        evidence = _extract_evidence(source_texts, label_keywords)
        if not evidence:
            evidence = [paper.title]
        return EvaluationPrediction(
            primary_research_object=primary_object,
            preference_labels=[label],
            negative_tier="positive",
            evidence_spans={"general": [paper.title], label: evidence},
            notes=f"基于标题、摘要与关键词的启发式规则判定主标签为：{label}。",
        )

    def _predict_primary_research_object(self, text: str) -> str:
        return _predict_scored_primary_research_object(text)

    def _predict_preference_label(
        self,
        text: str,
        primary_object: str,
    ) -> tuple[str | None, tuple[str, ...]]:
        for label, keywords in PREFERENCE_LABEL_RULES:
            if label == "模型压缩" and _contains_any(
                text,
                ("kv cache quantization", "kv-cache quantization", "kv cache compression"),
            ):
                continue
            if not _contains_any(text, keywords):
                continue
            if not self._passes_positive_gate(text, primary_object, label):
                continue
            return label, keywords
        return None, ()

    def _passes_positive_gate(
        self,
        text: str,
        primary_object: str,
        label: str,
    ) -> bool:
        has_negative_topic = _contains_any(text, NEGATIVE_ONLY_TOPIC_KEYWORDS)
        has_positive_context = _contains_any(text, POSITIVE_CONTEXT_KEYWORDS)
        has_primary_model_context = _contains_any(text, PRIMARY_MODEL_CONTEXT_KEYWORDS)
        if has_negative_topic and not has_positive_context:
            return False
        if (
            primary_object in SECONDARY_OBJECT_LABELS
            and label in {"模型压缩", "系统与调度优化", "算子与内核优化"}
            and not has_positive_context
        ):
            return False
        if primary_object in SECONDARY_OBJECT_LABELS and label in {
            "上下文与缓存优化",
            "系统与调度优化",
            "算子与内核优化",
            "模型压缩",
        }:
            prototype_similarities = _prototype_bucket_similarities(text)
            max_primary_similarity = max(
                prototype_similarities.get("LLM", 0.0),
                prototype_similarities.get("VLM", 0.0),
                prototype_similarities.get("Diffusion", 0.0),
            )
            if not has_primary_model_context and max_primary_similarity < PRIMARY_BUCKET_MIN_SIMILARITY:
                return False
        if label == "模型压缩" and not _contains_any(
            text,
            (
                "inference",
                "serving",
                "throughput",
                "latency",
                "memory",
                "efficient",
                "efficiency",
                "llm",
                "language model",
                "transformer inference",
                "serving",
            ),
        ):
            return False
        if label == "系统与调度优化" and not _contains_any(
            text,
            (
                "scheduler",
                "scheduling",
                "batching",
                "load balancing",
                "routing",
                "latency",
                "throughput",
                "runtime",
                "resource",
                "multi-tenant",
                "offload",
                "prefetch",
                "serving system",
            ),
        ):
            return False
        return not (
            label == "算子与内核优化"
            and not _contains_any(
                text,
                ("inference", "attention", "transformer", "latency", "throughput"),
            )
        )

    def _embedding_review_positive(
        self,
        *,
        paper: EvaluationPaper,
        text: str,
        primary_object: str,
        label: str,
    ) -> bool | None:
        if not self._should_embedding_review_positive(text, primary_object, label):
            return True
        margin = self._embedding_review_margin(paper=paper, label=label)
        if margin is None:
            return None
        if label == "系统与调度优化" and primary_object in SECONDARY_OBJECT_LABELS:
            if margin < SYSTEM_SECONDARY_EMBEDDING_MIN_MARGIN:
                return False
            return margin >= EMBEDDING_CLEAR_POSITIVE_MARGIN
        if margin <= -EMBEDDING_HARD_VETO_MARGIN:
            return False
        return True if margin >= EMBEDDING_CLEAR_POSITIVE_MARGIN else None

    def _embedding_review_margin(
        self,
        *,
        paper: EvaluationPaper,
        label: str,
    ) -> float | None:
        client = self._get_ai_client()
        if client is None or not client.resolved_api_key or not client.resolved_embedding_model:
            return None
        paper_vector = self._embed_text_cached(_paper_to_embedding_text_for_review(paper))
        if not paper_vector:
            return None
        anchors = self._get_embedding_anchors()
        if not anchors:
            return None
        positive_vectors = anchors["positive"].get(label, [])
        negative_vectors = anchors["negative"]
        if not positive_vectors or not negative_vectors:
            return None
        positive_similarity = max(_cosine_similarity_dense(paper_vector, vector) for vector in positive_vectors)
        negative_similarity = max(_cosine_similarity_dense(paper_vector, vector) for vector in negative_vectors)
        return positive_similarity - negative_similarity

    def _should_embedding_review_positive(
        self,
        text: str,
        primary_object: str,
        label: str,
    ) -> bool:
        has_negative_topic = _contains_any(text, NEGATIVE_ONLY_TOPIC_KEYWORDS)
        if label not in LLM_REVIEW_LABELS:
            return False
        if has_negative_topic:
            return True
        return primary_object in SECONDARY_OBJECT_LABELS

    def _should_llm_review_positive(self) -> bool:
        return False

    def _review_positive_with_llm(
        self,
        *,
        paper: EvaluationPaper,
        primary_object: str,
        label: str,
    ) -> bool:
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
            return True

        messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": (
                    "你是论文推理优化分类复核器。"
                    "只判断这篇论文是否明确属于以下五个推理优化偏好之一："
                    "解码策略优化、上下文与缓存优化、系统与调度优化、算子与内核优化、模型压缩。"
                    "如果论文主要是 benchmark、dataset、survey、analysis，"
                    "或只是通用训练/感知/检索任务，没有明确的推理效率优化方法，应判 false。"
                    '只输出 JSON：{"accept_positive": true/false, "reason": "..."}'
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
            return True
        content = str(response.get("content", "") or "")
        parsed = self._parse_llm_review_response(content)
        decision = parsed if parsed is not None else True
        with self._llm_cache_lock:
            self._llm_cache[cache_key] = decision
        return decision

    def _get_ai_client(self) -> EvaluationAiClient | None:
        if self._ai_client is None:
            if self.ai_provider == "openrouter":
                self._ai_client = FallbackAiClient(concurrency=4)
            elif self.ai_provider == "doubao":
                self._ai_client = DoubaoClient(concurrency=4)
            else:
                raise ValueError(f"不支持的 AI provider：{self.ai_provider}")
        return self._ai_client

    def _embed_text_cached(self, text: str) -> list[float] | None:
        with self._embedding_cache_lock:
            if text in self._embedding_cache:
                return self._embedding_cache[text]
        client = self._get_ai_client()
        if client is None or not client.resolved_embedding_model:
            return None
        try:
            response = client.embed_texts([text], model=client.resolved_embedding_model)
        except (RuntimeError, ValueError):
            vector: list[float] | None = None
        else:
            vector = response.vectors[0] if response.success and response.vectors else None
        with self._embedding_cache_lock:
            self._embedding_cache[text] = vector
        return vector

    def _get_embedding_anchors(self) -> dict[str, Any] | None:
        with self._embedding_cache_lock:
            if self._embedding_anchor_cache:
                return self._embedding_anchor_cache
        client = self._get_ai_client()
        if client is None or not client.resolved_embedding_model:
            return None
        positive_vectors: dict[str, list[list[float]]] = {}
        for label, texts in EMBEDDING_POSITIVE_ANCHORS.items():
            vectors = [self._embed_text_cached(text) for text in texts]
            positive_vectors[label] = [vector for vector in vectors if vector]
        negative_vectors = [
            vector
            for vector in (self._embed_text_cached(text) for text in EMBEDDING_NEGATIVE_ANCHORS)
            if vector
        ]
        if not negative_vectors:
            return None
        anchors = {"positive": positive_vectors, "negative": negative_vectors}
        with self._embedding_cache_lock:
            self._embedding_anchor_cache = anchors
        return anchors

    def _parse_llm_review_response(self, content: str) -> bool | None:
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
        accept_positive = payload.get("accept_positive")
        if isinstance(accept_positive, bool):
            return accept_positive
        return None


def _paper_to_embedding_text_for_review(paper: EvaluationPaper) -> str:
    parts = [
        paper.title.strip(),
        " ".join(paper.keywords or []),
        paper.abstract.strip(),
        paper.abstract_zh.strip(),
    ]
    return "\n".join(part for part in parts if part)


def _cosine_similarity_dense(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    numerator = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return numerator / (left_norm * right_norm)
