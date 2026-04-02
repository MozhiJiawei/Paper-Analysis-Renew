from __future__ import annotations

from dataclasses import dataclass
import math

from paper_analysis.api.evaluation_predictor import EvaluationPredictor
from paper_analysis.api.evaluation_protocol import EvaluationPaper, EvaluationPrediction
from paper_analysis.evaluation.ab_protocol import BinaryRoutePrediction
from paper_analysis.evaluation.errors import RouteNotImplementedError
from paper_analysis.evaluation.routes.base import BaseBinaryRoute
from paper_analysis.utils.doubao_client import DoubaoClient


@dataclass(frozen=True, slots=True)
class SimilarityAnchor:
    label: str
    text: str


POSITIVE_ANCHORS: tuple[SimilarityAnchor, ...] = (
    SimilarityAnchor(
        label="解码策略优化",
        text="Large language model inference optimization with speculative decoding, parallel decoding, draft model acceptance rate and early exit.",
    ),
    SimilarityAnchor(
        label="上下文与缓存优化",
        text="Inference optimization for long context, KV cache, cache compression, token eviction and prompt compression in LLM serving.",
    ),
    SimilarityAnchor(
        label="系统与调度优化",
        text="Serving system optimization for scheduler, batching, routing, prefetch, offload and multi-tenant LLM infrastructure.",
    ),
    SimilarityAnchor(
        label="算子与内核优化",
        text="GPU kernel and fused operator optimization for transformer inference, attention kernels and compiler-level acceleration.",
    ),
    SimilarityAnchor(
        label="模型压缩",
        text="Model compression for inference such as quantization, pruning, distillation, low-bit weights and sparsity.",
    ),
)

NEGATIVE_ANCHORS: tuple[str, ...] = (
    "Benchmark, dataset, survey or evaluation paper without a concrete LLM inference optimization method.",
    "Computer vision or multimodal benchmark paper focused on recognition accuracy instead of LLM inference efficiency.",
    "General machine learning analysis, empirical study or resource without a direct optimization algorithm for model inference.",
)

class EmbeddingRetrieverStubRoute(BaseBinaryRoute):
    def __init__(
        self,
        *,
        client: DoubaoClient | None = None,
        threshold_margin: float = -0.01,
        min_positive_similarity: float = 0.50,
    ) -> None:
        super().__init__(
            route_name="embedding_similarity_binary",
            algorithm_version="embedding-sim-binary-doubao-v1",
            capability_type="embedding_retriever",
            implementation_status="ready",
        )
        self._client = client or DoubaoClient()
        self._threshold_margin = threshold_margin
        self._min_positive_similarity = min_positive_similarity
        self._heuristic_predictor = EvaluationPredictor(
            algorithm_version=self.algorithm_version
        )
        self._positive_centroids: dict[str, list[float]] = {}
        self._negative_centroid: list[float] = []

    def prepare(self) -> None:
        embedding_model = self._client.resolved_embedding_model
        if not embedding_model:
            self.implementation_status = "stub"
            raise RouteNotImplementedError(
                "未配置 doubao.embedding_model；当前 worktree 的 embedding 路线会回退为 stub。"
            )

        positive_response = self._client.embed_texts(
            [anchor.text for anchor in POSITIVE_ANCHORS],
            model=embedding_model,
        )
        if not positive_response.success:
            self.implementation_status = "stub"
            raise RouteNotImplementedError(
                "Doubao embedding 模型暂不可用："
                f"{positive_response.error or '未知错误'}"
            )

        negative_response = self._client.embed_texts(
            list(NEGATIVE_ANCHORS),
            model=embedding_model,
        )
        if not negative_response.success:
            self.implementation_status = "stub"
            raise RouteNotImplementedError(
                "Doubao embedding 模型暂不可用："
                f"{negative_response.error or '未知错误'}"
            )

        self.implementation_status = "ready"
        self._positive_centroids = {
            anchor.label: vector
            for anchor, vector in zip(POSITIVE_ANCHORS, positive_response.vectors, strict=True)
        }
        self._negative_centroid = _average_vectors(negative_response.vectors)

    def predict_many(self, papers: list[EvaluationPaper]) -> list[BinaryRoutePrediction]:
        if not papers:
            return []
        if not self._positive_centroids or not self._negative_centroid:
            raise RouteNotImplementedError("embedding prototype 尚未准备完成。")

        embedding_response = self._client.embed_texts(
            [_paper_to_embedding_text(paper) for paper in papers],
            model=self._client.resolved_embedding_model,
        )
        if not embedding_response.success:
            raise RuntimeError(embedding_response.error or "Doubao embedding 调用失败。")

        predictions: list[BinaryRoutePrediction] = []
        for paper, vector in zip(papers, embedding_response.vectors, strict=True):
            top_label, top_similarity = max(
                (
                    (label, _cosine_similarity(vector, label_vector))
                    for label, label_vector in self._positive_centroids.items()
                ),
                key=lambda item: item[1],
            )
            negative_similarity = _cosine_similarity(vector, self._negative_centroid)
            margin = top_similarity - negative_similarity
            heuristic = self._heuristic_predictor.predict(paper)
            primary_object = heuristic.primary_research_object
            recall_priority_positive = (
                top_similarity >= self._min_positive_similarity
                and margin >= self._threshold_margin
            )

            if (
                recall_priority_positive
            ):
                prediction = EvaluationPrediction(
                    primary_research_object=primary_object,
                    preference_labels=[top_label],
                    negative_tier="positive",
                    evidence_spans={top_label: [paper.title], "general": [paper.title]},
                    notes=(
                        "基于 Doubao embedding 与正负原型相似度判定为 positive；"
                        f"top_similarity={top_similarity:.4f}，negative_similarity={negative_similarity:.4f}，"
                        f"margin={margin:.4f}。"
                    ),
                )
            else:
                prediction = EvaluationPrediction(
                    primary_research_object=primary_object,
                    preference_labels=[],
                    negative_tier="negative",
                    evidence_spans={"negative": [paper.title]},
                    notes=(
                        "基于 Doubao embedding 与负样本原型相似度对比判定为 negative；"
                        f"top_similarity={top_similarity:.4f}，negative_similarity={negative_similarity:.4f}，"
                        f"margin={margin:.4f}。"
                    ),
                )
            predictions.append(
                BinaryRoutePrediction(paper_id=paper.paper_id, prediction=prediction)
            )
        return predictions


def _paper_to_embedding_text(paper: EvaluationPaper) -> str:
    parts = [
        paper.title.strip(),
        " ".join(paper.keywords or []),
        paper.abstract.strip(),
        paper.abstract_zh.strip(),
    ]
    return "\n".join(part for part in parts if part)


def _average_vectors(vectors: list[list[float]]) -> list[float]:
    if not vectors:
        return []
    vector_length = len(vectors[0])
    result = [0.0] * vector_length
    for vector in vectors:
        if len(vector) != vector_length:
            raise ValueError("Embedding 向量维度不一致。")
        for index, value in enumerate(vector):
            result[index] += value
    return [value / len(vectors) for value in result]


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    numerator = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return numerator / (left_norm * right_norm)
