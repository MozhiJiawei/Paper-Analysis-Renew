"""Heuristic predictor for the evaluation API baseline."""

from __future__ import annotations

import re
from dataclasses import dataclass

from paper_analysis.api.evaluation_protocol import EvaluationPaper, EvaluationPrediction

MAX_EVIDENCE_SPANS = 2
PRIMARY_RESEARCH_OBJECT_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "多模态 / VLM",
        (
            "multimodal",
            "multi-modal",
            "vision-language",
            "vision language",
            "vision language model",
            "video-language",
            "vlm",
            "mllm",
            "llava",
            "visual token",
            "video token",
            "image-text",
            "image text",
            "视觉语言",
            "多模态",
            "图文",
        ),
    ),
    (
        "Diffusion / 生成模型",
        (
            "diffusion",
            "stable diffusion",
            "latent diffusion",
            "dit",
            "diffusion transformer",
            "text-to-image",
            "生成模型",
            "扩散模型",
        ),
    ),
    (
        "LLM",
        (
            "llm",
            "large language model",
            "language model",
            "transformer",
            "moe",
            "reasoning model",
            "大语言模型",
            "语言模型",
        ),
    ),
)


def _contains_keyword(text: str, keyword: str) -> bool:
    if re.search(r"[\u4e00-\u9fff]", keyword):
        return keyword in text
    pattern = r"(?<![a-z0-9])" + re.escape(keyword) + r"(?![a-z0-9])"
    return re.search(pattern, text) is not None


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(_contains_keyword(text, keyword) for keyword in keywords)


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


@dataclass(slots=True)
class EvaluationPredictor:
    """Predicts a single-label preference result from paper metadata."""

    algorithm_version: str = "heuristic-v1"

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
        for label, keywords in PRIMARY_RESEARCH_OBJECT_RULES:
            if _contains_any(text, keywords):
                return label
        return "通用机器学习"

    def _predict_preference_label(self, text: str) -> tuple[str | None, tuple[str, ...]]:
        rules: list[tuple[str, tuple[str, ...]]] = [
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
                ),
            ),
        ]
        for label, keywords in rules:
            if label == "模型压缩" and _contains_any(
                text,
                ("kv cache quantization", "kv-cache quantization", "kv cache compression"),
            ):
                continue
            if _contains_any(text, keywords):
                return label, keywords
        return None, ()
