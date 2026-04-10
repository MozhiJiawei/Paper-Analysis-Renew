from __future__ import annotations

import unittest

from paper_analysis.api.evaluation_protocol import EvaluationPaper
from paper_analysis.evaluation.errors import RouteNotImplementedError
from paper_analysis.evaluation.routes.embedding_retriever_stub import (
    EmbeddingRetrieverStubRoute,
    NEGATIVE_ANCHORS,
    POSITIVE_ANCHORS,
    _paper_to_embedding_text,
)
from paper_analysis.utils.doubao_client import DoubaoEmbeddingResponse


class FakeDoubaoClient:
    def __init__(
        self,
        *,
        embedding_model: str | None,
        paper_vectors: dict[str, list[float]] | None = None,
    ) -> None:
        self.resolved_embedding_model = embedding_model
        self._paper_vectors = paper_vectors or {}

    def embed_texts(
        self,
        texts: list[str],
        *,
        model: str | None = None,
    ) -> DoubaoEmbeddingResponse:
        resolved_model = model or self.resolved_embedding_model or ""
        if resolved_model != (self.resolved_embedding_model or ""):
            return DoubaoEmbeddingResponse(False, [], resolved_model, "unexpected model")

        vectors: list[list[float]] = []
        for text in texts:
            vector = self._paper_vectors.get(text)
            if vector is not None:
                vectors.append(vector)
                continue
            if text == POSITIVE_ANCHORS[0].text:
                vectors.append([1.0, 0.0])
                continue
            if text in {anchor.text for anchor in POSITIVE_ANCHORS[1:]}:
                vectors.append([0.0, 1.0])
                continue
            if text in NEGATIVE_ANCHORS:
                vectors.append([-1.0, 0.0])
                continue
            return DoubaoEmbeddingResponse(False, [], resolved_model, f"unexpected text: {text}")
        return DoubaoEmbeddingResponse(True, vectors, resolved_model)


def _paper(
    *,
    paper_id: str,
    title: str,
    abstract: str,
    keywords: list[str] | None = None,
) -> EvaluationPaper:
    return EvaluationPaper(
        paper_id=paper_id,
        title=title,
        abstract=abstract,
        authors=["Alice"],
        venue="ICLR 2026",
        year=2026,
        source="conference",
        source_path="tests.json",
        keywords=keywords or [],
    )


class EmbeddingRouteUnitTests(unittest.TestCase):
    def test_positive_anchors_do_not_include_removed_structure_label(self) -> None:
        self.assertNotIn(
            "模型结构侧推理优化",
            [anchor.label for anchor in POSITIVE_ANCHORS],
        )

    def test_prepare_falls_back_to_stub_without_embedding_model(self) -> None:
        route = EmbeddingRetrieverStubRoute(client=FakeDoubaoClient(embedding_model=None))

        with self.assertRaises(RouteNotImplementedError):
            route.prepare()

        self.assertEqual("stub", route.implementation_status)

    def test_route_predicts_positive_and_negative_by_similarity_margin(self) -> None:
        positive_paper = _paper(
            paper_id="paper-positive",
            title="Speculative decoding improves serving throughput",
            abstract="A draft model boosts LLM inference acceptance rate.",
            keywords=["speculative decoding"],
        )
        negative_paper = _paper(
            paper_id="paper-negative",
            title="A new benchmark for visual correspondence",
            abstract="We introduce an evaluation dataset for vision matching.",
            keywords=["benchmark"],
        )
        paper_vectors = {
            _paper_to_embedding_text(positive_paper): [1.0, 0.0],
            _paper_to_embedding_text(negative_paper): [-1.0, 0.0],
        }
        route = EmbeddingRetrieverStubRoute(
            client=FakeDoubaoClient(
                embedding_model="embedding-endpoint",
                paper_vectors=paper_vectors,
            )
        )

        route.prepare()
        predictions = route.predict_many([positive_paper, negative_paper])

        self.assertEqual("ready", route.implementation_status)
        self.assertEqual("positive", predictions[0].prediction.negative_tier)
        self.assertEqual(["解码策略优化"], predictions[0].prediction.preference_labels)
        self.assertEqual("negative", predictions[1].prediction.negative_tier)
        self.assertEqual([], predictions[1].prediction.preference_labels)

    def test_route_allows_embedding_positive_without_extra_gate(self) -> None:
        paper = _paper(
            paper_id="paper-embedding-only",
            title="Personality Alignment of Large Language Models",
            abstract="We study behavioral preferences of language models.",
            keywords=["large language models", "alignment"],
        )
        route = EmbeddingRetrieverStubRoute(
            client=FakeDoubaoClient(
                embedding_model="embedding-endpoint",
                paper_vectors={_paper_to_embedding_text(paper): [1.0, 0.0]},
            )
        )

        route.prepare()
        prediction = route.predict_many([paper])[0].prediction

        self.assertEqual("positive", prediction.negative_tier)


if __name__ == "__main__":
    unittest.main()
