from __future__ import annotations

from concurrent.futures import Future
import unittest

from paper_analysis.api.evaluation_predictor import EvaluationPredictor
from paper_analysis.api.evaluation_protocol import (
    EvaluationPaper,
    EvaluationPrediction,
    EvaluationProtocolError,
    aggregate_primary_research_object,
)


class _FakeAiClient:
    @property
    def resolved_api_key(self) -> str:
        return "fake-key"

    def submit(
        self,
        messages: list[dict[str, object]],
        *,
        stream: bool = False,
    ) -> Future[dict[str, object]]:
        future: Future[dict[str, object]] = Future()
        future.set_result(
            {
                "content": (
                    '{"broad_positive": true, "strict_positive": false, '
                    '"label": "解码策略优化", "reason": "边界相关但证据不够强"}'
                )
            }
        )
        return future


class _FakeReviewPredictor(EvaluationPredictor):
    def _get_ai_client(self) -> _FakeAiClient:
        return _FakeAiClient()


class EvaluationApiUnitTests(unittest.TestCase):
    def test_predictor_returns_single_positive_label_for_speculative_decoding(self) -> None:
        paper = EvaluationPaper(
            paper_id="paper-1",
            title="Speculative Decoding for Efficient LLM Inference",
            abstract="This speculative decoding method improves draft acceptance rate.",
            authors=["Alice"],
            venue="ICLR 2026",
            year=2026,
            source="conference",
            source_path="tests.json",
            keywords=["speculative decoding"],
        )

        prediction = EvaluationPredictor().predict(paper)

        self.assertEqual("positive", prediction.negative_tier)
        self.assertEqual(["解码策略优化"], prediction.preference_labels)
        self.assertEqual("LLM", prediction.primary_research_object)

    def test_predictor_keeps_quantized_llm_inference_positive(self) -> None:
        paper = EvaluationPaper(
            paper_id="paper-quant-llm-1",
            title="Low-Bit Quantization for Efficient LLM Inference",
            abstract="We optimize large language model inference throughput and memory via low-bit quantization.",
            authors=["Alice"],
            venue="ICLR 2026",
            year=2026,
            source="conference",
            source_path="tests.json",
            keywords=["quantization", "LLM", "inference"],
        )

        prediction = EvaluationPredictor().predict(paper)

        self.assertEqual("positive", prediction.negative_tier)
        self.assertEqual(["模型压缩"], prediction.preference_labels)

    def test_llm_review_returns_broad_and_strict_recommendation_layers(self) -> None:
        paper = EvaluationPaper(
            paper_id="paper-llm-layer-1",
            title="Speculative Decoding for Efficient LLM Inference",
            abstract="This speculative decoding method improves draft acceptance rate.",
            authors=["Alice"],
            venue="ICLR 2026",
            year=2026,
            source="conference",
            source_path="tests.json",
            keywords=["speculative decoding"],
        )
        predictor = _FakeReviewPredictor(llm_hard_case_review=True)

        prediction = predictor.predict(paper)

        self.assertEqual("negative", prediction.negative_tier)
        self.assertEqual([], prediction.preference_labels)
        self.assertEqual("positive", prediction.broad_negative_tier)
        self.assertEqual(["解码策略优化"], prediction.broad_preference_labels)
        self.assertEqual("broad_positive", prediction.recommendation_tier)

    def test_predictor_prioritizes_vlm_over_language_model_keywords(self) -> None:
        paper = EvaluationPaper(
            paper_id="paper-vlm-1",
            title="A Vision-Language Model for Image Reasoning with Language Model Distillation",
            abstract="This multimodal system aligns visual tokens with a language model backbone.",
            abstract_zh="这项多模态方法将视觉 token 与语言模型骨干对齐。",
            authors=["Alice"],
            venue="ICLR 2026",
            year=2026,
            source="conference",
            source_path="tests.json",
            keywords=["multimodal", "vision-language"],
        )

        prediction = EvaluationPredictor().predict(paper)

        self.assertEqual("多模态 / VLM", prediction.primary_research_object)

    def test_predictor_returns_diffusion_for_denoising_paper(self) -> None:
        paper = EvaluationPaper(
            paper_id="paper-diffusion-1",
            title="DiT Denoising for Text-to-Image Generation",
            abstract="We study diffusion denoising with a DiT backbone for text-to-image generation.",
            authors=["Alice"],
            venue="ICLR 2026",
            year=2026,
            source="conference",
            source_path="tests.json",
            keywords=["diffusion", "DiT"],
        )

        prediction = EvaluationPredictor().predict(paper)

        self.assertEqual("Diffusion / 生成模型", prediction.primary_research_object)

    def test_predictor_does_not_match_dit_inside_traditional(self) -> None:
        paper = EvaluationPaper(
            paper_id="paper-llm-traditional",
            title="QJL: 1-Bit Quantized JL Transform for KV Cache Quantization with Zero Overhead",
            abstract="Serving LLMs requires substantial memory due to KV cache growth. However, traditional quantization methods face accuracy bottlenecks in long-context inference.",
            authors=["Alice"],
            venue="ICLR 2026",
            year=2026,
            source="conference",
            source_path="tests.json",
            keywords=["large language model", "KV cache", "quantization"],
        )

        prediction = EvaluationPredictor().predict(paper)

        self.assertEqual("LLM", prediction.primary_research_object)

    def test_predictor_does_not_treat_context_denoising_as_diffusion(self) -> None:
        paper = EvaluationPaper(
            paper_id="paper-context-denoising",
            title="Context Denoising Training for Long-Context LLMs",
            abstract="We improve large language model inference with context denoising training and KV cache aware long-context optimization.",
            authors=["Alice"],
            venue="ICLR 2026",
            year=2026,
            source="conference",
            source_path="tests.json",
            keywords=["LLM", "long-context", "KV cache"],
        )

        prediction = EvaluationPredictor().predict(paper)

        self.assertEqual("LLM", prediction.primary_research_object)

    def test_predictor_falls_back_when_only_generic_transformer_signal_exists(self) -> None:
        paper = EvaluationPaper(
            paper_id="paper-transformer-only",
            title="Transformer Scaling Laws for General Representation Learning",
            abstract="We study transformer scaling behavior for general representation learning across multiple domains.",
            authors=["Alice"],
            venue="ICLR 2026",
            year=2026,
            source="conference",
            source_path="tests.json",
            keywords=["transformer", "representation learning"],
        )

        prediction = EvaluationPredictor().predict(paper)

        self.assertEqual("通用机器学习", prediction.primary_research_object)

    def test_predictor_recovers_llm_from_transformer_plus_inference_context(self) -> None:
        paper = EvaluationPaper(
            paper_id="paper-transformer-inference",
            title="Transformer Serving with KV Cache Compression",
            abstract="We improve transformer inference with KV cache compression and autoregressive token generation.",
            authors=["Alice"],
            venue="ICLR 2026",
            year=2026,
            source="conference",
            source_path="tests.json",
            keywords=["transformer", "KV cache", "autoregressive inference"],
        )

        prediction = EvaluationPredictor().predict(paper)

        self.assertEqual("LLM", prediction.primary_research_object)

    def test_predictor_routes_non_three_way_objects_into_other_bucket(self) -> None:
        paper = EvaluationPaper(
            paper_id="paper-structure-only",
            title="Retrieval-Augmented Ranking for Web Search",
            abstract="We study retrieval and ranking signals for production search systems.",
            authors=["Alice"],
            venue="ICLR 2026",
            year=2026,
            source="conference",
            source_path="tests.json",
            keywords=["retrieval", "ranking"],
        )

        prediction = EvaluationPredictor().predict(paper)

        self.assertEqual("其他", aggregate_primary_research_object(prediction.primary_research_object))
        self.assertEqual("negative", prediction.negative_tier)
        self.assertEqual([], prediction.preference_labels)
        self.assertIn("五个偏好标签", prediction.notes)

    def test_predictor_rejects_benchmark_like_quantization_paper_without_inference_context(self) -> None:
        paper = EvaluationPaper(
            paper_id="paper-benchmark-quant",
            title="A Benchmark for Quantization Methods in Vision Models",
            abstract="We present a benchmark and empirical evaluation dataset for quantization methods on image classification.",
            authors=["Alice"],
            venue="ICLR 2026",
            year=2026,
            source="conference",
            source_path="tests.json",
            keywords=["benchmark", "quantization", "vision"],
        )

        prediction = EvaluationPredictor().predict(paper)

        self.assertEqual("negative", prediction.negative_tier)
        self.assertEqual([], prediction.preference_labels)

    def test_research_object_aggregation_maps_public_labels_to_four_buckets(self) -> None:
        self.assertEqual("LLM", aggregate_primary_research_object("LLM"))
        self.assertEqual("VLM", aggregate_primary_research_object("多模态 / VLM"))
        self.assertEqual("Diffusion", aggregate_primary_research_object("Diffusion / 生成模型"))
        self.assertEqual("其他", aggregate_primary_research_object("评测 / Benchmark / 数据集"))

    def test_negative_prediction_clears_preference_labels(self) -> None:
        prediction = EvaluationPrediction(
            primary_research_object="评测 / Benchmark / 数据集",
            preference_labels=[],
            negative_tier="negative",
            evidence_spans={"negative": ["benchmark only"]},
            notes="negative",
        )

        self.assertEqual([], prediction.preference_labels)

    def test_positive_prediction_rejects_multiple_labels(self) -> None:
        with self.assertRaises(EvaluationProtocolError):
            EvaluationPrediction(
                primary_research_object="LLM",
                preference_labels=["解码策略优化", "系统与调度优化"],
                negative_tier="positive",
                evidence_spans={"general": ["bad"]},
            )

    def test_protocol_rejects_removed_structure_label(self) -> None:
        with self.assertRaises(EvaluationProtocolError):
            EvaluationPrediction(
                primary_research_object="LLM",
                preference_labels=["模型结构侧推理优化"],
                negative_tier="positive",
                evidence_spans={"模型结构侧推理优化": ["bad"]},
            )


if __name__ == "__main__":
    unittest.main()
