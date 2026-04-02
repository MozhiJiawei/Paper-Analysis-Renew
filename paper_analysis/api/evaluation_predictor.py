from __future__ import annotations

from dataclasses import dataclass
import re

from paper_analysis.api.evaluation_protocol import EvaluationPaper, EvaluationPrediction


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)


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
            if len(evidence) >= 2:
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
    algorithm_version: str = "heuristic-v1"

    def predict(self, paper: EvaluationPaper) -> EvaluationPrediction:
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
        if _contains_any(
            text,
            (
                "multimodal",
                "vision-language",
                "vlm",
                "mllm",
                "llava",
                "video token",
                "visual token",
            ),
        ):
            return "多模态 / VLM"
        if _contains_any(
            text,
            ("diffusion", "denoising", "stable diffusion", "u-net", "dit"),
        ):
            return "Diffusion / 生成模型"
        if _contains_any(
            text,
            ("reinforcement learning", "rl", "sequence decision", "policy optimization"),
        ):
            return "强化学习 / 序列决策"
        if _contains_any(
            text,
            ("retrieval", "recommendation", "recommender", "search engine", "ranking"),
        ):
            return "检索 / 推荐 / 搜索"
        if _contains_any(
            text,
            ("computer vision", "image classification", "object detection", "segmentation"),
        ):
            return "计算机视觉"
        if _contains_any(text, ("speech", "audio", "asr", "tts", "speaker")):
            return "语音 / 音频"
        if _contains_any(text, ("benchmark", "dataset", "survey", "empirical study")):
            return "评测 / Benchmark / 数据集"
        if _contains_any(
            text,
            ("serving platform", "system infrastructure", "resource manager", "runtime system"),
        ):
            return "AI 系统 / 基础设施"
        if _contains_any(
            text,
            (
                "llm",
                "large language model",
                "language model",
                "transformer",
                "moe",
                "reasoning model",
            ),
        ):
            return "LLM"
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
